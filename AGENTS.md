# Expertise Insight - Agent Engineering Guide

## 1. Purpose

This repository is an undergraduate Final Year Project (FYP) that may later be
deployed for faculty use. Build a complete, demonstrable, and academically
defensible system first. Keep a credible path to production, but do not build
infrastructure for hypothetical scale before the project needs it.

The governing principle is **KISS**: choose the smallest clear solution that
correctly satisfies the current use case.

## 2. Priority Order

When requirements compete, use this order:

1. Correct and complete FYP use cases.
2. A working end-to-end user flow with understandable feedback.
3. Data integrity, authentication, authorization, and secret safety.
4. Clear code with sensible route, service, and persistence boundaries.
5. Tests for critical business paths and failure cases.
6. Measured performance improvements for realistic faculty workloads.
7. Optional production hardening and research extensions.

Do not delay a core feature to build generic frameworks, speculative
microservices, exhaustive test scaffolding, or enterprise-grade high
availability.

## 3. Sources of Truth

Never guess an interface or business rule.

Before changing behavior:

1. Inspect the relevant route, schema, service, model, migration, frontend
   caller, and existing test.
2. Search the repository for every caller and representation of the affected
   field or endpoint.
3. Check `use_cases.md` and the FYP report when available.
4. For third-party APIs and libraries, consult current official documentation.
5. If code, use cases, and report disagree, state the discrepancy. Do not
   silently choose one or invent a fourth interpretation.
6. Ask the user only when the unresolved choice materially changes product
   behavior, research validity, or data compatibility.

Truth precedence for implementation details is:

- verified runtime behavior and database schema;
- current application code and migrations;
- confirmed user decisions;
- current official external documentation;
- repository documentation and the FYP report.

Documentation being lower in this list does not make it optional: update it
when an implementation decision changes.

## 4. Current Project Baseline

Treat this as a modular monolith, not as microservices.

- Frontend: React 18, TypeScript, Vite, Tailwind CSS, Zustand.
- API: FastAPI with versioned routes under `/api/v1`.
- Persistence: async SQLAlchemy 2, PostgreSQL, Alembic.
- Background processing: Redis broker and Celery worker.
- NLP: sentence-transformers/SciBERT-based processing plus an optional
  OpenAI-compatible LLM provider.
- External scholarly data: ORCID and OpenAlex. The existing IEEE global
  benchmarking implementation is under methodological and licensing review;
  do not expand it without confirming current official terms.

Current synchronization behavior is already asynchronous and durable:

- first-login, manual, administrator, and quarterly triggers create `SyncJob`
  records and enqueue Celery work;
- only one queued or running synchronization job is allowed per user;
- the UI displays a blocking, stage-aware synchronization modal and explicit
  terminal results;
- Celery Beat schedules quarterly synchronization.

Do not replace this with FastAPI `BackgroundTasks`, an in-memory queue, or a
second job mechanism. `docs/SCALABILITY_STRATEGY.md` contains older statements
about synchronous processing and must not override the current implementation.

## 5. Scope and Architecture Rules

Keep the existing layered modular-monolith structure:

- `backend/app/api/`: HTTP concerns, validation dependencies, status codes,
  and response schemas.
- `backend/app/services/`: reusable business workflows and external-service
  orchestration.
- `backend/app/db/`: persistence models and session setup.
- `backend/app/tasks/`: thin Celery entry points that call services.
- `frontend/src/api/`: shared HTTP client behavior.
- `frontend/src/pages/` and `layouts/`: user flows and presentation.

Use these boundaries pragmatically:

- Routes should not contain a second implementation of service logic.
- Services may use SQLAlchemy directly. Do not introduce repositories, command
  buses, domain-event frameworks, dependency-injection containers, or other
  abstraction layers unless repeated concrete pain justifies them.
- Extract a helper or service when logic is reused, independently testable, or
  makes a route substantially easier to understand, not merely to create more
  files.
- Prefer explicit code over metaprogramming and generic base classes.
- Preserve public interfaces unless the change intentionally updates every
  consumer.
