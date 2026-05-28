"""SciBERT keyword extraction service (UC-8 step 4).

SciBERT (``allenai/scibert_scivocab_uncased``) was trained on scientific
literature and is therefore the model of choice for technical keyword
extraction from publication abstracts.

This module exposes a single coroutine, :func:`extract_keywords`, that
runs SciBERT against a passage and returns the top-N most salient
candidate phrases. The implementation uses an attention-based saliency
strategy combined with token-level filtering to avoid stopwords and
sub-word fragments — sufficient as upstream input for the LLM-based
semantic normalization pass implemented in :mod:`app.services.llm_normalize`.

Heavy model objects are lazily loaded into a process-wide singleton and
inference is dispatched to a worker thread (transformer forward passes
are CPU-blocking and would otherwise stall the FastAPI event loop).
"""
from __future__ import annotations

import asyncio
import logging
import re
import threading
from collections import Counter
from typing import List, Tuple

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are aren as at be because
    been before being below between both but by could did do does doing don down
    during each few for from further had has have having he her here hers herself
    him himself his how i if in into is it its itself just me more most my myself
    no nor not now of off on once only or other our ours ourselves out over own
    same she should so some such than that the their theirs them themselves then
    there these they this those through to too under until up very was we were
    what when where which while who whom why will with you your yours yourself
    yourselves also among many may use using used based new study studies result
    results paper work proposed approach method methods model models system systems
    show shown shows demonstrate demonstrates demonstrated provide provides
    however therefore thus we present analysis data three two one set
    """.split()
)


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-]{2,}")


_tokenizer_lock = threading.Lock()
_pipeline_instance = None  # type: ignore[var-annotated]


def _load_pipeline():
    """Load the SciBERT fill-mask pipeline lazily.

    We actually use the bare model + tokenizer for embedding-based
    salience rather than fill-mask, but ``transformers.pipeline`` ensures
    the same heavy-weight imports only happen once per process.
    """
    global _pipeline_instance
    if _pipeline_instance is not None:
        return _pipeline_instance
    with _tokenizer_lock:
        if _pipeline_instance is not None:
            return _pipeline_instance
        from transformers import AutoModel, AutoTokenizer

        settings = get_settings()
        logger.info("Loading SciBERT tokenizer/model %s", settings.scibert_model)
        tokenizer = AutoTokenizer.from_pretrained(settings.scibert_model)
        model = AutoModel.from_pretrained(settings.scibert_model)
        model.eval()
        _pipeline_instance = (tokenizer, model)
        return _pipeline_instance


def _candidate_phrases(text: str) -> List[str]:
    """Yield unigram + bigram noun-like candidates from ``text``.

    A lightweight regex tokenizer is sufficient here because SciBERT's
    embedding pass — not POS tagging — is what supplies the semantic
    signal. We just need plausible technical phrases to score.
    """
    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    tokens = [t for t in tokens if t not in _STOPWORDS and not t.isdigit()]

    candidates: List[str] = []
    seen: set[str] = set()

    for token in tokens:
        if token not in seen:
            seen.add(token)
            candidates.append(token)

    for first, second in zip(tokens, tokens[1:]):
        bigram = f"{first} {second}"
        if bigram not in seen:
            seen.add(bigram)
            candidates.append(bigram)
    return candidates


def _embed_pool(tokenizer, model, texts: List[str]):
    """Return mean-pooled SciBERT embeddings for a batch of texts."""
    import torch  # local import — torch already loaded by the model.

    encoded = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=64,
        return_tensors="pt",
    )
    with torch.no_grad():
        output = model(**encoded)
        last_hidden = output.last_hidden_state  # (batch, seq, hidden)
        mask = encoded["attention_mask"].unsqueeze(-1).type_as(last_hidden)
        summed = (last_hidden * mask).sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1.0)
        pooled = summed / counts
        # L2 normalize so dot product equals cosine similarity.
        pooled = pooled / pooled.norm(dim=1, keepdim=True).clamp(min=1e-12)
    return pooled.cpu().numpy()


def _extract_sync(text: str, top_k: int) -> List[Tuple[str, float]]:
    if not text or not text.strip():
        return []
    tokenizer, model = _load_pipeline()

    candidates = _candidate_phrases(text)
    if not candidates:
        return []

    # Score candidates by cosine similarity to the full abstract embedding —
    # phrases most representative of the document surface to the top.
    import numpy as np

    doc_vec = _embed_pool(tokenizer, model, [text[:2000]])[0]

    # Batch candidate embeddings to keep memory bounded.
    scores: List[Tuple[str, float]] = []
    batch_size = 32
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start : start + batch_size]
        vecs = _embed_pool(tokenizer, model, batch)
        for phrase, vec in zip(batch, vecs):
            scores.append((phrase, float(np.dot(doc_vec, vec))))

    # Frequency boost — phrases that appear multiple times in the abstract
    # are usually the central concepts.
    surface = text.lower()
    frequency = Counter()
    for phrase, _ in scores:
        frequency[phrase] = surface.count(phrase)

    weighted = sorted(
        scores,
        key=lambda item: (item[1] + 0.05 * min(frequency[item[0]], 5)),
        reverse=True,
    )

    # Suppress shorter phrases that are subsumed by a higher-ranked bigram.
    chosen: List[Tuple[str, float]] = []
    chosen_set: set[str] = set()
    for phrase, score in weighted:
        if any(phrase in c for c in chosen_set):
            continue
        chosen.append((phrase, score))
        chosen_set.add(phrase)
        if len(chosen) >= top_k:
            break
    return chosen


async def extract_keywords(text: str, *, top_k: int = 20) -> List[Tuple[str, float]]:
    """Asynchronously extract the top ``top_k`` candidate keywords."""
    return await asyncio.to_thread(_extract_sync, text, top_k)
