# Expertise Insight

Expertise Insight is an undergraduate Final Year Project (FYP) for building and
searching academic staff expertise profiles, matching staff to course or grant
specifications, and comparing institutional expertise with external academic
signals.

The current product is a working full-stack prototype implemented as a modular
monolith. The immediate objective is to finish and validate the FYP use cases.
The design should remain capable of evolving into a faculty deployment, but
production infrastructure must be added only when a real requirement or
measurement justifies it.

> **Status date:** 2026-10-07
>
> **Current focus:** complete the benchmarking methodology and remaining
> critical validation before performance tuning or publication-oriented model
> optimization.

## Start Here in a New Development Session

Read these files before changing a module:

1. `AGENTS.md` (local and intentionally gitignored) - engineering rules, KISS
   constraints, testing expectations, and the definition of done when this file
   is available in the working environment.
2. This README - current implementation status, decisions, known gaps, and
   ordered TODO tasks.
3. `use_cases.md` - UC-1 through UC-18 product requirements.
4. The route, schema, service, model, migration, frontend caller, and existing
   tests related to the selected task.

Do not infer an interface from this README alone. The runtime code and database
migrations are the implementation source of truth. If the code, use cases, and
FYP report disagree, identify the difference before changing behavior.

For a one-task-per-conversation workflow, choose one unchecked task from
[Development Roadmap](#development-roadmap-one-task-per-session), complete its
acceptance criteria, update this README, and record any required report change.

## Product Scope and Roles

The system has two account identities:

- **Academic Staff** manage publications, expertise tags, academic background,
  synchronization, and portfolio export.
- **Faculty Administrators** receive one or more portfolios that control access:
  Faculty Manager, Head of Department, Deputy Dean (Research), or Deputy Dean
  (Undergraduate/Postgraduate).

An administrator may also provide an ORCID and operate as a dual-role user.
Frontend navigation is generated from role and portfolio data, while backend
dependencies enforce authorization on protected endpoints.

The main user flows are:

1. Register -> administrator approval -> login.
2. First successful login -> durable ORCID/OpenAlex synchronization job.
3. Review publications, supplement missing abstracts, and refine expertise.
4. Maintain academic background and export a PDF/DOCX snapshot.
5. Search staff and match course/grant specifications to ranked staff.
6. Compare internal expertise with global or peer data and generate gap reports.

## Current Architecture

```text
React/Vite SPA
    |
    | JSON or multipart requests; JWT bearer token
    v
FastAPI /api/v1
    |-- API routes: validation, authorization, HTTP contracts
    |-- Services: business workflows, NLP, mapping, export, external APIs
    |-- Async SQLAlchemy ---------------------------------> PostgreSQL
    |
    | create SyncJob and publish job ID
    v
Redis broker --> Celery worker --> ORCID/OpenAlex + NLP --> PostgreSQL
                     ^
Celery Beat ---------| quarterly schedule

Frontend SyncStatusGuard polls persisted SyncJob state and blocks conflicting
user actions until the job reaches succeeded, no_new_data, or failed.
```

This is intentionally a **modular monolith**, not a microservice system. Routes,
services, tasks, and persistence have useful boundaries, but SQLAlchemy may be
used directly in services. A repository layer, message bus, CQRS, or dependency
injection framework is not currently justified.

### Technology Stack

| Layer | Current technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand, React Router |
| API | Python 3.11+, FastAPI, Pydantic v2 |
| Persistence | PostgreSQL, async SQLAlchemy 2, asyncpg, Alembic |
| Background work | Redis 7 broker, Celery worker, Celery Beat |
| Embeddings/NLP | sentence-transformers, SciBERT, scikit-learn, UMAP |
| Optional LLM | LangChain with a provider-neutral OpenAI-compatible client |
| Document parsing | `pypdf` for PDF and `python-docx` for DOCX |
| External data | ORCID and OpenAlex; existing IEEE code is pending replacement |
| Export | ReportLab PDF and python-docx DOCX generation |

## Functional Progress

Status meanings:

- **Implemented**: the backend and required UI path exist in the current code.
  This does not imply comprehensive end-to-end test coverage.
- **Partial**: a usable prototype path exists, but a requirement, methodology,
  security control, or validation step is still incomplete.
- **Planned**: the intended solution is documented but not implemented.

| Use case | Status | Current implementation and remaining gap |
|---|---|---|
| UC-1 Register account | Implemented | Staff/admin registration, ORCID and portfolio validation, pending account creation, and duplicate-email handling exist. |
| UC-2 Authorize registration | Implemented | Faculty Manager can list, approve, or reject pending registrations; outcome email is sent/logged. Needs broader integration coverage. |
| UC-3 Login | Implemented | JWT login, pending-account rejection, role-aware redirect data, dual-role data, and first-login sync enqueueing exist. First-login behavior has focused tests. |
| UC-4 Reset/change password | Implemented | Forgot/reset/change flows and email delivery exist. Only SHA-256 digests of high-entropy reset tokens are stored; new requests revoke earlier links, and invalid/expired links have focused tests. |
| UC-5 Notification email | Implemented | SMTP-backed registration and password-reset notifications plus notification logging exist. Delivery depends on valid SMTP configuration. |
| UC-6 Role-based dashboard | Implemented | Portfolio-derived sidebars, staff/admin view selection, dual-role toggle, and backend portfolio checks exist. |
| UC-7 Consult staff profiles | Partial | Directory, category search, department filter, grouping, and detail views exist. The API still loads the full result set and performs much of the search in Python; pagination and access scoping are pending. |
| UC-8 Generate expertise profiles | Implemented | ORCID identity resolution, OpenAlex publication harvesting, abstract processing, SciBERT extraction, LLM normalization, tag embedding, and persistence exist. Quality still depends on evaluation and tuning. |
| UC-9 Supplement abstract | Implemented | Staff can enter an abstract or upload validated, size-limited PDF/DOCX text; embeddings/tags are refreshed. |
| UC-10 Academic background | Implemented | CRUD plus CSV template download and bulk import are available for education, appointment, award, and service records. |
| UC-11 Refine expertise tags | Implemented | Staff can validate/remove generated tags and add custom tags with embeddings. Mutations are blocked while that user's sync is active. |
| UC-12 Trigger expertise sync | Implemented | First-login, manual, administrator, and quarterly triggers share the Redis/Celery queue and persisted `SyncJob` model. Duplicate active jobs are constrained per user. |
| UC-13 Input course/grant specs | Implemented | Text and validated, size-limited PDF/DOCX ingestion, embedding, listing, and deletion exist. |
| UC-14 Match expertise | Partial | Cosine plus one-hop spreading activation, ranked results, saved reports, optional LLM explanation, and PDF export exist. The scoring design still needs evaluation against a defensible labelled set. |
| UC-15 Global benchmarking | Partial / redesign required | Current code queries eight fixed IEEE topics, embeds returned titles/abstracts, and measures distance to internal clusters. This is not a validated global trend detector and IEEE licensing/API access is unsuitable as the default. Planned replacement: independent OpenAlex topic/time-series data with deterministic trend and gap scores. |
| UC-16 Peer benchmarking | Partial | Validated, size-limited PDF/DOCX curriculum upload, bounded document chunking, semantic comparison, persisted results, UMAP/PCA visualization, and UI exist. Scoring validity and representative peer test data are pending. |
| UC-17 Gap analysis | Partial | The UI can run global/peer analysis and combine the latest runs into a narrative and ranked white spaces. Its validity depends on completing UC-15/16 methodology. |
| UC-18 Export customized CV | Implemented prototype | Staff can select or default profile items and export a one-page PDF or DOCX expertise snapshot. This is a snapshot, not a full general-purpose CV builder. |

## Synchronization and Concurrency: Implemented Decisions

The old synchronous-request design is no longer current.

- FastAPI creates and commits a `SyncJob`, then publishes only its ID to Celery.
- Redis is the durable broker; PostgreSQL stores user-visible job state.
- A partial unique database index allows only one `QUEUED` or `RUNNING` job per
  user, protecting the invariant across concurrent API requests.
- Celery uses late acknowledgement, worker-loss rejection, prefetch `1`, finite
  broker connection behavior, and a one-hour visibility timeout.
- Progress stages include profile resolution, publication fetching, abstract
  processing, keyword extraction, tag normalization, persistence, and finalizing.
- The frontend polls `/sync/jobs/{id}` approximately every three seconds and
  discovers administrator/quarterly jobs through `/sync/status`.
- The modal intentionally blocks that logged-in user from other operations
  during synchronization and presents explicit success, no-change, or failure
  feedback. Closing the browser does not cancel a durable job.
- Quarterly synchronization runs at 02:00 `Asia/Singapore` on January 1, April
  1, July 1, and October 1. Users do not need to be forced to log out.
- Polling is the current KISS choice. Do not add SSE or WebSocket alongside it
  unless measurement shows polling is a problem or real-time requirements grow.
- Windows local development uses Celery `--pool=solo`; production workers should
  run on Linux/Docker with the normal process pool.

## Other Recorded Decisions

### Engineering

- Complete FYP functionality and clear user flows before optional production
  infrastructure.
- Keep the modular monolith and refactor only around active features.
- Do not introduce a repository layer or generic framework merely to make the
  architecture look more sophisticated.
- Add only focused tests for critical behavior; 100% coverage is not a goal.
- Fix query design and pagination before adding cache.
- Run a small reproducible load test before tuning database pool sizes, worker
  counts, Redis caching, or vector indexes.
- Redis may later be reused for targeted caching/rate limiting, but cache must
  have an explicit TTL, invalidation rule, and database fallback.

### External APIs and NLP

- `LLM_API_KEY`, `LLM_API_BASE`, and `LLM_MODEL` are provider-neutral names.
  The application may use DeepSeek or another OpenAI-compatible provider without
  coupling configuration to `OPENAI_API_KEY`.
- DeepSeek is not accepted merely because it currently works. Provider choice
  must be supported by a controlled comparison on the same data, prompts, and
  metrics.
- PDFs and DOCX files are parsed directly with `pypdf` and `python-docx`.
  LangChain is used for the LLM integration, not as the document parser.
- The LLM may normalize tags and explain deterministic results. It must not
  generate both the external benchmark and the conclusion used to validate it.
- OpenAlex is the planned primary external source for global topic IDs, annual
  publication counts, and citation-derived signals. Semantic Scholar may later
  corroborate a limited sample. IEEE can be an optional licensed validation
  source only after official usage terms are confirmed.
- A real claim of "emerging global trends" requires a defined recent window,
  baseline window, growth/acceleration calculation, and source provenance. A
  semantic distance plot alone is only thematic coverage comparison.

### Internal Benchmark Representation

Current UC-15/16 code clusters individual rows from the global `ExpertiseTag`
table. The report previously described faculty expertise centroids, which is not
the same calculation. The planned correction is to build a weighted vector for
each staff member from that person's validated/confident tags, then cluster the
staff vectors. This prevents a widely reused vocabulary tag from being treated
as if it were an independent member of staff and better matches the institutional
capacity interpretation.

## Prototype Security Baseline

SEC-01 is implemented with controls proportionate to the current FYP pilot:

- Password-reset links contain a 32-byte random bearer token, while PostgreSQL
  stores only its SHA-256 digest. Issuing a new link revokes older links for the
  account. The SEC-01 migration expires all pre-existing plaintext reset tokens.
- PDF and DOCX uploads default to a 10 MiB per-file limit; CSV uploads default
  to 2 MiB. Limits are configured through `MAX_DOCUMENT_UPLOAD_BYTES` and
  `MAX_CSV_UPLOAD_BYTES`. Validation checks extensions, declared media types,
  and PDF/DOCX/CSV content before parsing.
- Access JWTs default to 480 minutes (eight hours), reduced from seven days. This
  supports a normal pilot workday without adding a refresh-token subsystem,
  while materially reducing the exposure window of a stolen bearer token.
- Real `.env` files remain ignored. However, `backend/.env` was present in Git
  history before it was untracked. The exposed `JWT_SECRET` was rotated after
  the incident and requires no further action solely because of that commit;
  the rotation invalidated tokens signed with the old secret. All other
  sensitive credentials contained in that historical environment file,
  including the SMTP app password, have also been rotated. Removing the current
  file does not remove old values from history, so coordinate a history rewrite
  separately if the repository has not already been distributed.

This is a prototype baseline, not a claim of compliance, complete auditability,
encryption at rest, or production readiness.

## Known Technical and Documentation Gaps

- Profile endpoints are split by the existing UC-7, UC-9, UC-10, and UC-11
  concerns while retaining the `/api/v1/profile` contract. Mapping PDF rendering
  is isolated in a narrow service helper, leaving the route responsible for the
  HTTP response.
- Staff directory filtering, faculty-wide authorization scope, aggregate counts,
  stable ordering, and pagination are implemented in PostgreSQL queries. The
  current case-insensitive substring search intentionally has no speculative
  text index; PERF-02 should measure it before considering PostgreSQL trigram
  search.
- Database pool sizing uses SQLAlchemy defaults. This is acceptable until a load
  test establishes an appropriate deployment-specific value.
- There is no general response cache and no API rate limiter yet.
- Auditability is limited to selected records such as sync jobs and notification
  logs; there is no comprehensive administrator audit trail.
- The key automated tests cover first-login sync, queue publication failure, and
  peer-document chunk completeness. Authentication, mapping, authorization,
  database constraints, and benchmarking formulas need focused coverage.
- `docs/SCALABILITY_STRATEGY.md` is stale: it still describes synchronous sync,
  `BackgroundTasks`, ARQ alternatives, speculative cache/pool values, and an
  inaccurate model of async database waiting. Treat those sections as historical
  proposals until task DOC-01 updates the file.
- The FYP report file is not currently present in this worktree. Report changes
  therefore cannot be applied automatically; every material task must record
  the report sections that need updating when the file is restored.

## Development Roadmap (One Task per Session)

The IDs below are intended to be used as session scopes. Do not combine several
tasks merely because they are listed together.

### P0 - Finish the FYP Core

#### [ ] BENCH-01 - Correct the Internal Expertise Representation

**Goal:** make the benchmark compare external concepts with actual institutional
capacity rather than clustering standalone vocabulary rows.

**Acceptance criteria:**

- Define and document the per-staff weighted profile-vector formula.
- Use validated/confident staff-tag links and handle users without embeddings.
- Cluster staff vectors with deterministic parameters and meaningful labels.
- Add focused tests for weighting, empty data, and stable input/vector alignment.
- Update UC-15/16 descriptions and list the affected FYP methodology section.

#### [ ] BENCH-02 - Replace the IEEE Fixed-Query Global Benchmark

**Depends on:** BENCH-01.

**Goal:** implement a reproducible OpenAlex-based global research trend source.

**Acceptance criteria:**

- Verify and use the current official OpenAlex API contract; do not guess fields.
- Remove the eight fixed `GLOBAL_QUERIES` from the active pipeline.
- Define recent and baseline publication windows and retrieve independent topic
  IDs/names and counts from OpenAlex.
- Compute documented deterministic popularity, growth/trend, semantic distance,
  and combined gap scores; keep the LLM out of numeric scoring.
- Persist source IDs, retrieval date, time windows, raw counts, formula inputs,
  and enough provenance to reproduce a run.
- Update backend schemas, migration, frontend labels/visuals, `.env.example`,
  tests, README, and the identified report sections together.
- The module works without an IEEE key. IEEE code/config is removed or clearly
  isolated as an optional future licensed source.

#### [ ] BENCH-03 - Validate Peer and Combined Gap Analysis

**Depends on:** BENCH-01 and BENCH-02.

**Goal:** make UC-16/17 results consistent, explainable, and demonstrable.

**Acceptance criteria:**

- Use a small documented set of representative peer curriculum files.
- Define how peer-chunk distances become ranked white spaces.
- Show the source, nearest internal cluster, component scores, and final score in
  the UI rather than relying only on an LLM narrative.
- Combined results retain global/peer provenance and handle either source being
  absent with a clear message.
- UMAP failure still yields the existing PCA/table fallback.
- Add focused formula and API tests and document limitations honestly.

#### [ ] MAP-01 - Evaluate Course/Grant Matching

**Goal:** demonstrate that UC-14 ranking is meaningful rather than only runnable.

**Acceptance criteria:**

- Create a small labelled set of specifications and relevant staff/expertise.
- Select ranking metrics appropriate to the task (for example Precision@K,
  Recall@K, MRR, or nDCG) and justify them.
- Evaluate the existing 0.7 cosine / 0.3 spreading weights and threshold without
  tuning on the final test examples.
- Record baseline results and only change weights when evidence supports it.
- Add deterministic scoring regression tests and update the FYP evaluation text.

#### [ ] QA-01 - Critical End-to-End Acceptance Pass

**Goal:** verify the implemented UC-1 to UC-18 prototype as a user, not just by
static inspection.

**Acceptance criteria:**

- Execute and record a concise manual acceptance checklist for registration,
  approval, login, first/manual sync, profile maintenance, search, mapping,
  benchmarking, gap analysis, and export.
- Add automated tests only for critical failures found during this pass.
- Confirm database migrations from a clean database and frontend production
  build.
- Update every use-case status in this README from observed results.

### P1 - Essential Engineering Before a Faculty Pilot

#### [x] PERF-01 - Move Staff Search to SQL and Add Pagination

**Goal:** fix the clearest existing query/scalability issue without adding cache.

**Acceptance criteria:**

- Confirm the faculty/department visibility rule with the user before coding.
- Apply authorized scope, search category filters, count, ordering, limit, and
  offset in SQL.
- Return pagination metadata and update all frontend callers and types.
- Add only indexes supported by the final query shape.
- Test authorization scope, category filtering, and page boundaries.

**Completed 2026-10-07:** the confirmed visibility rule is
faculty-wide for every Faculty Administrator so cross-department expertise can
be discovered; department remains a filter rather than an authorization
boundary. Authorized scope, name/department/expertise/publication filters,
aggregate counts, stable ordering, limit, and offset now run in SQL. The API
returns page metadata, all frontend callers use the paginated contract, and the
directory exposes Previous/Next controls. Focused regressions were added for
scope, categories, and page boundaries, and the frontend production build
passes. The focused PERF-01 tests, complete backend suite, and Alembic schema
check pass. No migration or index was added: the final contains-search shape
uses leading wildcards, which ordinary B-tree indexes do not accelerate at the
expected faculty-scale workload.

When the FYP report is restored, update its UC-7 / Staff Profile Search flow,
API contract, and Performance/Scalability section with the faculty-wide scope,
SQL filtering, deterministic pagination, and the decision to defer specialized
substring indexes until PERF-02 provides measurements.

#### [x] SEC-01 - Apply the Prototype Security Baseline

**Goal:** address high-value security gaps without building a compliance system.

**Acceptance criteria:**

- Store only a hash of new password-reset tokens and safely migrate or expire old
  plaintext records.
- Add configurable upload limits and validate supported file signatures/types as
  well as extensions for PDF, DOCX, and CSV flows.
- Ensure secrets and real environment files remain ignored; document credential
  rotation if any historical secret was exposed.
- Reassess JWT lifetime for pilot deployment and document the chosen trade-off.
- Add focused tests for invalid/expired reset tokens and oversized uploads.

**Completed 2026-10-06:** reset-token digests and old-token expiry are covered
by migration `d4e8b6a1c203`; bounded content-validated uploads cover PDF, DOCX,
and CSV entry points; the pilot JWT default is eight hours; and the historical
environment-file exposure is documented, including the confirmed JWT-secret
and other sensitive-credential rotations.
When the FYP report is restored, update its Security Design / Authentication
and Password Recovery section, File Upload Validation section, and Security
Limitations section with these implemented controls and their prototype scope.

#### [ ] SYNC-01 - Complete Queue Recovery and Operations Validation

**Goal:** validate the durable sync behavior under realistic failures.

**Acceptance criteria:**

- Test concurrent duplicate submissions against the PostgreSQL constraint.
- Test worker failure/redelivery and ensure a job cannot silently remain running
  forever; define a simple stale-job recovery policy if needed.
- Verify manual, first-login, administrator, and quarterly triggers use the same
  path and progress states.
- Document worker/Beat restart and failure-diagnosis commands.
- Do not add another queue, SSE, or WebSocket transport.

#### [x] ARCH-01 - Targeted Route/Service Cleanup

**Goal:** improve maintainability after core behavior is stable.

**Acceptance criteria:**

- Split `routes_profile.py` by coherent existing concerns without changing URLs.
- Move mapping PDF rendering out of the route module into an existing/new narrow
  service helper.
- Keep SQLAlchemy access in services where appropriate; do not introduce a
  repository framework or rewrite unrelated modules.
- Existing focused tests and frontend contracts remain unchanged and pass.

**Completed 2026-10-07:** `routes_profile.py` now owns only UC-7 staff
directory/profile endpoints; UC-9 publications, UC-10 academic background, and
UC-11 expertise refinement are registered from focused route modules without
changing URLs or response schemas. Shared profile response mapping is kept in a
small API helper. Mapping-report PDF rendering moved from `routes_mapping.py`
to `services/mapping_export.py`, including the existing off-event-loop render
behavior. Focused tests lock the profile/mapping URL and HTTP-method surface and
verify that the extracted renderer still produces a PDF. No database, frontend,
or use-case behavior changed, so no migration or FYP report content update is
required for this internal maintainability refactor.

#### [ ] DOC-01 - Reconcile Scalability Documentation and FYP Report

**Goal:** make documentation describe the implemented system.

**Acceptance criteria:**

- Replace synchronous/`BackgroundTasks` statements in
  `docs/SCALABILITY_STRATEGY.md` with the current Redis/Celery design.
- Correct the explanation of async database connection waiting: awaiting a pool
  connection yields the event loop; the risks are request latency, pool timeout,
  backlog, and database connection limits, not a traditional thread being held.
- Separate implemented behavior, proposed pilot work, and future scale work.
- Remove arbitrary pool/cache claims until measurements exist.
- When the report file is restored, update architecture, UC-3/8/12 flows,
  concurrency, benchmarking source/method, limitations, and evaluation sections.

### P2 - Evidence-Based Production Preparation

#### [ ] PERF-02 - Establish a Load-Test Baseline

**Depends on:** PERF-01 and QA-01.

**Acceptance criteria:**

- Seed a documented realistic faculty dataset with no real personal data.
- Test normal browsing/search and separately test expensive job submission.
- Record throughput, p50/p95 latency, error rate, database pool waits, and worker
  queue depth using a small reproducible scenario.
- Define faculty-pilot targets before changing configuration.
- Commit the scenario/configuration, not generated large result files.

#### [ ] PERF-03 - Tune Only the Bottleneck Found by PERF-02

**Acceptance criteria:**

- Prefer query/index improvements first.
- Tune connection pool and worker concurrency within PostgreSQL/server limits.
- Add a narrow Redis cache only if repeated reads remain a measured bottleneck;
  document key, TTL, invalidation, and Redis-down fallback.
- Add rate limiting first to login/reset, sync, uploads, and expensive AI or
  benchmarking endpoints when preparing public access.
- Record before/after evidence. Do not add Kubernetes, Kafka, Redis Sentinel,
  read replicas, or microservices for the current FYP.

#### [ ] DEPLOY-01 - Create a Reproducible Faculty-Pilot Deployment

**Acceptance criteria:**

- Provide a Linux/Docker deployment for frontend, API, worker, Beat, Redis, and
  PostgreSQL with secrets supplied outside version control.
- Run exactly one Beat scheduler and document worker scaling.
- Add health checks, structured logs, backup/restore instructions, and database
  migration procedure.
- Document HTTPS/reverse-proxy configuration and a rollback procedure.
- Call it production-ready only after QA, security, backup restore, and load
  targets have been demonstrated.

### Research and Publication Track (After Core FYP Completion)

#### [ ] NLP-01 - Repair and Freeze the Golden-Set Evaluation Protocol

**Acceptance criteria:**

- Confirm annotation unit, inclusion rules, train/dev/test separation, and
  inter-annotator process.
- Report exact and semantic matching without allowing soft matching to hide label
  quality problems.
- Include micro/macro precision, recall, F1, per-document behavior, uncertainty,
  and reproducible model/version settings where appropriate.
- Prevent evaluation-set leakage during parameter tuning.

#### [ ] NLP-02 - Compare LLM Providers Fairly

**Depends on:** NLP-01.

**Acceptance criteria:**

- Run DeepSeek and selected alternatives using the same inputs, prompt,
  temperature, output schema, retry policy, and evaluation set.
- Compare task quality, parse success, latency, cost, and failure categories.
- Explain provider selection from measured trade-offs, not brand preference.
- Preserve raw run metadata without committing provider secrets.

#### [ ] RESEARCH-01 - Define a Publishable Research Question

**Depends on:** validated mapping/benchmarking and NLP protocols.

**Acceptance criteria:**

- Formulate one narrow research question rather than presenting the entire
  software system as the contribution.
- Candidate direction: explainable, tool-using LLM support for evidence-backed
  expertise inference or gap explanation, inspired by research on LLM tool
  interaction but not described as fault localization.
- Separate the deterministic evidence/retrieval layer from the LLM explanation
  layer and evaluate faithfulness, not only fluency.
- Define baselines, ablation study, dataset, metrics, threats to validity, and a
  reproducibility package before claiming publication readiness.

## Project Structure

```text
expertise-insight/
|-- AGENTS.md                         # Local agent rules; intentionally ignored
|-- README.md                         # Current status and task handoff document
|-- use_cases.md                      # UC-1 through UC-18 specification
|-- compose.yaml                      # Redis service for local development
|-- backend/
|   |-- app/
|   |   |-- api/                      # FastAPI routes and dependencies
|   |   |-- core/                     # Settings, security, exceptions
|   |   |-- db/                       # SQLAlchemy models/session
|   |   |-- services/                 # Business, NLP, mapping, export logic
|   |   |-- tasks/                    # Celery task entry points
|   |   `-- worker.py                 # Celery configuration and Beat schedule
|   |-- alembic/versions/             # Database migrations
|   |-- evaluation/                   # Golden data, scripts, generated reports
|   |-- tests/                        # Focused critical tests
|   |-- pyproject.toml
|   `-- .env.example
|-- frontend/
|   |-- src/
|   |   |-- api/                      # Shared Axios client
|   |   |-- layouts/                  # Auth shell and sync status guard
|   |   |-- navigation/               # Portfolio-aware navigation
|   |   |-- pages/                    # Feature pages
|   |   |-- store/                    # Zustand auth/session state
|   |   `-- types.ts                  # Frontend API contracts
|   `-- package.json
`-- docs/
    |-- LLM_EVALUATION.md
    `-- SCALABILITY_STRATEGY.md        # Partially stale; see DOC-01
```

Generated build copies are not source code and must remain ignored. Local
`.env` and `.env.*` files are ignored except for redacted example files.

## Local Development

### Prerequisites

- Python 3.11 or later. The current developer environment uses Python 3.13.2.
- Node.js 18 or later.
- PostgreSQL 14 or later.
- Docker Desktop or a local Redis 7 server.
- SMTP credentials for real email delivery.
- Network access to ORCID/OpenAlex and an optional OpenAI-compatible LLM.

IEEE credentials are not required for the intended replacement global benchmark.
The current UC-15 implementation still references them until BENCH-02 is done.

### 1. Configure PostgreSQL

Create a local database, for example:

```sql
CREATE DATABASE expertise_insight;
```

### 2. Install and Configure the Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Fill in `backend/.env` with local values. Use `.env.example` as the canonical
list of settings; never put real credentials in this README or commit `.env`.

Apply migrations:

```powershell
alembic upgrade head
```

### 3. Start Redis

From the repository root:

```powershell
docker compose up -d redis
docker compose ps
```

### 4. Start the Celery Worker and Scheduler

From `backend/`, with the virtual environment active, use separate terminals:

```powershell
# Windows local development only
celery -A app.worker:celery_app worker --pool=solo --loglevel=INFO

# Run exactly one scheduler
celery -A app.worker:celery_app beat --loglevel=INFO
```

Linux/Docker worker:

```bash
celery -A app.worker:celery_app worker --loglevel=INFO
```

Celery does not automatically reload project code in the current Windows setup.
Restart the worker after changing task, queue, harvesting, NLP, or related model
code.

### 5. Start the API

From `backend/`:

```powershell
uvicorn app.main:app --reload
```

- API: `http://localhost:8000`
- OpenAPI UI: `http://localhost:8000/docs`
- Liveness: `http://localhost:8000/health`

### 6. Start the Frontend

From a separate terminal:

```powershell
cd frontend
npm install
npm run dev
```

The Vite application runs at `http://localhost:5173` and proxies `/api` to the
backend during local development.

## Verification

Run focused tests during development and the broader checks before completing a
cross-layer task:

```powershell
# From backend with .venv active
python -m pytest
alembic check

# From frontend
npm run build
```

Current focused automated tests:

- `test_first_login_sync.py`: first login queues exactly one sync only when an
  ORCID is present.
- `test_sync_queue.py`: Redis publication failure persists a failed job state.
- `test_peer_benchmark_chunks.py`: long peer documents are split without losing
  their final content.
- `test_security_baseline.py`: reset-token hashing and invalid/expired handling,
  bounded upload reads, and disguised upload rejection.
- `test_staff_search.py`: faculty-wide administrator scope, SQL category
  predicates, pagination bounds/metadata, and deterministic limit/offset.
- `test_architecture_cleanup.py`: unchanged profile/mapping route contracts and
  mapping PDF service rendering.

Verification completed on **2026-10-06**:

- backend: **12 tests passed**, including all SEC-01 regressions;
- Alembic connected successfully but reported the local database is not yet at
  head because migration `d4e8b6a1c203` has not been applied; run
  `alembic upgrade head`, then `alembic check`;
- frontend: not rerun for SEC-01 because no frontend contract or source changed
  (the preceding TypeScript/Vite production build had succeeded).

PERF-01 verification completed on **2026-10-07**:

- focused backend: **12 tests passed** in `test_staff_search.py`;
- complete backend: **24 tests passed**;
- Alembic: `alembic check` reported no new upgrade operations;
- frontend: `npm run build` succeeded;
- PERF-01 contains no schema change or migration.

ARCH-01 verification completed on **2026-10-07**:

- focused backend: **15 tests passed** across the architecture-contract and
  staff-search suites;
- complete backend: **27 tests passed**;
- Alembic: `alembic check` reported no new upgrade operations;
- frontend: `npm run build` succeeded; the profile/mapping URL and HTTP-method
  surface is also covered by a backend regression test and matches the
  pre-change snapshot.

Re-run these commands rather than assuming the snapshot remains true after later
changes.

The scripts in `backend/evaluation/` are research evaluation tools. They do not
replace software unit/integration tests.

## Documentation and Report Handoff Rule

Every completed roadmap task must update this README's status and checkbox. Also
decide whether it changes:

- functional/non-functional requirements or a use-case flow;
- architecture, deployment, database, or concurrency diagrams;
- algorithm, external dataset, model/provider, or evaluation method;
- security, scalability, limitation, or implementation-status claims.

If it does, update the corresponding repository document in the same task. When
the FYP report is available again, record and apply the matching report edits.
Never describe a proposal as implemented, and never describe an unverified
prototype as production-ready.
