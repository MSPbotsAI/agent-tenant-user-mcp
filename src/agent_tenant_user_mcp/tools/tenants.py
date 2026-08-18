from collections.abc import Callable
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .._json import dump_json_capped
from ..api_client import AgentTenantUserClient, AgentTenantUserError
from ._common import NO_TOKEN

_MAX_PAGE_SIZE = 100


def register(mcp: FastMCP, client_factory: Callable[[], AgentTenantUserClient | None]) -> None:

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def mspbots_user_list_tenants(
        page: Annotated[
            int | None, Field(description="Page number, starting from 1. Default 1.")
        ] = None,
        page_size: Annotated[
            int | None,
            Field(description="Results per page, 1-100 (default 20; values above 100 are clamped)."),
        ] = None,
        search: Annotated[
            str | None,
            Field(
                description="Case-insensitive substring match against name, slug, or microsoftTenantName."
            ),
        ] = None,
        is_active: Annotated[
            str | None,
            Field(description='Active-status filter: "true" or "false". Other values are ignored.'),
        ] = None,
        created_from: Annotated[
            str | None,
            Field(
                description=(
                    "Inclusive lower bound on registration time. Accepts YYYY-MM-DD, "
                    '"YYYY-MM-DD HH:MM:SS", or an ISO 8601 datetime; no-timezone values '
                    "are parsed as UTC."
                )
            ),
        ] = None,
        created_to: Annotated[
            str | None,
            Field(
                description=(
                    "Inclusive upper bound on registration time, same formats as "
                    "created_from; a date-only value widens to end of that day."
                )
            ),
        ] = None,
    ) -> str:
        """List platform tenants (paginated, filterable). Requires superAdmin/admin role.

        Filters combine with AND; results are always sorted by createdAt
        descending; an invalid date in created_from/created_to is silently
        ignored rather than erroring.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        if page_size is not None:
            page_size = min(page_size, _MAX_PAGE_SIZE)
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
            return dump_json_capped(result)
        except AgentTenantUserError as e:
            return e.to_envelope()
