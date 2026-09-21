"""tools/list snapshot + error-envelope mapping tests.

No network calls: tool enumeration goes through FastMCP's in-process
list_tools(), and the error-code mapping is tested directly against
AgentTenantUserError, independent of any real HTTP request.
"""

import pytest

from agent_tenant_user_mcp.api_client import AgentTenantUserError
from agent_tenant_user_mcp.config import Settings
from agent_tenant_user_mcp.server import create_mcp_server

EXPECTED_TOOLS = {
    "mspbots_user_list_tenants": set(),
    "mspbots_user_list_users": set(),
}


@pytest.mark.asyncio
async def test_tools_list_snapshot():
    mcp = create_mcp_server(Settings())
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == set(EXPECTED_TOOLS), f"unexpected tool set: {names}"

    by_name = {t.name: t for t in tools}
    for name, expected_required in EXPECTED_TOOLS.items():
        tool = by_name[name]
        required = set(tool.inputSchema.get("required", []))
        assert required == expected_required, f"{name}: required={required}"
        assert tool.annotations is not None and tool.annotations.readOnlyHint is True
        assert len(tool.description or "") <= 500, f"{name}: description too long"
        first_line = (tool.description or "").strip().splitlines()[0]
        assert len(first_line) <= 100, f"{name}: first line too long: {first_line!r}"
        assert "API:" not in (tool.description or ""), f"{name}: leaked implementation detail"


@pytest.mark.asyncio
async def test_service_instructions_present_and_bounded():
    mcp = create_mcp_server(Settings())
    assert mcp.instructions
    assert len(mcp.instructions) <= 1500


@pytest.mark.parametrize(
    "status_code,expected_code,expected_retryable",
    [
        (0, "upstream_error", True),
        (400, "invalid_argument", False),
        (401, "unauthorized", False),
        (403, "unauthorized", False),
        (404, "not_found", False),
        (422, "invalid_argument", False),
        (429, "rate_limited", True),
        (500, "upstream_error", True),
        (503, "upstream_error", True),
    ],
)
def test_error_envelope_mapping(status_code, expected_code, expected_retryable):
    import json

    err = AgentTenantUserError(status_code, "boom")
    envelope = json.loads(err.to_envelope())
    assert envelope["error"]["code"] == expected_code
    assert envelope["error"]["retryable"] is expected_retryable
    assert envelope["error"]["message"] == "boom"


class _StubClient:
    """Records the downstream call a tool would have made."""

    def __init__(self):
        self.calls = []

    async def get(self, path, params=None):
        self.calls.append((path, params))
        return {"code": 200, "data": {"users": [], "total": 0}}


def _users_server(stub):
    from mcp.server.fastmcp import FastMCP

    from agent_tenant_user_mcp.tools import users

    mcp = FastMCP(name="test")
    users.register(mcp, lambda: stub)
    return mcp


@pytest.mark.asyncio
async def test_list_users_exposes_the_documented_filters():
    mcp = create_mcp_server(Settings())
    tool = {t.name: t for t in await mcp.list_tools()}["mspbots_user_list_users"]
    assert set(tool.inputSchema["properties"]) == {
        "page",
        "page_size",
        "tenant_id",
        "search",
        "department",
        "is_active",
        "sort_by",
        "sort_order",
    }


@pytest.mark.asyncio
async def test_list_users_maps_arguments_to_downstream_query_params():
    stub = _StubClient()
    mcp = _users_server(stub)
    await mcp.call_tool(
        "mspbots_user_list_users",
        {
            "page": 2,
            "page_size": 50,
            "tenant_id": "org_abc",
            "search": "jason",
            "department": "R&D",
            "is_active": "true",
            "sort_by": "lastLoginAt",
            "sort_order": "asc",
        },
    )
    path, params = stub.calls[0]
    assert path == "/users/page"
    assert params == {
        "page": 2,
        "pageSize": 50,
        "tenantId": "org_abc",
        "search": "jason",
        "department": "R&D",
        "isActive": "true",
        "sortBy": "lastLoginAt",
        "sortOrder": "asc",
    }


@pytest.mark.asyncio
async def test_list_users_page_size_is_clamped_to_the_upstream_cap():
    stub = _StubClient()
    mcp = _users_server(stub)
    await mcp.call_tool("mspbots_user_list_users", {"page_size": 5000})
    assert stub.calls[0][1]["pageSize"] == 100


@pytest.mark.asyncio
async def test_tenant_id_comes_only_from_the_tool_argument():
    # There is no tenant header any more, so the argument is the single
    # source: pass it and it travels, omit it and the param is dropped by
    # the real client's _clean_params, leaving the downstream to fall back
    # to the tenant the credential itself belongs to.
    stub = _StubClient()
    mcp = _users_server(stub)
    await mcp.call_tool("mspbots_user_list_users", {"tenant_id": "org_explicit"})
    assert stub.calls[0][1]["tenantId"] == "org_explicit"

    await mcp.call_tool("mspbots_user_list_users", {})
    assert stub.calls[1][1]["tenantId"] is None
