# Production Scalability Strategy: Handling High User Volume

## 1. Context & Assumptions

ExpertiseInsight is currently in **MVP (Minimum Viable Product)** stage, targeting a single
faculty (~200–300 academic staff).  In this stage several architectural simplifications are
intentional — synchronous ORCID sync, in-memory Python filtering for staff search, default
database connection pool sizes — because they reduce operational complexity during development
and local deployment.

This section describes the **concrete engineering steps** required to evolve the system
to serve **1 000+ staff** across multiple departments and to sustain **concurrent requests
from dozens of administrator users** in a production deployment.  All strategies align with
the existing technology stack (FastAPI, PostgreSQL, SQLAlchemy Async, React) and are ordered
by impact.

---

## 2. Database Query Optimisation (P0 — Immediate Impact)

### 2.1 Problem: Missing Department-Scope Filter + In-Memory Search

The `GET /profile/staff` endpoint is authenticated via `get_current_user` — every
request carries a JWT identifying the actor's role, department, and faculty
affiliation.  An HoD of Electrical & Electronic Engineering should only browse
staff within EEE; a Deputy Dean should only search their own school.

However, the current implementation:

1. Loads **every active academic staff** row across **all** faculties from the
   ``users`` table — ignoring the actor's department scope entirely.
2. Eager-loads all associated `publications` and `user_expertise_tags` via
   `selectinload` for every matching row.
3. Performs keyword matching (`q`, `department`, `tag_label`) **in Python
   memory** with nested `for` loops on the full result set.

Even within a single large faculty (e.g. 300 staff × ~15 publications × ~12 tags
= ~8 100 rows), every request repeatedly loads and iterates the same data.  Over
a university-wide deployment with multiple faculties (1 000+ staff total), the
lack of scope filtering means the Engineering HoD inadvertently queries the
entire database on every directory browse.

### 2.2 Solution: Scope-Gated + SQL-Level Filtering + Pagination

**Step 1 — Department-scope gating (first-line reduction).**

Before any keyword matching, filter the query to only the faculty/department
scope the actor is authorized to view.  The ``require_portfolio`` dependency
already carries this information:

```python
# HoDs see only their own department; Deputy Deans see their school.
stmt = stmt.where(User.department == actor.department)
```

This single clause reduces the scanned row set from the **institution-wide**
total to the **actor's own faculty** size (typically 100–300 staff) — an
immediate 70–90% reduction before any keyword filtering or pagination is
applied.

**Step 2 — Server-side pagination.**

Add `page` and `page_size` query parameters to `GET /profile/staff` (default
`page=1`, `page_size=20`).  The endpoint returns a subset of matching staff
rather than the full scoped list, with a `total_count` field so the frontend
can render pagination controls.

**Step 3 — SQL-level filtering.**

Replace Python keyword-matching with PostgreSQL `ILIKE` clauses applied
directly to the `WHERE` condition of the underlying `SELECT` statement:

```sql
-- Scoped to actor's department + SQL filtering + paginated:
SELECT users.*, expertise_tags.*, publications.*
FROM users
LEFT JOIN user_expertise_tags ON ...
LEFT JOIN expertise_tags ON ...
WHERE users.status = 'active'
  AND users.department = :actor_department        -- scope gate
  AND users.full_name ILIKE '%keyword%'            -- name search
  AND expertise_tags.canonical_label ILIKE '%keyword%'  -- expertise search
ORDER BY users.full_name
LIMIT 20 OFFSET 0;
```

This reduces per-request data transfer from the full-scope set to just the
**requested page size** (e.g. 20 rows), a reduction of over 95 % even within
a single large faculty.

**Step 3 — Add covering indexes.**

```sql
-- Accelerate filtered staff lookups
CREATE INDEX idx_users_status_role ON users (status, role);

-- Accelerate ILIKE queries (requires pg_trgm extension)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_users_full_name_trgm ON users USING GIN (full_name gin_trgm_ops);
CREATE INDEX idx_expertise_tags_label_trgm ON expertise_tags USING GIN (canonical_label gin_trgm_ops);
```

The `pg_trgm` GIN indexes support `ILIKE '%keyword%'` with sub-millisecond lookup
even on 100 000+ rows, avoiding the sequential scan that a bare `ILIKE` would trigger.

---

## 3. Connection Pool Tuning

### 3.1 Problem: Default Pool Too Small for Concurrency

