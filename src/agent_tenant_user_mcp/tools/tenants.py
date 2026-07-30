import json
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from ..api_client import AgentTenantUserClient, AgentTenantUserError
from ._common import NO_TOKEN


def register(mcp: FastMCP, client_factory: Callable[[], AgentTenantUserClient | None]) -> None:

    @mcp.tool()
    async def mspbots_user_list_tenants(
        page: int | None = None,
        page_size: int | None = None,
        search: str | None = None,
        is_active: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> str:
        """List all platform tenants (paginated, filterable). Requires superAdmin/admin role.

        API: GET /apps/mb-platform-user/api/tenants

        Per the current INT-branch implementation (service/tenant.ts:87, confirmed
        by Leo Yang 2026-07-30 — supersedes the original source doc, which only
        documented page/pageSize): all filters combine with AND; results are
        always sorted by createdAt descending; an invalid date value in
        created_from/created_to is silently ignored rather than erroring.

        Response shape: {"code": 200, "data": {"tenants": [...], "total": int,
        "page": int, "pageSize": int, "totalPages": int}}. Each tenant object:
        id (uuid), name, slug, agentDomain, microsoftTenantId,
        microsoftTenantName, microsoftDomain, registrarEmail (nullable),
        timezoneId, timezoneName, timezoneOffset, isActive, createdAt,
        updatedAt, userCount.

        Args:
            page: Optional page number, starting from 1. Default 1.
            page_size: Optional results per page, range 1-100 (values above
                100 are clamped to 100). Default 20.
            search: Optional case-insensitive substring match against name,
                slug, or microsoftTenantName — any match is returned.
            is_active: Optional active-status filter. Only "true" or "false"
                are honored; any other value is treated as no filter.
            created_from: Optional inclusive lower bound on registration time.
                Accepts YYYY-MM-DD, "YYYY-MM-DD HH:MM:SS",
                YYYY-MM-DDThh:mm:ssZ, or YYYY-MM-DDThh:mm:ss+hh:mm; a value
                with no timezone suffix is parsed as UTC.
            created_to: Optional inclusive upper bound on registration time,
                same accepted formats as created_from; a date-only value is
                widened to 23:59:59.999 of that day.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {
            "page": page,
            "pageSize": page_size,
            "search": search,
            "isActive": is_active,
            "createdFrom": created_from,
            "createdTo": created_to,
        }
        try:
            result = await client.get("/tenants", params=params)
            return json.dumps(result, indent=2, default=str)
        except AgentTenantUserError as e:
            return f"Error: {e}"
