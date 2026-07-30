# agent-tenant-user-mcp

MCP server for the **MSPbots Agent Platform tenant/user API** (`mb-platform-user` service) — lets an Agent list all platform tenants.

> **Naming note:** this is not a third-party vendor integration. It wraps an **internal MSPbots App API** (path prefix `/apps/mb-platform-user/api/...`) on the Agent Platform (`agent.mspbots.ai`). "MSP" in the header names below refers to the MSPbots Agent Platform itself, not an external MSP tool vendor. Auth convention follows the same pattern already established in `ticketqa-mcp` (another internal Agent Platform App API MCP), per explicit instruction to reuse that pattern.

## Overview

- Stateless HTTP service. No credentials are ever persisted — each request supplies its own bearer token/tenant/host via headers, used only for the lifetime of that single request.
- Supports concurrent requests; per-request credential isolation is done via Python `contextvars`, not a global/shared client instance.
- Entry points: `POST /mcp` (MCP protocol) and `GET /health` (health check).
- Default port: `8080` (configurable via `MCP_HTTP_PORT`).

## Scope

**1 tool**, matching the single documented endpoint (`tenants.md`, attached to [PRD-15236](https://app.clickup.com/t/2280862/PRD-15236)):

- `mspbots_user_list_tenants` — `GET /apps/mb-platform-user/api/tenants` (paginated + filterable, returns **all platform tenants**; requires `superAdmin`/`admin` role per the source doc).

No larger public API exists to reference for broader scope (this is a first-party internal service), so scope is exactly what the source doc documents.

**Query parameters were corrected on 2026-07-30** — Leo Yang posted the actual current INT-branch implementation (`service/tenant.ts:87`), which documents 4 filter parameters (`search`, `isActive`, `createdFrom`, `createdTo`) beyond the `page`/`pageSize` in the original `tenants.md` attachment, and clarifies that `page`/`pageSize` are both optional (defaults 1 / 20), not required. This tool has been updated to match that corrected spec.

## Authentication

Per the source doc, this endpoint requires:
- `Authorization: Bearer <JWT>` (EdDSA-signed) — tenant/user/role are decoded from the JWT itself.
- An `X_Tenant_ID` value for platform routing — the source doc describes this as a **Cookie**, but the established working convention on this platform (confirmed in `ticketqa-mcp`, where the equivalent header was empirically required because a bearer token alone gets `404 App not found`) is to forward it as an **HTTP header** instead. This server follows that same convention rather than the doc's literal wording, for consistency with the platform's other MCP servers.

The Agent Platform host (`agent.mspbots.ai` or its per-environment equivalent) is also supplied per-request, since different environments (INT/STG/PROD) may use different hosts.

### HEADER 授权参数说明

| Header | 类型 | 是否必填 | 默认值 | 枚举值 | 字段描述 | Example |
|---|---|---|---|---|---|---|
| `X-MSP-Token` | string | 是 | 无 | 无（自由文本，JWT） | Agent Platform 已签发的访问凭证（EdDSA 签名的 JWT bearer token）。本服务原样转发为下游请求的 `Authorization: Bearer <token>`，不做任何换取/校验逻辑。 | `X-MSP-Token: eyJhbGciOiJFZERTQSJ9...` |
| `X-MSP-Tenant-Id` | string | 是 | 无 | 无（自由文本，UUID） | 租户标识。转发给下游 API 时改名为 `X_Tenant_ID` header——这是平台路由层用来判断请求归属哪个租户的机制，源文档写的是 Cookie，但沿用本平台已验证可用的 header 转发方式。 | `X-MSP-Tenant-Id: e9f794fe-a6b4-4f35-bd2f-fcd19c5cc308` |
| `X-MSP-Host` | string | 是 | 无 | 无（自由文本，base URL） | Agent Platform 所在的 host。本服务会拼接 `/apps/mb-platform-user/api/<endpoint>` 得到完整请求地址。 | `X-MSP-Host: https://agent.mspbots.ai` |

Missing any header returns `401`:
```json
{
  "error": "Missing credentials",
  "message": "This server requires the X-MSP-Token header (Agent Platform bearer access credential), the X-MSP-Tenant-Id header, and the X-MSP-Host header (Agent Platform host)",
  "required_headers": ["X-MSP-Token", "X-MSP-Tenant-Id", "X-MSP-Host"],
  "optional_headers": []
}
```

## Environment Variables

| Variable | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `MCP_HTTP_PORT` | int | 否 | `8080` | HTTP 监听端口 |
| `MCP_HTTP_HOST` | string | 否 | `0.0.0.0` | HTTP 监听地址 |

## MCP Endpoint

- `POST /mcp` — MCP protocol (streamable HTTP transport)
- `GET /health` — health check, returns `{"status": "ok", "service": "agent-tenant-user-mcp", "transport": "http"}`

## Tool List

| Tool | 功能 | 方法+路径 | 参数 |
|---|---|---|---|
| `mspbots_user_list_tenants` | 分页获取全平台租户列表，支持关键字/启用状态/注册时间区间过滤（需 superAdmin/admin 角色） | GET /apps/mb-platform-user/api/tenants | page(可选,默认1), page_size(可选,默认20), search(可选), is_active(可选), created_from(可选), created_to(可选) |

`search`/`is_active`/`created_from`/`created_to` combine as AND; results are always sorted by `createdAt` descending; an invalid date value in `created_from`/`created_to` is silently ignored (not an error) per the confirmed INT-branch implementation.

## 测试示例

```bash
# Health check
curl -s http://localhost:8080/health

# Call the tool via the MCP protocol (streamable HTTP) — requires an
# initialize handshake first per the MCP spec; abbreviated example below
# shows the tool-call request body only:
curl -s -X POST http://localhost:8080/mcp \
  -H "X-MSP-Token: <jwt>" \
  -H "X-MSP-Tenant-Id: <tenant-id>" \
  -H "X-MSP-Host: https://agent.mspbots.ai" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <session-id-from-initialize>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "mspbots_user_list_tenants",
      "arguments": {"page": 1, "page_size": 50, "created_from": "2026-07-01"}
    }
  }'
```

## API Reference

- Source doc: `tenants.md`, attached to [PRD-15236](https://app.clickup.com/t/2280862/PRD-15236) — superseded for the query-parameter list by Leo Yang's 2026-07-30 confirmation of the actual current INT-branch implementation (`service/tenant.ts:87`), posted in the MB_AgentPlatform Teams chat.

## Known Gaps

- **Live self-test still not passing** — every attempt so far (a PROD web-panel token, then a real Agent Platform admin-role JWT) has returned `403 Permission denied`, even with header/cookie transport variations for `X_Tenant_ID` ruled out as the cause (all three transports gave the identical result). Current working theory: the JWT's `appRoles` field was an empty object (`{}`) and this endpoint may check per-app `appRoles` rather than the top-level `roles` array — unconfirmed, needs backend-side clarification.
- The `X_Tenant_ID`-as-header-not-cookie assumption is carried over from `ticketqa-mcp`'s empirical finding on the same platform, not independently re-verified for this specific `mb-platform-user` service.
- `code`/`timezoneOffset`/timestamp-format semantics beyond the corrected query-parameter table are still only inferred from the original source doc, not officially confirmed by the backend team.
