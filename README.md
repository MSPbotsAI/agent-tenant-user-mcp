# agent-tenant-user-mcp

MCP server for the **MSPbots Agent Platform directory API** — lets an Agent list platform tenants and the users of a tenant.

> **Naming note:** this is not a third-party vendor integration. It wraps an **internal MSPbots App API** on the Agent Platform. "MSP" in the header names below refers to the MSPbots Agent Platform itself, not an external MSP tool vendor.

## Overview

- Stateless HTTP service. No credentials are ever persisted — each request supplies its own credential and host via headers, used only for the lifetime of that single request.
- Supports concurrent requests; per-request credential isolation is done via Python `contextvars`, not a global/shared client instance.
- Entry points: `POST /mcp` (MCP protocol) and `GET /health` (health check).
- Default port: `8080` (configurable via `MCP_HTTP_PORT`).

## Scope

**2 tools:**

- `mspbots_user_list_tenants` — paginated + filterable, returns platform tenants (needs a platform-level credential).
- `mspbots_user_list_users` — paginated + filterable, returns the users of one tenant (the set of assignable owners).

## Authentication

This server requires, per request:
- A credential in `X-API-Key` — normally a tenant **API key** (`mbk_…`), minted on the platform's API Keys page. A user JWT also works for debugging.
- The Agent Platform host, supplied per-request since different environments may use different hosts.

There is **no tenant header**. The credential is already tenant-scoped: an API key belongs to the tenant that minted it, and a JWT carries its tenant. To read a different tenant, pass `mspbots_user_list_users`' `tenant_id` argument — which only a platform-level credential is allowed to use.

**凭证怎么转发**：`X-API-Key` 以 `mbk_` 开头时，下游收到 `X-API-Key: <token>`；否则按 JWT 处理，下游收到 `Authorization: Bearer <token>`。本服务不做任何换取/校验逻辑。

### HEADER 授权参数说明

| Header | 类型 | 是否必填 | 默认值 | 枚举值 | 字段描述 | Example |
|---|---|---|---|---|---|---|
| `X-API-Key` | string | 是 | 无 | 无（自由文本） | 平台凭证。推荐用租户 API key（`mbk_` 前缀）；也接受用户 JWT（主要用于调试）。 | `X-API-Key: mbk_xxx` |
| `X-MSP-Host` | string | 是 | 无 | 无（自由文本，base URL） | Agent Platform 所在的 host。本服务会拼接内部 App API 路径得到完整请求地址。 | `X-MSP-Host: <platform-host>` |

> ⏳ **过渡期兼容（2026-09-21 起）**：`X-API-Key` 取代了原来的 `X-MSP-Token`。改名前写入的租户凭据仍以旧名存在注册库里、由网关原样注入，因此中间件在读不到 `X-API-Key` 时仍会回退读 `X-MSP-Token`。两个都在时以 `X-API-Key` 为准。等所有租户的凭据都按新名重存一遍后，删掉 `server.py` 里那段回退和 `tests/test_middleware.py::test_legacy_token_header_is_still_accepted`。
>
> 🚫 `X-MSP-Tenant-Id` 已移除，不再读取；传了也会被忽略。原先由它提供的 `mspbots_user_list_users` 默认租户，现在只能由工具参数 `tenant_id` 指定。

Missing a required header returns `401`:
```json
{
  "error": "Missing credentials",
  "message": "This server requires the X-API-Key header (Agent Platform API key, or a user JWT) and the X-MSP-Host header (Agent Platform host).",
  "required_headers": ["X-API-Key", "X-MSP-Host"]
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
| `mspbots_user_list_tenants` | 分页获取全平台租户列表，支持关键字/启用状态/注册时间区间过滤（需平台级凭证） | page(可选,默认1), page_size(可选,默认20), search(可选), is_active(可选), created_from(可选), created_to(可选) |
| `mspbots_user_list_users` | 分页获取单个租户的用户列表（可分配 owners，返回 id/email/username/displayName/部门/角色等） | page(可选,默认1), page_size(可选,默认20), tenant_id(可选), search(可选), department(可选), is_active(可选), sort_by(可选,默认 createdAt), sort_order(可选,默认 desc) |

`mspbots_user_list_tenants` 的 `search`/`is_active`/`created_from`/`created_to` combine as AND; results are always sorted by `createdAt` descending; an invalid date value in `created_from`/`created_to` is silently ignored (not an error).

`mspbots_user_list_users` 始终只返回**一个租户**的用户：不传 `tenant_id` 时就是凭证自身的租户；只有平台级凭证能用 `tenant_id` 指定别的租户，其他凭证传了也会被下游忽略。`sort_by` 取值 `createdAt` / `email` / `displayName` / `department` / `lastLoginAt`。`page_size` 上限 100，超过会被削到 100。

## 测试示例

```bash
# Health check
curl -s http://localhost:8080/health

# Call a tool via the MCP protocol (streamable HTTP) — requires an
# initialize handshake first per the MCP spec; abbreviated example below
# shows the tool-call request body only:
curl -s -X POST http://localhost:8080/mcp \
  -H "X-API-Key: mbk_xxx" \
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
      "arguments": {"page": 1, "page_size": 20}
    }
  }'
```
