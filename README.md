# agent-tenant-user-mcp

MCP server for the **MSPbots Agent Platform tenant/user API** — lets an Agent list platform tenants and platform users.

> **Naming note:** this is not a third-party vendor integration. It wraps an **internal MSPbots App API** on the Agent Platform. "MSP" in the header names below refers to the MSPbots Agent Platform itself, not an external MSP tool vendor.

## Overview

- Stateless HTTP service. No credentials are ever persisted — each request supplies its own bearer token/tenant/host via headers, used only for the lifetime of that single request.
- Supports concurrent requests; per-request credential isolation is done via Python `contextvars`, not a global/shared client instance.
- Entry points: `POST /mcp` (MCP protocol) and `GET /health` (health check).
- Default port: `8080` (configurable via `MCP_HTTP_PORT`).

## Scope

**2 tools:**

- `mspbots_user_list_tenants` — paginated + filterable, returns platform tenants (requires `superAdmin`/`admin` role).
- `mspbots_user_list_users` — paginated, returns platform users (the set of assignable owners).

## Authentication

This server requires, per request:
- `Authorization: Bearer <JWT>` (EdDSA-signed) — tenant/user/role are decoded from the JWT itself.
- A tenant identifier value for platform routing.
- The Agent Platform host, supplied per-request since different environments may use different hosts.

### HEADER 授权参数说明

| Header | 类型 | 是否必填 | 默认值 | 枚举值 | 字段描述 | Example |
|---|---|---|---|---|---|---|
| `X-MSP-Token` | string | 是 | 无 | 无（自由文本，JWT） | Agent Platform 已签发的访问凭证（EdDSA 签名的 JWT bearer token）。本服务原样转发为下游请求的 `Authorization: Bearer <token>`，不做任何换取/校验逻辑。 | `X-MSP-Token: <jwt>` |
| `X-MSP-Tenant-Id` | string | 是 | 无 | 无（自由文本，UUID） | 租户标识。转发给下游 API 作为平台路由层判断请求归属哪个租户的机制。 | `X-MSP-Tenant-Id: <tenant-uuid>` |
| `X-MSP-Host` | string | 是 | 无 | 无（自由文本，base URL） | Agent Platform 所在的 host。本服务会拼接内部 App API 路径得到完整请求地址。 | `X-MSP-Host: <platform-host>` |

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

| Tool | 功能 | 参数 |
|---|---|---|
| `mspbots_user_list_tenants` | 分页获取全平台租户列表，支持关键字/启用状态/注册时间区间过滤（需 superAdmin/admin 角色） | page(可选,默认1), page_size(可选,默认20), search(可选), is_active(可选), created_from(可选), created_to(可选) |
| `mspbots_user_list_users` | 分页获取全平台用户列表（可分配 owners，返回 id/email/displayName/userName） | page(可选,默认1), page_size(可选,默认100) |

`mspbots_user_list_tenants` 的 `search`/`is_active`/`created_from`/`created_to` combine as AND; results are always sorted by `createdAt` descending; an invalid date value in `created_from`/`created_to` is silently ignored (not an error).

## 测试示例

```bash
# Health check
curl -s http://localhost:8080/health

# Call a tool via the MCP protocol (streamable HTTP) — requires an
# initialize handshake first per the MCP spec; abbreviated example below
# shows the tool-call request body only:
curl -s -X POST http://localhost:8080/mcp \
  -H "X-MSP-Token: <jwt>" \
  -H "X-MSP-Tenant-Id: <tenant-uuid>" \
  -H "X-MSP-Host: <platform-host>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <session-id-from-initialize>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "mspbots_user_list_users",
      "arguments": {"page": 1, "page_size": 100}
    }
  }'
```
