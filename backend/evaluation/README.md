# Evaluation Suite

This directory contains reproducible evaluation scripts to measure the reliability of this system. Each script produces a Markdown report and a companion JSON file under `reports/`.

---

## Quick Start

All scripts run from the `backend/` directory with the virtual environment activated:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1

# Example: run NLP evaluation
python -m evaluation.scripts.eval_nlp --gold evaluation/datasets/gold_tags.jsonl
```

---

## NLP Tag Extraction Accuracy

**`eval_nlp.py`**

| Aspect | Detail |
|--------|--------|
| **Purpose** | Measure how accurately the SciBERT → LLM pipeline extracts expertise tags from publication abstracts |
| **Input** | `datasets/gold_tags.jsonl` — hand-curated (publication_id, title, abstract, gold_tags) |
| **Metrics** | **Precision**, **Recall**, **F1** (both *hard match* — exact string after normalisation, and *soft match* — SciBERT cosine similarity ≥ 0.70) |
| **Runs** | Two pipelines compared side-by-side: **SciBERT-only** (raw keyword extraction) vs **SciBERT + LLM** (normalised canonical tags) |
| **Acceptance** | Hard-match F1 ≥ 0.85, Soft-match F1 ≥ 0.90 |
| **Usage** | `python -m evaluation.scripts.eval_nlp --gold evaluation/datasets/gold_tags.jsonl --k 10` |
| **Flags** | `--k 5` for stricter Top-5; `--verbose` to print per-paper predictions; `--emit-pairs <csv>` to dump raw/normalised/gold triples for Study 3 |

---

## LLM Provider Comparison

**`eval_llm.py`**

| Aspect | Detail |
|--------|--------|
| **Purpose** | Quantitatively compare multiple LLM providers (DeepSeek, GPT-4o-mini, Gemini 2.0 Flash, custom) on the same tag-normalisation task to answer: *"Is DeepSeek's quality acceptable despite its lower cost? What is the concrete trade-off?"* |
| **Input** | `datasets/gold_tags.jsonl` — the same gold set used by Study 1 |
| **Metrics** | **Hard/Soft Precision, Recall, F1** (same definitions as Study 1), **Success Rate** (fraction of papers where the LLM returned parseable JSON), **p50/p95 Latency**, **Estimated Cost per 1 000 papers**, **Error Categorisation** (json_parse_error, api_timeout, empty_response, api_other) |
| **Runs** | Each provider goes through the identical SciBERT → LLM pipeline. The script temporarily overrides the LLM factory with provider-specific credentials, runs all gold-set papers, then restores the original configuration |
| **Providers** | `deepseek` (needs `DEEPSEEK_API_KEY`), `gpt4o-mini` (needs `OPENAI_API_KEY`), `gemini` (needs `GEMINI_API_KEY`, uses Google's OpenAI-compatible endpoint), `custom` (generic OpenAI-compatible endpoint via `EVAL_LLM_*` env vars) |
| **Usage** | `python -m evaluation.scripts.eval_llm --gold evaluation/datasets/gold_tags.jsonl --providers deepseek,gpt4o-mini,gemini` |
| **Flags** | `--sample 10` to test on first N papers only; `--k 15` for SciBERT top-K; `--quiet` to suppress console output; `--providers deepseek` for single-provider run |
| **Output** | A Markdown + JSON pair under `reports/llm_comparison_*.md` and `.json` containing the aggregate metrics table, per-provider error breakdown, per-paper predictions, and an interpretation guide |

---

## Staff Tag Validation

**`eval_staff_tags.py`**

| Aspect | Detail |
|--------|--------|
| **Purpose** | Validate AI-extracted tags against staff self-declared expertise areas — do the fine-grained publication-anchored tags semantically cover what the staff member said they do? |
| **Input** | AI tags (from DB via `--user-id`, or CLI via `--ai-tags`, or JSON file via `--ai-tags-file`) + self-declared areas (`--self-declared` or `--self-declared-file`) |
| **Metrics** | **Self-declared coverage rate** (fraction of self-declared areas covered by ≥1 AI tag above threshold), **AI anchor rate** (fraction of AI tags that map to ≥1 self-declared area), **Discovery tags** (AI tags with no self-declared equivalent), **Gap analysis** (vocab/granularity/publication gap classification) |
| **Method** | SciBERT soft-cosine similarity with parent-chain boosting (walks the `parent_label` hierarchy to bridge vocabulary gaps like "Software Defect Prediction" → "Software Engineering" → "Empirical Software Engineering") |
| **Threshold** | Cosine ≥ 0.65 (softer than Study 1 to accommodate course-catalogue vs. publication vocabulary) |
| **Usage** | `python -m evaluation.scripts.eval_staff_tags --user-id <uuid> --self-declared "Data Mining, Software Engineering"` |
| **Data** | Provide a staff member's self-declared areas (from UMExpert or their CV). AI tags can be pulled from the DB or specified manually |

---

## Supporting Tools

### `build_gold_set.py` — Sample publications for annotation

```powershell
python -m evaluation.scripts.build_gold_set --n 50 --out evaluation/datasets/_to_annotate.csv
```

Stratified-samples N publications (by department) from the database, outputting a CSV with columns `publication_id`, `title`, `abstract`, `user_full_name`, `department`, plus empty `gold_tags` and `notes` columns for annotators to fill in.

### `prepare_data.py` — Solo-developer annotation workflow

If you are working alone (no external annotators), maintain a single wide CSV (`my_raw_annotation.csv`) with columns:

```
publication_id, title, abstract, author_tags, ai_tags, final_gold_tags
```

Run this script to split it into the three canonical files that feed `iaa_kappa.py` and `eval_nlp.py`:

```powershell
python -m evaluation.scripts.prepare_data --raw evaluation/datasets/my_raw_annotation.csv
```

### `iaa_kappa.py` — Inter-Annotator Agreement

```powershell
python -m evaluation.scripts.iaa_kappa --a evaluation/datasets/annotator_author.csv --b evaluation/datasets/annotator_ai.csv
```

Computes **Cohen's κ** between two annotators on the same gold set. Target: κ ≥ 0.60 ("substantial agreement"). Run this before treating a merged set as ground truth.