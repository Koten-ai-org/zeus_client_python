"""POST /v2/session retries once on HTTP 409 or HTTP 500. Zeus mints the id."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from zeus_client.adapters.secrets_env.store import EnvSecretStore
from zeus_client.adapters.zeus_http.session import HttpxSessionClient
from zeus_client.config.models import ZeusEndpointConfig

ZEUS = "http://zeus.test:8080"


def _client() -> HttpxSessionClient:
    return HttpxSessionClient(
        endpoint=ZeusEndpointConfig(url=ZEUS),
        secrets=EnvSecretStore({}),
    )


def _bodies(route: respx.Route) -> list[dict]:
    return [json.loads(call.request.content) for call in route.calls]


@pytest.mark.asyncio
@respx.mock
async def test_create_retries_500_then_201() -> None:
    route = respx.post(f"{ZEUS}/v2/session").mock(
        side_effect=[
            httpx.Response(500, text="fail"),
            httpx.Response(201, json={"session_id": "sid-minted", "round": 1}),
        ]
    )
    client = _client()
    result = await client.create(
        contract_id="cid",
        contract_hash="md5:aaa",
        chat_request={},
        conversation=[],
    )
    assert route.call_count == 2
    assert result.ok is True
    assert result.status_code == 201
    assert isinstance(result.body, dict)
    assert result.body["session_id"] == "sid-minted"
    bodies = _bodies(route)
    assert bodies[0] == bodies[1]
    assert "session_id" not in bodies[0]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_create_retries_409_then_201() -> None:
    route = respx.post(f"{ZEUS}/v2/session").mock(
        side_effect=[
            httpx.Response(409, text="conflict"),
            httpx.Response(201, json={"session_id": "sid-next", "round": 1}),
        ]
    )
    client = _client()
    result = await client.create(
        contract_id="cid",
        contract_hash="md5:aaa",
        chat_request={},
        conversation=[],
    )
    assert route.call_count == 2
    assert result.ok is True
    assert result.status_code == 201
    assert isinstance(result.body, dict)
    assert result.body["session_id"] == "sid-next"
    assert "session_id" not in _bodies(route)[0]
    assert "session_id" not in _bodies(route)[1]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_create_retries_500_then_500() -> None:
    route = respx.post(f"{ZEUS}/v2/session").mock(return_value=httpx.Response(500, text="fail"))
    client = _client()
    result = await client.create(
        contract_id="cid",
        contract_hash="md5:aaa",
        chat_request={},
        conversation=[],
    )
    assert route.call_count == 2
    assert result.ok is False
    assert result.status_code == 500
    assert result.error == "HTTP 500"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_create_does_not_retry_400() -> None:
    route = respx.post(f"{ZEUS}/v2/session").mock(return_value=httpx.Response(400, text="bad"))
    client = _client()
    result = await client.create(
        contract_id="cid",
        contract_hash="md5:aaa",
        chat_request={},
        conversation=[],
    )
    assert route.call_count == 1
    assert result.ok is False
    assert result.status_code == 400
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_create_does_not_retry_201() -> None:
    route = respx.post(f"{ZEUS}/v2/session").mock(
        return_value=httpx.Response(201, json={"session_id": "sid", "round": 1})
    )
    client = _client()
    result = await client.create(
        contract_id="cid",
        contract_hash="md5:aaa",
        chat_request={},
        conversation=[],
    )
    assert route.call_count == 1
    assert result.ok is True
    assert result.status_code == 201
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_create_does_not_retry_transport_error() -> None:
    route = respx.post(f"{ZEUS}/v2/session").mock(side_effect=httpx.ConnectError("reset"))
    client = _client()
    result = await client.create(
        contract_id="cid",
        contract_hash="md5:aaa",
        chat_request={},
        conversation=[],
    )
    assert route.call_count == 1
    assert result.ok is False
    assert result.status_code == 0
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_continue_turn_does_not_retry_500() -> None:
    route = respx.post(f"{ZEUS}/v2/session/sid/turn").mock(
        return_value=httpx.Response(500, text="fail")
    )
    client = _client()
    result = await client.continue_turn(
        session_id="sid",
        client_round=2,
        chat_request={},
        new_turns=[{"role": "assistant", "content": "ok"}],
    )
    assert route.call_count == 1
    assert result.ok is False
    assert result.status_code == 500
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_post_trace_does_not_retry_500() -> None:
    route = respx.post(f"{ZEUS}/v2/session/trace").mock(
        return_value=httpx.Response(500, text="fail")
    )
    client = _client()
    result = await client.post_trace(
        session_id="sid",
        client_round=1,
        req_id="req-1",
        contract_id="cid",
        contract_hash="md5:aaa",
        chat_request={},
        turns=[],
        zeus_response={"status": 200},
    )
    assert route.call_count == 1
    assert result.ok is False
    assert result.status_code == 500
    await client.aclose()
