"""Login cache drops on a force-closed session and on an explicit forget."""

from __future__ import annotations

import httpx
import pytest

from zeus_client.adapters.secrets_env.store import EnvSecretStore
from zeus_client.adapters.zeus_http.verbs import HttpxZeusPort
from zeus_client.config.models import DataTarget, ZeusEndpointConfig
from zeus_client.ports import VerbRequest


@pytest.mark.asyncio
async def test_session_force_closed_drops_cached_login() -> None:
    mints = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/session"):
            mints["n"] += 1
            return httpx.Response(
                200,
                json={"session_id": f"sid-{mints['n']}-abcdef", "expires_in": 1800},
            )
        return httpx.Response(
            429,
            json={
                "error": "session_force_closed",
                "message": "session exceeded per-session round budget; re-authenticate to continue",
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    secrets = EnvSecretStore(environ={"ZEUS_PASSWORD": "s3cret-password"})
    endpoint = ZeusEndpointConfig(
        url="http://zeus.example",
        auth_mode="basic",
        username="admin",
        password_env="ZEUS_PASSWORD",
    )
    port = HttpxZeusPort(endpoint=endpoint, secrets=secrets, client=http)
    port._auth.client = http
    target = DataTarget(bucket="beer-sample", scope="_default")
    first = await port.call_verb(
        VerbRequest(verb="find", body={"entity_type": "Beer"}, target=target)
    )
    assert first.status_code == 429
    assert mints["n"] == 1
    second = await port.call_verb(
        VerbRequest(verb="find", body={"entity_type": "Beer"}, target=target)
    )
    assert second.status_code == 429
    assert mints["n"] == 2
    await http.aclose()
