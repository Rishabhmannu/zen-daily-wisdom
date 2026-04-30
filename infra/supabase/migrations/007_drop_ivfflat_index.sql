-- 007_drop_ivfflat_index.sql
-- Drop the IVFFLAT approximate-nearest-neighbor index on passages.embedding.
--
-- Why: with only ~4.6k rows × 768 dims, the IVFFLAT index (lists=100,
-- default probes=1) was visiting only ~46 candidate passages per query.
-- That caused 30% of RAG eval queries to return fewer than the requested
-- top-k rows, because the relevant passages happened to live in unprobed
-- list partitions. Sequential scan over the full corpus is ~50-100 ms
-- which is fine for a daily cron and fine for the occasional /checkin
-- submit. We can add an HNSW index later (better recall than IVFFLAT)
-- once the corpus grows past ~50k rows, but that's far away.

drop index if exists passages_embedding_idx;

-- Keep the GIN index on theme_tags and the b-tree on sent_history.sent_date;
-- those are not affected by this change.