The current `create_async_engine` call in ``app/db/session.py`` does not set
``pool_size`` or ``max_overflow``, relying on asyncpg/SQLAlchemy defaults:

* **``pool_size``** defaults to **5** (SQLAlchemy 2.0 default; asyncpg's own
  default is 10 but SQLAlchemy overrides it to 5 when no explicit size is given).
* **``max_overflow``** defaults to **10**.  This means the pool can create up to
  5 + 10 = **15 total connections** during a burst, but connections above
  ``pool_size`` are torn down after use (they are not recycled).

**What happens when the pool is exhausted (step by step):**

1. **The first 5 requests** each acquire a persistent connection from the base
   pool immediately and begin executing their SQL queries.

2. **Requests 6 through 15** trigger an **overflow connection**.  SQLAlchemy
   opens a brand-new connection to PostgreSQL (TCP handshake + SSL negotiation +
   authentication — typically 50–200 ms).  This connection is handed to the
   waiting request, used for the duration of that request's database work, then
   **closed and discarded** rather than returned to the pool.

3. **Request 16 and beyond** find all 5 base connections in use AND all 10
   overflow slots consumed.  SQLAlchemy's internal ``QueuePool`` makes the
   calling coroutine **``await`` on an internal ``asyncio.Event``**.  This is
   the key detail: the request is **not rejected** (no HTTP 503), but it is
   **suspended** — the FastAPI route handler sits blocked at the ``await
   session.execute(...)`` call, holding the Uvicorn worker thread, until one of
   the 15 in-flight connections finishes its work and is returned to the pool
   (or discarded for overflow connections, freeing an overflow slot).

4. **Uvicorn's own worker pool is also finite** (default: number of CPU cores).
   If enough FastAPI routes are suspended waiting for database connections,
   Uvicorn runs out of free workers to accept new HTTP connections.  At this
   point **new incoming requests are queued at the OS socket level** (TCP
   listen backlog), and eventually the load balancer or browser sees a
   connection timeout.

**User-visible symptoms of pool exhaustion:**

| Stage | Symptom | Root Cause |
|-------|---------|------------|
| Pool full, small wait | Page loads in 3–5 seconds instead of 300 ms | Request spent 2–4 seconds ``await``-ing for a free pool slot |
| Pool full, longer wait | Browser shows "Waiting for server..." spinner for 8–15 seconds | Request queued behind multiple waiters; each must finish its SQL work before the next gets a connection |
| Uvicorn worker starvation | Load balancer returns HTTP 502 Bad Gateway or browser shows "Connection refused" | No Uvicorn worker is free to accept the TCP connection; all are suspended waiting for DB connections |
| Extreme case | PostgreSQL logs "too many clients" errors | Overflow connections pushed total connections past PostgreSQL's ``max_connections`` limit (default 100) — this would require 85+ simultaneous overflow connections, unlikely at faculty scale but possible under a connection-leak bug |

**Why this matters for the staff directory specifically:**

The current ``GET /profile/staff`` implementation (see Section 2.1) exacerbates
the problem.  Because every request loads all staff + all publications + all
tags into Python memory, each request holds its database connection **far longer**
than necessary — potentially 500–2000 ms for a full-table-scan query with
eager-loaded joins on 300+ staff.  During that entire duration, the connection
is occupied and unavailable to other requests.  If each request holds its
connection for 1 second and the pool has only 5 base connections, the
throughput ceiling is **5 requests/second** — the 6th simultaneous user
experiences a growing queue.

With the query optimisations from Section 2.2 (scope-gated + paginated + SQL
filtering), the per-request connection hold time drops to ~20–50 ms, raising
throughput from 5 req/s to ~100 req/s on the same 5-connection pool alone —
a 20× improvement before even tuning the pool size.

### 3.2 Solution

Explicitly configure the pool in `app/db/session.py`:

```python
engine = create_async_engine(
    settings.database_url,
    pool_size=20,          # base pool size
    max_overflow=10,       # up to 30 total under burst load
    pool_recycle=3600,     # recycle connections after 1 hour
    pool_pre_ping=True,    # validate connections before use
)
```

This supports **20 concurrent database sessions** under steady load and bursts up to
**30** without introducing a separate connection-pool infrastructure (like PgBouncer),
which is appropriate for a single-server faculty-scale deployment.

---

## 4. Caching Strategy

### 4.1 Problem: Repeated Identical Queries Waste Resources

