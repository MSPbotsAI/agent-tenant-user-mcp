import json
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from ..api_client import AgentTenantUserClient, AgentTenantUserError
from ._common import NO_TOKEN


def register(mcp: FastMCP, client_factory: Callable[[], AgentTenantUserClient | None]) -> None:

    @mcp.tool()
    async def mspbots_user_list_users(
        page: int | None = None,
        page_size: int | None = None,
    ) -> str:
        """List platform users (paginated). Returns the set of assignable owners.

        Response shape (note: `data` is an OBJECT, not an array):
        {"success": true, "data": {"users": [...], "total": int}}. Each user
        object exposes: id, email, displayName, userName — these are the fields
        the caller maps onto owners.

        Args:
            page: Optional 1-based page number, starting from 1. Default 1.
            page_size: Optional results per page. Default 100.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {
            "page": page,
            "pageSize": page_size,
        }
        try:
            result = await client.get("/users/page", params=params)
            return json.dumps(result, indent=2, default=str)
        except AgentTenantUserError as e:
            return f"Error: {e}"
