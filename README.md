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

> **Status date:** 2026-10-18
>
> **Current focus:** complete the benchmarking methodology and remaining
> critical validation before performance tuning or publication-oriented model
> optimization.

> **Pilot packaging:** a reproducible single-server Docker deployment and a
> guarded local demo-account importer are now implemented. They remain a
> controlled UAT package—not a production-readiness claim—until the outstanding
> QA, sync-recovery, restore-drill, security, and load evidence is completed.

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
| External data | ORCID and OpenAlex |
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
| UC-6 Role-based dashboard | Implemented | Portfolio-derived sidebars, staff/admin view selection, dual-role toggle, and backend portfolio checks exist. The administrator Strategic Dashboard presents a benchmark-independent overview of the most represented expertise areas, profile coverage, staff and department reach, and concise concentration/data-gap signals without exposing individual assignments. |
| UC-7 Consult staff profiles | Partial | Directory, category search, department filter, grouping, and detail views exist. The API still loads the full result set and performs much of the search in Python; pagination and access scoping are pending. |
| UC-8 Generate expertise profiles | Implemented | ORCID identity resolution, OpenAlex publication harvesting, abstract processing, SciBERT extraction, LLM normalization, tag embedding, and persistence exist. Quality still depends on evaluation and tuning. |
| UC-9 Supplement abstract | Implemented | Staff can enter an abstract or upload validated, size-limited PDF/DOCX text; embeddings/tags are refreshed. |
| UC-10 Academic background | Implemented | CRUD plus CSV template download and bulk import are available for education, appointment, award, and service records. |
| UC-11 Refine expertise tags | Implemented | Staff can validate/remove generated tags and add custom tags with embeddings. Mutations are blocked while that user's sync is active. |
| UC-12 Trigger expertise sync | Implemented | First-login, manual, administrator, and quarterly triggers share the Redis/Celery queue and persisted `SyncJob` model. Duplicate active jobs are constrained per user. |
| UC-13 Input course/grant specs | Implemented | Text and validated, size-limited PDF/DOCX ingestion, embedding, listing, and deletion exist. |
| UC-14 Match expertise | Partial | Cosine plus one-hop spreading activation, ranked results, saved reports, optional LLM explanation, and PDF export exist. The scoring design still needs evaluation against a defensible labelled set. |
| UC-15 Global benchmarking | Implemented baseline / administrator validation pending | The system uses the official OpenAlex Computer Science hierarchy, selects two high-output research topics per subfield, compares their name/description embeddings with internal capability clusters, and displays source counts, provenance, nearest clusters, and raw coverage distance in a full report page. Global and peer runs are mutually exclusive, global runs default to five per local day, and the latest five reports per type are retained. UC-15 does not generate an LLM executive summary. This is current topic coverage for administrator review, not trend prediction or an automatic staffing-gap conclusion. |
| UC-16 Peer curriculum overview | Implemented | Validated PDF/DOCX upload, deterministic cleaning, administrator section review, automatic exclusion of obvious dates/examination/web-administration content, persisted source excerpts, full-page reports, and five-run history exist. The overview deliberately performs no staff matching, embedding-based coverage scoring, gap classification, visualization, or LLM synthesis. |
| UC-17 Gap analysis | Implemented baseline / administrator validation pending | Each generation uses the newest retained Global report available at click time and creates a Global-only review-priority queue with full provenance. Peer curriculum overviews are intentionally excluded until a faculty-labelled course-level alignment method has been validated. The displayed priority is not a probability or proven staffing/curriculum gap. |
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
- OpenAlex is the implemented primary external source for UC-15 topic IDs,
  hierarchy metadata, and research-output counts. The baseline uses the official
  `/fields/17`, `/works` grouping, and `/topics` contracts documented at
  https://help.openalex.org/data/topics/ and
  https://help.openalex.org/api/grouping/. It works without an API key; an
  optional free key can provide a larger request allowance. IEEE is not part of
  the active pipeline.
- The FYP UC-15 baseline answers one deliberately limited question: **which
  computer-science topics are represented in the selected global scholarly
  classification, and how strongly does the faculty's current expertise
  representation semantically cover them?** This is global topic coverage, not
  automatic trend prediction.
- A real claim of "emerging global trends" requires a defined recent window,
  baseline window, growth/acceleration calculation, and source provenance. A
  semantic distance plot alone is only thematic coverage comparison.

### Internal Benchmark Representation

Before BENCH-01, UC-15/16 clustered individual rows from the global
`ExpertiseTag` table, which described the vocabulary rather than institutional
capacity. BENCH-01 is now implemented: current UC-15/16 code constructs one
vector per eligible staff profile and clusters those staff vectors. An eligible
profile belongs to an active academic staff member or an
active dual-role administrator and contains at least one usable tag link. For a
staff member `u`, let `E_u` contain links whose tag has a finite, non-zero
embedding and which are either staff-validated or have AI confidence at least
`tau`. Let `e_i` be the L2-normalized embedding for tag `i`. The link weight is:

