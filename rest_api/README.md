# FastAPI management architecture demo

A MySQL-backed, multi-tenant backend illustrating dependency injection, validated contracts, service policies, bearer authentication, authorization, OpenAPI, and request middleware.

## Run with Docker Compose (MySQL + API)

```sh
cp rest_api/.env.example rest_api/.env
# Edit rest_api/.env and choose your passwords and JWT secret.
docker compose --project-directory rest_api up --build -d
```

Compose runs MySQL 8.4 with persistent `mysql_data` storage and an unprivileged application database user. The API waits for an authenticated MySQL health check before initializing tables and optionally seeding demo data. API and database ports are bound to localhost. Start Docker Desktop before running these commands.

```sh
docker compose --project-directory rest_api logs -f api
docker compose --project-directory rest_api stop
```

Stopping containers preserves the named database volume. MySQL initialization variables apply only to a fresh volume; changing `.env` passwords does not change credentials in an existing database.

## Run Python locally with MySQL in Docker

```sh
cp rest_api/.env.example rest_api/.env
# Edit the values, then start just MySQL:
docker compose --project-directory rest_api up -d --wait mysql
python3 -m venv rest_api/.venv
source rest_api/.venv/bin/activate
pip install -e 'rest_api/rest_api_server[dev,ui]'
set -a
source rest_api/.env
set +a
python -m rest_api_server.migrations
uvicorn rest_api_server.main:app --reload
```

`globals.py` builds a `mysql+aiomysql` URL from `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER` and `MYSQL_PASSWORD`. URL construction safely handles special characters in the password. Local processes connect to `127.0.0.1`; the Compose API connects to service hostname `mysql`. You may override the connection with `DATABASE_URL`. Connection health checking and pool recycling are enabled. MySQL enforces foreign keys through InnoDB; no application connection listener or SQLite PRAGMA is used.

Open http://localhost:8000/docs for Swagger UI, `/redoc` for reference documentation, and `/openapi.json` for the schema. Click **Authorize**, enter one of the usernames below and your `DEMO_PASSWORD`, then execute requests. OAuth2's username/password form issues a 30-minute JWT. API clients send `Authorization: Bearer <access_token>`.

```sh
curl -X POST http://localhost:8000/api/v1/users/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'username=platform.admin' \
  --data-urlencode "password=$DEMO_PASSWORD"
# Copy access_token from the response:
export TOKEN='paste-access-token'
curl http://localhost:8000/api/v1/organizations -H "Authorization: Bearer $TOKEN"
```

Registration works without demo seeding. Demo seeding is opt-in and runs only when no users exist. It creates Acme, Engineering, one employee, one group and four accounts, all using the supplied demo password. Restarting preserves records. Changing `DEMO_PASSWORD` does not reset existing accounts.

## Roles and boundaries

| Account / role | Read access | Write access |
| --- | --- | --- |
| `platform.admin` / platform_admin | All resources | All resources |
| `tenant.admin` / tenant_admin | Own tenant | Own tenant name, organizations, lower-privilege users, employees, groups |
| `org.admin` / organization_admin | Own organization and parent tenant | Own organization name, employees and groups within own organization |
| `viewer` / viewer | Assigned organization and parent tenant | None |

A viewer may alternatively be assigned tenant-wide access by omitting organization_id. Roles and scope are loaded from the database for each request; disabling a user immediately invalidates access through existing tokens. Tenant admins cannot create or deactivate peer tenant admins. Cross-scope resource IDs return 404, prohibited operations return 403, invalid inputs return 422, and duplicate usernames/dependent deletions return 409. Tenant and organization deletion require dependents to be removed first. Users are deactivated rather than deleted; self-deactivation is prevented.

## API inventory

All management routes are prefixed `/api/v1` and require a bearer token.

