"""Registration through real HTTP and independently observed PostgreSQL."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
import pytest_asyncio
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import migration, server

from opengym_platform.core.database import Database, DatabaseError
from opengym_platform.identity.registration import normalize_email, password_problem


def test_independent_node_registration_vectors():
    vectors = json.loads(
        (
            Path(__file__).parents[2] / "contracts/identity-registration.v1.json"
        ).read_text()
    )
    for case in vectors["passwords"]:
        assert password_problem(case["password"], case["name"]) == case["expected"]
    for case in vectors["emails"]:
        assert normalize_email(case["raw"]) == case["expected"]


@pytest_asyncio.fixture
async def registration(deployment):
    observer, environment = deployment
    environment["PASSWORD_LOGIN"] = "1"
    await migration(environment, "up")
    return observer, environment


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body,code",
    [
        ({}, "missing"),
        ({"name": "Alice"}, "too-short"),
        ({"name": "Alice", "password": "short"}, "too-short"),
        ({"name": "Alice", "password": "long" * 90}, "too-long"),
        ({"name": "Alice", "password": "Password123!"}, "too-common"),
        ({"name": "Alice", "password": "alice.2024.2024"}, "too-common"),
        (
            {"name": "Alice", "password": "violet river stones", "email": "bad"},
            "email-invalid",
        ),
    ],
)
async def test_registration_rejects_invalid_input_without_creating_accounts(
    deployment, body, code
):
    observer, environment = deployment
    environment["PASSWORD_LOGIN"] = "1"
    await migration(environment, "up")
    async with server(environment) as client:
        response = await client.post("/api/v1/register/password", json=body)
        assert response.status_code == 400
        assert response.json()["code"] == code
        assert "set-cookie" not in response.headers
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("race", ["alias", "email", "invite", "first-admin"])
async def test_concurrent_claims_are_atomic(deployment, race):
    observer, environment = deployment
    environment.update(
        PASSWORD_LOGIN="1",
        FIRST_USER_ADMIN="1",
        INVITE_ONLY="1" if race == "invite" else "0",
    )
    await migration(environment, "up")
    if race == "invite":
        await observer.execute(
            "INSERT INTO identity.invitations VALUES ('LEGACY','', 'historic',NULL,false,NULL,NULL,false)"
        )
    async with server(environment) as client:
        responses = await asyncio.gather(
            *[
                client.post(
                    "/api/v1/register/password",
                    json={
                        "name": ("Ａｌｉｃｅ" if i else "alice")
                        if race == "alias"
                        else f"Person {i}",
                        "email": "shared@example.test" if race == "email" else "",
                        "code": " legacy ",
                        "password": "violet river stones",
                    },
                )
                for i in range(2)
            ]
        )
        assert sorted(r.status_code for r in responses) == (
            [200, 200]
            if race == "first-admin"
            else [200, 403 if race == "invite" else 409]
        )
        users = await observer.fetch("SELECT id,is_admin FROM identity.users")
        assert len(users) == (2 if race == "first-admin" else 1)
        assert sum(u["is_admin"] for u in users) == 1
        assert await observer.fetchval(
            "SELECT count(*) FROM identity.password_credentials"
        ) == len(users)
        if race == "invite":
            invitation = await observer.fetchrow("SELECT * FROM identity.invitations")
            assert invitation["consumed"] and invitation["used_by"] == users[0]["id"]
            assert invitation["created_at"] is None
            await observer.execute("DELETE FROM identity.users")
            retry = await client.post(
                "/api/v1/register/password",
                json={
                    "name": "Later",
                    "password": "violet river stones",
                    "code": "LEGACY",
                },
            )
            assert retry.status_code == 403
            assert (
                await observer.fetchval("SELECT consumed FROM identity.invitations")
                is True
            )
        if race == "email":
            loser = next(r for r in responses if r.status_code == 409)
            assert loser.json() == {
                "error": "another profile already uses this e-mail address",
                "code": "email-taken",
            }


@pytest.mark.asyncio
async def test_password_registration_creates_a_usable_private_account(deployment):
    observer, environment = deployment
    environment["PASSWORD_LOGIN"] = "1"
    await migration(environment, "up")
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/register/password",
            json={"name": " Alice ", "password": "violet river stones", "admin": True},
        )
        assert response.status_code == 200
        user = response.json()["user"]
        assert user == {"id": user["id"], "name": "Alice", "admin": False}
        assert (await client.get("/api/v1/me")).json() == {"user": user}
        client.cookies.clear()
        login = await client.post(
            "/api/v1/login/password",
            json={"identifier": "ＡＬＩＣＥ", "password": "violet river stones"},
        )
        assert login.status_code == 200
        assert login.json() == {"user": user}
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 1
        assert (
            await observer.fetchval(
                "SELECT created_at = p.set_at FROM identity.users u JOIN "
                "identity.password_credentials p ON p.owner_id=u.id"
            )
            is True
        )
        assert await observer.fetchval("SELECT count(*) FROM training.documents") == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["invite", "name", "email"])
async def test_claims_rechecked_after_crypto_without_holding_a_database_lease(
    registration, tmp_path, change
):
    observer, environment = registration
    environment["INVITE_ONLY"] = "1"
    await observer.execute(
        "INSERT INTO identity.invitations VALUES ('CODE','', 'historic',NULL,false,NULL,NULL,false)"
    )
    entered, release = tmp_path / "entered", tmp_path / "release"
    (tmp_path / "crypto_boundary.py").write_text(f"""
