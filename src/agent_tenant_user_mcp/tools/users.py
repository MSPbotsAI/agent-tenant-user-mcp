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
            Field(description="Results per page (default 100; values above 100 are clamped)."),
        ] = None,
    ) -> str:
        """List users within the caller's own tenant (paginated) — scoped to
        the tenant identified by the credential, not the whole platform.
        Returns the set of assignable owners (id, email, displayName,
        userName per user).
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        if page_size is not None:
            page_size = min(page_size, _MAX_PAGE_SIZE)
        params = {
            "page": page,
            "pageSize": page_size,
        }
        try:
            result = await client.get("/users/page", params=params)
            return dump_json_capped(result)
        except AgentTenantUserError as e:
            return e.to_envelope()