- Refactor incrementally around the feature being changed. Do not rewrite the
  whole application to make a local improvement.

## 6. Implementation Workflow

For each task:

1. Restate the intended behavior and identify the affected use case.
2. Inspect before editing; search for existing interfaces and reusable code.
3. Note any assumption that affects behavior.
4. Implement the smallest coherent vertical slice: database, backend,
   frontend, and user feedback when all are needed.
5. Run ONLY targeted, minimal tests for the directly impacted code during iteration.
6. Avoid redundant all-suite runs or unprompted frontend builds if no frontend files or cross-boundary contract changes were modified. Verify only what actually changed.
7. Inspect the diff for unrelated edits, duplicate logic, stale names, leaked
   secrets, and report/documentation drift.
8. Tell the user exactly what changed, what was verified, and what remains.

Do not claim that something works if it was only reviewed statically. If a
test cannot run, report the actual command and error.

## 7. API and Frontend Contracts

- Reuse existing endpoints and schemas where they express the required
  operation.
- Do not invent request fields, response fields, status values, or third-party
  payload shapes from memory.
- When changing a contract, update backend schemas, frontend types, every
  caller, tests, and relevant documentation in the same change.
- Use appropriate HTTP status codes and structured errors. Do not return HTTP
  200 for a failed operation merely to simplify the frontend.
- Long-running work must return promptly as a job-based operation rather than
  holding an HTTP request open.
- Every queued operation must expose discoverable progress, success, no-change,
  and failure states. Prevent accidental duplicate submissions.
- Prefer polling for the small number of long-running FYP jobs unless measured
  UX or load requirements justify SSE/WebSocket complexity. Do not maintain
  polling and push transports simultaneously without a demonstrated need.
- User-visible behavior matters: loading, empty, disabled, failure, recovery,
  and success states are part of the feature.

## 8. Dependencies

Keep the dependency surface small.

Before adding a package, determine whether:

- the standard library or an installed dependency already solves the problem;
- the package removes meaningful complexity rather than a few lines of clear
  code;
- it is actively maintained and compatible with the existing runtime;
- it materially increases install size, startup time, security exposure, or
  deployment complexity.

Adding a dependency requires a concrete use in the same change. Do not add
alternative libraries for technology already selected (for example, a second
task queue, ORM, state manager, HTTP client, or component framework). Remove a
dependency when its last real use is removed.

Avoid production infrastructure additions until justified by a measured
bottleneck or a confirmed deployment requirement. Redis already has a required
role as the Celery broker; reusing it for a small, proven caching or rate-limit
need is preferable to introducing another service.

## 9. Database and Migrations

- PostgreSQL is the authoritative persistent store.
- Any schema change must have an Alembic migration and matching SQLAlchemy
  model/schema changes.
- Prefer database constraints for invariants that must survive concurrent
  requests; application-only checks are insufficient for uniqueness or other
  race-sensitive rules.
- Preserve existing data. Never drop or rewrite user data without explicit
  approval and a migration/backfill plan.
- Avoid N+1 queries and loading full tables when pagination or SQL filtering is
  straightforward.
- Add an index only for a known query pattern; explain the query it supports.
- Do not tune pool sizes, add pgvector indexes, or cache query results using
  arbitrary numbers. First establish expected workload or measurement, then
  make the smallest supported change.
- Cache is an optimization, never the system of record. Define TTL,
  invalidation, and Redis-unavailable behavior before introducing a cache.

## 10. Concurrency and Background Work

- Keep expensive external API, NLP, and synchronization work in Celery.
- Make jobs safe against duplicate delivery where practical; Celery delivery
  is not an exactly-once guarantee.
- Persist job status and progress in PostgreSQL so restarts do not erase user
  feedback.
- Enforce one active synchronization per user in the database and retain a
  clear application-level response for conflicts.
- Set finite timeouts and bounded retries for external calls. Retry transient
  errors, not validation failures or permanent authorization errors.
- Do not force all users to log out for quarterly synchronization. Apply
  per-user conflict handling and consistent UI status.
