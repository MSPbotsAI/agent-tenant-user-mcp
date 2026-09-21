"""Gateway credential middleware tests: missing-header 401, and header
values correctly reaching the per-request contextvar (no global-state
leakage across requests).
"""

from starlette.testclient import TestClient

from agent_tenant_user_mcp.__main__ import _build_http_app
from agent_tenant_user_mcp.config import Settings
from agent_tenant_user_mcp.server import create_mcp_server, get_client_from_context


def _make_app():
    settings = Settings()
    mcp = create_mcp_server(settings)
    return _build_http_app(mcp, settings), settings


def test_health_is_local_and_does_not_require_credentials():
    app, _ = _make_app()
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_missing_header_returns_401_with_required_headers_listed():
    app, _ = _make_app()
    with TestClient(app) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"Accept": "application/json, text/event-stream"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["required_headers"] == ["X-API-Key", "X-MSP-Host"]


def test_missing_single_header_still_returns_401():
    app, _ = _make_app()
    with TestClient(app) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={
                "Accept": "application/json, text/event-stream",
                "X-API-Key": "dummy-token",
                # X-MSP-Host intentionally omitted
            },
        )
        assert resp.status_code == 401


def test_the_two_required_headers_are_enough():
    # There is no tenant header any more: the credential is already
    # tenant-scoped, so X-API-Key + X-MSP-Host must reach the MCP handler.
    app, _ = _make_app()
    with TestClient(app) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={
                "Accept": "application/json, text/event-stream",
                "X-API-Key": "dummy-token",
                "X-MSP-Host": "https://agent.mspbots.ai",
            },
        )
        assert resp.status_code == 200


def test_legacy_token_header_is_still_accepted():
    # NOTE(transition, 2026-09-21): credential rows written before the
    # X-MSP-Token -> X-API-Key rename still inject the old name. Delete this
    # test together with the fallback in GatewayTokenMiddleware once every
    # tenant credential has been re-saved.
    app, _ = _make_app()
    with TestClient(app) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={
                "Accept": "application/json, text/event-stream",
                "X-MSP-Token": "legacy-token",
                "X-MSP-Host": "https://agent.mspbots.ai",
            },
        )
        assert resp.status_code == 200


def test_x_api_key_wins_when_both_names_are_present():
    # A tenant mid-migration can briefly have both stored; the new name is
    # the one that counts, so re-saving a credential takes effect immediately.
    import asyncio

    from agent_tenant_user_mcp.server import GatewayTokenMiddleware, _gateway_creds_var

    seen = {}

    async def fake_app(scope, receive, send):
        seen["creds"] = _gateway_creds_var.get()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = GatewayTokenMiddleware(fake_app, Settings())

    async def run():
        scope = {
            "type": "http",
            "path": "/mcp",
            "headers": [
                (b"x-api-key", b"new-key"),
                (b"x-msp-token", b"legacy-key"),
                (b"x-msp-host", b"https://agent.mspbots.ai"),
            ],
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            pass

        await middleware(scope, receive, send)

    asyncio.run(run())
    assert seen["creds"] == ("new-key", "https://agent.mspbots.ai")


def test_header_present_reaches_request_context(monkeypatch):
    # Directly exercises the middleware's contextvar plumbing without a full
    # MCP protocol round-trip: confirms the header values that arrive on the
    # request are exactly what get_client_from_context sees, and that they
    # are reset afterward (no leakage to the next request).
    import asyncio

    from agent_tenant_user_mcp.server import GatewayTokenMiddleware, _gateway_creds_var

    settings = Settings()
    seen = {}

    async def fake_app(scope, receive, send):
        seen["creds"] = _gateway_creds_var.get()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = GatewayTokenMiddleware(fake_app, settings)

    async def run():
        scope = {
            "type": "http",
            "path": "/mcp",
            "headers": [
                (b"x-api-key", b"test-token-123"),
                (b"x-msp-host", b"https://agent.mspbots.ai"),
            ],
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        sent = []

        async def send(message):
            sent.append(message)

        await middleware(scope, receive, send)

    asyncio.run(run())
    assert seen["creds"] == ("test-token-123", "https://agent.mspbots.ai")
    # After the request completes, the contextvar must be reset — a fresh
    # get() outside any request context sees no leftover credential.
    assert _gateway_creds_var.get() is None


def test_client_factory_returns_none_without_context():
    assert get_client_from_context() is None
