# Spec: Add /health endpoint

## Task description
Add a GET /health endpoint that returns `{"status": "ok", "version": "1.0"}`.

## Acceptance criteria

### P0 — Must work
- [ ] GET /health returns HTTP 200
- [ ] Response body is valid JSON
- [ ] Response JSON contains `status: "ok"` (P0)

### P1 — Should work
- [ ] Endpoint responds within 200ms
- [ ] No authentication required

## Affected files
- `main.py` — add `/health` route
- `.harness/test_health.py` — integration test

## Out of scope
- Health checks for databases or external services
- Detailed system metrics
