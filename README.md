# ExpertiseInsight

Decoupled client–server platform implementing the specification matrix
declared in [`instructions.md`](instructions.md), [`DESIGN.md`](DESIGN.md),
and [`use_cases.md`](use_cases.md). All three documents constitute the
single source of truth — no code or UI element in this repository
diverges from them.

## Repository layout

```
backend/    FastAPI service, SQLAlchemy schema, Alembic migrations,
            services (auth, notifications, external API clients),
            and HTTP routers under /api/v1.
frontend/   Vite + React + TypeScript + Tailwind SPA wired to the
            Linear design tokens. Implements the dual-role header
            toggle (FR-012) and the portfolio-driven sidebar.
```

## Build phases

This repository is delivered in phases so that every shipped layer is
production-grade (no mocks, no decorative endpoints) per
`instructions.md` §4 rule 6.

| Phase | Use cases delivered |
| ----- | ------------------- |
| **1 (this commit)** | UC-1 register, UC-2 authorize, UC-3 login, UC-4 reset password, UC-5 email service, UC-6 role/portfolio resolution + dual-role view toggle, external API clients with retry/503 (UC-8 / UC-12 / UC-15 connectivity rules), full database schema for UC-1…UC-18. |
| 2 (next) | UC-7 staff directory + global search, UC-8 ORCID→OpenAlex→SciBERT→LLM pipeline, UC-9 abstract supplement, UC-11 tag refinement, UC-12 manual + quarterly sync. |
| 3 | UC-13 spec ingestion, UC-14 cosine + spreading-activation mapping, UC-10 academic background CRUD. |
| 4 | UC-15 global benchmarking, UC-16 peer benchmarking, UC-17 combined gap report, UC-18 portfolio snapshot export. |

Sidebar links for not-yet-delivered modules render the explicit "No
records found" empty state mandated by UC-7's exception flow and
`instructions.md` §4 rule 1 — they never display fabricated data.

## Backend — running locally

Prerequisites: Python 3.11+, PostgreSQL 14+, an SMTP relay reachable
from the host, and (for later phases) ORCID/OpenAlex network access
plus an OpenAI-compatible LLM endpoint.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .

Copy-Item .env.example .env   # then edit secrets
alembic revision --autogenerate -m "initial schema"
alembic upgrade head

uvicorn app.main:app --reload
```

OpenAPI documentation: `http://localhost:8000/docs`.

## Frontend — running locally

```powershell
cd frontend
npm install
npm run dev
```

Vite serves the SPA on `http://localhost:5173` and proxies `/api`
requests to the FastAPI service on port 8000.

## Architectural guardrails (must remain enforced)

1. Source code, comments, docstrings, and API descriptions are
   English-only (`instructions.md` §4 rule 2).
2. Every ORCID/OpenAlex/IEEE Xplore call goes through
   `app.services.external_apis` so the retry policy and the
   `503 ExternalServiceError` envelope are uniform.
3. All database schema changes flow through Alembic migrations — never
   through ad-hoc DDL.
4. Frontend styling uses only the tokens declared in
   `frontend/tailwind.config.js`; no inline pixel values.
5. New sidebar links must trace to a UC and to a real backend
   endpoint, or they must not be added.
