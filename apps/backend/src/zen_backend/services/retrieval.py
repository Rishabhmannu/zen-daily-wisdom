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
    max_per_tradition: int | None = None,
) -> list[dict[str, Any]]:
    """Top-k passages by tag/season/cosine ranking.

    `max_per_tradition`: if set, the result list is post-filtered so that no
    single tradition occupies more than this many slots in the top-`limit`.
    Implemented by over-fetching from the database (limit × 4) and applying
    a streaming per-tradition cap in Python, preserving the SQL ranking
    among the survivors. Defaults to `None` (back-compat: no cap).
    """
    qvec = to_pgvector_literal(embed_text(query))
    has_required_tags = bool(required_tags)
    # Over-fetch when a diversity cap is active so the cap doesn't starve
    # the result list. Cheap because the corpus is small.
    sql_limit = limit if max_per_tradition is None else max(limit * 4, 40)
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
    params.extend([qvec, sql_limit])

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = [desc.name for desc in cur.description]
    ranked = [dict(zip(cols, row)) for row in rows]

    if max_per_tradition is None:
        return ranked[:limit]
    return _diversify_by_tradition(ranked, max_per_tradition=max_per_tradition, limit=limit)


def _diversify_by_tradition(
    ranked: list[dict[str, Any]],
    *,
    max_per_tradition: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Stream the ranked list, dropping any passage from a tradition that
    has already filled its quota. Preserves the original ranking among
    survivors. If the cap is so tight that we'd return fewer than `limit`
    rows, we relax the cap and top up from the leftovers in original order
    so callers always get up to `limit` results when there's enough data.
    """
    seen: dict[str, int] = {}
    primary: list[dict[str, Any]] = []
    leftovers: list[dict[str, Any]] = []
    for row in ranked:
        tradition = str(row.get("tradition") or "unknown")
        if seen.get(tradition, 0) < max_per_tradition:
            primary.append(row)
            seen[tradition] = seen.get(tradition, 0) + 1
        else:
            leftovers.append(row)
        if len(primary) >= limit:
            break
    if len(primary) >= limit:
        return primary[:limit]
    # Top up from the leftovers if the cap was so tight we'd starve.
    needed = limit - len(primary)
    return primary + leftovers[:needed]


def choose_passage(ranked_passages: list[dict[str, Any]]) -> dict[str, Any]:
    if not ranked_passages:
        raise ValueError("No ranked passages found.")
    return ranked_passages[0]

