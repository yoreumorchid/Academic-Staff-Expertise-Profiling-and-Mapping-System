# Supervisor Meeting Talking Points

## Current progress

- The project now has an end-to-end modular-monolith prototype with React, FastAPI, PostgreSQL, Redis/Celery, authenticated staff/admin flows, and persisted background-job progress.
- Registration, approval, login, password reset, first-login/manual/admin/quarterly expertise synchronization, profile generation, tag refinement, and academic-background management are implemented.
- Staff search and profile consultation work, although access scoping and some search/pagination validation still need completion before a faculty pilot.
- Course/grant specification upload and staff matching work end to end, but the ranking formula still needs evaluation with a small faculty-labelled set.
- Global Topic Coverage now uses OpenAlex Computer Science topics rather than a fixed IEEE query, records provenance and retrieval time, and compares topics with internal capability clusters without claiming true trend prediction.
- Global runs stay on the current page while processing, open the report only when ready, are limited to five completed faculty-wide runs per local day, and retain the latest five reports.
- Peer uploads now create a curriculum overview: obvious dates, examination logistics, marks, and generic web references are excluded, while selected academic headings and excerpts remain auditable.
- I removed Peer nearest-staff and automatic-gap claims because arbitrary handbook passages produced misleading matches and the synthetic thresholds did not validate that business interpretation.
- Gap Analytics currently uses only the newest saved Global report and treats its score as review priority, not probability or proven gap severity; Peer overviews are deliberately excluded.
- Global and Peer work cannot run concurrently, reports are shared only among authorized faculty administrators, and the latest five reports of each type are retained.
- CV snapshot export, a proportional prototype security baseline, and targeted database/search improvements are implemented, while broader end-to-end pilot validation remains outstanding.

## Decisions I need from my supervisor

- What decision should Peer data support: understanding another university’s curriculum, identifying possible internal teaching capability, or claiming a curriculum/staffing gap?
- What should be the valid Peer unit of analysis: course title, title plus description, learning outcomes, topic list, or complete programme?
- Can one syllabus represent only its module, and what minimum collection is required before making any programme- or institution-level statement?
- Are dates, examination rules, marks, regulations, and generic links always out of scope, and what other faculty-specific content should be excluded?
- If Peer alignment is required, should it compare with staff profiles, capability clusters, current course offerings, or a combination of them?
- Should course descriptions remain the primary auditable evidence, or may human-approved topic labels be added; is it acceptable to reject LLM-generated tags as the sole evidence?
- Who can label a small real Peer evaluation set, how many examples are feasible, and what metric or threshold would count as acceptable performance?
- Should Global and future Peer evidence remain side by side, or does the user genuinely need one combined priority ranking?
- If a combined ranking is required, what rationale determines its weights and how should missing, older, or differently dated reports be handled?
- Is “Gap Analysis” still the right name for the current Global-only priority view, or should it be renamed “Global Coverage Priorities” until Peer alignment is validated?
- For Global benchmarking, is current OpenAlex topic prominence sufficient, or must the study add a time window and growth calculation to support an emerging-trend claim?
- For course/grant matching, what does a correct result mean to reviewers, who can provide relevance labels, and which ranking metric should be reported?
- Is the shared `all-MiniLM-L6-v2` embedding baseline acceptable if it performs adequately on labelled examples, or is comparison with one domain-oriented model necessary?
- What is the final golden-set protocol for expertise-tag extraction, and who can confirm the labels used for Precision, Recall, and F1?
- Does the dissertation need a formal comparison of LLM providers, and if so, which fixed dataset, prompt, metrics, and cost/latency conditions should be used?
- Which real or synthetic data may be shown in the demonstration and report, and what permissions or anonymization are required?
- What is the intended deployment/UAT scope: local demonstration, supervised faculty pilot, or production-like deployment, and who are the expected participants?
- What realistic workload should be used for performance testing, including staff count, concurrent users, uploaded records, and expensive operations?
- Which synchronization failure/recovery scenarios must be demonstrated, such as worker restart, broker outage, duplicate delivery, and stale jobs?
- Which FYP report sections and diagrams are already fixed, and may I update the use cases, methodology, evaluation, limitations, database design, and UI figures to match the implementation?

## Proposed next work after the meeting

- First, record the agreed Peer unit, claim boundary, Gap presentation, and validation plan before adding any new scoring logic.
- Finish and verify the descriptive Peer filter with representative clean, administration-heavy, table-based, long, and extraction-poor files.
- If Peer alignment is approved, build a new faculty-labelled course-unit evaluation instead of restoring the old arbitrary chunk-to-staff thresholds.
- Evaluate course/grant matching and expertise-tag extraction with small, decision-focused labelled sets and report the appropriate ranking and classification metrics.
- Validate Global topic relevance and internal-coverage plausibility with administrators, while keeping prominence separate from trend prediction.
- Complete a focused critical-flow acceptance pass covering authentication, synchronization, uploads, benchmarking, matching, exports, and failure feedback.
- Prepare a clean, permission-safe demonstration dataset and a repeatable demo script so the end-to-end FYP contribution can be shown reliably.
- Reconcile README, `use_cases.md`, scalability notes, database/architecture diagrams, and the FYP report after the supervisor decisions are recorded.
- Run a modest load test only after the expected pilot workload is agreed, then optimize measured bottlenecks rather than adding speculative infrastructure.
- Complete queue-recovery checks and deployment documentation only to the level required by the agreed demonstration or faculty-pilot scope.

## Current boundary to explain clearly

- Peer currently answers “What academic content appears in these uploaded files?” and does not answer “Which staff member is closest?” or “What is our institutional gap?”
- One module syllabus may be saved as an overview of that module, but it must not be presented as evidence about the whole peer institution.
- Gap Analytics currently selects the newest retained Global report at generation time; the result is a snapshot and must be regenerated after a newer Global run is saved.
- A future Peer Curriculum Alignment is only a proposal until the unit of analysis, faculty labels, evaluation method, interpretation, and any combined weighting are approved.
