import contextvars
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .api_client import AgentTenantUserClient
from .config import Settings

# Per-request credential isolation via contextvars.
# GatewayTokenMiddleware sets this before the MCP handler runs.
# Python asyncio copies context per task, so concurrent SSE connections are isolated.
_gateway_creds_var: contextvars.ContextVar[tuple[str, str] | None] = (
    contextvars.ContextVar("agent_tenant_user_gateway_creds", default=None)
)


def get_client_from_context() -> AgentTenantUserClient | None:
    """Resolve the active AgentTenantUserClient for the current request context."""
    creds = _gateway_creds_var.get()
    if not creds:
        return None
    token, host = creds
    return AgentTenantUserClient(token, host)


class GatewayTokenMiddleware:
    """ASGI middleware.

    Reads X-API-Key and X-MSP-Host (both required) from request headers and
    stores them in the contextvar. Returns 401 on /mcp requests if either is
    missing.

    There is no tenant header: the credential in X-API-Key is already
    tenant-scoped (an API key belongs to the tenant that minted it, a JWT
    carries its tenant). A caller that needs to read another tenant passes
    mspbots_user_list_users' tenant_id argument, which only a platform-level
    credential is allowed to use.
    """

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        token = request.headers.get("x-api-key")
        if not token:
            # NOTE(transition, 2026-09-21): X-API-Key replaced X-MSP-Token as the
            # credential header name. Credential rows written before the rename
            # still hold the old key and the gateway injects whatever is stored,
            # so keep honouring it until every tenant's credential has been
            # re-saved under X-API-Key. Remove this fallback — and
            # test_legacy_token_header_is_still_accepted — once that is done.
            token = request.headers.get("x-msp-token")
        host = request.headers.get("x-msp-host")
        if not token or not host:
            response = JSONResponse(
                {
                    "error": "Missing credentials",
                    "message": (
                        "This server requires the X-API-Key header (Agent Platform "
                        "API key, or a user JWT) and the X-MSP-Host header (Agent "
                        "Platform host)."
                    ),
                    "required_headers": ["X-API-Key", "X-MSP-Host"],
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        ctx_token = _gateway_creds_var.set((token, host))
        try:
            await self.app(scope, receive, send)
        finally:
            _gateway_creds_var.reset(ctx_token)


def create_mcp_server(settings: Settings) -> FastMCP:
    """Build the FastMCP server instance and register all tenant/user tools."""
    # DNS-rebinding protection is a browser-oriented safeguard that rejects
    # non-localhost Host headers with 421. Disable it so the server works
    # correctly behind a reverse proxy or docker network.
    mcp = FastMCP(
        name="agent-tenant-user-mcp",
        instructions=(
            "This server wraps an internal MSPbots Agent Platform directory "
            "API — not a third-party vendor product. It exposes "
            "platform-level tenant and user records, not customer support or "
            "ticketing data. mspbots_user_list_tenants lists onboarded tenant "
            "organizations with pagination and optional filters (free-text "
            "search, active status, registration date range). "
            "mspbots_user_list_users lists users of one tenant — the set of "
            "assignable owners — with search, department, active-status and "
            "sort options. Both need a platform-level credential to see "
            "beyond a single tenant; otherwise the results narrow to the "
            "credential's own tenant, or a permission error comes back. "
            "Tenant and user ids are the platform's directory ids, the same "
            "ones other platform services use. Typical use: audit which "
            "tenants exist, find a tenant's id/slug, or look up a user to "
            "assign as an owner. This is a read-only service — no tool "
            "creates, updates, or deletes tenants or users."
        ),
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        stateless_http=True,
        json_response=True,
    )

    client_factory: Callable[[], AgentTenantUserClient | None] = get_client_from_context

    from .tools import tenants, users

    tenants.register(mcp, client_factory)
    users.register(mcp, client_factory)

    return mcp