| Route | Methods / purpose |
| --- | --- |
| `/users/register` | POST registration; creates tenant and returns user + token (public) |
| `/users/login` | POST JSON credentials; returns token (public) |
| `/users/token` | POST OAuth2 form credentials; returns token (public) |
| `/users/me` | GET current user |
| `/tenants` | GET paginated list, POST create |
| `/organizations` | GET paginated list, POST create |
| `/users` | GET paginated list, POST create |
| `/employees` | GET paginated list, POST create |
| `/employee-groups` | GET paginated list, POST create |
| Each resource `/{record_id}` | GET, PATCH; DELETE except users |
| `/employee-groups/{record_id}/members` | GET employee members |
| `/employee-groups/{record_id}/members/{employee_id}` | PUT add, DELETE remove (idempotent) |
| `/health` | GET liveness (public) |

List parameters: `offset=0&limit=50`, maximum limit 100. PATCH accepts a name for tenants, organizations and groups; employee PATCH requires name and email with optional job_title; user PATCH accepts `active`. Relationship IDs and roles cannot be changed through PATCH. Membership requires both records to belong to the same organization. Responses never expose password hashes.

## Architecture walkthrough

```text
HTTP request → request ID / timing middleware
             → router + Pydantic input validation
             → injected repository + authenticated current user
             → Domain service (role, scope, relationship checks)
             → domain repositories → SQLAlchemy AsyncSession → relational tables
             → response model (public fields only) → HTTP response
```

`main.py` composes the app and runs schema initialization in its async lifespan.

| Layer | Responsibility |
| --- | --- |
| `routers/` | HTTP paths, payloads, query parameters, status codes and response schemas; calls services only |
| `schemas.py` | Pydantic request and response validation |
| `services/` | Domain-specific business rules, authorization and repository coordination |
| `repositories/` | Async SQLAlchemy queries and persistence, one repository per resource |
| `models/` | Declarative table definitions, column types, primary keys, unique/check constraints and foreign keys |
| `globals.py` | Configuration, async engine, `async_sessionmaker`, and request-scoped `get_session` dependency |
| `migrations.py` | Initial schema creation from `Base.metadata`, also callable as a CLI |
| `dependencies.py` | Wires repositories and services to the request session and resolves authentication |

Each request shares one `AsyncSession` across authentication and domain repositories. The session dependency opens a transaction, commits on success, rolls back on failure, and closes the session. Repositories flush writes but do not commit, allowing services to coordinate multiple writes atomically. List queries apply tenant/organization filters, ordering and pagination in SQL. Password hashing and verification run in a worker thread to avoid blocking the async event loop.

Tables are `tenants`, `organizations`, `users`, `employees`, `employee_groups`, and `group_memberships`. Composite foreign keys enforce organization/tenant consistency and ensure group members belong to the same organization, even for writes outside HTTP services. Restricted parent deletion and cascading membership deletion are enforced by the database.

### Database configuration and initialization

The MySQL database itself is created by the official Docker image. `migrations.py` initializes its tables from SQLAlchemy models:

```sh
python -m rest_api_server.migrations
# Or against the Compose API environment:
docker compose --project-directory rest_api exec api python -m rest_api_server.migrations
```

Startup also invokes this initializer. It creates missing tables and can run repeatedly; it does **not** alter existing columns or provide versioned upgrades. Future schema evolution should use Alembic revisions. Existing SQLite data is not copied to MySQL automatically. The former JSON `records` layout is still detected and refused without modifying its data.

This remains a presentation application. For production, add versioned migrations, an external identity provider, login throttling, audit logging and refresh/revocation policies. Without `JWT_SECRET`, a temporary process secret is generated: tokens stop working after restart; set the same strong secret for every worker. Initialize and seed with one process before starting multiple workers. `/health` is liveness, not a database readiness check.

## Presentation sequence

