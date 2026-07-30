from typing import Any

import httpx

# The App API is only reachable at this path prefix (see tenants.md): "https://
# <host>/apps/mb-platform-user/api/<endpoint>". Do not hardcode this prefix
# elsewhere — X-MSP-Host only carries the bare host.
_API_PREFIX = "/apps/mb-platform-user/api"


class AgentTenantUserError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Agent Platform API error {status_code}: {message}")


class AgentTenantUserClient:
    """Async httpx client wrapping the MSPbots Agent Platform tenant/user API.

    Per the established pattern for this platform (confirmed in ticketqa-mcp),
    the routing layer resolves which tenant a request belongs to via an
    `X_Tenant_ID` header — the source doc (tenants.md) describes this as a
    Cookie requirement, but the working convention across this platform's
    other MCP servers is to forward it as an HTTP header instead, which the
    gateway/routing layer accepts equivalently.
    """

    def __init__(self, access_token: str, host: str, tenant_id: str):
        self._token = access_token
        self._tenant_id = tenant_id
        self._base_url = host.rstrip("/") + _API_PREFIX

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "X_Tenant_ID": self._tenant_id,
            "Accept": "application/json",
        }

    def _clean_params(self, params: dict | None) -> dict:
        if not params:
            return {}
        return {k: v for k, v in params.items() if v is not None}

    async def get(self, path: str, params: dict | None = None) -> Any:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(
                    f"{self._base_url}{path}",
                    headers=self._headers(),
                    params=self._clean_params(params),
                )
            except httpx.RequestError as e:
                raise AgentTenantUserError(
                    0, f"{e or type(e).__name__} (url={self._base_url}{path})"
                ) from e
            return self._handle(resp)

    def _handle(self, resp: httpx.Response) -> Any:
        try:
            body = resp.json()
        except ValueError:
            body = {"raw_response": resp.text}
        if resp.status_code >= 400:
            message = body.get("message") if isinstance(body, dict) else str(body)
            raise AgentTenantUserError(resp.status_code, message or "unknown error")
        return body
