"""Sentence-Transformer embedding service (UC-8, UC-14, UC-15, UC-16).

Wraps a single ``sentence-transformers`` model behind a lazy singleton so
expensive model download and tokenizer construction happen exactly once
per process. Inference is offloaded to a worker thread because
SentenceTransformer is CPU-blocking.

The output dimensionality is whatever the configured model produces;
``all-MiniLM-L6-v2`` (the default) yields 384-dim vectors which are
stored in PostgreSQL ``ARRAY(Float)`` columns by ``models.py``.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Iterable, List, Sequence

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)


_model_lock = threading.Lock()
_model_instance = None  # type: ignore[var-annotated]


def _load_model():
    """Lazily import and load the SentenceTransformer model."""
    global _model_instance
    if _model_instance is not None:
        return _model_instance
    with _model_lock:
        if _model_instance is not None:
            return _model_instance
        # Imported lazily — sentence_transformers pulls in torch on import,
        # which we want to defer until the first NLP request is served.
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        logger.info("Loading sentence-transformer model %s", settings.embedding_model)
        _model_instance = SentenceTransformer(settings.embedding_model)
        return _model_instance


def _encode_sync(texts: Sequence[str]) -> List[List[float]]:
    model = _load_model()
    vectors = model.encode(
        list(texts),
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [vec.astype(float).tolist() for vec in vectors]


async def embed_texts(texts: Iterable[str]) -> List[List[float]]:
    """Embed an iterable of strings into L2-normalized float vectors."""
    materialized = [t for t in texts if t and t.strip()]
    if not materialized:
        return []
    return await asyncio.to_thread(_encode_sync, materialized)


async def embed_text(text: str) -> List[float]:
    """Embed a single string. Returns an empty list when input is blank."""
    if not text or not text.strip():
        return []
    vectors = await embed_texts([text])
    return vectors[0] if vectors else []


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two equally-shaped vectors.

    Inputs are assumed to be L2-normalized (which ``embed_texts`` enforces),
    but we still divide by the norm product for safety so callers can pass
    raw vectors without surprise.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    va = np.asarray(a, dtype=float)
    vb = np.asarray(b, dtype=float)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0.0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def cosine_similarity_matrix(
    query: Sequence[float], candidates: Sequence[Sequence[float]]
) -> List[float]:
    """Cosine similarity of ``query`` against every candidate vector."""
    if not query or not candidates:
        return []
    q = np.asarray(query, dtype=float)
    cand = np.asarray(candidates, dtype=float)
    q_norm = np.linalg.norm(q)
    c_norms = np.linalg.norm(cand, axis=1)
    safe = c_norms * q_norm
    safe[safe == 0.0] = 1e-12
    return (cand @ q / safe).tolist()
