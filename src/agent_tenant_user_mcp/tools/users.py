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
    async def mspbots_user_list_users(
        page: Annotated[
            int | None, Field(description="Page number, starting from 1. Default 1.")
        ] = None,
        page_size: Annotated[
            int | None,
            Field(description="Results per page, 1-100 (default 20; values above 100 are clamped)."),
        ] = None,
        tenant_id: Annotated[
            str | None,
            Field(
                description=(
                    "Tenant to list users of. Only honoured for a platform-level "
                    "credential; anyone else always gets their own tenant. Omit it "
                    "to read the tenant the credential itself belongs to."
                )
            ),
        ] = None,
        search: Annotated[
            str | None,
            Field(
                description=(
                    "Case-insensitive substring match against email, displayName, "
                    "givenName, surname, jobTitle, or department."
                )
            ),
        ] = None,
        department: Annotated[
            str | None,
            Field(description="Exact department match (not a substring match)."),
        ] = None,
        is_active: Annotated[
            str | None,
            Field(description='Active-status filter: "true" or "false". Other values are ignored.'),
        ] = None,
        sort_by: Annotated[
            str | None,
            Field(
                description=(
                    "Sort field: createdAt (default), email, displayName, "
                    "department, or lastLoginAt."
                )
            ),
        ] = None,
        sort_order: Annotated[
            str | None,
            Field(description='Sort direction: "asc" or "desc" (default "desc").'),
        ] = None,
    ) -> str:
        """List users of one tenant (paginated, filterable) — the set of assignable owners.

        Scoped to a single tenant: the credential's own unless a
        platform-level credential passes tenant_id. Filters combine with AND.
        Each user carries id, email, username, displayName, job/department
        fields, active flag, last login, and directory roles.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        if page_size is not None:
            page_size = min(page_size, _MAX_PAGE_SIZE)
        params = {
            "page": page,
            "pageSize": page_size,
            "tenantId": tenant_id,
            "search": search,
            "department": department,
            "isActive": is_active,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        try:
            result = await client.get("/users/page", params=params)
            return dump_json_capped(result)
        except AgentTenantUserError as e:
            return e.to_envelope()
