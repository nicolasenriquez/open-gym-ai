"""WebAuthn at the independent vector and real HTTP/restricted PostgreSQL seams."""

import asyncio
import base64
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import migration, server
from webauthn import verify_authentication_response, verify_registration_response
from webauthn.helpers.exceptions import WebAuthnException

from opengym_platform.core.database import Database, DatabaseError


@pytest.mark.asyncio
async def test_passkey_options_are_discoverable_and_do_not_create_accounts(deployment):
    observer, environment = deployment
    environment.update(
        RP_ID="localhost", ORIGIN="http://localhost:8080", PASSWORD_LOGIN="0"
    )
    await migration(environment, "up")
    async with server(environment) as client:
        login = await client.post("/api/v1/login/options", json={})
        assert login.status_code == 200
        registration = await client.post(
            "/api/v1/register/options", json={"name": "  Alice  "}
        )
        assert registration.status_code == 200
        first, second = login.json(), registration.json()
        assert first["cid"] != second["cid"]
        assert first["options"]["rpId"] == "localhost"
        assert first["options"]["userVerification"] == "preferred"
        assert first["options"]["allowCredentials"] == []
        assert first["options"]["challenge"] != second["options"]["challenge"]
        assert second["options"]["rp"] == {"id": "localhost", "name": "openGym"}
        assert second["options"]["user"]["name"] == "Alice"
        assert second["options"]["authenticatorSelection"] == {
            "residentKey": "required",
            "requireResidentKey": True,
            "userVerification": "preferred",
        }
        assert second["options"]["excludeCredentials"] == []
        assert second["options"]["attestation"] == "none"
        assert second["options"]["extensions"] == {"credProps": True}
        assert second["options"]["pubKeyCredParams"] == [
            {"alg": alg, "type": "public-key"} for alg in (-8, -7, -257)
        ]
        assert registration.headers["cache-control"] == "no-store"
        assert "set-cookie" not in registration.headers
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 0


VECTORS = json.loads(
    (Path(__file__).parents[2] / "contracts/identity-passkeys.v1.json").read_text()
)


def vector(name):
    return next(row for row in VECTORS["cases"] if row["name"] == name)


def fixed_challenge_app():
    from opengym_platform.application import create_app
    from opengym_platform.identity import passkeys

    # Randomness boundary only: replay fixed independently signed Node responses.
    def fixed_bytes(size=None):
        return base64.urlsafe_b64decode(VECTORS["challenge"] + "==")

    passkeys.token_bytes = fixed_bytes
    return create_app()


@pytest.mark.asyncio
@pytest.mark.parametrize("algorithm", ["ES256", "RS256", "Ed25519"])
async def test_node_credentials_register_login_and_persist_without_password_claims(
    deployment, algorithm
):
    observer, environment = deployment
    environment.update(
        RP_ID="localhost",
        ORIGIN=VECTORS["origin"],
        PASSWORD_LOGIN="0",
        FIRST_USER_ADMIN="1",
    )
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    await migration(environment, "up")
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        options = (
            await client.post(
                "/api/v1/register/options", json={"name": "Alice", "admin": False}
            )
        ).json()
        registration = await client.post(
            "/api/v1/register/verify",
            json={
                "cid": options["cid"],
                "credential": vector(algorithm + "/register")["credential"],
            },
        )
        assert registration.status_code == 200, registration.text
        user = registration.json()["user"]
        assert user["name"] == "Alice" and user["admin"] is True
        assert (await client.get("/api/v1/me")).json() == {"user": user}
        credential = await observer.fetchrow("SELECT * FROM identity.passkeys")
        assert credential["owner_id"] == user["id"]
        assert bytes(credential["public_key"]) == base64.urlsafe_b64decode(
            vector(algorithm + "/register")["publicKey"] + "=="
        )
        assert credential["counter"] == 0
        assert credential["created_at"] == credential["last_used_at"]
        assert credential["transports"] == ["internal", "hybrid"]
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.login_aliases") == 0
        )
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.password_credentials"
            )
            == 0
        )
        client.cookies.clear()
        login = (await client.post("/api/v1/login/options", json={})).json()
        response = await client.post(
            "/api/v1/login/verify",
            json={
                "cid": login["cid"],
                "credential": vector(algorithm + "/assertion")["credential"],
            },
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"user": user}
        assert "HttpOnly" in response.headers["set-cookie"]
        assert (await client.get("/api/v1/me")).json() == {"user": user}
        assert await observer.fetchval("SELECT counter FROM identity.passkeys") == 1