The staff directory, department lists, and canonical expertise tag vocabulary change
infrequently (typically only after a quarterly sync or manual refinement).  Without
caching, every page load re-executes the same database queries.

### 4.2 Solution: Redis Read-Through Cache

**Infrastructure:** Add a Redis instance (single-node, sufficient for faculty scale;
upgradeable to Redis Sentinel for high availability).

**Cache keys** follow a deterministic pattern:
```
staff:list:<department_hash>:<query_hash>:page:<n>
staff:detail:<user_id>
tags:vocabulary
departments:list
```

**Cache policy:**
| Data | TTL | Invalidation Trigger |
|------|-----|---------------------|
| Staff directory page | 5 minutes | Any staff update / sync completion |
| Staff profile detail | 10 minutes | Staff update / tag refinement |
| Tag vocabulary | 1 hour | New tag creation |
| Department list | 24 hours | Manual admin action |

**Fallback:** If Redis is unreachable, the system transparently falls back to direct
database queries — the cache is an acceleration layer, not a hard dependency.

### 4.3 Frontend Cache

React Query (TanStack Query) on the frontend provides a second cache layer:

```typescript
// Staff directory query — stale time prevents re-fetch on tab switch
useQuery({
  queryKey: ['staff', { page, department, q }],
  queryFn: () => fetchStaffDirectory({ page, department, q }),
  staleTime: 2 * 60 * 1000,  // 2 minutes — data is fresh enough
  gcTime: 10 * 60 * 1000,    // keep in garbage collection for 10 minutes
});
```

This eliminates redundant API calls when users navigate between pages and return,
reducing backend load without compromising data freshness.

---

## 5. API Rate Limiting

### 5.1 Problem: No Protection Against Abuse or Bug Loops

The current API has no per-user or per-IP rate limits.  A misbehaving frontend
loop or a malicious actor could overwhelm the server with thousands of requests
per second.

### 5.2 Solution

Integrate `slowapi` (a FastAPI-compatible rate limiter backed by Redis or in-memory
storage):

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/profile/staff")
@limiter.limit("30/minute")  # per IP
async def search_staff(...):
    ...
```

| Endpoint | Limit | Rationale |
|----------|-------|-----------|
| `GET /profile/staff` | 30 req/min per IP | Directory browsing is not a real-time operation |
| `POST /sync` | 2 req/min per user | Sync is expensive; prevent rapid re-triggering |
| `POST /auth/login` | 10 req/min per IP | Brute-force protection |
| `GET /health` | Unlimited | Load-balancer liveness probes |

For a multi-server deployment, the limiter backend switches from in-memory to Redis
so all application replicas share a unified rate-limit state.

---

## 6. Asynchronous Sync Pipeline (Current Limitation)

### 6.1 Problem: Synchronous Sync Blocks the Request Thread

The ORCID/OpenAlex harvesting endpoint (`POST /sync`) currently executes the full
pipeline — API calls, NLP extraction, LLM normalisation, database writes —
synchronously within the HTTP request lifecycle.  The frontend shows a blocking modal
with a 10-minute timeout while the user waits.

For a single user this is acceptable during MVP.  For production with dozens of
concurrent syncs, it would exhaust the Uvicorn worker pool.

### 6.2 Solution: Background Task Queue

Replace the synchronous flow with a **task queue architecture**:

```
POST /sync  →  Create SyncJob(status=QUEUED)  →  Return 202 Accepted
                                                    │
                    ┌───────────────────────────────┘
                    ▼
            ARQ / Celery Worker
                    │
                    ├─ Fetch publications from ORCID + OpenAlex
                    ├─ SciBERT keyword extraction
                    ├─ LLM tag normalisation
                    ├─ Store results in PostgreSQL
                    └─ Set SyncJob(status=SUCCEEDED)
```

The frontend polls `GET /sync/status/{job_id}` or receives a **WebSocket push**
notification when the job completes.  This frees HTTP workers immediately and
allows horizontal scaling of background workers independently of the API server.

**Note for the current MVP:** A pragmatic intermediate step is FastAPI's built-in
`BackgroundTasks`, which moves work off the request thread without introducing
a separate queue infrastructure.  This is sufficient for single-server deployment
and requires no new dependencies.

---

## 7. Vector Search Acceleration

### 7.1 Problem: Brute-Force Cosine Similarity Over All Tags

The mapping engine (`MappingService.generate_report`) computes cosine similarity
between a specification embedding and **every expertise tag embedding** in the
database.  With 1 000 staff × ~15 tags each = 15 000 vectors at 384 dimensions,
this is ~11 million floating-point operations — acceptable at MVP scale (~2–5
milliseconds on modern hardware) but linearly growing with staff count.

### 7.2 Solution: pgvector IVFFlat Index

Create an **IVFFlat (Inverted File Flat)** index on the `expertise_tags.embedding`
column:

```sql
CREATE INDEX idx_expertise_tags_embedding_ivf
ON expertise_tags
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