1. Show `/docs` and the request/response schemas.
2. Log in as platform.admin; list the seeded tenant, organization, employee and group.
3. Create another tenant and organization; show isolation by logging in as tenant.admin.
4. Log in as org.admin; create an employee, create a group, and add membership.
5. Log in as viewer; demonstrate reads succeeding and writes returning 403.
6. Show missing/invalid tokens returning 401, cross-scope IDs returning 404, and bad payloads returning 422.
7. Walk through a router, dependency, service policy, and repository method. Show `X-Request-ID` and generated OpenAPI.

## Verification

```sh
rest_api/.venv/bin/python -m pytest rest_api/tests -q
```

Fast tests use isolated temporary SQLite databases as test doubles (SQLite driver and constraint setup are test-only). They do not prove MySQL runtime compatibility. Tests and cover authentication, roles, tenant/organization isolation, CRUD, memberships, validation, account deactivation, expiry, conflicts, schema initialization, rollback, database foreign keys and preservation of legacy databases.

The API image runs as a non-root user; persistent storage belongs to the MySQL service. Configuration examples are in `.env.example`. Compose reads `.env` automatically; local Python processes need those variables exported.

Authentication implementation follows the [official FastAPI JWT tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/).

Async persistence follows the [SQLAlchemy asyncio documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).


## User onboarding and bearer headers

`POST /api/v1/users/register` accepts `username`, `password` (at least 12 characters and at most 72 UTF-8 bytes), and optional `tenant_name` and `role`. A new account receives its own tenant. The role defaults to `tenant_admin`; `organization_admin` and `viewer` are also supported for demonstrations. Organization-admin registration creates a default organization and assigns the account to it. Viewer registration provides tenant-wide read access. Tenant and user creation share a transaction. Duplicate usernames return 409 and do not create an extra tenant. Password whitespace is preserved.

Public registration accepts only the three tenant-scoped demo roles above; `platform_admin` and existing tenant/organization IDs are rejected. To give someone access to an existing tenant, an administrator creates their login account through protected `POST /api/v1/users` with the intended role, tenant_id, and optional organization_id. Login does not register accounts or create tenants. `POST /api/v1/users/login` accepts JSON credentials; `/users/token` accepts the OAuth2 form for Swagger. Both return a short-lived access token. `/auth/token` and `/auth/me` remain compatibility routes.

Every protected endpoint requires `Authorization: Bearer <access_token>`. Tokens in URL parameters or JSON bodies are not accepted. Registration, login, token issuance, health and API documentation are public because they bootstrap access or support diagnostics. `GET /api/v1/users/me` shows the authenticated account and its tenant.

Model classes are now visible in `rest_api_server/models/`:

```text
models/
  base.py              Base, Record, OrganizationScoped
  tenant.py            Tenant
  organization.py      Organization
  user.py              User
  employee.py          Employee
  employee_group.py    EmployeeGroup
  group_membership.py  GroupMembership
  __init__.py          exports and migration metadata registration
```

Routers use domain-specific operation names (`register_user`, `login_user`, `list_employees`, etc.) and singular service dependencies (`user_service`, `employee_group_service`, etc.).

## Streamlit API client

After installing the `ui` extra, start the API in one terminal and the client in another:

```sh
source rest_api/.venv/bin/activate
# API should already be running through Compose or the local setup above.
# In another terminal with the same environment activated:
streamlit run rest_api/streamlit_app.py
```

Open http://localhost:8501. Register a user, or log in using a seeded account. The client stores the access token only in the current Streamlit session and sends it as a bearer header for every protected API call. Logout clears local credentials; it does not revoke an already-issued token. Changing the API URL clears the session so its token is not reused with the new server.

The sidebar provides a **Tenant → Organization** selector and individual **Overview, Tenants, Organizations, Users, Employees, Employee groups** pages. A breadcrumb shows your current path, such as `Workspace › Acme › Engineering › Employees`. Changing tenants clears the organization selection. Select **All tenants** or **All organizations** to broaden the view within your account's backend permissions.

**Overview** shows scoped counts and expandable tenant/organization cards. Each individual table supports search and CSV download and displays human-readable tenant and organization names alongside record IDs. The client fetches every paginated API page before applying its hierarchy filters, so counts and tables include records beyond the first server page.

