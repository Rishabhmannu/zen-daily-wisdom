from __future__ import annotations

import hashlib
import math

EMBEDDING_DIM = 768


def embed_text(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
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


def to_pgvector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"

