import json
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from ..api_client import AgentTenantUserClient, AgentTenantUserError
from ._common import NO_TOKEN


def register(mcp: FastMCP, client_factory: Callable[[], AgentTenantUserClient | None]) -> None:

    @mcp.tool()
    async def agent_tenant_user_list_tenants(page: int, page_size: int) -> str:
        """List all platform tenants (paginated). Requires superAdmin/admin role.

        API: GET /apps/mb-platform-user/api/tenants

        Response shape: {"code": 200, "data": {"tenants": [...], "total": int,
        "page": int, "pageSize": int, "totalPages": int}}. Each tenant object:
        id (uuid), name, slug, agentDomain, microsoftTenantId,
        microsoftTenantName, microsoftDomain, registrarEmail (nullable),
        timezoneId, timezoneName, timezoneOffset, isActive, createdAt,
        updatedAt, userCount.

        Args:
            page: Required page number, starting from 1.
            page_size: Required number of results per page.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"page": page, "pageSize": page_size}
        try:
            result = await client.get("/tenants", params=params)
            return json.dumps(result, indent=2, default=str)
        except AgentTenantUserError as e:
            return f"Error: {e}"
