-- 006_dashboard_narrative_cache.sql
-- Stores the dashboard's "this week" Gemini-written narrative card so we
-- don't call Gemini on every dashboard load. One row per kind ("weekly"
-- today, room for "monthly" / "year_in_review" later without schema
-- changes).

create table if not exists dashboard_narrative_cache (
  id text primary key,
  body text not null,
  source_method text not null,
  generated_at timestamptz not null default now()
);

comment on table dashboard_narrative_cache is
  'Server-side cache for Gemini-generated dashboard narrative cards.';

comment on column dashboard_narrative_cache.id is
  'Narrative kind. Currently "weekly" only. Stable identifier used as the upsert key.';

comment on column dashboard_narrative_cache.source_method is
  'Tag identifying how the body was produced: "gemini" or "fallback".';
