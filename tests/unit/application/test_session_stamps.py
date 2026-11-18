"""Session create/trace POST bodies stamp user=zeus_client (CHECKLIST D)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from zeus_client.adapters.secrets_env.store import EnvSecretStore
from zeus_client.adapters.zeus_http.session import HttpxSessionClient
from zeus_client.config.models import ClientIdentity, ZeusEndpointConfig
from zeus_client.domain.stamps import PRODUCT_USER

ZEUS = "http://zeus.test:8080"


@pytest.mark.asyncio
@respx.mock
async def test_create_session_stamps_product_user() -> None:
    route = respx.post(f"{ZEUS}/v2/session").mock(
        return_value=httpx.Response(
            201,
            json={"session_id": "sess_1", "round": 1, "contract_status": "ok"},
            headers={"X-Zeus-Req-Id": "d4000000-0000-4000-8000-000000000004"},
        )
    )
    client = HttpxSessionClient(
        endpoint=ZeusEndpointConfig(url=ZEUS),
        secrets=EnvSecretStore({}),
        identity=ClientIdentity(ip_address="203.0.113.9"),
    )
    result = await client.create(
        contract_id="cid",
        contract_hash="md5:aaa",
        chat_request={},
        conversation=[],
    )
    assert result.ok
    body = json.loads(route.calls.last.request.content)
    assert body["user"] == PRODUCT_USER
    assert body["user"] != "admin"
    assert body["ip_address"] == "203.0.113.9"
    assert body["version"]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_post_trace_stamps_and_keeps_dispatch_req_id() -> None:
    route = respx.post(f"{ZEUS}/v2/session/trace").mock(
        return_value=httpx.Response(201, json={"contract_status": "match"})
    )
    client = HttpxSessionClient(
        endpoint=ZeusEndpointConfig(url=ZEUS),
        secrets=EnvSecretStore({}),
    )
    dispatch = "a91c2e10-0c44-4f11-9b2e-88e0d1f3aa01"
    await client.post_trace(
        session_id="sess_1",
        client_round=1,
        req_id=dispatch,
        contract_id="cid",
        contract_hash="md5:aaa",
        chat_request={},
        turns=[],
        zeus_response={"status": 200},
        turn_id="turn-join-1",
    )
    body = json.loads(route.calls.last.request.content)
    assert body["req_id"] == dispatch
    assert body["session_id"] == "sess_1"
    assert body["turn_id"] == "turn-join-1"
    assert body["user"] == PRODUCT_USER
    assert body["zeus_response"]["user"] == PRODUCT_USER
    await client.aclose()


@pytest.mark.asyncio
async def test_create_retries_http_500_then_201() -> None:
    seen = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        if seen["n"] == 1:
            return httpx.Response(500, text="document exists")
        return httpx.Response(201, json={"session_id": "sess_new", "round": 1})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = HttpxSessionClient(
        endpoint=ZeusEndpointConfig(url=ZEUS),
        secrets=EnvSecretStore({}),
        client=http,
    )
    result = await client.create(contract_id="cid", contract_hash="h", chat_request={})
    assert result.ok
    assert result.body["session_id"] == "sess_new"
    assert seen["n"] == 2
    await http.aclose()


@pytest.mark.asyncio
async def test_create_does_not_retry_http_400() -> None:
    seen = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        return httpx.Response(400, text="bad")

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = HttpxSessionClient(
        endpoint=ZeusEndpointConfig(url=ZEUS),
        secrets=EnvSecretStore({}),
        client=http,
    )
    result = await client.create(contract_id="cid", contract_hash="h", chat_request={})
    assert not result.ok
    assert result.status_code == 400
    assert seen["n"] == 1
    await http.aclose()