- On Windows, the Celery `solo` pool is acceptable for local testing only;
  normal production workers should run on Linux/Docker with the standard pool.

## 11. Testing and Verification

Test important behavior, not implementation trivia. The project does not seek
100% coverage.

Prioritize tests for:

- authentication, authorization, and first-login synchronization;
- queue submission, duplicate-job prevention, and failure persistence;
- synchronization data transformations and critical NLP/mapping calculations;
- course/grant matching and benchmarking score formulas;
- destructive or integrity-sensitive profile operations;
- regressions discovered during development.

Use unit tests for deterministic business logic and a small number of
integration tests for flows where database, route, and service behavior must
work together. Do not add tests that only prove FastAPI starts, settings can be
imported, or a framework behaves as documented unless they guard a real past
failure.

Keep test setup local and readable. Avoid elaborate fixture hierarchies,
factory frameworks, full-browser E2E suites, or broad mocking infrastructure
unless multiple valuable tests genuinely need them.

### Verification Scope Rules

- **Targeted First, Minimal Always**: Never run full regression test suites repeatedly for local edits. Only run tests specifically covering the modified functionality.
- **No Unnecessary Frontend Builds**: Do NOT execute frontend build commands (`npm run build`) unless frontend code (`frontend/src/`) or API contract types were explicitly modified. If only backend code was changed, frontend building is strictly forbidden.
- **No Duplicate Test Executions**: If a test suite or verification check has passed and no code was modified afterward, do NOT re-run it "just to be sure."
- **Skip Pure Static Diff Audits**: Do not run repetitive file searches or diff audits unless there is an unhandled syntax/import exception. Trust git tracking and targeted test output.

Relevant verification commands:

```powershell
# Backend (run from backend with its virtual environment active)
python -m pytest
alembic check

# Frontend
npm run build
```

Run targeted tests first while iterating. Only run boundary checks (e.g., alembic check or npm run build) for the specific layers that were actually updated.

### Sandbox and Python Environment Diagnosis

The repository's `backend/.venv` is valid and its `pyvenv.cfg` points to the
local Python 3.13.2 installation under the user's profile. In the agent sandbox,
that base interpreter path may return `EPERM` because it is outside the allowed
filesystem boundary. `EPERM` means sandbox access was denied; it does **not**
mean the interpreter or the user's local environment is missing or broken.

If the virtual-environment launcher reports that it cannot find its base Python:

1. Read `backend/.venv/pyvenv.cfg` and inspect the configured base interpreter.
2. Check the base path and distinguish `EPERM`/access denied from
   `ENOENT`/path not found.
3. When the result is `EPERM`, request permission to run the existing `.venv`
   command outside the sandbox and use that result as the source of truth.
4. Do not describe the Python installation as missing or damaged unless an
   authorized check actually returns `ENOENT` or another verified local error.

## 12. Security Baseline

Security work should be proportionate, but these basics are not optional:

- Never commit `.env`, credentials, tokens, private keys, or real personal
  data. Maintain redacted `.env.example` files.
- If a secret was committed, removing the file is not enough; advise rotating
  the credential and removing it from tracked history where appropriate.
- Hash reset tokens or other bearer secrets at rest.
- Validate upload type and size; do not trust filenames or client MIME types.
- Enforce authorization server-side, including faculty/department scope.
- Avoid logging tokens, passwords, complete uploaded documents, or unnecessary
  personal data.
- Use parameterized SQL through SQLAlchemy and validate external URLs/IDs.
- Apply rate limiting first to login, password reset, sync triggers, uploads,
  and expensive AI/benchmarking endpoints when preparing a real deployment.
- Do not claim encryption, audit coverage, compliance, or production readiness
  unless implemented and verified.

## 13. NLP, LLM, and Research Integrity

The research contribution must remain reproducible and defensible.

- Keep deterministic retrieval, embeddings, similarity calculations, and
  evaluation separate from LLM-written explanations.
- Do not let an LLM generate both the benchmark truth and the conclusion used
  to validate the system.
- LLM output must not silently replace externally sourced counts, labels,
  citations, ground truth, or metric values.
