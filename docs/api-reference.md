# API Reference

GroundTruth exposes a versioned REST API (plus a streaming WebSocket). This page covers every endpoint, authentication, rate limits, and error handling.

## Base URL

- **Production:** `https://api.groundtruth.finance/api/v1`
- **Local development:** `http://localhost:8000/api/v1`
- **Interactive docs:** `http://localhost:8000/docs` (FastAPI auto-generated Swagger UI)

## Authentication

The API accepts two authentication mechanisms. Either works on every endpoint.

### Clerk session JWT (primary)

Preferred for web users. Pass the Clerk session token:

```
Authorization: Bearer <clerk-session-jwt>
```

The backend verifies the JWT signature against Clerk's JWKS, extracts the `sub` (Clerk user ID), and looks up or creates the corresponding GroundTruth `User` row.

### API key (fallback, dev/scripts)

Preferred for CLI scripts and development.

```
X-API-Key: <api-key>
```

Keys are hashed on the server; the plaintext key is returned only once on creation.

### Dual auth behaviour

If both headers are present, Clerk takes precedence. If neither is present in **production**, the request returns 401. In **dev mode** (no `VITE_CLERK_PUBLISHABLE_KEY` set), unauthenticated requests may be allowed for certain endpoints.

## Rate limiting

- **Authenticated requests:** 100 requests/minute per user
- **Unauthenticated requests:** 20 requests/minute per IP

Exceeded limits return HTTP 429 with a `Retry-After` header.

## Endpoints

### Analyse

**`POST /api/v1/analyse`** — Run complete financial analysis.

Request:

```json
{
  "profile": { "personal": { "age": 31, ... }, "income": {...}, ... }
}
```

Response:

```json
{
  "profile_name": "Alex Morgan",
  "overall_score": 72.4,
  "grade": "B",
  "report": { "meta": {...}, "scoring": {...}, "cashflow": {...}, ... },
  "run_id": 1234
}
```

### Validate

**`POST /api/v1/validate`** — Validate profile structure without running analysis.

Request: same profile body as `/analyse`.  
Response: list of validation flags with severities.

### Assumptions

**`GET /api/v1/assumptions`** — Return current assumptions (tax bands, rates, weights).  
**`GET /api/v1/assumptions/status`** — Freshness status (when each parameter was last updated).  
**`POST /api/v1/assumptions/diff`** — Compare two assumption sets (dry-run for config changes).

### History

**`GET /api/v1/history?limit=10`** — List recent analysis runs for the authenticated user.

```json
{
  "runs": [
    { "id": 1234, "timestamp": "2026-04-14T...", "profile_name": "Alex", "overall_score": 72.4, "grade": "B", "surplus_monthly": 412, "net_worth": 45200 }
  ],
  "count": 10
}
```

**`GET /api/v1/history/{run_id}`** — Retrieve a specific historical run's full report.

### What-if

**`POST /api/v1/whatif`** — Run analysis with modified parameters.

```json
{
  "profile": {...},
  "modifications": { "income.primary_gross_annual": 65000 }
}
```

### Compare

**`POST /api/v1/compare`** — Side-by-side comparison of two profiles.  
**`POST /api/v1/compare/branch`** — Compare current profile against a modification branch.

### Sensitivity

**`POST /api/v1/sensitivity`** — Parameter sensitivity sweep (how output changes as input varies).

### Scenarios

**`POST /api/v1/scenarios`** — Stress scenario modelling (job loss, rate shock, drawdown).

### Cashflow drift

**`POST /api/v1/cashflow/drift`** — Compare planned vs actual spending from bank data.

### Exports

**`POST /api/v1/export/{run_id}/{format}`** — Export a run in CSV, XLSX, or PDF format.  
Format values: `csv`, `xlsx`, `pdf`.

### Account

**`DELETE /api/v1/account`** — GDPR account erasure. Wipes PII, deletes profiles/bank connections/notifications, soft-deletes the User row, preserves audit log with user_id set to NULL.

**`GET /api/v1/account/export`** — GDPR right to access. Returns a full JSON dump of everything the platform holds about the user — profiles (decrypted), reports, bank connections (tokens redacted), notifications, audit log.

### Health

**`GET /api/v1/health`** — Liveness check.  
**`GET /health`** — Alias for infrastructure health checks.

### WebSocket

**`WS /ws/analyse`** — Streaming analysis. Stages complete incrementally; the client receives partial results as each stage finishes.

Authentication: pass `?token=<jwt>` or `?api_key=<key>` as a query parameter. The connection is verified before `accept()`. Failed auth closes with code 4001.

Message shape:

```json
{ "stage": "cashflow", "status": "done", "payload": {...} }
```

## Error responses

All errors return JSON:

```json
{ "detail": "Human-readable error message" }
```

| Status | Meaning |
|-------:|---------|
| 400 | Invalid request (bad JSON, missing required fields) |
| 401 | Authentication required or failed |
| 403 | Authenticated but not authorised (e.g., admin endpoints) |
| 404 | Resource not found |
| 422 | Validation error (Pydantic) |
| 429 | Rate limit exceeded |
| 500 | Server error (check logs) |

## Examples

### Run analysis from Python

```python
import httpx

API_BASE = "http://localhost:8000/api/v1"
API_KEY = "your-api-key"

profile = {
    "personal": {"age": 31, "retirement_age": 65, "risk_profile": "moderate"},
    "income": {"primary_gross_annual": 58000},
    "expenses": {"housing": {"rent_monthly": 1100}},
    "savings": {"emergency_fund": 4200, "pension_balance": 18000},
}

response = httpx.post(
    f"{API_BASE}/analyse",
    json={"profile": profile},
    headers={"X-API-Key": API_KEY},
)
report = response.json()
print(f"Score: {report['overall_score']} ({report['grade']})")
```

### Stream analysis via WebSocket

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/analyse?token=${clerkToken}`);
ws.onmessage = (event) => {
  const { stage, status, payload } = JSON.parse(event.data);
  console.log(`${stage}: ${status}`, payload);
};
ws.onopen = () => ws.send(JSON.stringify({ profile }));
```

### GDPR export

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://api.groundtruth.finance/api/v1/account/export \
  -o my-data.json
```

## Versioning

The API is versioned at the path level (`/api/v1`). Breaking changes require a new version path. Non-breaking additions (new endpoints, new optional fields) ship within the current version.
