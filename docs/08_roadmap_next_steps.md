# 08 · Roadmap: from these two services to the whole ScriptChain

This folder = the **Lab 2 part**: two services, REST, OpenAPI, tests. Everything else in the brief builds on it.
Each step below is a future "starter" of the same kind (spec + TODOs + tests + guide). Ask for the next one when this one is green.

| Step | What | Brief objective | Builds on | Suggested lead |
|---|---|---|---|---|
| **R1 Auth service** | `POST /v1/auth/login` (password check → JWT with `sub`, `role`, `exp`), `GET /v1/users/{id}`; users + hashed passwords; **`HttpUserDirectory`** that replaces `StaticUserDirectory` in the Script service (same port, no change in the API or store) | JWT + four roles; Auth service chosen by the team | `security.py`, `ports.py` | Kelly (security) + Franck |
| **R2 AI Moderation Helper** | `POST/GET /v1/batches/{id}/analyses`, `GET /v1/analyses/{id}`: outliers (> 2 standard deviations), distribution, large adjustments, summary; **read-only** client of the Mark service (`MarkReader` port); template summary first | team addition; must never write or approve marks, never be needed | Mark `GET` endpoints | Franck |
| **R3 GraphQL BFF (Strawberry)** | queries `batch`, `pendingModeration`; mutation `transferCustody`; forwards the JWT; holds **no** business rule; plus a client that runs a query and a mutation with variables, handles errors and makes **one direct REST call** | GraphQL BFF ≥ 2 queries + 1 mutation | both services | Franck |
| **R4 PostgreSQL** | replace the in-memory stores with SQLAlchemy + one database **per service**; `custodian lookup = single read`; the transaction that accepts a transfer also updates `current_custodian_id` | database per service | `store.py` interface (the API does not change) | Franck |
| **R5 Docker** | a `Dockerfile` per service, Docker Compose with the databases, environment variables (`JWT_SECRET`, `SCRIPT_SERVICE_URL`) from a `.env` | three containers + Compose | health routes `/health/live`, `/health/ready` (already there) | Kelly |
| **R6 Kubernetes (kind/Minikube)** | Deployments, Services, ConfigMap, **Secret** for the JWT key, liveness/readiness probes, one end-to-end request through the cluster | deployment objective | R5 | Kelly |

## Things already prepared for you
* **Ports**: `UserDirectory` (Script) and `CustodianClient` (Mark) are the only doors to other services. Replacing a fake by a real
  client never touches the business code.
* **Health probes**: `/health/live` and `/health/ready` exist and are not counted as endpoints (hidden from the OpenAPI file).
* **Configuration by environment**: `JWT_SECRET`, `SCRIPT_SERVICE_URL`, `HOST`, `PORT`.
* **Fail closed**: Script refuses transfers when Auth is down; Mark refuses marks when Script is down.

## Things to decide before R1 (put them to the lecturer, see `00`)
HS256 (shared secret, simple) or RS256 (private key only in Auth, public key everywhere else — better, a bit more work)? Token lifetime
(30 minutes is our assumption)? Where does the first user come from (a seed script)?

## Reminder from the brief about retries and timeouts
One value for service-to-service calls, documented (the default in `HttpCustodianClient` is **2 seconds, 2 retries**: say why in the report);
retry only safe reads; the custody could change between the check and the save — accepted, and the stored `custodian_id_at_entry` snapshot makes it auditable.
