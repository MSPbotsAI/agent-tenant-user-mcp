"""Downstream contract tests: the directory API path prefix, and picking
the right auth header for the credential that was handed in.

No network calls — only the request the client would have made.
"""

from agent_tenant_user_mcp.api_client import AgentTenantUserClient


def test_base_url_points_at_the_setting_directory_mcp_surface():
    client = AgentTenantUserClient("mbk_abc", "https://agentint.mspbots.ai", "tenant-1")
    assert client._base_url == (
        "https://agentint.mspbots.ai/apps/mb-platform-setting/api/directory/mcp"
    )


def test_trailing_slash_on_host_does_not_double_up():
    client = AgentTenantUserClient("mbk_abc", "https://agentint.mspbots.ai/", None)
    assert "//apps" not in client._base_url


def test_api_key_credential_goes_in_x_api_key():
    headers = AgentTenantUserClient("mbk_live_123", "https://h", None)._headers()
    assert headers["X-API-Key"] == "mbk_live_123"
    assert "Authorization" not in headers


def test_jwt_credential_still_goes_in_authorization_bearer():
    headers = AgentTenantUserClient("eyJhbGciOiJFZERTQSJ9.aaa.bbb", "https://h", None)._headers()
    assert headers["Authorization"] == "Bearer eyJhbGciOiJFZERTQSJ9.aaa.bbb"
    assert "X-API-Key" not in headers


def test_tenant_id_is_never_sent_as_a_header():
    # The downstream derives tenancy from the credential; a stray tenant
    # header would be dead weight at best and misleading at worst.
    headers = AgentTenantUserClient("mbk_abc", "https://h", "tenant-1")._headers()
    assert not [k for k in headers if "tenant" in k.lower()]


def test_none_params_are_dropped_before_the_request():
    client = AgentTenantUserClient("mbk_abc", "https://h", None)
    assert client._clean_params({"page": 1, "search": None}) == {"page": 1}
    assert client._clean_params(None) == {}
