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


_PROMPT_TEMPLATE = """You are an academic-expertise normalization engine. Your job is to
read a research paper's ABSTRACT plus a list of candidate phrases that
were mechanically extracted from it, and output the broad research
sub-fields this paper belongs to. The downstream consumer is a
faculty-management dashboard that needs to know "what research areas
does this professor work in".

############################################################
# THE ONE ACID TEST every tag must pass:
#
#   "Could a professor reasonably list this verbatim under
#    'AREAS OF EXPERTISE' on their CV / faculty profile page?"
#
# Examples of tags that PASS the acid test (these are taken from
# real faculty CVs and university expertise directories):
#
#   - Cloud Infrastructure
#   - Computer Intrusion Detection and Prevention System
#   - Digital Security Services
#   - Data Science Programming and Computing
#   - Predictive Modelling
#   - Cryptography
#   - Wireless Sensor Networks
#   - Internet of Things
#   - Computer Vision
#   - Natural Language Processing
#   - Software Engineering
#   - Software Quality Assurance
#   - Health Informatics
#   - Environmental Governance
#   - Atmospheric Science
#   - Multi-Criteria Decision Making
#   - Educational Technology
#   - Virtual Reality
#
# Examples of tags that FAIL the acid test (no professor would put
# these verbatim on a CV — they are descriptions, narrow tasks, or
# topic phrasings):
#
#   - "Stakeholder Engagement"            (activity, not a research field)
#   - "Institutional Factors in Healthcare" (essay subtitle, not a field)
#   - "Customer Review Analysis"          (a task, not a research area)
#   - "Block Ciphers"                     (a specific cipher family;
#                                          use "Cryptography")
#   - "Fuzzy C-Means"                     (an algorithm;
#                                          use "Fuzzy Logic" or
#                                          "Unsupervised Learning")
#   - "Visual Programming"                (different field from
#                                          program comprehension; do
#                                          not invent)
#   - "Software Maintenance" / "Software Security" /
#     "Software Performance" / "Software Reliability"
#     when the abstract does NOT actually study them (do not
#     hallucinate adjacent SE sub-areas).
#   - "Singapore Politics", "Indonesia Studies",
#     "Pandemic Policy"                   (country labels or event
#                                          labels are NOT research
#                                          fields unless the paper IS
#                                          area studies / public-health
#                                          policy work)
#   - "Norm Diffusion", "Humanitarian Advocacy", "Psychotherapy"
#                                         (random adjacent ideas not
#                                          actually in the abstract)
#
# When in doubt: prefer fewer, broader, more canonical tags over
# more, narrower, descriptive ones.
############################################################

CRITICAL RULES (violations are common LLM mistakes — do NOT make them):

1. **Use the abstract as the source of truth.** The candidate phrases
   are noisy hints; the abstract tells you what the paper is actually
   about. If a phrase appears generic in isolation (e.g. "product",
   "feature", "rate") but the abstract clarifies it (e.g. "software
   product quality"), use the abstract-clarified meaning.

2. **Do NOT do surface-word association.** Common mistakes to avoid:
   - "feature extraction" in a sentiment-analysis paper is NOT
     "Feature Engineering"; it is "Opinion Mining" or "Aspect-Based
     Sentiment Analysis".
   - "product" / "software product" in a quality-metrics paper is NOT
     "Product Management"; it is "Software Quality Assurance" or
     "Software Metrics".
   - "rate" in a network-classification paper is NOT "Rate-Distortion
     Theory"; it is "Network Performance".
   - "review" in a study that performs a literature review IS
     "Systematic Review"; but "customer review" is NLP / Opinion Mining.

3. **NEVER output methodology / research-design labels as tags.**
   These describe HOW the research was done, not WHAT field it is in.
   FORBIDDEN labels include:
     "Systematic Review", "Literature Review", "Meta-Analysis",
     "Survey Methodology", "Structural Equation Modeling",
     "Bibliometric Analysis" (allowed ONLY if the paper IS a
     bibliometric study of a research field — rare),
     "Cross-Sectional Study", "Qualitative Research",
     "Experimental Study", "Case Study", "Statistical Analysis".
   If a paper IS a literature review of, say, VR safety training,
   output "Virtual Reality" + "Safety Training", NOT "Systematic Review".

4. **NEVER output specific algorithms, models, or technique names as
   tags.** Lift them to the parent research field. FORBIDDEN examples:
     "Latent Dirichlet Allocation"        -> "Topic Modeling"
     "Fuzzy AHP-TOPSIS"                   -> "Multi-Criteria Decision Making"
     "Feature Extraction" (as a tag)      -> "Information Extraction" or
                                              "Opinion Mining" depending
                                              on context
     "Heuristic Pattern-Based Methods"    -> "Information Extraction"
     "Pattern Mining"                     -> "Data Mining"
     "Topic Coherence"                    -> "Topic Modeling"
     "Backdoor Attacks" / "Model Poisoning" / "Label Flipping"
                                          -> "Adversarial Machine Learning"
     "Routing Attack Detection"           -> "Network Security" or
                                              "Intrusion Detection System"
     "URL Filtering"                      -> "Web Content Filtering"

5. **NEVER output disease names, anatomical structures, clinical
   conditions, or population-specific labels as tags.** Lift to the
   underlying CS / informatics field. FORBIDDEN examples:
     "Aortic Stenosis", "Left Ventricular Remodeling",
     "Wall Motion Analysis"      -> "Cardiac Image Analysis" or
                                     "Medical Imaging"
     "Childhood Obesity",
     "Dietary Habits",
     "Physical Activity"          -> "Health Informatics" or
                                     "Health Behavior Intervention"
     "Pedestrian Safety",
     "Child Safety"               -> "Safety Engineering" or
                                     "Educational Technology"

6. **Lift narrow devices / formats / protocols to their host field.**
     "Head-Mounted Displays" alone -> "Virtual Reality"
     "Role-Playing Games" alone     -> "Educational Technology" or
                                       "Game-Based Learning"
     "RPL Protocol" / "OpenFlow"    -> "Routing Protocols" or
                                       "Software-Defined Networking"
   If you have already output the parent field, DO NOT also output the
   device name as a separate tag.

7. **Expand abbreviations to canonical full forms**:
   CNN -> Convolutional Neural Networks (or Computer Vision if the
                                         paper is about vision)
   NLP -> Natural Language Processing
   GAN -> Generative Adversarial Networks
   SDN -> Software-Defined Networking
   IoT -> Internet of Things
   AES -> Cryptography (the algorithm is too narrow; lift to the field)
   WSN -> Wireless Sensor Networks
   HMD -> Virtual Reality (lift the device to its field)

8. **Always include the natural umbrella field when applicable.**
   If the paper is about image forensics with deep learning, include
   "Computer Vision" as an umbrella alongside "Image Forensics".
   If the paper is about software metrics, include "Software
   Engineering" alongside "Software Metrics". If a paper does
   information extraction from text, include "Natural Language
   Processing" alongside "Information Extraction". Faculty research
   pages list both the umbrella and the specific sub-area.

9. **NEVER output overly generic, non-domain words.** FORBIDDEN
   examples: "Classification", "Selection", "Branching Architectures",
   "Applied Research", "Statistical Analysis", "Framework",
   "Empirical Study", "Performance Evaluation".

10. **Aim for 5 to 10 tags.** Err on the side of producing more
    specific sub-field tags rather than collapsing into one umbrella —
    but follow rule 8 and include the umbrella too. If the abstract
    spans multiple sub-fields (e.g. NLP + topic modeling +
    information retrieval), output all three.

11. **Match canonical academic vocabulary.** Prefer the exact phrase
    a professor would write on their Research Interests page:
    "Wireless Sensor Networks" (not "Sensor Networks"),
    "Natural Language Processing" (not "Text Understanding"),
    "Computer Vision" (not "Image Processing" unless the paper is
    classical signal-domain work).

12. **NEVER output descriptive phrases, essay-subtitle style, or
    activity nouns.** FORBIDDEN patterns:
      - "<X> in <Y>" or "<X> for <Y>" as a tag
        ("Institutional Factors in Healthcare",
         "Security and Privacy Compliance",
         "Stakeholder Engagement").
      - Anything ending in "Analysis" / "Engagement" / "Promotion" /
        "Intervention" / "Compliance" that is not a recognised
        academic field
        ("Customer Review Analysis"  -> "Opinion Mining";
         "Health Behavior Intervention" if not a field, lift to
         "Health Informatics";
         "Stakeholder Engagement"  -> drop entirely).
      - Invented compound topics
        ("Norm Diffusion", "Humanitarian Advocacy",
         "Sustainability Governance" — instead use
         "Environmental Governance" + "Sustainability Science").

13. **NEVER hallucinate adjacent sub-areas the abstract does not
    actually cover.** If the paper is about software quality
    metrics, output "Software Engineering" + "Software Quality
    Assurance" + "Software Metrics" — do NOT also output
    "Software Security", "Software Performance", "Software
    Reliability", "Software Maintenance" unless the abstract
    explicitly discusses each of them. Quality > coverage.

14. **NEVER output country names, city names, or specific events as
    tags** unless the paper is genuinely area-studies / regional
    politics / event-specific public-health policy work.
    FORBIDDEN:
      "Singapore Politics", "Indonesia Studies",
      "Indonesian Studies", "Pandemic Policy",
      "COVID-19" (use "Public Health" or "Health Informatics"
                   if the paper is health work; otherwise drop).
    ALLOWED:
      "Southeast Asian Studies" or "ASEAN Studies" only when the
      paper explicitly frames itself as area / regional studies
      (e.g. comparative governance across ASEAN states).

Return strictly valid JSON matching this schema:

{{
  "tags": [
    {{
      "canonical_label": "<broad sub-field name>",
      "domain": "<higher-level discipline or null>",
      "source_phrases": ["<original raw phrase>", ...],
      "confidence": <float between 0 and 1>
    }}
  ]
}}

Do not include any prose outside the JSON.

ABSTRACT:
{abstract}

CANDIDATE RAW PHRASES (noisy — use abstract to disambiguate):
{phrases}
"""


async def normalize_keywords(
    phrases: List[str], *, abstract: str | None = None
) -> List[NormalizedTag]:
    """Map raw SciBERT keywords to canonical expertise tags via the LLM.

    Parameters
    ----------
    phrases:
        Raw candidate phrases produced by ``extract_keywords``.
    abstract:
        Optional full abstract text. **Strongly recommended.** Without it
        the LLM has to guess what generic words like "product", "feature"
        or "rate" mean in context and will frequently produce surface-
        word-association tags (e.g. mapping "feature extraction" from a
        sentiment-analysis paper to "Feature Engineering"). Pass the
        original abstract to anchor the normalization in the paper's
        actual domain.
    """
    if not phrases:
        return []

    llm = get_chat_llm()
    prompt = _PROMPT_TEMPLATE.format(
        abstract=(abstract or "(abstract unavailable — rely on phrases alone)")[:4000],
        phrases="\n".join(f"- {p}" for p in phrases[:80]),
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
