# ExpertiseInsight — Evaluation Suite

This folder contains everything needed to run the five evaluation studies
described in the project Methodology chapter:

| # | Study | Script | Input file(s) | Output |
|---|---|---|---|---|
| 1 | NLP tag extraction (P/R/F1, ablation) | `scripts/eval_nlp.py` | `datasets/gold_tags.jsonl` | `reports/nlp_<date>.json` + `.md` |
| 2 | Recommender Top-N accuracy | `scripts/eval_recommender.py` | `datasets/gold_recommendations.jsonl` | `reports/recommender_<date>.json` + `.md` |
| 3 | Terminology normalization expert review | `scripts/eval_expert_review.py` | `datasets/expert_review.csv` | `reports/expert_review_<date>.json` + `.md` |
| 4 | Sync coverage vs. UMExpert | `scripts/eval_sync_coverage.py` | `datasets/profile_completion.csv` | `reports/sync_coverage_<date>.json` + `.md` |
| 5 | Time-on-task / efficiency | `scripts/eval_efficiency.py` | `datasets/efficiency.csv` | `reports/efficiency_<date>.json` + `.md` |

There is also one supporting tool:

| Tool | Purpose |
|---|---|
| `scripts/build_gold_set.py` | Sample N random publications from the DB and emit a CSV for human annotators |
| `scripts/iaa_kappa.py`      | Compute Cohen's Kappa between two annotators on the same gold set |