Create forms automatically use the selected tenant or organization. Choose a row by name to edit or delete it; deletion requires confirmation. The user table supports account activation/deactivation. The employee-group page shows a separate membership table and lets you add employees from the same organization or remove existing members. Write controls are hidden for read-only roles; the backend continues to enforce all role and scope policies.

The sidebar includes account details and the last API request's method, path, status and request ID. Bearer tokens are redacted. Logout clears local credentials but does not revoke a token already issued by the backend.

Set `API_BASE_URL` to change the default API address. This client communicates only through HTTP and does not access database sessions directly. Its session handling follows the [Streamlit session-state documentation](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state).


## Action-based authorization

The single action policy is `services/authorization.py`. Services call `authorize("create")`, `authorize("update")`, `authorize("delete")`, or `authorize("manage_members")` before writes. Reads also check the `read` grant. Resource lookups then validate tenant/organization visibility; list queries apply the same scope filters in SQL. A permitted action never bypasses scope.

| Resource / action | Platform admin | Tenant admin | Organization admin | Viewer |
| --- | --- | --- | --- | --- |
| Read resources | All tenants | Own tenant | Own organization and parent tenant | Assigned scope |
| Create/delete tenants | Yes | No | No | No |
| Update tenant name | Any | Own tenant | No | No |
| Create/delete organizations | Any | Own tenant | No | No |
| Update organization name | Any | Own tenant | Own organization | No |
| Create users / change active status | Yes | Lower-privilege users in own tenant | No | No |
| Create/update/delete employees | Any | Own tenant | Own organization | No |
| Create/update/delete groups | Any | Own tenant | Own organization | No |
| Add/remove group members | Any | Own tenant | Own organization | No |

Users have one assigned tenant and optional organization. Tenant administrators cannot create or modify peer tenant administrators or platform administrators. User roles and relationship IDs cannot be changed by PATCH; it only accepts active status. Self-deactivation is blocked. Parent deletion is blocked by database relationships, and group membership requires employees from the same organization.

`GET /api/v1/users/me/permissions` returns the authenticated account's current role, scope, resource actions and additional restrictions. It requires a bearer header. Streamlit's **Permissions** page displays this response, and create/edit/delete/membership controls use these API-provided grants. Backend checks remain authoritative even when someone calls an endpoint directly. Missing/invalid authentication returns 401, denied actions return 403, and out-of-scope IDs return 404.

For a presentation, log in successively as `platform.admin`, `tenant.admin`, `org.admin`, and `viewer`, open Permissions, then attempt the same update from each account. Organization admins can update their own organization's name while viewers cannot. Creating an employee does not create a login or automatically grant tenant access; create the person's user account separately through Users.

The removed onboarding feature's models and endpoints are no longer used. Existing database tables from an earlier version are left untouched to preserve stored data; the application does not load their grants. Accounts directly created in a tenant by that version retain their assigned role and scope until an administrator deactivates them.

New passwords use bcrypt with a random salt. Existing Argon2 hashes remain verifiable for compatibility. Password hashing and verification remain in worker threads. The 72-byte password limit is validated before new accounts are created; multibyte characters count by UTF-8 size.

## Guided Streamlit authentication and authorization presentation

Open **Auth demo** in the sidebar after signing in. It calls real API routes and shows expected versus actual results. No backend permission bypass is added.

