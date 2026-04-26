from zen_backend.services.embedding import embed_text, to_pgvector_literal


def test_embedding_dimension_and_literal() -> None:
    vec = embed_text("focus on present and calm work")
    assert len(vec) == 768
    literal = to_pgvector_literal(vec)
    assert literal.startswith("[")
    assert literal.endswith("]")
    assert "," in literal