All scripts are runnable from the `backend/` directory after activating
your `.venv`, e.g.:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m evaluation.scripts.build_gold_set --n 50 --out evaluation/datasets/_to_annotate.csv
python -m evaluation.scripts.eval_nlp        --gold evaluation/datasets/gold_tags.jsonl
```

---

## What you (the human) must supply

There are **5 input artefacts** you need to produce by hand. Each one has
a strict format below. Place every file under `evaluation/datasets/`.

### 1. `gold_tags.jsonl` — NLP gold standard (Study 1)

**Why:** ground truth for measuring Precision / Recall / F1 of the
SciBERT-only and SciBERT+LLM pipelines.

**How to obtain:**
1. Run `python -m evaluation.scripts.build_gold_set --n 50` — this
   exports 50 stratified-by-department publications into
   `datasets/_to_annotate.csv` with columns
   `publication_id,title,abstract,user_full_name,department`.
2. Send the CSV to **2 independent annotators** (domain experts).
3. Each annotator adds two columns:
   - `gold_tags` — comma-separated canonical expertise tags they would
     assign after reading the abstract (3–8 tags).
   - `notes` — optional free text.
4. Merge the two annotations (you keep the tags both annotators agreed
   on; for disagreements, ask a third reviewer to break the tie).
5. Save the final merged result as JSONL using this schema **(one
   object per line, no trailing comma)**:

```json
{"publication_id":"e9f0...-uuid","title":"...","abstract":"...","gold_tags":["computer vision","medical image segmentation","convolutional neural network"]}
```

**Minimum size:** 30 publications. **Recommended:** 50.
**Pre-flight check:** run `python -m evaluation.scripts.iaa_kappa
--a annotator_a.csv --b annotator_b.csv` and confirm **Cohen's κ ≥ 0.60**
before treating the set as gold.

**Annotation rules to give the annotators (paste this verbatim into
your email):**

> - Read only the title + abstract. Do not Google the author.
> - List **between 3 and 8 tags** per paper.
> - Each tag is a **broad domain** (e.g. "Computer Vision"), **not a
>   method name** ("ResNet-50") and **not a generic word** ("analysis").
> - Expand abbreviations: write "Natural Language Processing", not "NLP".
> - Use lowercase, separate tags by commas, no quoting.
> - If the abstract is too short / off-topic, leave `gold_tags` empty
>   and add a note "SKIP — insufficient signal".

---

### 2. `gold_recommendations.jsonl` — Recommender ground truth (Study 2)

**Why:** measure Hit@5, Precision@5, MRR, nDCG@5 for the course / grant
matching engine, with an ablation against cosine-only and
spreading-only.

**How to obtain:**
1. Collect **10 real items**: 5 grant calls (PDF or text) + 5 course
   syllabi. Anonymise them if needed.
2. Recruit **2 senior academics** (ideally HoDs). Give each one the
   item *and* a printed list of all active staff names + departments
   (NOT the system's recommendation list).
3. Ask each reviewer to pick the **top-5 staff** they would recommend.
4. Merge the two lists into a single ground-truth set per item
   (union, with reviewer overlap flagged — overlap = stronger signal).

**Schema:**

```json
{
  "item_id": "grant_001",
  "item_type": "grant",
  "title": "AI-driven medical diagnostics seed grant",
  "raw_text": "<full call text, ≥ 80 chars>",
  "expert_picks": [
    "uuid-of-staff-1",
    "uuid-of-staff-2",
    "uuid-of-staff-3",
    "uuid-of-staff-4",
    "uuid-of-staff-5"
  ],
  "expert_picks_consensus": ["uuid-of-staff-1", "uuid-of-staff-3"]
}
```

`item_type` must be one of `course` | `grant`. `expert_picks` is the
union; `expert_picks_consensus` is the intersection (optional but
useful for a stricter score).

---

### 3. `expert_review.csv` — Terminology normalization Likert (Study 3)

**Why:** prove that the LLM normalization step ("CNN" → "Computer
Vision") is preferred by domain experts over raw SciBERT keywords.

**How to obtain:**
1. Pick **20 staff** that already have ≥ 5 harvested tags in the DB.
2. For each, export the **raw SciBERT keywords** and the **LLM
   normalized tags** side-by-side. (Use `eval_nlp.py --emit-pairs`
   which dumps the two columns automatically.)
3. Hand the table to **3 senior academics**. Each scores every pair on
   a 5-point Likert and picks a preference.

**Schema (one row per pair, per reviewer):**

| Column | Type | Allowed values |
|---|---|---|
| `staff_id` | uuid | from DB |
| `reviewer_id` | str | `R1`, `R2`, `R3` |
| `raw_keywords` | str | semicolon-separated |
| `normalized_tags` | str | semicolon-separated |
| `accuracy` | int 1–5 | does normalized correctly represent domain? |
| `specificity` | int 1–5 | is granularity right (not too broad, not too narrow)? |
| `preference` | str | `raw` \| `normalized` \| `tie` |
| `comment` | str | optional |

---

### 4. `profile_completion.csv` — UMExpert coverage (Study 4)

**Why:** show that automated harvesting yields a richer profile than
manual UMExpert entry, justifying the "no double-entry" claim.

**How to obtain:**
1. Pick **20 staff** with public UMExpert profiles AND a working ORCID.
2. Manually transcribe their UMExpert "Research Interests" field.
3. Export the system's `UserExpertiseTag` list for each.

**Schema:**

| Column | Type | Notes |
|---|---|---|
| `staff_id` | uuid | from `users` table |
| `staff_name` | str | for traceability |
| `umexpert_interests` | str | semicolon-separated, as written on UMExpert |
| `system_tags` | str | semicolon-separated, copied from the system |
| `umexpert_pub_count` | int | publications listed on UMExpert |
| `system_pub_count` | int | publications in our DB |
| `system_latest_year` | int | most recent publication year in our DB |
| `umexpert_latest_year` | int | most recent publication year listed on UMExpert |

Script computes: coverage uplift, recency uplift, completeness rate.

---

### 5. `efficiency.csv` — Time-on-task experiment (Study 5)

**Why:** quantify the manual-labour reduction vs. the existing workflow.

**How to obtain:**
1. Recruit **3 participants** (admin staff or postgrads).
2. Give each the SAME 10 staff CVs (PDF).
3. Time them on the **manual** task: read each CV, write 5 expertise
   tags + a 50-word bio.
4. Then time them using the **ExpertiseInsight export** flow for the
   same 10 staff.

**Schema:**

| Column | Type | Notes |
|---|---|---|
| `participant_id` | str | `P1`, `P2`, `P3` |
| `staff_id` | uuid | one row per (participant × staff × mode) |
| `mode` | str | `manual` \| `system` |
| `time_seconds` | int | elapsed wall-clock |
| `tags_produced` | int | number of distinct expertise tags written / accepted |
| `subjective_load` | int 1–10 | NASA-TLX-lite self-report |

---

## Acceptance thresholds (used in `reports/*.md`)

| Metric | Target | Source |
|---|---|---|
| Inter-annotator κ (Study 1) | ≥ 0.60 | Cohen 1960; Landis & Koch 1977 ("substantial") |
| NLP F1 (hard match, K=10) | ≥ 0.85 | Project SLA |
| NLP F1 (soft match, K=10) | ≥ 0.90 | Project SLA |
| Recommender Hit@5 | ≥ 0.80 | Project SLA |
| Recommender MRR | ≥ 0.60 | Project SLA |
| Expert review preference for normalized | ≥ 75 % | Project SLA |
| Coverage uplift vs. UMExpert | ≥ +100 % tags | Project SLA |
| Sync job success rate | ≥ 95 % | Operations target |
| Time reduction (system vs. manual) | ≥ 5× faster | Project SLA |

---

## Threats to validity (write up in §4.8 of your report)

- Sample size limited to UM staff; results may not generalise to other
  institutions.
- Annotator pool is small (n=2) — mitigated by Cohen's κ reporting.
- Recommender ground truth depends on HoD subjective judgement.
- LLM responses are non-deterministic; rerun with `temperature=0` and
  cache responses for reproducibility.
- Efficiency experiment has only 3 participants — report effect size
  and confidence interval, not just means.