1. **Authentication:** run the same `/users/me` request without a bearer token (401), with an invalid token (401), and with the session's login token (200). Explain that authentication identifies the account; inspect its role, tenant and organization.
2. **Role grants:** show the current resource/action matrix from `/users/me/permissions`. A tenant administrator has tenant-wide management rights; an organization administrator manages its organization; a viewer reads only its assigned scope.
3. **Tenant and organization actions:** select a target and run GET and PATCH. The default PATCH keeps the current name, while exercising the real update policy. For `tenant.admin`, tenant and organization updates return 200. For `org.admin`, tenant update returns 403 while its own organization update returns 200. For `viewer`, both updates return 403. Optional create checks produce real demo records when permitted; remove them using the dedicated cleanup buttons before logout.
4. **Scope isolation:** obtain a real record ID from a second tenant or a sibling organization using `platform.admin`. Copy the ID, switch to the scoped demo account, and run the GET scope check. A record outside that account's scope returns 404; platform admin can access it with 200. A random/nonexistent ID does not prove isolation.
5. **Evidence:** review the request path, expected status, actual status, pass/fail and request ID. Download the current session's JSON evidence for the presentation. Expected authorization failures count as passing checks. History is cleared on logout; download it before changing accounts.

Seeded-account presentation order: `platform.admin` → `tenant.admin` → `org.admin` → `viewer`, each using your configured `DEMO_PASSWORD`. To show scope boundaries, first create a second tenant and organization using the workspace tables and copy their IDs. No credentials are displayed in the demo evidence. Real create/update/delete operations require an explicit button click; there are no automatic destructive checks.

The Streamlit registration form includes **Role (optional)**. Leave **Default — Tenant administrator** selected to use the default. After login, Overview shows the account role and access scope with an expandable list of allowed actions. Use **Permissions** or **Auth demo** to compare capabilities. A viewer cannot create additional records; populate its tenant through a platform administrator when needed for a presentation.

## Streaming tenant summaries with Azure AI Foundry

Configure a deployed model that supports the OpenAI-compatible **Chat Completions streaming** API:

```dotenv
AZURE_FOUNDRY_ENDPOINT=https://YOUR-RESOURCE.services.ai.azure.com/openai/v1/
AZURE_FOUNDRY_API_KEY=your-resource-api-key
AZURE_FOUNDRY_DEPLOYMENT=your-chat-model-deployment-name
```

The endpoint may also be `https://YOUR-RESOURCE.openai.azure.com` (the application adds `/openai/v1`). Use the model deployment name, not a project ID, project endpoint, or model catalog name. Settings use resource API-key authentication. Compose forwards the three variables from `.env`; rebuild/restart the API after configuring them. For local execution, export them in the API process environment. Without configuration, summaries return HTTP 503 while the rest of the application remains available.

```sh
docker compose --project-directory rest_api up --build -d
curl -N -X POST \
  http://localhost:8000/api/v1/tenants/TENANT_ID/summary/stream \
  -H "Authorization: Bearer $TOKEN"
```

In Streamlit, choose a tenant in the sidebar, open **Tenant assistant**, and click **Summarize current tenant**. The source snapshot is shown separately from the model-generated Markdown. A completed summary can be downloaded. The backend streams Server-Sent Events:

| Event | Data |
| --- | --- |
| `snapshot` | Exact authorized counts, visibility, capped organization/group details and job-title distribution |
| `delta` | Incremental model text in `{ "text": "..." }` |
| `done` | Successful completion |
| `error` | Sanitized generation failure; previously received text is partial |

The route uses the same bearer authentication and scope rules as normal reads. An organization administrator or organization-scoped viewer sees only its organization, including scoped account counts. Full-tenant totals are never sent for an organization-scoped request. Unrelated tenant IDs return 404 before the provider is contacted. No password hashes, usernames, employee names or emails are included in the Azure prompt. Organization/group names and job titles are included; these and aggregate business counts leave the API for the configured Azure deployment.

The report repository performs aggregate queries; detail lists are capped at 50 organizations, 50 groups, and 20 job titles. Counts cover all authorized rows. The prompt explicitly labels these limits and treats database values as data. Generated observations should be verified against the source snapshot. No SQL or tools are exposed to the model.

HTTP 401/404/503 failures occur before streaming starts. Provider failures after streaming starts are reported as `error` events rather than changing the HTTP 200 status; clients must wait for `done` before treating a summary as complete. API-key/provider error details are not exposed. Clients and provider connections are closed on cancellation. Database sessions finish before the stream begins, avoiding an occupied transaction while model text arrives.

