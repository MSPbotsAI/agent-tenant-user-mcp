"""Downstream contract tests: the directory API path prefix, and picking
the right auth header for the credential that was handed in.

No network calls — only the request the client would have made.
"""

from agent_tenant_user_mcp.api_client import AgentTenantUserClient


def test_base_url_points_at_the_setting_directory_mcp_surface():
    client = AgentTenantUserClient("mbk_abc", "https://agentint.mspbots.ai")
    assert client._base_url == (
        "https://agentint.mspbots.ai/apps/mb-platform-setting/api/directory/mcp"
    )


def test_trailing_slash_on_host_does_not_double_up():
    client = AgentTenantUserClient("mbk_abc", "https://agentint.mspbots.ai/")
    assert "//apps" not in client._base_url


def test_api_key_credential_goes_in_x_api_key():
    headers = AgentTenantUserClient("mbk_live_123", "https://h")._headers()
    assert headers["X-API-Key"] == "mbk_live_123"
    assert "Authorization" not in headers


def test_credential_is_passed_through_whatever_it_looks_like():
    """No sniffing: the credential goes out as X-API-Key regardless of shape.

    Pinned because the old code branched on a "mbk_" prefix and sent anything
    else as Authorization: Bearer. Reintroducing that would be invisible here
    unless a non-prefixed value is asserted too — and in production it would
    surface only as a 401 that looks exactly like an expired key.
    """
    headers = AgentTenantUserClient("eyJhbGciOiJFZERTQSJ9.aaa.bbb", "https://h")._headers()
    assert headers["X-API-Key"] == "eyJhbGciOiJFZERTQSJ9.aaa.bbb"
    assert "Authorization" not in headers


def test_tenant_id_is_never_sent_as_a_header():
    # The downstream derives tenancy from the credential; the client holds no
    # tenant at all, so nothing tenant-shaped can leak into the headers.
    headers = AgentTenantUserClient("mbk_abc", "https://h")._headers()
    assert not [k for k in headers if "tenant" in k.lower()]


def test_none_params_are_dropped_before_the_request():
    client = AgentTenantUserClient("mbk_abc", "https://h")
    assert client._clean_params({"page": 1, "search": None}) == {"page": 1}
    assert client._clean_params(None) == {}
