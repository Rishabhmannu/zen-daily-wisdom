from __future__ import annotations

from typing import Any

from zen_backend.db.pg_client import pg_connection
from zen_backend.services.embedding import embed_text, to_pgvector_literal


def fetch_ranked_passages(
    query: str,
    *,
    source_tier: str = "gold",
    tradition: str | None = None,
    required_tags: list[str] | None = None,
    prefer_season_words: bool = False,
    limit: int = 20,
) -> list[dict[str, Any]]:
    qvec = to_pgvector_literal(embed_text(query))
    has_required_tags = bool(required_tags)
    sql = """
        select
            id,
            tradition,
            source,
            citation,
            text,
            theme_tags,
            tone,
            length_bucket,
            source_tier,
            1 - (embedding <=> %s::vector) as similarity,
            case when %s::boolean and theme_tags && %s::text[] then 1 else 0 end as tag_score,
            case
                when %s::boolean and text ~* '\\m(spring|summer|autumn|fall|winter|monsoon|rain|dawn|evening|season)\\M'
                then 1
                else 0
            end as season_score
        from passages
        where embedding is not null
          and source_tier = %s
    """
    params: list[Any] = [qvec, has_required_tags, required_tags or [], prefer_season_words, source_tier]
    if tradition:
        sql += " and tradition = %s"
        params.append(tradition)
    sql += " order by tag_score desc, season_score desc, embedding <=> %s::vector asc limit %s"
    params.extend([qvec, limit])

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = [desc.name for desc in cur.description]
    return [dict(zip(cols, row)) for row in rows]


def choose_passage(ranked_passages: list[dict[str, Any]]) -> dict[str, Any]:
    if not ranked_passages:
        raise ValueError("No ranked passages found.")
    return ranked_passages[0]

