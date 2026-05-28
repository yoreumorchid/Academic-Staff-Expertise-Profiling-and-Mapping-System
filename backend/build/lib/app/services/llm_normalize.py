"""LLM-driven semantic normalization (UC-8 steps 5 and 6).

After SciBERT surfaces candidate technical phrases, an LLM is asked to
collapse near-duplicates (e.g. "CNN", "convolutional neural network")
into a single canonical domain label ("Computer Vision"). LangChain's
structured-output binding guarantees a strict JSON response so we never
have to parse free-form prose.

The same factory powers UC-15 / UC-17 narrative synthesis through
:func:`synthesize_narrative`, keeping every LLM call within one module
for auditability.
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.exceptions import ExternalServiceError
from app.services.llm import get_chat_llm

logger = logging.getLogger(__name__)


class NormalizedTag(BaseModel):
    """One row in the LLM response."""

    canonical_label: str = Field(
        description="Broad, standardized expertise domain (e.g. 'Computer Vision')."
    )
    domain: Optional[str] = Field(
        default=None,
        description="Higher-level discipline (e.g. 'Artificial Intelligence').",
    )
    source_phrases: List[str] = Field(
        default_factory=list,
        description="The raw candidate phrases that mapped to this canonical label.",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="LLM's self-reported confidence in the mapping.",
    )


class NormalizationResult(BaseModel):
    tags: List[NormalizedTag] = Field(default_factory=list)


_PROMPT_TEMPLATE = """You are an academic expertise normalization engine.

Below is a list of raw technical phrases extracted from a researcher's
publication abstracts. Group them into a small set of broad, well-known
canonical expertise domains. Resolve abbreviations to their full names
(e.g. "CNN" -> "Computer Vision"; "NLP" -> "Natural Language Processing";
"GAN" -> "Generative Models"). Merge near-synonyms. Drop overly generic
words (e.g. "method", "analysis").

Return strictly valid JSON matching this schema:

{{
  "tags": [
    {{
      "canonical_label": "<broad domain name>",
      "domain": "<higher-level discipline or null>",
      "source_phrases": ["<original phrase>", ...],
      "confidence": <float between 0 and 1>
    }}
  ]
}}

Aim for between 3 and 12 tags. Do not include any prose outside the JSON.

Raw phrases:
{phrases}
"""


async def normalize_keywords(phrases: List[str]) -> List[NormalizedTag]:
    """Map raw SciBERT keywords to canonical expertise tags via the LLM."""
    if not phrases:
        return []

    llm = get_chat_llm()
    prompt = _PROMPT_TEMPLATE.format(
        phrases="\n".join(f"- {p}" for p in phrases[:80])
    )

    try:
        response = await llm.ainvoke(prompt)
    except Exception as exc:  # noqa: BLE001 — surface as 503 to the client.
        logger.exception("LLM normalization call failed")
        raise ExternalServiceError(
            "LLM provider failed to respond during semantic normalization."
        ) from exc

    content = getattr(response, "content", str(response)).strip()
    # Strip optional ``` fences that some providers prepend.
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip().rstrip("`").strip()

    try:
        parsed = NormalizationResult.model_validate_json(content)
    except Exception:  # noqa: BLE001 — try a tolerant JSON fallback.
        try:
            raw = json.loads(content)
            parsed = NormalizationResult.model_validate(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM returned non-JSON payload: %s", content[:300])
            raise ExternalServiceError(
                "LLM returned an unparseable normalization payload."
            ) from exc

    return parsed.tags


async def synthesize_narrative(prompt: str) -> str:
    """Generic LLM call used by UC-15 / UC-17 to author gap-analysis prose."""
    llm = get_chat_llm()
    try:
        response = await llm.ainvoke(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM narrative synthesis call failed")
        raise ExternalServiceError(
            "LLM provider failed to respond during narrative synthesis."
        ) from exc
    return getattr(response, "content", str(response)).strip()