The `lists` parameter (rule of thumb: `sqrt(n_rows)`) partitions the vector space
into 100 clusters.  At query time, only the nearest clusters are searched, reducing
the comparison set by 90–95 % while maintaining > 99 % recall.

For the `publications.embedding` column and `course_grant_specs.embedding`, the
same strategy applies with `lists` proportional to their respective row counts.

**Current limitation:** IVFFlat requires the table to have sufficient data before
index creation (typically ≥ 1 000 rows).  The index should be created as part of
a post-seeding database migration after initial data population.

---

## 8. Deployment Topology for Production

For a single-faculty deployment (1 000–2 000 staff, tens of concurrent users),
the recommended topology is:

```
                     ┌──────────────────┐
                     │   Load Balancer   │
                     │  (Nginx / Caddy)  │
                     └────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
     ┌────────▼────────┐ ┌───▼────────┐ ┌───▼────────┐
     │  FastAPI × 2     │ │  FastAPI   │ │  FastAPI   │
     │  (API workers)   │ │  (worker)  │ │  (worker)  │
     └────────┬─────────┘ └───┬────────┘ └───┬────────┘
              │               │               │
              └───────────────┼───────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
     ┌────────▼────────┐ ┌───▼────────┐ ┌───▼────────┐
     │  PostgreSQL       │ │  Redis     │ │  ARQ/      │
     │  + pgvector       │ │  (cache)   │ │  Celery    │
     └──────────────────┘ └────────────┘ └────────────┘
```

| Component | Scaling Strategy |
|-----------|-----------------|
| FastAPI | Horizontal — add replicas behind load balancer |
| PostgreSQL | Vertical first (more RAM/CPU); read replicas for heavy reporting |
| Redis | Single-node → Sentinel for HA |
| Task Queue | Add ARQ/Celery worker processes independently |

**For the MVP:** A single Docker Compose stack (FastAPI + PostgreSQL + optional Redis)
is fully sufficient and exactly what the current project delivers.

---

## 9. Summary: From MVP to Production

| Concern | MVP (Current) | Production (1 000+ Staff) | Effort |
|---------|--------------|--------------------------|--------|
| Staff search | Full table load + Python filter | SQL `ILIKE` + `pg_trgm` indexes + pagination | Low |
| Connection pool | Default 5 (+10 overflow) | `pool_size=20, max_overflow=10` | Low (one config line) |
| Caching | None | Redis read-through + React Query `staleTime` | Medium |
| Rate limiting | None | `slowapi` per-endpoint limits | Low |
| ORCID sync | Synchronous (blocking) | Background task queue (ARQ) | Medium |
| Vector search | Brute-force cosine | pgvector IVFFlat index | Medium (post-seeding migration) |
| Deployment | Single `uvicorn` process | Docker Compose multi-replica | Medium |

The architecture was designed with these extensions in mind — the database schema
already includes proper foreign-key indexes, the async SQLAlchemy session management
supports connection pooling, and the service layer is stateless (enabling horizontal
replication).  Each productionisation step is an **incremental addition** to the
existing codebase, not a rewrite.

---

## 10. Load Testing Methodology (For Future Work)

To validate the production readiness of these changes, the following load-testing
plan is proposed:

1. **Seed the database** with 1 000 synthetic staff profiles (each with 10–20
   publications and 10–15 expertise tags).
2. **Run Locust** with the following scenario:
   - 50 concurrent virtual users
   - Each user browses the staff directory (paginated), views 3–5 staff profiles,
     and performs 2 keyword searches.
   - Ramp-up over 60 seconds, sustain for 5 minutes.
3. **Success criteria:**
   - p95 response time < 500 ms for staff directory listing
   - p95 response time < 200 ms for staff profile detail
   - Zero connection-pool exhaustion errors
   - PostgreSQL CPU utilisation < 70 %

These benchmarks would be included in a future section of the evaluation chapter
once the productionisation steps are implemented.