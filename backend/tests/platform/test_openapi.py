"""Public YAML authority checked against real Python HTTP, not framework defaults."""

import re
from pathlib import Path

import pytest
from fastapi.openapi.utils import get_openapi
from test_identity_session import B
from test_identity_session import identities as identities  # noqa: PLC0414
from test_lifecycle import deployment as deployment  # noqa: PLC0414
from test_lifecycle import server


def operations():
    # Read only path/method/response keys from this hand-maintained YAML layout.
    text = (Path(__file__).parents[2] / "openapi.yaml").read_text()
    result = {}
    for path, block in re.findall(
        r"^  (/[^\n]+):\n(.*?)(?=^  /|^components:|\Z)", text, re.MULTILINE | re.DOTALL
    ):
        for method, operation in re.findall(
            r"^    (get|post|put|delete):\n(.*?)(?=^    (?:get|post|put|delete):|\Z)",
            block,
            re.MULTILINE | re.DOTALL,
        ):
            result[method.upper(), path] = set(
                re.findall(r"^        ['\"]?(\d{3})['\"]?:", operation, re.MULTILINE)
            )
    assert len(result) == 68
    assert all(result.values())
    return result


@pytest.mark.asyncio
async def test_public_methods_and_http_responses_match_canonical_yaml(
    identities, monkeypatch, tmp_path
):
    from opengym_platform.application import create_app

    _, environment = identities
    environment["PASSWORD_LOGIN"] = "1"
    environment["MEDIA_UPLOADS"] = "1"
    environment["DATA_DIR"] = str(tmp_path / "data")
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    app = create_app()
    schema = get_openapi(title="probe", version="0", routes=app.routes)
    normalize = lambda path: re.sub(r"\{[^}]+\}", "{parameter}", path)
    documented = operations()
    actual = {
        (method.upper(), normalize(path))
        for path, methods in schema["paths"].items()
        for method in methods
    }
    expected = {(method, normalize(path)) for method, path in documented}
    probes = {("GET", "/api/v1/health/live"), ("GET", "/api/v1/health/ready")}
    assert actual - probes == expected
    async with server(environment) as client:
        for (method, path), statuses in documented.items():
            url = re.sub(r"\{[^}]+\}", "0" * 64, path)
            response = await client.request(
                method, url, **({"json": {}} if method in {"POST", "PUT"} else {})
            )
            assert str(response.status_code) in statuses, (
                method,
                path,
                response.status_code,
                response.text,
            )
            assert response.status_code != 422
            assert response.headers["cache-control"] == "no-store"
            assert isinstance(response.json(), dict)
        for path in (
            "/me",
            "/data",
            "/data/rev",
            "/account/password",
            "/account/passkeys",
            "/push/status",
            "/admin/users",
            "/admin/invites",
            "/admin/audit",
            "/coach/status",
        ):
            response = await client.get(
                "/api/v1" + path, headers={"Authorization": f"Bearer {B}"}
            )
            expected_status = 503 if path == "/coach/status" else 200
            assert response.status_code == expected_status, (path, response.text)
            assert str(expected_status) in documented["GET", "/api/v1" + path]
            assert response.headers["cache-control"] == "no-store"
            assert isinstance(response.json(), dict)
        for path in (
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/openapi.json",
            "/api/health",
        ):
            assert (await client.get(path)).status_code == 404