Implementation: `repositories/tenant_reports.py` → `services/tenant_summaries.py` → tenant streaming router. `summary_dashboard.py` parses SSE for Streamlit. Tests use a simulated provider and verify scoped aggregates, authentication, redaction and partial-failure handling; a live Azure deployment requires your resource credentials.

Connection format follows [Microsoft Foundry's documented endpoints](https://learn.microsoft.com/en-us/azure/ai-foundry/model-inference/concepts/endpoints?tabs=python).


## Conversational tenant assistant

**Tenant assistant** supports follow-up questions using `POST /api/v1/tenants/{id}/chat/stream`:

```json
{"question":"What can my role do in this tenant?","history":[{"role":"user","content":"Summarize my tenant"},{"role":"assistant","content":"Your assigned organization is visible."}]}
```

The question is limited to 2,000 characters; history accepts up to 10 user/assistant messages of 4,000 characters each. Every turn rechecks access and builds a fresh database snapshot with the account's effective permission grants. History cannot supply system messages or grant access to another tenant. Chat sends both the user's question and recent messages to Azure in addition to scoped aggregate data; do not put credentials in chat messages.

Streamlit keeps separate history by account, tenant, role and organization in the current session. Clear conversation resets that thread, and logout clears the session. The quick summary button starts the same streaming chat flow. The earlier summary endpoint remains available for one-shot clients.

Workspace shortcuts open the corresponding tenant-scoped table and management forms. The assistant explains actions and flow but cannot execute mutations or tools; creating, editing and deleting records still requires the normal controls and backend authorization. Incomplete answers are not stored as assistant history. Source data and effective permissions can be expanded for each answer.

## RabbitMQ worker service: exchange-rate jobs

The presentation now covers three distinct request patterns:

| Pattern | Example | Completion |
| --- | --- | --- |
| REST | Tenant/organization CRUD | Result returned in the HTTP response |
| SSE | Tenant assistant | Text events streamed through an open HTTP connection |
| Worker + RabbitMQ | Exchange-rate retrieval | HTTP 202 returns a job ID; a separate process saves the eventual result |

### Run the services

Set these in `rest_api/.env` (new settings are listed in `.env.example`):

```dotenv
RABBITMQ_USER=management_worker
RABBITMQ_PASSWORD=choose-a-local-password
EXCHANGE_RATES_API_KEY=your-exchangerate-api-key
```

```sh
docker compose --project-directory rest_api up --build -d
docker compose --project-directory rest_api ps
docker compose --project-directory rest_api logs -f worker
```

Compose starts MySQL, RabbitMQ, the API and the worker. The API initializes the new `exchange_rate_jobs` table. The API starts an asynchronous outbox publisher in its lifespan. The worker waits for API/MySQL/RabbitMQ health checks, then starts its separate queue consumer. No new columns are required on existing tables. RabbitMQ data persists in `rabbitmq_data`; MySQL job data persists in `mysql_data`. Default broker ports are localhost 5672 (AMQP) and localhost 15672 (management dashboard). Log into http://localhost:15672 using the configured RabbitMQ user/password. RabbitMQ initialization credentials only take effect on a fresh broker volume.

For local Python development, start MySQL/RabbitMQ with Compose, export `.env`, run migrations/API as usual, and in another terminal run:

```sh
python -m rest_api_server.worker
```

The API needs the database to accept jobs and broker credentials to dispatch them. Provider credentials are used only by the worker. Jobs remain durable in the database if broker dispatch is unavailable. An empty provider key produces a visible failed job instead of breaking the API or other workers.

### Worker API and authorization

| Endpoint | Behavior |
| --- | --- |
| `POST /api/v1/tenants/{tenant_id}/exchange-rate-jobs` | Accepts `{"base_currency":"USD","organization_id":null}`; returns 202 and a Location header |
| `GET /api/v1/tenants/{tenant_id}/exchange-rate-jobs` | Paginated job history, newest first |
| `GET /api/v1/tenants/{tenant_id}/exchange-rate-jobs/{job_id}` | Status, attempts, timing, sanitized error and saved rates |

Platform, tenant and organization admins can submit jobs within their scope. Viewers can read accessible jobs. Organization-scoped users only see jobs assigned to their organization; a tenant-wide job is hidden from them. The tenant ID, optional organization, and job ID are all checked server-side. Currency defaults to USD and must be three uppercase letters. Unsupported provider currencies fail as job errors rather than HTTP request failures.

### Processing and failure flow

```text
Authenticated POST
  → validate role + tenant/organization
  → commit queued job in MySQL (also acts as durable outbox)
  → return HTTP 202 + job ID

API lifespan publisher
  → poll committed, unpublished jobs
  → publish persistent job-ID messages to durable RabbitMQ queue

Separate worker container
  → consume with prefetch=1 and claim a database lease
  → GET https://v6.exchangerate-api.com/v6/{api_key}/latest/{base_currency}
  → store normalized rates or sanitized failure in MySQL
  → acknowledge the queue message

Dashboard GET → queued / running / succeeded / failed + rates table
```

The external request timeout is **10 seconds**. Timeouts, network failures, HTTP 429 and server errors retry up to three attempts through the durable outbox; invalid credentials/currency/data fail without repeated requests. Retry dispatch is polled every two seconds (no exponential backoff). The API key is never put into queue messages, API results or worker request logs.

Publisher confirms and persistent messages provide durable, at-least-once delivery. A crash between publish and outbox marking may produce duplicate messages. Conditional database claims skip completed jobs, an active lease defers duplicate delivery, and attempt fencing prevents stale workers from overwriting newer results. A crashed in-flight attempt becomes claimable after its 60-second lease expires. Fetching exchange rates may happen again after a crash; this is not an exactly-once external-call guarantee. Broker/database infrastructure failures requeue messages; permanent provider failures are retained as failed jobs in MySQL. Malformed messages are rejected rather than endlessly requeued.

### Streamlit presentation flow

Open **Worker jobs**, choose the tenant, and submit a USD job. Show the 202 response in **Last API request**, then refresh to see attempts, timestamps and the returned currency table. Very fast jobs may finish before the next refresh.

To show queueing independently from processing:

```sh
docker compose --project-directory rest_api stop worker
# Submit a job in Streamlit: the API publishes it and RabbitMQ shows a ready message.
docker compose --project-directory rest_api start worker
# Refresh Streamlit; inspect the RabbitMQ queue and worker logs.
```

The dashboard displays the most recent 50 accessible jobs. Viewers have no submission control. Running without an ExchangeRate-API key demonstrates the failure path; set a valid key and recreate the worker to demonstrate successful real rates. Tests exercise provider parsing/timeouts, scoped job APIs, retries, duplicate processing, lease recovery and the publish/retry race using local test databases and simulated provider responses.

Provider contract: [ExchangeRate-API standard requests](https://www.exchangerate-api.com/docs/standard-requests). Queue implementation follows [aio-pika work queues](https://docs.aio-pika.com/rabbitmq-tutorial/2-work-queues.html).


## Presenter guide aligned to the PowerPoint

A detailed guide with notes for all 16 supplied slides, application startup, ORM/session handling, REST and bearer security, SSE/Foundry chat, RabbitMQ workers, a rehearsal runbook, terminology and slide corrections is available as [editable Word](docs/FastAPI_Architecture_Presenter_Guide.docx), [PDF](docs/FastAPI_Architecture_Presenter_Guide.pdf), and [searchable HTML](docs/FastAPI_Architecture_Presenter_Guide.html). Scheduling, latest-rate upserts and membership notifications are explicitly separated from implemented on-demand jobs.
