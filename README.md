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
| UC-6 Role-based dashboard | Implemented | Portfolio-derived sidebars, staff/admin view selection, dual-role toggle, and backend portfolio checks exist. |
| UC-7 Consult staff profiles | Partial | Directory, category search, department filter, grouping, and detail views exist. The API still loads the full result set and performs much of the search in Python; pagination and access scoping are pending. |
| UC-8 Generate expertise profiles | Implemented | ORCID identity resolution, OpenAlex publication harvesting, abstract processing, SciBERT extraction, LLM normalization, tag embedding, and persistence exist. Quality still depends on evaluation and tuning. |
| UC-9 Supplement abstract | Implemented | Staff can enter an abstract or upload validated, size-limited PDF/DOCX text; embeddings/tags are refreshed. |
| UC-10 Academic background | Implemented | CRUD plus CSV template download and bulk import are available for education, appointment, award, and service records. |
| UC-11 Refine expertise tags | Implemented | Staff can validate/remove generated tags and add custom tags with embeddings. Mutations are blocked while that user's sync is active. |
| UC-12 Trigger expertise sync | Implemented | First-login, manual, administrator, and quarterly triggers share the Redis/Celery queue and persisted `SyncJob` model. Duplicate active jobs are constrained per user. |
| UC-13 Input course/grant specs | Implemented | Text and validated, size-limited PDF/DOCX ingestion, embedding, listing, and deletion exist. |
| UC-14 Match expertise | Partial | Cosine plus one-hop spreading activation, ranked results, saved reports, optional LLM explanation, and PDF export exist. The scoring design still needs evaluation against a defensible labelled set. |
| UC-15 Global benchmarking | Implemented baseline / administrator validation pending | The system uses the official OpenAlex Computer Science hierarchy, selects two high-output research topics per subfield, compares their name/description embeddings with internal capability clusters, and displays source counts, provenance, nearest clusters, and raw coverage distance. This is current topic coverage for administrator review, not trend prediction or an automatic staffing-gap conclusion. |
| UC-16 Peer benchmarking | Implemented baseline / faculty validation pending | Validated PDF/DOCX upload, deterministic cleaning and token-bounded chunking, nearest-staff and nearest-cluster semantic evidence, persisted provenance, sortable three-way coverage display, UMAP/PCA visualization, and explicit pending-review status exist. Synthetic calibration is reproducible, but real faculty-labelled examples are still required before accuracy claims. |
| UC-17 Gap analysis | Implemented baseline / faculty UAT pending | The UI combines the latest global/peer runs into one source-balanced review queue, retains the underlying evidence, and exposes the provisional 50/50 formula and missing-source warnings. UC-17 is cross-source synthesis and prioritization; it does not turn unvalidated UC-15/16 inputs into ground truth. Faculty management must confirm or revise the weighting during UAT. |
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

### Benchmarking Interpretation Boundary

- **UC-16 peer benchmarking** parses uploaded curriculum documents, produces
  embeddings, compares them with internal staff capability representations, and
  reports reproducible semantic-coverage distances plus their source text. It
  may surface candidate gaps, but a human administrator must confirm whether a
  distant segment is meaningful curriculum evidence or extraction/noise.
- For UC-16, a peer "curriculum document" means a programme-level curriculum or
  a collection that adequately represents the programme across multiple
  courses, such as a four-year study plan plus course titles/descriptions. One
  isolated module syllabus is not sufficient evidence for an institution-level
  peer gap and must not be presented as if it represented the whole programme.
- **UC-17 gap analysis** combines and prioritizes evidence from global and peer
  benchmark runs and may use an LLM to explain the deterministic evidence. It is
  not the first point at which comparison happens, and it cannot make weak
  UC-15/16 evidence valid merely by combining it.
