create table if not exists checkin_responses (
  id uuid primary key default gen_random_uuid(),
  checkin_date date not null,
  "window" text not null check ("window" in ('morning', 'midday', 'evening')),
  channel text not null check (channel in ('email', 'telegram', 'dashboard')),
  answers jsonb not null,
  mood_score numeric not null,
  challenge_score numeric,
  note text,
  submitted_at timestamptz not null default now(),
  schema_version int not null default 1
);

create index if not exists checkin_responses_date_idx on checkin_responses (checkin_date desc);
create index if not exists checkin_responses_submitted_idx on checkin_responses (submitted_at desc);