async def seed_passkey(observer, case):
    await observer.execute(
        "INSERT INTO identity.users(id,display_name) VALUES ('A','Alice'),('B','Bob')"
    )
    await observer.execute(
        "INSERT INTO identity.passkeys(credential_id,owner_id,public_key,counter,transports) VALUES ($1,'A',$2,$3,'{}')",
        case["credentialId"],
        base64.urlsafe_b64decode(case["publicKey"] + "=="),
        case["observedCounter"],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("algorithm", ["ES256", "RS256", "Ed25519"])
async def test_all_independent_node_vectors_through_http_and_pg(deployment, algorithm):
    observer, environment = deployment
    environment.update(RP_ID="localhost", ORIGIN=VECTORS["origin"])
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    await migration(environment, "up")
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        for case in [row for row in VECTORS["cases"] if row["algorithm"] == algorithm]:
            await observer.execute("DELETE FROM identity.users")
            client.cookies.clear()
            if case["kind"] == "login":
                await seed_passkey(observer, case)
            start = await client.post(
                "/api/v1/" + case["kind"] + "/options", json={"name": "Same name"}
            )
            response = await client.post(
                "/api/v1/" + case["kind"] + "/verify",
                json={"cid": start.json()["cid"], "credential": case["credential"]},
            )
            assert response.status_code == (200 if case["expected"] else 400), (
                case["name"],
                response.text,
            )
            assert ("set-cookie" in response.headers) == case["expected"]
            if case["kind"] == "login":
                count = (
                    case["newCounter"] if case["expected"] else case["observedCounter"]
                )
                assert (
                    await observer.fetchval("SELECT counter FROM identity.passkeys")
                    == count
                )
            else:
                assert await observer.fetchval(
                    "SELECT count(*) FROM identity.passkeys"
                ) == int(case["expected"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "owner",
        "version",
        "key",
        "counter",
        "credential-delete",
        "account-delete",
        "disabled",
    ],
)
async def test_crypto_result_revalidates_identity_and_credentials_without_a_lease(
    deployment, tmp_path, mutation
):
    observer, environment = deployment
    environment.update(RP_ID="localhost", ORIGIN=VECTORS["origin"])
    await migration(environment, "up")
    case = vector("ES256/assertion")
    await seed_passkey(observer, case)
    entered, release = tmp_path / "entered", tmp_path / "release"
    (tmp_path / "crypto_boundary.py").write_text(f"""
import time
from pathlib import Path
from opengym_platform.identity import passkeys
from opengym_platform.application import create_app as application
original = passkeys.verify_authentication_response

def verify(**kwargs):
    Path({str(entered)!r}).touch()
    deadline = time.monotonic() + 8
    while not Path({str(release)!r}).exists():
        if time.monotonic() > deadline:
            raise ValueError("crypto deadline")
        time.sleep(0.01)
    return original(**kwargs)

def create_app():
    passkeys.token_bytes = lambda size: bytes(range(32))
    passkeys.verify_authentication_response = verify
    return application()
""")
    environment["PYTHONPATH"] = str(tmp_path) + ":/app/src"
    async with server(environment, factory="crypto_boundary:create_app") as client:
        options = (await client.post("/api/v1/login/options", json={})).json()
        task = asyncio.create_task(
            client.post(
                "/api/v1/login/verify",
                json={"cid": options["cid"], "credential": case["credential"]},
            )
        )
        try:
            async with asyncio.timeout(4):
                while not entered.exists():
                    await asyncio.sleep(0.01)
            assert not await observer.fetchval(
                "SELECT EXISTS (SELECT FROM pg_stat_activity WHERE usename='opengym_api_runtime' AND xact_start IS NOT NULL)"
            )
            await observer.execute(
                {
                    "owner": "UPDATE identity.passkeys SET owner_id='B'",
                    "version": "UPDATE identity.users SET session_version=1 WHERE id='A'",
                    "key": "UPDATE identity.passkeys SET public_key='\\\\x00'::bytea",
                    "counter": "UPDATE identity.passkeys SET counter=2",
                    "credential-delete": "DELETE FROM identity.passkeys",
                    "account-delete": "DELETE FROM identity.users WHERE id='A'",
                    "disabled": "UPDATE identity.users SET disabled=true WHERE id='A'",
                }[mutation]
            )
        finally:
            release.touch()
        response = await task
        assert response.status_code == (403 if mutation == "disabled" else 400)
        assert "set-cookie" not in response.headers
        expected = (
            2
            if mutation == "counter"
            else 1
            if mutation == "disabled"
            else None
            if mutation.endswith("delete")
            else 0
        )
        assert (
            await observer.fetchval("SELECT counter FROM identity.passkeys") == expected
        )


@pytest.mark.asyncio
async def test_challenge_replay_wrong_kind_and_unknown_credential_fail_closed(
    deployment,
):
    observer, environment = deployment
    environment.update(RP_ID="localhost", ORIGIN=VECTORS["origin"])
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    await migration(environment, "up")
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        registration = (
            await client.post("/api/v1/register/options", json={"name": "Alice"})
        ).json()
        wrong_kind = await client.post(
            "/api/v1/login/verify",
            json={
                "cid": registration["cid"],
                "credential": vector("ES256/assertion")["credential"],
            },
        )
        assert (
            wrong_kind.status_code == 400
            and wrong_kind.json()["code"] == "challenge-expired"
        )
        used = await client.post(
            "/api/v1/register/verify",
            json={
                "cid": registration["cid"],
                "credential": vector("ES256/register")["credential"],
            },
        )
        assert used.status_code == 400 and used.json()["code"] == "challenge-expired"
        login = (await client.post("/api/v1/login/options", json={})).json()
        response = await client.post(
            "/api/v1/login/verify",
            json={
                "cid": login["cid"],
                "credential": vector("ES256/assertion")["credential"],
            },
        )
        assert (
            response.status_code == 404
            and response.json()["code"] == "unknown-credential"
        )
        failed_replay = await client.post(
            "/api/v1/login/verify",
            json={
                "cid": login["cid"],
                "credential": vector("ES256/assertion")["credential"],
            },
        )
        assert (
            failed_replay.status_code == 400
            and failed_replay.json()["code"] == "challenge-expired"
        )
        registration = (
            await client.post("/api/v1/register/options", json={"name": "Alice"})
        ).json()
        body = {
            "cid": registration["cid"],
            "credential": vector("ES256/register")["credential"],
        }
        responses = await asyncio.gather(
            *[client.post("/api/v1/register/verify", json=body) for _ in range(2)]
        )
        assert sorted(row.status_code for row in responses) == [200, 400]
        rejected = next(row for row in responses if row.status_code == 400)
        assert (
            rejected.json()["code"] == "challenge-expired"
            and "set-cookie" not in rejected.headers
        )
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 1
        login = (await client.post("/api/v1/login/options", json={})).json()
        body = {
            "cid": login["cid"],
            "credential": vector("ES256/assertion")["credential"],
        }
        responses = await asyncio.gather(
            *[client.post("/api/v1/login/verify", json=body) for _ in range(2)]
        )
        assert sorted(row.status_code for row in responses) == [200, 400]
        assert await observer.fetchval("SELECT counter FROM identity.passkeys") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("race", ["credential", "invite", "first-admin"])
async def test_registration_claim_invitation_and_first_admin_are_atomic(
    deployment, race
):
    observer, environment = deployment
    environment.update(
        RP_ID="localhost",
        ORIGIN=VECTORS["origin"],
        INVITE_ONLY="1" if race == "invite" else "0",
        FIRST_USER_ADMIN="1",
    )
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    await migration(environment, "up")
    if race == "invite":
        await observer.execute(
            "INSERT INTO identity.invitations VALUES ('CODE','','historic',NULL,false,NULL,NULL,false)"
        )
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        starts = [
            await client.post(
                "/api/v1/register/options",
                json={"name": "Duplicate name", "code": "code"},
            )
            for _ in range(2)
        ]
        responses = await asyncio.gather(
            *[
                client.post(
                    "/api/v1/register/verify",
                    json={
                        "cid": start.json()["cid"],
                        "credential": vector(algorithm + "/register")["credential"],
                    },
                )
                for start, algorithm in zip(
                    starts,
                    ["ES256", "ES256" if race == "credential" else "Ed25519"],
                    strict=True,
                )
            ]
        )
        assert sorted(row.status_code for row in responses) == (
            [200, 409]
            if race == "credential"
            else [200, 403]
            if race == "invite"
            else [200, 200]
        )
        assert (
            await observer.fetchval(
                "SELECT count(*) FROM identity.users WHERE is_admin"
            )
            == 1
        )
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == (
            2 if race == "first-admin" else 1
        )
        assert (
            await observer.fetchval("SELECT count(*) FROM identity.login_aliases") == 0
        )
        if race == "invite":
            invitation = await observer.fetchrow("SELECT * FROM identity.invitations")
            assert invitation["consumed"] and invitation["used_by"] == next(
                row.json()["user"]["id"] for row in responses if row.status_code == 200
            )
            assert invitation["created_at"] is None
            await observer.execute("DELETE FROM identity.users")
            assert (
                await client.post(
                    "/api/v1/register/options", json={"name": "Another", "code": "CODE"}
                )
            ).status_code == 403


@pytest.mark.asyncio
async def test_malformed_credentials_are_client_errors_and_never_persist(deployment):
    observer, environment = deployment
    environment.update(RP_ID="localhost", ORIGIN=VECTORS["origin"])
    await migration(environment, "up")
    async with server(environment) as client:
        for credential in (None, [], "not an object", {}, {"response": []}):
            start = (
                await client.post("/api/v1/register/options", json={"name": "Alice"})
            ).json()
            response = await client.post(
                "/api/v1/register/verify",
                json={"cid": start["cid"], "credential": credential},
            )
            assert response.status_code == 400, response.text
            assert "set-cookie" not in response.headers
            assert await observer.fetchval("SELECT count(*) FROM identity.users") == 0


def test_independent_node_vectors_match_python_crypto():
    for case in VECTORS["cases"]:
        kwargs = {
            "credential": case["credential"],
            "expected_challenge": base64.urlsafe_b64decode(VECTORS["challenge"] + "=="),
            "expected_origin": VECTORS["origin"],
            "expected_rp_id": VECTORS["rpId"],
            "require_user_verification": False,
        }
        try:
            if case["kind"] == "register":
                result = verify_registration_response(**kwargs)
                assert result.credential_public_key == base64.urlsafe_b64decode(
                    case["publicKey"] + "=="
                )
                assert result.sign_count == case["newCounter"]
            else:
                result = verify_authentication_response(
                    **kwargs,
                    credential_public_key=base64.urlsafe_b64decode(
                        case["publicKey"] + "=="
                    ),
                    credential_current_sign_count=case["observedCounter"],
                )
                assert result.new_sign_count == case["newCounter"]
            assert case["expected"], case["name"]
        except WebAuthnException:
            assert not case["expected"], case["name"]


def expired_challenge_app():
    from opengym_platform.identity import passkeys

    app = fixed_challenge_app()
    clock = iter([0, 301])
    passkeys.time = SimpleNamespace(time=lambda: next(clock))
    return app


@pytest.mark.asyncio
async def test_expired_ceremony_and_removed_routes_cannot_create_a_session(deployment):
    observer, environment = deployment
    environment.update(RP_ID="localhost", ORIGIN=VECTORS["origin"])
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    await migration(environment, "up")
    async with server(
        environment, factory="test_identity_passkey:expired_challenge_app"
    ) as client:
        start = (
            await client.post("/api/v1/register/options", json={"name": "Alice"})
        ).json()
        response = await client.post(
            "/api/v1/register/verify",
            json={
                "cid": start["cid"],
                "credential": vector("ES256/register")["credential"],
            },
        )
        assert (
            response.status_code == 400
            and response.json()["code"] == "challenge-expired"
        )
        assert "set-cookie" not in response.headers
        for path in (
            "/api/login/options",
            "/api/register/verify",
            "/api/v1/login/options/",
        ):
            removed = await client.post(path, json={})
            assert removed.status_code == 404 and "location" not in removed.headers
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 0


@pytest.mark.asyncio
async def test_passkey_transport_keeps_node_csrf_exemption_and_body_limits(deployment):
    observer, environment = deployment
    environment.update(RP_ID="localhost", ORIGIN=VECTORS["origin"])
    await migration(environment, "up")
    async with server(environment) as client:
        for kind in ("login", "register"):
            path = "/api/v1/" + kind + "/options"
            allowed = await client.post(
                path,
                json={"name": "Alice"},
                headers={
                    "Origin": "https://foreign.test",
                    "Sec-Fetch-Site": "cross-site",
                },
            )
            assert allowed.status_code == 200
            assert allowed.headers["cache-control"] == "no-store"
            # Node login options ignore the body; registration options parse it.
            assert (await client.post(path, content="{")).status_code == (
                200 if kind == "login" else 400
            )
            assert (await client.post(path, content='{"bad":NaN}')).status_code == (
                200 if kind == "login" else 400
            )
            assert (
                await client.post(path, content="x" * (5 * 1024 * 1024 + 1))
            ).status_code == (200 if kind == "login" else 413)
        assert (await client.post("/api/v1/register/options", json={})).json() == {
            "error": "name required"
        }
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 0


@pytest.mark.asyncio
async def test_previous_head_upgrades_preserving_history_and_privileges(
    deployment, tmp_path, monkeypatch
):
    observer, environment = deployment
    shutil.copytree(
        Path(__file__).parents[2] / "src/opengym_platform",
        tmp_path / "opengym_platform",
        ignore=shutil.ignore_patterns(
            "p003_coach.py",
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
        ),
    )
    await migration({**environment, "PYTHONPATH": str(tmp_path)}, "up")
    assert (
        await observer.fetchval("SELECT version_num FROM public.alembic_version")
        == "p001_password_register"
    )
    await observer.execute(
        "INSERT INTO identity.users(id,display_name) VALUES ('historic','Repeat')"
    )
    await migration(environment, "up")
    assert (
        await observer.fetchval(
            "SELECT created_at FROM identity.users WHERE id='historic'"
        )
        is None
    )
    case = vector("ES256/assertion")
    await seed_passkey(observer, case)
    before = dict(await observer.fetchrow("SELECT * FROM identity.passkeys"))
    await migration(environment, "up")
    assert dict(await observer.fetchrow("SELECT * FROM identity.passkeys")) == before
    assert before["created_at"] is None and before["last_used_at"] is None
    assert await observer.fetchval(
        "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='identity.passkeys'::regclass"
    )
    assert (
        await observer.fetchval(
            "SELECT count(*) FROM pg_indexes WHERE schemaname='identity' AND tablename='passkeys'"
        )
        == 2
    )
    functions = await observer.fetch(
        "SELECT p.prosecdef, p.proconfig, pg_get_userbyid(p.proowner) AS owner, has_function_privilege('opengym_api_runtime',p.oid,'EXECUTE') AS runtime, EXISTS(SELECT FROM aclexplode(p.proacl) a WHERE a.grantee=0) AS public FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='identity' AND p.proname IN ('register_passkey','lookup_passkey','finish_passkey_login')"
    )
    assert len(functions) == 3
    for row in functions:
        assert row["prosecdef"] and row["runtime"] and not row["public"]
        assert row["owner"] == "opengym_identity_executor" and row["proconfig"] == [
            "search_path=pg_catalog, pg_temp"
        ]
    assert not await observer.fetchval(
        "SELECT has_column_privilege('opengym_identity_executor','identity.passkeys','owner_id','UPDATE')"
    )
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PLATFORM_DB_PASSWORD", raising=False)
    monkeypatch.setenv(
        "PLATFORM_DB_PASSWORD_FILE", environment["PLATFORM_RUNTIME_PASSWORD_FILE"]
    )
    database = await Database.open_platform()
    try:
        rows = await database.fetch(
            "SELECT * FROM identity.lookup_passkey($1)", case["credentialId"]
        )
        assert len(rows) == 1 and rows[0]["owner_id"] == "A"
        assert (
            await database.fetch("SELECT * FROM identity.lookup_passkey($1)", "unknown")
            == []
        )
        assert await database.fetch("SELECT * FROM identity.passkeys") == []
        for sql in (
            "INSERT INTO identity.passkeys(credential_id) VALUES ('forged')",
            "SET ROLE opengym_identity_executor",
        ):
            with pytest.raises(DatabaseError):
                await database.execute(sql)
        assert await database.fetch("SELECT id FROM identity.users") == []
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["invite-revoked", "credential-insert"])
async def test_final_registration_failure_keeps_account_and_invitation_atomic(
    deployment, failure
):
    observer, environment = deployment
    environment.update(RP_ID="localhost", ORIGIN=VECTORS["origin"], INVITE_ONLY="1")
    environment["PYTHONPATH"] += ":" + str(Path(__file__).parent)
    await migration(environment, "up")
    await observer.execute(
        "INSERT INTO identity.invitations VALUES ('CODE','', 'historic',NULL,false,NULL,NULL,false)"
    )
    async with server(
        environment, factory="test_identity_passkey:fixed_challenge_app"
    ) as client:
        start = (
            await client.post(
                "/api/v1/register/options", json={"name": "Alice", "code": "CODE"}
            )
        ).json()
        if failure == "invite-revoked":
            await observer.execute("UPDATE identity.invitations SET revoked=true")
        else:
            await observer.execute("""
                CREATE FUNCTION public.reject_credential() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'private-passkey-marker'; END $$;
                CREATE TRIGGER reject_credential BEFORE INSERT ON identity.passkeys
                    FOR EACH ROW EXECUTE FUNCTION public.reject_credential();
            """)
        body = {
            "cid": start["cid"],
            "credential": vector("ES256/register")["credential"],
        }
        response = await client.post("/api/v1/register/verify", json=body)
        assert response.status_code == (403 if failure == "invite-revoked" else 500)
        assert (
            "set-cookie" not in response.headers
            and "private-passkey-marker" not in response.text
        )
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 0
        assert (
            await observer.fetchval("SELECT consumed FROM identity.invitations")
            is False
        )
        assert (await client.post("/api/v1/register/verify", json=body)).json()[
            "code"
        ] == "challenge-expired"
        if failure == "invite-revoked":
            await observer.execute("UPDATE identity.invitations SET revoked=false")
        else:
            await observer.execute(
                "DROP TRIGGER reject_credential ON identity.passkeys"
            )
        start = (
            await client.post(
                "/api/v1/register/options", json={"name": "Alice", "code": "CODE"}
            )
        ).json()
        response = await client.post(
            "/api/v1/register/verify", json={**body, "cid": start["cid"]}
        )
        assert response.status_code == 200
        assert await observer.fetchval("SELECT count(*) FROM identity.users") == 1
        assert (
            await observer.fetchval("SELECT consumed FROM identity.invitations") is True
        )