import hashlib
import time
from pathlib import Path
from opengym_platform.application import create_app as application
original = hashlib.scrypt

def crypto(password, **kwargs):
    if password == b"violet river stones":
        Path({str(entered)!r}).touch()
        deadline = time.monotonic() + 8
        while not Path({str(release)!r}).exists():
            if time.monotonic() > deadline:
                raise ValueError("synthetic crypto deadline")
            time.sleep(0.01)
    return original(password, **kwargs)

def create_app():
    hashlib.scrypt = crypto
    return application()
""")
    environment["PYTHONPATH"] = str(tmp_path) + ":/app/src"
    async with server(environment, factory="crypto_boundary:create_app") as client:
        task = asyncio.create_task(
            client.post(
                "/api/v1/register/password",
                json={
                    "name": "Alice",
                    "password": "violet river stones",
                    "email": "a@example.test",
                    "code": "CODE",
                },
            )
        )
        try:
            async with asyncio.timeout(4):
                while not entered.exists():
                    await asyncio.sleep(0.01)
            assert not await observer.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND xact_start IS NOT NULL)"
            )
            async with observer.transaction():
                await observer.execute("SELECT pg_advisory_xact_lock(728323)")
                if change == "invite":
                    await observer.execute(
                        "UPDATE identity.invitations SET revoked=true"
                    )
                else:
                    await observer.execute(
                        "INSERT INTO identity.users(id,display_name) VALUES ('competitor','Other')"
                    )
                    await observer.execute(
                        "INSERT INTO identity.login_aliases VALUES ($1,'competitor',true,false,NULL)",
                        "alice" if change == "name" else "a@example.test",
                    )
        finally:
            release.touch()
        response = await task
        assert response.status_code == (403 if change == "invite" else 409)
        assert response.json()["code"] == (
            "invite" if change == "invite" else change + "-taken"
        )
        assert "set-cookie" not in response.headers
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.password_credentials"
            )
            == 0
        )
        assert (
            await observer.fetchval("SELECT consumed FROM identity.invitations")
            is False
        )


@pytest.mark.asyncio
async def test_alias_purposes_expiry_and_historical_fields(registration):
    observer, environment = registration
    await observer.execute("""
        INSERT INTO identity.users(id,display_name) VALUES
            ('historic','Repeat'),('email','Email'),('reserved','Reserved'),('pending','Pending');
        INSERT INTO identity.login_aliases VALUES
            ('owned@example.test','email',true,false,NULL),
            ('expired','reserved',false,false,clock_timestamp()-interval '1 second'),
            ('pending@example.test','pending',false,false,clock_timestamp()+interval '1 day');
    """)
    async with server(environment) as client:
        for name, email, status, code in (
            ("Repeat", " repeat@example.test ", 200, None),
            ("owned@example.test", "", 409, "name-taken"),
            ("pending@example.test", "", 409, "name-taken"),
            ("New", "pending@example.test", 409, "email-taken"),
            ("New", "repeat", 400, "email-invalid"),
            ("New", "repeat@example.test", 409, "email-taken"),
            ("Expired", "", 200, None),
            ("same@example.test", "SAME@example.test", 200, None),
        ):
            response = await client.post(
                "/api/v1/register/password",
                json={
                    "name": name,
                    "email": email,
                    "password": "violet river stones",
                },
            )
            assert response.status_code == status
            if code:
                assert response.json()["code"] == code
        client.cookies.clear()
        response = await client.post(
            "/api/v1/login/password",
            json={
                "identifier": "REPEAT@example.test",
                "password": "violet river stones",
            },
        )
        assert response.status_code == 200
        assert response.json()["user"]["name"] == "Repeat"
    assert (
        await observer.fetchval(
            "SELECT created_at FROM identity.users WHERE id='historic'"
        )
        is None
    )
    assert (
        await observer.fetchval(
            "SELECT count(*) FROM identity.login_aliases WHERE alias_key='same@example.test' AND email_claim AND password_name_claim"
        )
        == 1
    )
    assert (
        await observer.fetchval(
            "SELECT count(*) FROM identity.login_aliases WHERE owner_id='reserved'"
        )
        == 0
    )


@pytest.mark.asyncio
async def test_failed_registration_rolls_back_every_claim_and_invitation(registration):
    observer, environment = registration
    environment.update(INVITE_ONLY="1", FIRST_USER_ADMIN="1")
    await observer.execute("""
        INSERT INTO identity.invitations VALUES ('CODE','','historic',NULL,false,NULL,NULL,false);
        CREATE FUNCTION identity.fail_signup() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'synthetic insert failure'; END $$;
        CREATE TRIGGER fail_signup BEFORE INSERT ON identity.password_credentials
        FOR EACH ROW EXECUTE FUNCTION identity.fail_signup();
    """)
    async with server(environment) as client:
        response = await client.post(
            "/api/v1/register/password",
            json={
                "name": "Alice",
                "password": "violet river stones",
                "code": "CODE",
            },
        )
        assert response.status_code == 500
        assert "set-cookie" not in response.headers
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 0
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.login_aliases") == 0
        )
        assert (
            await observer.fetchval("SELECT consumed FROM identity.invitations")
            is False
        )
        await observer.execute(
            "DROP TRIGGER fail_signup ON identity.password_credentials"
        )
        response = await client.post(
            "/api/v1/register/password",
            json={
                "name": "Alice",
                "password": "violet river stones",
                "code": "CODE",
            },
        )
        assert response.status_code == 200
        assert response.json()["user"]["admin"] is True


@pytest.mark.asyncio
async def test_invitation_privacy_limits_and_mode_off(registration):
    observer, environment = registration
    environment["INVITE_ONLY"] = "1"
    async with server(environment) as client:
        for _ in range(21):
            response = await client.post(
                "/api/v1/register/password",
                json={
                    "name": "Alice",
                    "password": "short",
                    "email": "bad",
                    "code": "bad",
                },
            )
            assert response.status_code == 403
            assert response.json() == {
                "error": "a valid invite code is required",
                "code": "invite",
            }
        response = await client.post(
            "/api/v1/register/password", json={"name": "Alice"}
        )
        assert response.status_code == 429
        assert response.json()["code"] == "locked"
        assert "set-cookie" not in response.headers
    environment["PASSWORD_LOGIN"] = "0"
    async with server(environment) as client:
        assert (
            await client.post("/api/v1/register/password", json={})
        ).status_code == 404
    assert await observer.fetchval("SELECT count(*) FROM identity.users") == 0


@pytest.mark.asyncio
async def test_registration_transport_and_database_failure_are_safe(registration):
    observer, environment = registration
    async with server(environment) as client:
        for headers in (
            {"Origin": "https://foreign.example"},
            {"Sec-Fetch-Site": "cross-site"},
        ):
            response = await client.post(
                "/api/v1/register/password", json={}, headers=headers
            )
            assert response.status_code == 403
        for body in ("[]", '{"name":NaN}', "{"):
            response = await client.post("/api/v1/register/password", content=body)
            assert response.status_code == 400
            assert response.json() == {"error": "invalid json"}
        assert (
            await client.post(
                "/api/v1/register/password", content="x" * (5 * 1024 * 1024 + 1)
            )
        ).status_code == 413
        await observer.execute(
            "REVOKE EXECUTE ON FUNCTION identity.register_password(text,text,text,text,text,text,timestamptz) FROM opengym_api_runtime"
        )
        response = await client.post(
            "/api/v1/register/password",
            json={
                "name": "Alice",
                "password": "violet river stones",
            },
        )
        assert response.status_code == 500
        assert response.json() == {"error": "server error"}
        assert "set-cookie" not in response.headers
    assert await observer.fetchval("SELECT count(*) FROM identity.users") == 0


@pytest.mark.asyncio
async def test_registration_migration_preserves_previous_head_and_restricted_grants(
    deployment, tmp_path, monkeypatch
):
    observer, environment = deployment
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        tmp_path / "opengym_platform",
        ignore=shutil.ignore_patterns(
            "p003_coach.py",
            "p004_admin_users.py",
            "p005_subscriptions.py",
            "p003_coach_client.py",
            "p003_coach_admin.py",
            "p003_coach_lifecycle.py",
            "p003_coach_http.py",
            "p003_coach_jobs.py",
            "p002_media_gc.py",
            "p001_links.py",
            "p001_reset.py",
            "p001_passkey_manage.py",
            "p001_account.py",
            "p001_passkey.py",
            "p001_password_register.py",
        ),
    )
    await migration({**environment, "PYTHONPATH": str(tmp_path)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p002_training_write"
    )
    await observer.execute(
        "INSERT INTO identity.users(id,display_name) VALUES ('historic','Preserved')"
    )
    await migration(environment, "up")
    assert tuple(
        await observer.fetchrow("SELECT id,created_at,last_pull_at FROM identity.users")
    ) == ("historic", None, None)
    signature = "identity.register_password(text,text,text,text,text,text,timestamptz)"
    meta = await observer.fetchrow(
        "SELECT pg_get_userbyid(proowner) AS owner, prosecdef, proconfig FROM pg_proc WHERE oid=$1::regprocedure",
        signature,
    )
    assert meta["owner"] == "opengym_identity_executor" and meta["prosecdef"]
    assert meta["proconfig"] == ["search_path=pg_catalog, pg_temp"]
    assert not await observer.fetchval(
        "SELECT EXISTS (SELECT 1 FROM pg_proc p, LATERAL aclexplode(coalesce(p.proacl, acldefault('f',p.proowner))) a WHERE p.oid=$1::regprocedure AND a.grantee=0 AND a.privilege_type='EXECUTE')",
        signature,
    )
    for key, value in {
        **environment,
        "PLATFORM_DB_PASSWORD_FILE": environment["PLATFORM_RUNTIME_PASSWORD_FILE"],
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PLATFORM_DB_PASSWORD", raising=False)
    database = await Database.open_platform()
    try:
        assert await database.fetch("SELECT * FROM identity.login_aliases") == []
        with pytest.raises(DatabaseError):
            await database.fetch("SELECT * FROM identity.invitations")
        with pytest.raises(DatabaseError):
            await database.execute("SET ROLE opengym_identity_executor")
        with pytest.raises(DatabaseError):
            await database.execute(
                "INSERT INTO identity.users(id,display_name) VALUES ('forged','Forged')"
            )
    finally:
        await database.close()
