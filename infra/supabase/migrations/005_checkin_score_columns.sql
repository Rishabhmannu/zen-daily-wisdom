-- 005_checkin_score_columns.sql
-- Adds the weighted Mood Score (0-100), the equal-weight Mood Score (0-100),
-- and a `score_method` tag so future scoring revisions can be ablated against
-- historical data without a destructive migration.
--
-- Backwards compatibility: the existing `mood_score` column is RETAINED with
-- its original semantics (raw mean of 1-5 answer scores). New rows will keep
-- writing it for back-compat with any consumer that still reads it. The
-- canonical "headline" number going forward is `mood_score_weighted`.

alter table checkin_responses
  add column if not exists mood_score_weighted numeric,
  add column if not exists mood_score_equal numeric,
  add column if not exists mood_score_method text;

comment on column checkin_responses.mood_score is
  'Legacy: raw mean of 1-5 answer scores. Mathematically incoherent for mixed positive/reverse-coded items. Retained for back-compat. Prefer mood_score_weighted.';

comment on column checkin_responses.mood_score_weighted is
  'Headline 0-100 mood score, computed as weighted sum of goodness-normalized answers (positive items: (s-1)/4; reverse items: 1-(s-1)/4) using window-specific weights summing to 1.0. See IMPLEMENTATION_PLAN.md section 12.5.';

comment on column checkin_responses.mood_score_equal is
  'Equal-weight 0-100 mood score (1/n weights). Persisted alongside the weighted score so the differential weighting can be ablated against the unweighted backstop.';

comment on column checkin_responses.mood_score_method is
  'Tag identifying the scoring algorithm used for this row. Current value: weighted_v1.';