- Record model/provider name, important parameters, dataset version or date,
  prompts where relevant, and fallback behavior for experiments.
- Compare LLM providers using the same dataset, prompt, metrics, and conditions.
  Do not justify DeepSeek, or any provider, only through anecdotal output.
- Use the golden-standard dataset for measurable evaluation. Report precision,
  recall, F1, and any ranking metrics at the correct unit of analysis; do not
  choose a data model solely to make one metric easier to calculate.
- Distinguish semantic coverage comparison from true trend prediction. Claims
  of emerging global research trends require external time-series evidence,
  growth or acceleration measures, and a documented time window.
- Prefer an independent, legally usable scholarly source such as OpenAlex for
  global topic/count data. Semantic Scholar may be used for limited independent
  corroboration. LLMs may explain results but must not create the benchmark.
- Verify official API terms before downloading, embedding, or publishing
  results from IEEE or any other provider. Store provenance and source IDs.

## 14. Documentation and FYP Report Consistency

Code, README, use cases, scalability documentation, and the FYP report must
describe the same system.

For every material change, decide whether it changes any of the following:

- functional or non-functional requirements;
- use-case preconditions, main flow, alternate flow, or UI behavior;
- architecture/component/deployment diagrams;
- database design or concurrency behavior;
- algorithms, external datasets, model/provider choice, or evaluation method;
- limitations, security claims, scalability claims, or implementation status.

If so, update the repository documentation in the same change and identify the
exact report section that must be revised. If the report file is unavailable,
do not reconstruct it from memory; leave a concise report-update note for the
user.

Use accurate status labels:

- **Implemented**: code exists and the relevant path was verified.
- **Partially implemented**: a real path exists but known requirements remain.
- **Proposed**: design only; do not describe it as current architecture.
- **Future work**: intentionally outside the current FYP completion scope.

Never inflate academic claims. A prototype can be well engineered without
being described as production-ready.

## 15. Performance and Production Readiness

Design for a plausible faculty deployment, but optimize from evidence.

Before a performance change:

1. Define a realistic workload (staff count, concurrent users, record volume,
   and expensive actions).
2. Identify the actual bottleneck through query inspection, timings, logs, or a
   small repeatable load test.
3. Fix query shape, pagination, and unnecessary work before adding caches or
   more infrastructure.
4. Record the before/after measurement and operational trade-off.

The likely evolution path is:

1. complete and verify use cases;
2. move filtering/pagination into SQL where still needed;
3. add targeted indexes;
4. run a modest reproducible load test;
5. tune the database pool and worker count to the deployment limits;
6. add narrowly scoped Redis caching/rate limiting only if evidence supports
   it;
7. consider horizontal scaling or specialized vector indexing only when the
   dataset and measurements justify them.

Do not add Kubernetes, Redis Sentinel, Kafka, a service mesh, read replicas,
multiple caches, event sourcing, CQRS, or microservices for this FYP unless the
user explicitly changes the project scope and provides a concrete requirement.

## 16. Definition of Done

A change is done when:
- The requested user flow works end to end.
- Affected interfaces were directly verified through targeted checks.
- Relevant focused tests pass (run only the test files directly related to the edit).
- Frontend build passes **ONLY IF** frontend code or client-facing API response schemas were modified.
- An Alembic migration exists and `alembic check` passes **ONLY IF** database models or schema changed.
- No secrets, generated build outputs, or unrelated changes remain in the diff.
- Remaining limitations or docs updates are stated concisely.

Do not re-run tests or build steps that have already passed in the same session without code changes.

## 17. Working Conduct

- Preserve unrelated user changes in a dirty worktree.
- Use small, reviewable diffs even when implementing a complete vertical slice.
- Do not perform destructive Git or database actions without explicit approval.
- Do not edit generated build copies as if they were source code.
- Do not create a new interface when an existing one can be correctly reused.
- Do not hide uncertainty. Investigate first; ask when a consequential ambiguity
  remains.
- Do not over-explain routine edits, but explain architectural, research, data,
  and compatibility decisions clearly enough for an undergraduate maintainer to
  defend them during a presentation.
