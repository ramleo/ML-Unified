Chapter 6Public API &amp; MCP


> Call a stable subset of the tools from your own code, or from an AI client, authenticated with an API key.

## At a glance

| | |
|---|---|
| **Auth** | an API key — `X-API-Key` header (REST) or Bearer token (MCP) |
| **REST base** | `https://wram1708-ml-unified.hf.space/v1` |
| **MCP endpoint** | `https://wram1708-ml-unified.hf.space/mcp/` |
| **Spec** | `https://wram1708-ml-unified.hf.space/v1/openapi.json` |
| **Limits** | per-key monthly request quota + spend budget |

## Getting a key

Keys are issued on request — contact the site owner. Each key carries a tier, a monthly request quota, and a spend budget, and can be revoked at any time. Only a hash of the key is ever stored.

## The REST API

Three endpoints are available today, all `POST` with JSON in and out:

- `POST /v1/tls-headers/check` — TLS & security-header scan. Body: `{ "host": "example.com" }`
- `POST /v1/email-auth/check` — SPF/DKIM/DMARC analysis. Body: `{ "headers": "" }`
- `POST /v1/anomaly-detection/score` — anomaly scores. Body: `{ "baseline": [...], "events": [...] }`

```bash
curl -X POST https://wram1708-ml-unified.hf.space/v1/tls-headers/check \
  -H "X-API-Key: ak_live_…" \
  -H "Content-Type: application/json" \
  -d '{"host":"example.com"}'
```

A missing or invalid key returns `401`; over the quota or rate limit returns `429`. Import `/v1/openapi.json` into Postman or a client generator for the full schema.

## MCP (for AI clients)

The same tools are exposed over the Model Context Protocol (Streamable HTTP), so clients such as Claude Desktop and Cursor can use them. Point the client at the MCP endpoint and pass your key as a Bearer token:

```json
{
  "mcpServers": {
    "airaml": {
      "url": "https://wram1708-ml-unified.hf.space/mcp/",
      "headers": { "Authorization": "Bearer ak_live_…" }
    }
  }
}
```
