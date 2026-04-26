alter table passages enable row level security;
alter table sent_history enable row level security;
alter table feedback enable row level security;
alter table mood_log enable row level security;
alter table bandit_state enable row level security;
alter table prompt_versions enable row level security;

-- NOTE:
-- For initial development, backend writes should use service-role key.
-- User-facing read policies can be added once Supabase auth wiring is complete.