```text
w_ui = 1                         if the link is staff-validated
       clamp(confidence_ui,0,1) otherwise
```

The staff profile vector is the normalized weighted mean:

```text
raw_profile_u = sum(i in E_u, w_ui * e_i) / sum(i in E_u, w_ui)
profile_u     = raw_profile_u / ||raw_profile_u||_2
```

Validation therefore has full weight while a retained unvalidated AI tag can
contribute only in proportion to its confidence. A user-added tag is already
stored as validated with confidence `1.0`. Links below `tau`, missing or invalid
embeddings, zero-weight links, and profiles left with no usable vector are
excluded. The run must report insufficient internal data instead of inventing
centroids when fewer than three usable staff profiles or fewer than two distinct
profile vectors remain.

K-Means is then fitted to the staff vectors, not the tag vectors. Inputs are
sorted by stable user identifier, K-Means uses k-means++ initialization with an
explicit random seed and multiple initializations, and centroids are normalized
before cosine comparison with external vectors. Candidate `k` values range from
`2` through `min(K_max, staff_count - 1, distinct_profile_count)`. The selected
`k` maximizes mean cosine silhouette; an exact tie selects the smaller model.
Each cluster is labelled with its highest aggregate-weight member tags, with
alphabetical tie-breaking, instead of treating an arbitrary global tag as the
cluster identity.

`tau`, `K_max`, and the K-Means initialization count are small methodological
parameters rather than hidden magic numbers. The selected defaults are
`tau = 0.70`, `K_max = 6`, and `n_init = 10`. `evaluation/scripts/` contains a
DB-independent BENCH-01 sensitivity script that evaluates candidate settings on
a deterministic labelled fixture. It records adjusted Rand index (agreement
with known fixture groups), cosine silhouette, staff coverage, and stability
under repeated input permutations. This synthetic evaluation is a regression
and parameter-sensitivity check, not evidence that the resulting real faculty
clusters are externally valid; BENCH-03 must still validate interpretation on
representative faculty and peer data.

The 2026-10-08 sensitivity run evaluated 32 combinations across deterministic
three-group and six-group fixtures. The selected setting achieved mean ARI
`1.0000`, mean cosine silhouette `0.9921`, staff coverage `1.0000`, and
permutation stability `1.0000`; increasing `n_init` from 10 to 20 did not change
the result. The timestamped Markdown and JSON reports under
`backend/evaluation/reports/internal_expertise_tuning_20261008_033148.*` retain
all tested settings. These values justify stable prototype defaults only, not
real-world cluster validity.

Methodological basis:

- A weighted mean preserves each staff member as the unit of analysis while
  allowing confirmed and uncertain evidence to contribute transparently.
- L2 normalization makes staff profiles comparable by direction and keeps the
  later cosine-distance interpretation consistent with the normalized
  sentence-transformer embeddings.