- UC-17 currently uses a provisional 50% global / 50% peer review-priority
  rule requested before faculty UAT. Because global evidence measures distance
  to an internal cluster while peer evidence measures distance to an individual
  staff profile, raw distances are not directly averaged. Evidence is ranked by
  distinct raw distance within its own source, with the weakest coverage assigned
  relative priority `1` and the strongest `0` (a single or fully tied source is
  assigned `1`). The displayed score is
  `source_weight * source_relative_priority`. It determines review order only;
  it is not a probability, accuracy measure, or gap-severity scale. No unvalidated
  semantic topic-pairing is invented between OpenAlex topics and curriculum
  chunks.
- When either source is absent, UC-17 names the missing source and retains the
  available source's 50% weight rather than silently treating it as 100% of the
  evidence. The individual UC-15 and UC-16 views remain available for detailed
  source-specific inspection.
- Embedding comparison avoids generative hallucination in numeric scoring, but
  it is still a machine-learned semantic judgement and can misunderstand
  specialist vocabulary, long text, or mismatched writing styles. Describe it
  as reproducible rather than perfectly objective.
- The current shared `all-MiniLM-L6-v2` model is a small general-purpose
  sentence/paragraph encoder, not a curriculum or scientific-domain truth
  model. Its
  [official model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
  states that inputs longer than 256 word pieces are truncated. PEER-01 therefore
  improves document representation before EMBED-01 asks whether this model is
  sufficiently accurate for this FYP.
- UC-16 uses heading/sentence-aware chunks capped at 220 model tokens with a
  25-token overlap. It returns every retained chunk within the existing
  60-chunk request limit and lets administrators sort the evidence; it no
  longer applies the previous top-25 result truncation. These remain FYP/UAT
  choices rather than universally validated curriculum-analysis constants.
- Until stakeholders confirm weighting rules, every retained peer segment has
  equal importance; the system does not claim that compulsory modules, credit
  weight, programme frequency, accreditation requirements, and one-off mentions
  are equivalent in real curriculum strategy.

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
- UC-16: peer segments labelled as curriculum-relevant/noise and, where
  relevant, covered/partially covered/candidate gap (`PEER-01`).
- UC-17: stakeholder review of cross-source priority and whether the generated
  explanation is faithful to the displayed evidence (`BENCH-03` and `QA-01`).

For the next supervisor UAT, real synchronized staff publication/tag data may be
used as the internal evidence without waiting for the formal labelled sets.
First confirm that synchronization completed and manually inspect/correct the
demonstration staff tags. The external peer input may be a clearly labelled
synthetic programme-curriculum fixture rather than material attributed to a real
university: it should contain a plausible multi-year structure and multiple
course titles/descriptions so expected matches are understandable. Treat this
as a functional UAT smoke check, not real peer-university evidence or the final
accuracy evaluation; the documented 30-50-example evaluation remains
EMBED-01/MAP-01 work.

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

**Goal:** give UC-14 and UC-16 the same small, deterministic document-
representation pipeline before their text is embedded; do not add an LLM parser
or OCR infrastructure for the UAT baseline.

**Acceptance criteria:**

- Continue parsing PDF/DOCX with the existing direct parsers, then remove
  repeated headers/footers and unusably short or administrative-only fragments.
- Split on detected headings, paragraphs, and sentence boundaries. For peer
  curricula, preserve course title, description, learning outcomes, and topic
  lists; for course/grant specifications, preserve title, duties or objectives,
  requirements, and technical topics.
- Produce token-bounded chunks below the selected embedding model's input limit.
  Start with approximately 20-30 tokens of overlap, keep the setting explicit,
  and verify that boundary topics and the final chunk are not lost.
- Generate chunk embeddings in batches rather than one model call per chunk.
- Detect image-only or extraction-poor PDFs and return a clear request for a
  text-based copy. Defer OCR unless representative UAT files demonstrate that it
  is required.
- Provide a preview in which the administrator can include or exclude extracted
  sections before running UC-14 or UC-16. Preserve filename, detected section,
  and exact source excerpt for every retained chunk.
- For UC-16, explain in the upload UI that the intended unit is a complete
  programme curriculum or a multi-document collection covering that programme.
  Warn when the preview appears to contain only one course and require the
  administrator to confirm adequate programme coverage; do not label a single-
  course comparison as an institution-level gap.
- Reuse one focused service from both mapping and peer benchmarking rather than
  implementing two divergent chunking/filtering pipelines.

**Completed 2026-10-18:** UC-14 specification uploads and UC-16 peer-curriculum
uploads now share one deterministic, non-LLM document-representation service.
Both flows are two-stage: the API first returns a review preview, then the
administrator includes or excludes detected sections before ingestion or
analysis. The UI groups sections by file, keeps long previews in a scrollable
collapsed list, provides per-file select/clear controls, and shows default-
excluded administrative material so it can be restored rather than silently
discarded. UC-16 describes the expected input as a complete programme
curriculum or multi-document collection; a conservative single-course
detection produces a warning and requires explicit programme-coverage
confirmation.

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
- Chunks are embedded in one batched call (`EMBEDDING_BATCH_SIZE`, default 32),
  not one inference call per chunk. UC-14 stores an L2-normalized mean of its
  chunk vectors for compatibility with the existing matching formula. The new
  nullable `course_grant_specs.document_payload` JSONB column preserves each
  retained chunk's filename, detected section, exact cleaned source excerpt,
  token count, model, and aggregation rule. UC-16 stores the same provenance in
  the existing benchmark `source_payload`.
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
administrator-review status, with sorting by coverage or subfield. IEEE client
code, settings, and credentials have been removed. OpenAlex basic access needs
no key; `OPENALEX_API_KEY` remains optional.

The October 2026 OpenAlex topic-classifier change affects assignments to topics,
so retrieval and source update dates are retained and results from different
dates must not be treated as a stable time series. Focused tests cover the
official query shape, deterministic distance ordering/provenance, and API
contract. When the FYP report is restored, update UC-15, External Data Sources,
Benchmarking Methodology, Results Presentation, and Limitations with this
current-topic coverage design, the administrator-review boundary, the no-time-
series decision, and the OpenAlex classifier-version caveat.

Verification completed with the three focused BENCH-02 tests and seven affected
PEER-01 regressions passing. The frontend production build passes. Alembic
migration `a61d72e5b904` was applied to the local development database and
`alembic check` reports no new upgrade operations. Live read-only OpenAlex
requests also confirmed the documented primary-topic grouping response and the
batch topic-detail fields used by the implementation.

#### [x] PEER-01 - Validate Peer Curriculum Benchmarking

**Depends on:** BENCH-01 and DOCREP-01.

**Goal:** make UC-16 a reproducible semantic-coverage benchmark that produces
reviewable candidate gaps without requiring an LLM to parse or score documents.

**Acceptance criteria:**

- Treat DOCREP-01 document representation as the first priority: improve
  extraction and remove or isolate obvious non-curriculum noise before changing
  the embedding model, distance formula, threshold, or result count.
- Build a small documented test set covering normal text PDFs/DOCX, a long
  programme curriculum, an administration-heavy document, tables, and a scanned or
  extraction-poor PDF. The UAT fixture may be a synthetic multi-year programme
  curriculum, but its synthetic provenance must be visible in test records and
  any screenshots or exported results.
- Label extracted segments as curriculum-relevant or noise before choosing a
  filter. Measure the noise effect first; prefer deterministic heading,
  sentence, repeated-header/footer, minimum-content, and manual include/exclude
  controls over an LLM parser unless evidence shows they are insufficient.
- Replace character-only chunking with heading/sentence-aware, token-bounded
  DOCREP-01 chunks that remain below the configured embedding model's input
  limit; test the 20-30-token overlap, batched embedding, and final-section
  retention through the UC-16 path.
- Define how segment distance becomes **covered**, **partially covered**, or a
  **candidate gap**, using a small human-labelled development set. Keep the raw
  distance and source excerpt visible for review.
- Each result must show the peer filename, detected section, exact source
  excerpt, nearest staff profile, nearest capability cluster, raw distance, and
  **pending administrator review** status. This evidence display is part of the
  UC-16 result, not an optional LLM explanation.
- Use nearest staff to expose niche expertise that a cluster average can hide,
  while retaining nearest cluster as the institutional summary. Defer cluster-
  headcount weighting unless it becomes a confirmed stakeholder requirement.
- Treat the current top-25 cap as unvalidated. During UAT ask whether users need
  a fixed top-N, a calibrated threshold, all sortable results, or pagination;
  record the chosen display and decision rationale.
- During UAT ask whether compulsory/elective status, credit weight, recurrence
  across programmes, accreditation importance, and single mentions should
  affect priority. Until confirmed and available as reliable input, keep equal
  weighting and display that limitation.
- Ask stakeholders and the supervisor to approve wording that UC-16 surfaces
  **candidate white spaces requiring administrator review**, rather than
  claiming automatically proven institutional gaps. Update `use_cases.md` and
  the FYP report only after that decision.
- Add focused extraction, chunk-completeness, formula, ordering, and API tests;
  document the representative files without committing copyrighted curricula.

**Completed baseline 2026-10-18:** UC-16 now treats every selected curriculum
chunk as reviewable evidence rather than an automatically proven institutional
gap. The raw score is cosine distance to the nearest eligible staff profile,
which exposes niche expertise that a cluster mean can hide. The response also
stores and displays the nearest staff member, nearest internal cluster and its
distance, peer filename, detected section, exact source excerpt, provisional
coverage class, and `pending_administrator_review` status. All retained chunks
within the existing 60-chunk input bound are returned and can be sorted by gap,
coverage, or source; the unvalidated top-25 truncation was removed for UC-16.

The confirmed UAT decisions are to keep retained chunks equally weighted, not
infer compulsory/elective, credit, recurrence, accreditation, or single-mention
importance from unreliable input, and use **candidate coverage gap requiring
administrator review** wording. The optional LLM narrative receives only the
deterministic evidence and is instructed not to claim proven institutional
gaps; it does not parse, score, or classify curriculum text.

`evaluation/datasets/peer_benchmark_synthetic.json` is an explicitly synthetic
development set informed only by the public structure of Stanford and Oxford
Computer Science curriculum pages. No third-party curriculum file is committed.
The documented generated-file matrix covers a normal text PDF, a DOCX table, a
long multi-year programme, administration-heavy content, repeated page
furniture, and an extraction-poor PDF. The repeatable calibration with
`all-MiniLM-L6-v2` selected `covered <= 0.40`, `partially covered <= 0.68`, and
otherwise `candidate gap`, with macro F1 `0.719` on 14 synthetic examples. The
JSON/Markdown report records per-example distances, predictions, the formula,
model, provenance, and confusion matrix.

This is an **implemented synthetic baseline**, not real-faculty validation.
Before reporting UC-16 accuracy, rerun the supplied evaluation workflow with
the institution's permitted UC-14 syllabus/peer examples and faculty or
supervisor labels. `backend/evaluation/PEER_BENCHMARK.md` records that UAT
handoff and the public reference links.

Focused verification passed: 13 PEER-01/DOCREP/upload tests, followed by 7
PEER-01 tests after adding the API-contract and narrative-boundary assertions;
the frontend production build succeeded. Migration `f3a1c9d84e62` was applied
to the local database and
`alembic check` reports no new upgrade operations.

When the FYP report is restored, update the UC-16 use-case flow, benchmarking
methodology, database design, evaluation results, limitations, and UI evidence
figures with the nearest-staff formula, separate cluster summary, synthetic
threshold provenance, equal-weight decision, pending-review wording, and the
requirement for later faculty-labelled calibration.

#### [ ] EMBED-01 - Confirm the Shared Embedding Model Is Good Enough

**Depends on:** DOCREP-01 and the initial PEER-01/MAP-01 UAT examples.

**Goal:** make one small, human-grounded model decision for UC-14 and UC-16;
this task is not a model-tuning research project and does not seek a universally
best embedding model.

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

#### [ ] BENCH-03 - Validate Combined Gap Analysis

**Depends on:** BENCH-02 and PEER-01. EMBED-01 supplies later accuracy evidence
but does not block the initial supervisor UAT.

**Goal:** make UC-17 combine validated global-topic and peer-curriculum evidence
consistently, explainably, and demonstrably.

**Acceptance criteria:**

- Keep global and peer results usable separately. Show source provenance,
  nearest internal cluster, component scores, review status, and supporting
  excerpts where available rather than relying only on an LLM narrative.
- During UAT, ask faculty management whether UC-17 should show the two evidence
  sources side by side or calculate a combined priority. Add global/peer weights
  only when stakeholders confirm both that a combined ranking is useful and how
  the weighting should be interpreted.
- Combined results retain global/peer provenance and handle either source being
  absent with a clear message.
- UMAP failure still yields the existing PCA/table fallback.
- Add focused formula and API tests and document limitations honestly.

**Implementation status (2026-10-18):** the technical baseline is implemented.
UC-17 returns a unified source-balanced review queue with full provenance,
component values, provisional 50/50 weights, missing-source warnings, and an LLM
prompt that preserves the interpretation boundary. The frontend exposes the
formula and supporting evidence rather than relying on the narrative. Focused
formula, missing-source, and contract regressions are in
`test_combined_gap_analysis.py`. The task remains unchecked until faculty UAT
confirms whether the 50/50 rule reflects decision-making practice or supplies a
replacement rule; no stakeholder decision has been fabricated.

Technical verification completed on **2026-10-18**: the four focused BENCH-03
tests passed and the TypeScript/Vite production build succeeded. No Alembic
check was run because this change does not alter database models or schema.

**FYP report update required when the report is available:** revise the UC-17
method/formula, combined-report UI and limitation/UAT subsections to describe
the provisional source-balanced ranking, missing-source behavior, and the fact
that the score is review order rather than validated gap severity.

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

- Build a simple local-only GUI, preferably with Python's standard-library
  Tkinter, that accepts multiple rows containing staff name and ORCID ID plus a
  shared/default department.
- Validate ORCID format/checksum and duplicate ORCID/name rows before making any
  database change. Do not commit staff names, ORCID IDs, generated credentials,
  or exported real data to the repository.
- Generate unique, visibly simulated, non-deliverable email addresses under the
  reserved `example.invalid` domain. Create academic-staff accounts directly in
  `active` state for this demo-only workflow, without sending registration or
  approval notifications.
- Reuse the application's password hashing, SQLAlchemy models, and existing
  durable `SyncJob`/Celery enqueue path. Do not call the harvesting service
  directly or create a second synchronization mechanism. Show enqueue success or
  failure for each created account.
- Provide a destructive reset action that is disabled outside an explicitly
  configured local/development environment. Before it runs, display the resolved
  database target, all accounts that would be removed, and the exact one
  administrator account selected to remain; require typed confirmation and make
  a timestamped backup/export.
- In one transaction, remove the other user-owned/demo analytical data and stale
  benchmark/mapping results while preserving the selected active administrator
  and required schema. Report what was removed. Do not infer the retained
  administrator from role alone when several administrators exist.
- Keep reset and import as separate buttons so the user can preview/validate the
  batch without deleting data. Make reruns detect existing email/ORCID conflicts
  rather than silently duplicating staff.
- After reset/import, run a focused demo-readiness check: retained administrator
  login, expected staff count, one queued/successful sync per imported ORCID, and
  no unexpected pending accounts. Record the commands and recovery steps.
- This utility is developer/demo tooling, not an administrator-facing production
  feature and not part of the normal UC-1/UC-2 registration contract.

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
