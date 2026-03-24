# Observability

Local-first observability baseline:

- Structured application logs to stdout
- `GET /api/v1/ops/summary` as product-facing summary endpoint
- Temporal UI on `http://localhost:8080`
- Export cleanup script for TTL simulation

Cloud metrics stacks are intentionally deferred.
