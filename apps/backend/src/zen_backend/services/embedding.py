"""Text embedding for the wisdom corpus + query side.

**Default backend: hash.** A deterministic SHA256-based hashed-token
embedder. Sparse, lexical, not semantic — but free, fast, no rate limits,
and fully reproducible. This is what production runs on today.

The Gemini backend (`gemini-embedding-001`) is implemented and tested;
enable it via `EMBEDDING_METHOD=gemini` once you've migrated off the
free-tier embedding quota (which caps at ~1,000 RPD and can't backfill
this corpus in one pass). When you flip the env var you must also re-run
`scripts/backfill_passage_embeddings.py --reset` so the corpus matches
the query-side encoder; cosine similarity across mismatched encoders is
meaningless.

Both backends produce 768-dim L2-normalized vectors, so swapping models
doesn't require a pgvector schema change.

Env vars:
  - `EMBEDDING_METHOD=hash`   (or unset) — use the hash backend.
  - `EMBEDDING_METHOD=gemini` — use Gemini text-embedding-001.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768
GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
# Gemini's task_type lets the model produce different embeddings for the
# query side vs the document side of a retrieval pair (and tells it that
# this is RAG, not generic similarity). Using the matched pair gives
# noticeably better recall than a single shared task_type.
GEMINI_QUERY_TASK = "RETRIEVAL_QUERY"
GEMINI_DOCUMENT_TASK = "RETRIEVAL_DOCUMENT"


# --- Hash backend (offline fallback, kept for tests + degraded mode) ---


def _embed_text_hash(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Deterministic SHA256-based hashed-token embedding. Sparse, lexical,
    not semantic. Useful as a no-network fallback for unit tests."""
    vec = [0.0] * dim
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        b1 = digest[0] % dim
        b2 = digest[1] % dim
        sign1 = -1.0 if digest[2] % 2 else 1.0
        sign2 = -1.0 if digest[3] % 2 else 1.0
        vec[b1] += sign1
        vec[b2] += 0.5 * sign2
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


# --- Gemini backend ---


@lru_cache(maxsize=1)
def _gemini_client():
    """Late, cached construction so we don't hit the network at import time
    (notebooks and tests import this module just to access constants)."""
    from google import genai  # local import keeps the dep optional for hash-only runs

    from zen_backend.config import settings

    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    return genai.Client(api_key=settings.gemini_api_key)


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _coerce_dim(vec: list[float], dim: int = EMBEDDING_DIM) -> list[float]:
    if len(vec) == dim:
        return vec
    return (vec + [0.0] * dim)[:dim]


def _extract_values(emb_obj) -> list[float]:
    """The google-genai EmbedContentResponse exposes embeddings via
    `response.embeddings[i].values` in newer SDK versions and
    `response.embedding.values` for single-input calls. Be tolerant."""
    if hasattr(emb_obj, "values"):
        return list(emb_obj.values)
    if isinstance(emb_obj, dict) and "values" in emb_obj:
        return list(emb_obj["values"])
    if isinstance(emb_obj, list):
        return list(emb_obj)
    raise RuntimeError(f"Unrecognized embedding object shape: {type(emb_obj)}")


def _gemini_config(task_type: str, dim: int):
    """Build the EmbedContentConfig for a given retrieval side. Imported
    lazily because google.genai.types is only loadable when the SDK is
    installed (which it is, but we keep imports localized to embed paths)."""
    from google.genai import types

    return types.EmbedContentConfig(
        task_type=task_type,
        output_dimensionality=dim,
    )


def _embed_text_gemini(
    text: str,
    dim: int = EMBEDDING_DIM,
    task_type: str = GEMINI_QUERY_TASK,
) -> list[float]:
    """Single-text Gemini embedding. Defaults to RETRIEVAL_QUERY (caller
    side at retrieval time). For ingesting passages, pass
    task_type=GEMINI_DOCUMENT_TASK."""
    client = _gemini_client()
    result = client.models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=text,
        config=_gemini_config(task_type, dim),
    )
    if hasattr(result, "embeddings") and result.embeddings:
        values = _extract_values(result.embeddings[0])
    elif hasattr(result, "embedding"):
        values = _extract_values(result.embedding)
    else:
        raise RuntimeError("Gemini embed_content returned no embedding.")
    return _normalize(_coerce_dim(values, dim))


def embed_texts_gemini_batch(
    texts: list[str],
    dim: int = EMBEDDING_DIM,
    task_type: str = GEMINI_DOCUMENT_TASK,
) -> list[list[float]]:
    """Batched Gemini embedding for backfill efficiency. Returns a list
    parallel to `texts`. Default task_type is RETRIEVAL_DOCUMENT — the
    backfill side of the RAG pair. Used by
    `scripts/backfill_passage_embeddings.py`."""
    if not texts:
        return []
    client = _gemini_client()
    result = client.models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=texts,
        config=_gemini_config(task_type, dim),
    )
    embs = getattr(result, "embeddings", None) or []
    if len(embs) != len(texts):
        raise RuntimeError(
            f"Gemini batch returned {len(embs)} embeddings for {len(texts)} inputs."
        )
    return [_normalize(_coerce_dim(_extract_values(e), dim)) for e in embs]


# --- Dispatcher ---


def _selected_method() -> str:
    """Resolve which backend to use for the current call.

    Default is the hash backend (free, no rate limits, deterministic).
    Set `EMBEDDING_METHOD=gemini` explicitly to opt in to Gemini.
    """
    explicit = (os.environ.get("EMBEDDING_METHOD") or "").strip().lower()
    if explicit == "gemini":
        return "gemini"
    return "hash"


_warned_about_fallback = False


def embed_text(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Public entry point. Picks the backend per `_selected_method`."""
    method = _selected_method()
    if method == "gemini":
        try:
            return _embed_text_gemini(text, dim)
        except Exception as exc:
            global _warned_about_fallback
            if not _warned_about_fallback:
                logger.warning(
                    "Gemini embedding failed (%s); falling back to hash backend "
                    "for this call. Subsequent failures will not log this warning.",
                    exc,
                )
                _warned_about_fallback = True
            return _embed_text_hash(text, dim)
    return _embed_text_hash(text, dim)


def to_pgvector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