- K-Means remains the existing KISS clustering method; k-means++ provides
  deliberate centroid seeding and a fixed seed/repeated initialization makes
  this implementation reproducible. See Arthur and Vassilvitskii,
  [k-means++: The Advantages of Careful Seeding](https://theory.stanford.edu/~sergei/papers/kMeansPP-soda.pdf).
- Mean silhouette measures within-cluster cohesion against nearest-cluster
  separation and supplies a bounded, data-dependent choice of `k`. See
  Rousseeuw, [Silhouettes: a graphical aid to the interpretation and validation
  of cluster analysis](https://doi.org/10.1016/0377-0427(87)90125-7) and the
  [scikit-learn silhouette definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html).
- Adjusted Rand index is used only where the evaluation fixture has reference
  groups; it compares partitions while correcting for chance and is invariant
  to cluster-label numbering. See the
  [scikit-learn ARI definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.adjusted_rand_score.html).

### Benchmarking Access, Execution, Retention, and Report Selection

The following rules are the implemented UC-15/16/17 business contract:

- **Access and sharing:** only users holding the `faculty_manager`,
  `head_of_department`, or `deputy_dean_ugpg` portfolio may run benchmarking,
  list history, open retained reports, or generate Gap Analytics. Ordinary
  academic staff cannot access these routes. Reports, history, and limits are
  shared at faculty scope rather than owned privately by the administrator who
  triggered a run.
- **Mutual exclusion:** only one Global or Peer analysis may run at a time for
  the faculty. The UI disables both actions while either is active, and the API
  independently enforces the rule with one PostgreSQL transaction-level
  advisory lock so another browser tab or administrator cannot bypass it.
  Upload preview is preparatory work; the mutual-exclusion rule applies when the
  benchmark analysis begins.
- **Global daily allowance:** at most five successfully persisted Global runs
  are allowed per faculty calendar day by default. Failed or rejected attempts
  are not counted. The API checks the persisted Global run count before calling
  OpenAlex or running embeddings. `GLOBAL_BENCHMARK_DAILY_LIMIT` changes the
  allowance, and `GLOBAL_BENCHMARK_DAILY_TIMEZONE` defines the calendar-day
  boundary; the default timezone is `Asia/Kuala_Lumpur`.
- **Retention:** Global and Peer history each retain only their five newest
  successful reports. Saving a sixth report of a type deletes that type's
  oldest report and its associated evidence through the existing cascade.
  Reports are listed separately by type. A new run keeps the administrator on
  the benchmarking page with an explicit processing state, then navigates the
  current tab only after the report has been fully persisted. Historical report
  links may still be opened separately for comparison.
- **Global output:** UC-15 stores and displays the OpenAlex retrieval time,
  field/topic provenance, research-output counts, embeddings, nearest internal
  clusters, raw cosine distances, visualization inputs, and method details. It
  does not generate an LLM executive summary. The evidence is current topic
  coverage for administrator review, not a trend forecast or proven staffing
  gap.
- **Peer output:** UC-16 is a descriptive curriculum overview. The server
  automatically excludes obvious term dates, examination logistics, marks,
  question-count instructions, and bare website/reference sections even if a
  client attempts to select them. The administrator reviews the remaining
  course/module headings and exact excerpts before saving. The current workflow
  does not embed peer text, identify a closest staff member or cluster, assign a
  coverage label, claim a gap, create a projection, or ask an LLM to interpret
  it. Five Peer overviews are retained separately from five Global reports.
- **Gap Analytics source selection:** every click selects the newest retained
  Global report at that moment. Its ID and creation time are returned and shown
  in the generated response. Peer overview IDs are absent because Peer evidence
  is not used in the score. An already open response is a snapshot and does not
  update when a newer Global report is saved; the administrator must generate it
  again.
- **Gap Analytics calculation:** evidence from the selected Global report is
  ranked by distinct raw semantic distance to internal capability clusters. The
  weakest-covered topic receives relative priority `1`, the strongest `0`, and
  a single or fully tied set receives `1`. The configured Global weight is
  `1.0`; the Peer weight is `0.0`. The displayed value determines review order
  only and is not a probability, accuracy measure, or gap-severity score. An LLM
  may explain this deterministic Global evidence but cannot change its score.

### Benchmarking Interpretation Boundary

- **UC-16 Peer curriculum overview** answers “what academic content appears in
  the uploaded files?” It does not answer “which staff member is closest?” or
  “what is our gap?” Dates, examination mechanics, marks, and bare web/reference
  text are excluded automatically; administrators can further deselect noisy or
  irrelevant sections. A syllabus for one module is valid as an overview of that
  module, but it is not evidence about the whole peer institution.
- **UC-17 Gap Analysis** currently prioritizes evidence only from the newest
  retained UC-15 Global report. This is deliberate: combining validated
  OpenAlex topic evidence with unvalidated arbitrary handbook passages would
  create an apparently precise but methodologically weak result. The report
  shows the selected Global run and retrieval time, is a snapshot, and must be
  regenerated after a newer Global run is saved.
- **Proposed, not implemented:** a future “Peer Curriculum Alignment” may
  compare administrator-confirmed academic units (course/module title plus
  description, learning outcomes, or syllabus topics) with internal capability
  clusters. It should not reduce the source to LLM-invented tags. Before this can
  feed Gap Analytics, faculty reviewers must label representative real units,
  approve the unit of analysis and interpretation, and validate the retrieval or
  ranking method. Only then should stakeholders decide whether Global and Peer
  evidence stay side by side or receive an explicit combined weighting.
Supervisor meeting questions and speaking notes are maintained separately in
[`SUPERVISOR_MEETING_TALKING_POINTS.md`](SUPERVISOR_MEETING_TALKING_POINTS.md).

### Human Validation Plan for Analytical Use Cases

Keep the labelled sets small and decision-focused; this FYP does not require a
large model-training programme.

- UC-8/NLP: publication-to-tag gold labels for extraction precision, recall, and
  F1 (`NLP-01`).
- UC-14: specification-to-relevant-staff judgements for ranking metrics
  (`MAP-01`).
- UC-15: administrator review of whether selected OpenAlex computer-science
  topics are relevant and whether the displayed internal coverage is plausible
  (`BENCH-02`).
- UC-16: peer sections labelled as academic-content/relevant or administrative
  noise to validate the overview filter (`PEER-01`).
- UC-17: administrator review of Global-only priority and whether the generated
  explanation is faithful to displayed evidence (`BENCH-03` and `QA-01`). Any
  later Peer alignment needs a separate faculty-labelled validation set.

For the next supervisor UAT, real synchronized staff publication/tag data may be
used as the internal evidence without waiting for the formal labelled sets.
First confirm that synchronization completed and manually inspect/correct the
demonstration staff tags. The external Peer input may be a clearly labelled
synthetic curriculum fixture rather than material attributed to a real
university. Treat it only as an extraction and overview UAT smoke check, not
evidence of alignment or a final accuracy evaluation.

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

Recommended dependency-aware implementation order as of 2026-10-18:

1. `DOCREP-01` - prepare clean, reviewable text for the next UC-14/16 UAT.
2. `PEER-01` - implemented synthetic baseline; repeat calibration with the
   supplied institutional syllabus and supervisor/faculty labels when available.
3. `BENCH-02` - replace IEEE with the limited OpenAlex UC-15 topic-coverage
   baseline.
4. `BENCH-03` - complete the UC-17 separate-source/combined presentation and
   capture stakeholder decisions about weighting.
5. `MAP-01` - evaluate UC-14 after it uses the shared document representation.
6. `EMBED-01` - use the accumulated UC-14/16 examples for the small formal
   "good enough" embedding evaluation; this does not block the first UAT.
7. `SYNC-01` - validate recovery and operations for the already implemented
   synchronization queue.
8. `QA-01` - run the final critical end-to-end acceptance pass after the core
   analytical and synchronization paths are settled.
9. `DOC-01` - reconcile remaining scalability documentation and the FYP report
   when the report source is available.
10. `DEMO-01` - as the final pre-demo task, rebuild a clean local demonstration
    dataset and enqueue staff synchronization.
11. `PERF-02`, then `PERF-03` - measure first and tune only a proven bottleneck.
12. `DEPLOY-01` - package the verified system for a faculty pilot.
13. `NLP-01`, then `NLP-02`, then `RESEARCH-01` - optional post-core research
    and publication work.

`BENCH-01`, `PERF-01`, `SEC-01`, and `ARCH-01` are complete and should not be
reopened unless a later task exposes a concrete regression.

### P0 - Finish the FYP Core

#### [x] BENCH-01 - Correct the Internal Expertise Representation

**Goal:** make the benchmark compare external concepts with actual institutional
capacity rather than clustering standalone vocabulary rows.

**Acceptance criteria:**

- Define and document the per-staff weighted profile-vector formula.
- Use validated/confident staff-tag links and handle users without embeddings.
- Cluster staff vectors with deterministic parameters and meaningful labels.
- Add focused tests for weighting, empty data, and stable input/vector alignment.
- Update UC-15/16 descriptions and list the affected FYP methodology section.

**Completed 2026-10-08:** UC-15/16 now construct one L2-normalized weighted
vector per active academic or dual-role staff profile from validated tags and
unvalidated AI tags meeting the evaluated `0.70` confidence threshold. Validated
links receive weight `1.0`; retained AI links use their confidence. Invalid or
inconsistent embeddings and empty profiles are excluded. Deterministic K-Means
selects `k` from 2 through at most 6 by cosine silhouette, uses k-means++ with
seed 42 and 10 initializations, normalizes final centroids, and labels clusters
with aggregate-weight representative member tags. A DB-independent sensitivity
script recorded all 32 evaluated parameter combinations; the selected setting
achieved mean ARI `1.0000`, silhouette `0.9921`, coverage `1.0000`, and input-
permutation stability `1.0000` on the stated synthetic fixtures. Five focused
BENCH-01 tests plus the affected UC-16 chunk regression pass. No schema, API
response, or frontend contract changed, so no migration or frontend build was
required.

When the FYP report is restored, update its UC-15 / UC-16 flows and
Benchmarking Methodology / Internal Expertise Representation section with the
staff-vector formula, evidence eligibility and weighting, silhouette-based
cluster-count selection, deterministic parameters, cluster labelling rule,
sensitivity results, and the explicit limitation that synthetic tuning is not
external validation of real faculty clusters.

#### [x] DOCREP-01 - Clean and Structure Uploaded Analytical Documents

**Goal:** give UC-14 and UC-16 the same small, deterministic extraction pipeline;
UC-14 embeds bounded chunks, while UC-16 saves reviewed source sections as a
descriptive overview. Do not add an LLM parser or OCR infrastructure.

**Acceptance criteria:**

- Continue parsing PDF/DOCX with the existing direct parsers, then remove
  repeated headers/footers and unusably short or administrative-only fragments.
- Split on detected headings, paragraphs, and sentence boundaries. For peer
  curricula, preserve course title, description, learning outcomes, and topic
  lists; for course/grant specifications, preserve title, duties or objectives,
  requirements, and technical topics.
- For UC-14, produce token-bounded chunks below the selected embedding model's
  input limit, retain boundary/final content, and generate embeddings in batches.
- For UC-16, retain reviewed academic sections as source excerpts without
  embedding or staff comparison.
- Detect image-only or extraction-poor PDFs and return a clear request for a
  text-based copy. Defer OCR unless representative UAT files demonstrate that it
  is required.
- Provide a preview in which the administrator can include or exclude extracted
  sections before UC-14 ingestion or UC-16 overview creation. Preserve filename,
  detected section, and exact source excerpt for every retained item.
- For UC-16, automatically exclude obvious administrative/examination content,
  enforce that exclusion server-side, and warn that one syllabus describes only
  that material rather than the institution.
- Reuse one focused service from both mapping and Peer overview creation rather than
  implementing two divergent chunking/filtering pipelines.

**Completed 2026-10-18:** UC-14 specification uploads and UC-16 peer-curriculum
uploads now share one deterministic, non-LLM document-representation service.
Both flows are two-stage: the API first returns a review preview, then the
administrator includes or excludes detected sections before ingestion or
analysis. The UI groups sections by file, keeps long previews in a scrollable
collapsed list, provides per-file select/clear controls, and shows default-
excluded administrative material with its reason. UC-16 exclusions cannot be
re-enabled by the client, and single-course detection warns about the limited
scope without blocking a descriptive overview.

The representation is deliberately tolerant of differing document structures:

- PDF parsing retains page boundaries long enough to remove short lines repeated
  in page-header/footer positions. DOCX parsing preserves top-level paragraphs
  and table rows in document order. Page numbers, repeated furniture, unusably
  short fragments, and clearly administrative-only sections are excluded by
  default.
- Numbered headings, common analytical headings, and short all-caps headings are
  detected with explicit rules. These labels are suggestions, not asserted
  semantics. If no reliable heading exists, the service falls back to numbered
  paragraph groups so unfamiliar templates remain reviewable. Extracted source
  text is not summarized or rewritten by an LLM.
- Selected sections are split at paragraph and sentence boundaries using the
  configured embedding model's tokenizer. `DOCUMENT_CHUNK_MAX_TOKENS` defaults
  to 220 but is capped below the model's actual input limit;
  `DOCUMENT_CHUNK_OVERLAP_TOKENS` explicitly defaults to 25. Boundary content
  and the final chunk are retained. UC-14 is limited to 4,500 selected source
  tokens and 24 chunks; UC-16 is limited to 11,000 selected source tokens and
  60 chunks. The preview shows selected tokens and estimated chunks, warns at
  80% of either budget, and disables submission above the limit. Backend token
  counting remains authoritative and over-limit content is rejected rather
  than silently truncated.
- These are conservative FYP/UAT baselines, not claimed universal industry
  constants. Azure AI Search documents 512 tokens with 25% overlap as a common
  starting point for larger embedding systems, while the configured
  `all-MiniLM-L6-v2` model card states that inputs over 256 word pieces are
  truncated and that its fine-tuning used 128-token sequences. The project's
  220-token chunks therefore stay within the smaller model's actual limit; the
  UC-specific total budgets deliberately constrain topic dilution and should be
  revisited only with recorded UAT quality evidence.
- UC-16 accepts at most 8 files per analysis, 10 MiB per file, and 25 MiB for
  the combined request. The per-file and request limits bound parsing/memory
  work; the token/chunk budgets are the accuracy-oriented limits.
- UC-14 chunks are embedded in one batched call (`EMBEDDING_BATCH_SIZE`, default
  32), not one inference call per chunk. UC-14 stores an L2-normalized mean of its
  chunk vectors for compatibility with the existing matching formula. The new
  nullable `course_grant_specs.document_payload` JSONB column preserves each
  retained chunk's filename, detected section, exact cleaned source excerpt,
  token count, model, and aggregation rule. UC-16 stores reviewed source-section
  provenance in the existing benchmark `source_payload` without embeddings.
- Extraction-poor, scanned, or image-only files receive a request for a text-
  based copy. OCR and LLM parsing remain intentionally deferred until UAT files
  demonstrate a need.

Focused DOCREP-01 tests cover repeated page furniture, administrative defaults,
heading-free fallback, token bounds/overlap/final-content retention, source
metadata, batched UC-14 embedding, and exact source-token budget enforcement.
The focused tests and frontend production build pass. Alembic migration
`c9a712e684f1` was applied to the local development database, and `alembic
check` reports no new upgrade
operations.

When the FYP report is restored, update UC-13/14/16 flows, the Document
Processing / NLP Methodology section, the database design, and the limitations
section with the review-before-analysis interaction, deterministic cleaning and
fallback rules, token-bounded batched representation, retained provenance, and
the explicit no-OCR/no-LLM-parser scope.

#### [x] BENCH-02 - Replace the IEEE Fixed-Query Global Benchmark

**Depends on:** BENCH-01.

**Goal:** replace IEEE with a reproducible, FYP-sized OpenAlex computer-science
topic coverage benchmark. Treat time-series trend detection as a later extension
unless stakeholders or the research question require it.

**Acceptance criteria:**

- Verify and use the current official OpenAlex API contract; do not guess fields.
- Remove the eight fixed `GLOBAL_QUERIES` from the active pipeline.
- Retrieve independent OpenAlex topic IDs/names and documented count or
  prominence fields, scoped to computer science; do not download arbitrary
  article samples and describe them as a ready-made trend feed.
- Compute and label a deterministic **topic coverage** comparison against
  internal staff capability. Do not call it an emerging-trend score unless a
  later task adds and validates publication windows and growth evidence.
- Persist source IDs, retrieval date, source query/filter, raw counts, embedding
  model, formula inputs, and enough provenance to reproduce a run.
- Ask stakeholders whether current topic prominence is sufficient for UC-15 or
  whether recent/baseline growth is actually required; record the decision
  before adding time-series complexity.
- Update backend schemas, migration, frontend labels/visuals, `.env.example`,
  tests, README, and the identified report sections together.
- The module works without an IEEE key. IEEE code/config is removed or clearly
  isolated as an optional future licensed source.

**Completed 2026-10-18:** UC-15 now implements a deliberately limited OpenAlex
Computer Science topic-coverage baseline. The stakeholder decision is to use
current prominence rather than time-series growth: academic frontiers take time
to reach university teaching, and staff also need time to acquire and evidence
new capability. The administrative question is therefore which established,
globally active areas appear weakly aligned with current faculty capability and
deserve human review for programme planning, staff development, collaboration,
or recruitment discussion.

The service resolves OpenAlex field `17` and its official subfields at runtime.
For each subfield it groups works by `primary_topic.id` and retains the two
largest groups after limiting the corpus to articles, reviews, books, and book
chapters. This produces a small cross-subfield set without fixed search terms or
arbitrary paper samples. It then embeds each topic name plus description and
computes `1 - max cosine_similarity(topic, internal cluster centroid)`. Higher
distance means weaker semantic coverage only; it is not a trend score, staffing
recommendation, or proven institutional gap.

Each persisted run records retrieval time, OpenAlex field and topic IDs, exact
filters and selection rule, filtered research-output counts, OpenAlex raw counts
and update dates, embedding model and input text, topic embeddings, internal
centroids, and the distance formula. The UI exposes source IDs, subfields,
counts, descriptions, nearest internal clusters, raw distances, and pending
administrator-review status, with sorting by coverage or subfield. Global runs
do not generate an LLM executive summary; the deterministic report opens in a
full page with method details expanded. Global and peer execution is mutually
exclusive, only the latest five reports of each type are retained, and the
configurable global default is five completed runs per Kuala Lumpur calendar
day. IEEE client
code, settings, and credentials have been removed. OpenAlex basic access needs
no key; `OPENALEX_API_KEY` remains optional.

The October 2026 OpenAlex topic-classifier change affects assignments to topics,
so retrieval and source update dates are retained and results from different
dates must not be treated as a stable time series. Focused tests cover the
official query shape, deterministic distance ordering/provenance, and API
contract. When the FYP report is restored, update UC-15, External Data Sources,
Benchmarking Methodology, Results Presentation, and Limitations with this
current-topic coverage design, the administrator-review boundary, the no-time-
series decision, report retention/rate-limit behavior, full-page report flow,
and the OpenAlex classifier-version caveat.

Verification completed with the three focused BENCH-02 tests and seven affected
PEER-01 regressions passing. The frontend production build passes. Alembic
migration `a61d72e5b904` was applied to the local development database and
`alembic check` reports no new upgrade operations. Live read-only OpenAlex
requests also confirmed the documented primary-topic grouping response and the
batch topic-detail fields used by the implementation.

#### [x] PEER-01 - Provide a Defensible Peer Curriculum Overview

**Depends on:** DOCREP-01.

**Current goal:** make UC-16 a reviewable source overview without implying that
arbitrary handbook paragraphs are comparable staff-capability units.

**Implemented decision (2026-10-20):** the earlier synthetic semantic-gap
baseline is superseded. It produced implausible results such as matching term
dates and examination instructions to a “closest staff” member. Synthetic
threshold calibration did not establish that handbook chunks were a valid unit
for institutional gap claims.

The active UC-16 path therefore:

- validates and parses PDF/DOCX files, removes repeated page furniture, and
  shows detected sections for administrator review;
- automatically excludes obvious term dates, examination logistics, marks,
  question-count instructions, and bare website/reference sections, with the
  same exclusion enforced by the server on submission;
- persists selected filename, heading, exact excerpt, and source provenance;
- retains the latest five Peer overviews and opens the completed overview in the
  current tab; and
- performs no Peer embeddings, nearest-staff/cluster retrieval, coverage
  thresholds, gap labels, projection, or LLM narrative.

Migration `91c7e4b2d5a0` makes Peer evidence distance nullable and removes
derived staff/gap fields from historical Peer reports while retaining their
source excerpts. The old synthetic dataset and evaluation artefacts remain only
as an audit trail of the superseded experiment; they must not be cited as
validation of the current overview or a future Peer alignment method.

The next product/research decision is intentionally deferred to
`SUPERVISOR_MEETING_TALKING_POINTS.md`. If course-level alignment is approved, create a new
faculty-labelled evaluation task using administrator-confirmed course/module
units. Do not reactivate the previous chunk-to-nearest-staff thresholds.

When the FYP report is restored, revise UC-16, Benchmarking Methodology,
Evaluation, Limitations, database design, and UI figures to distinguish the
superseded experiment from the implemented descriptive overview.

#### [ ] EMBED-01 - Confirm the Shared Embedding Model Is Good Enough

**Depends on:** DOCREP-01 and MAP-01 UAT examples; a future Peer alignment would
need its own approved examples.

**Goal:** make one small, human-grounded model decision for the active embedded
matching/coverage use cases. UC-16 currently performs no embedding. This task is
not a model-tuning research project and does not seek a universally best model.

**Acceptance criteria:**

- Prepare approximately 30-50 human-judged examples across expertise-tag pairs,
  cleaned course/grant text-to-tag pairs, and cleaned peer-segment-to-tag pairs,
  including clear matches, difficult related pairs, and unrelated pairs.
- Include a small set of peer segments labelled **covered**, **partially
  covered**, or **candidate gap** by the student and, where practical, reviewed
  by the supervisor or a faculty stakeholder.
- Evaluate the existing `all-MiniLM-L6-v2` baseline with simple similarity,
  ranking, and error-review results. Optionally compare at most one
  domain-oriented candidate under the same examples and conditions; do not
  fine-tune a model unless the baseline clearly fails and the FYP scope changes.
- Keep the current model when it is accurate enough for human-assisted review.
  Record the selected model name, exact revision, input limit, dataset version,
  and decision rationale in the evaluation document.
- Freeze the selected model for the remaining FYP implementation. If the
  evaluation selects a different model before the pilot, perform and document a
  one-time regeneration of affected embeddings and reports. Do not build online
  model switching, dual-version storage, or a general migration platform.

#### [ ] BENCH-03 - Validate Gap Analytics and Decide Whether to Combine Sources

**Depends on:** BENCH-02 and the supervisor decisions recorded in
`SUPERVISOR_MEETING_TALKING_POINTS.md`. A future
Peer alignment also depends on a new faculty-labelled validation task.

**Current implementation (2026-10-20):** UC-17 selects the newest retained
Global report, preserves its provenance and raw cluster distances, and produces
a Global-only relative review-priority queue. Global weight is `1.0`; Peer is
explicitly excluded with weight `0.0`. The result is a snapshot and its score is
not a probability or validated gap-severity measure.

The previous provisional 50/50 Global/Peer queue is superseded because the Peer
input is now a descriptive curriculum overview and has no validated comparable
score. Focused tests must preserve this exclusion and the missing-Global error.

**Decision and validation still required:**

- Ask whether the current view should retain the “Gap Analysis” name or be
  renamed to “Global Coverage Priorities”.
- Validate selected Global-topic relevance, cluster alignment plausibility, and
  the faithfulness of any optional LLM explanation with administrators.
- If Peer alignment is later approved and validated, ask whether sources should
  remain side by side or receive a combined priority; add weights only after the
  management decision and interpretation are documented.

**FYP report update required when available:** replace the old 50/50 method with
the current Global-only boundary and clearly mark any future combined method as
proposed until stakeholder-approved and validated.

#### [ ] MAP-01 - Evaluate Course/Grant Matching

**Depends on:** DOCREP-01.

**Goal:** demonstrate that UC-14 ranking is meaningful rather than only runnable.

**Acceptance criteria:**

- Before evaluating weights, use DOCREP-01 to remove repeated/administrative
  noise, retain title, duties/objectives, requirements, and technical topics,
  and represent long specifications as administrator-selected, token-bounded
  sections so the model does not silently judge only a truncated prefix.
- Create a small labelled set of specifications and relevant staff/expertise.
- Select ranking metrics appropriate to the task (for example Precision@K,
  Recall@K, MRR, or nDCG) and justify them.
- Evaluate the existing 0.7 cosine / 0.3 spreading weights and threshold without
  tuning on the final test examples.
- Record baseline results and only change weights when evidence supports it.
- Keep the current best-tag staff score unless labelled errors show that a
  staff-profile representation materially improves ranking; do not add a second
  scoring architecture speculatively.
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

#### [ ] DEMO-01 - Prepare a Clean Local Demonstration Dataset

**Depends on:** QA-01 and DOC-01. Run this only as the final preparation step
before the FYP demonstration, after normal development data is no longer needed.

**Goal:** provide a small local graphical utility that replaces inconsistent
development records with a deliberate demo dataset without requiring the user
to register and approve each academic account manually.

**Acceptance criteria:**

- Build a local-only Tkinter window with separate fields for one staff name,
  ORCID ID, department, and a shared password for the session.
- Validate ORCID format/checksum and duplicate ORCID/name rows before making any
  database change. Do not commit staff names, ORCID IDs, generated credentials,
  or exported real data to the repository.
- Continue the confirmed local login convention
  `academic_staff[N]@um.edu.my` from the highest preserved number. Create
  academic-staff accounts directly in `active` state for this demo-only
  workflow, without sending registration or approval notifications.
- Reuse the application's password hashing, SQLAlchemy models, and existing
  durable `SyncJob`/Celery enqueue path. Do not call the harvesting service
  directly or create a second synchronization mechanism. Show enqueue success or
  failure for each created account.
- Provide a destructive reset action that is disabled outside an explicitly
  configured local/development environment. Before it runs, display the resolved
  database target, all accounts that would be removed, and every non-academic
  account selected to remain; require typed confirmation and make
  a timestamped backup/export.
- In one transaction, remove the other user-owned/demo analytical data and stale
  benchmark/mapping results while preserving all faculty-administrator accounts
  and required schema. Report what was removed.
- Keep reset and staff entry in separate GUI tabs so the user can preview and
  validate entries without deleting data. Make reruns detect existing name and
  ORCID conflicts rather than silently duplicating staff.
- After reset/import, run a focused demo-readiness check: retained administrator
  login, expected staff count, one queued/successful sync per imported ORCID, and
  no unexpected pending accounts. Record the commands and recovery steps.
- This utility is developer/demo tooling, not an administrator-facing production
  feature and not part of the normal UC-1/UC-2 registration contract.

**Partially implemented 2026-10-19:** `python -m app.tools.demo_accounts` opens
a Tkinter window with one-person input fields, a reviewable pending list, a
shared hidden password, queue results, and a separate reset-preview tab. The
Windows launcher `backend/launch_demo_accounts_gui.cmd` opens the same window
by double-click; existing CLI commands remain available. The tool validates ORCID checksums and
session/database duplicates, assigns the existing incrementing
`academic_staff[N]@um.edu.my` login format, preserves faculty administrators,
and requires a `pg_dump` backup plus exact confirmation before reset. Account
creation reuses the durable synchronization queue. See `docs/DEPLOYMENT.md`.
The local reset has not yet been executed, staff have not yet been entered, and
the post-sync readiness check remains outstanding.

When the FYP report is restored, document this only as local demonstration-data
tooling in the Implementation/Test Data Preparation section; it is not a new
administrator use case or a production bulk-account interface.

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

**Partially implemented 2026-10-18:** `deploy/compose.yaml` packages PostgreSQL, persistent
Redis, a one-shot Alembic migration, FastAPI, scalable Celery workers, exactly
one Beat scheduler, the built React/Nginx frontend, and Caddy HTTPS on one Linux
host. It includes service health checks, JSON application/access logs with
rotation, externalized secrets, persistent data/model-cache volumes, guarded
backup/restore scripts, and documented migration, diagnosis, scaling, update,
rollback, and shutdown procedures in `docs/DEPLOYMENT.md`. This is a faculty-
pilot/UAT package. Live HTTPS deployment, a restore drill, QA-01, SYNC-01, and
PERF-02/03 evidence remain outstanding, so the project is not described as
production-ready.

When the FYP report is restored, update Deployment Architecture, Operational
Recovery, Security Limitations, and Performance Evaluation with the single-host
pilot topology, one-Beat invariant, secrets boundary, health/logging behavior,
backup/rollback procedure, and remaining evidence gates.

Compose configuration parsing passes, but a real Linux image build, HTTPS
launch, migration run, and restore drill are still required before this task can
be checked complete.

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

UC-15 works with OpenAlex basic access and does not require IEEE credentials.
An OpenAlex API key is optional for a larger request allowance.

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
- `test_internal_expertise.py`: BENCH-01 weighting, evidence filtering, empty
  data, per-staff observations, and deterministic input/vector alignment.
- `test_combined_gap_analysis.py`: BENCH-03 within-source ranking, provisional
  source weighting, provenance retention, missing-source messaging, and
  interpretation-boundary regressions.

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

BENCH-01 verification completed on **2026-10-08**:

- parameter evaluation: 32 settings recorded in
  `internal_expertise_tuning_20261008_033148.json` and `.md`; selected
  `tau=0.70`, `K_max=6`, and `n_init=10`;
- focused backend: **6 tests passed** across the new internal-expertise suite
  and the affected peer-document chunk regression;
- Alembic: not run because no database model or schema changed;
- frontend: not built because no frontend source or client-facing API contract
  changed.

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
