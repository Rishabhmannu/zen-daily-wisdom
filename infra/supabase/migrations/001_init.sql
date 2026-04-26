create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists passages (
  id uuid primary key default gen_random_uuid(),
  tradition text not null,
  source text not null,
  citation text not null,
  text text not null,
  theme_tags text[] not null default '{}',
  tone text,
  length_bucket text,
  source_tier text not null default 'gold',
  embedding vector(768),
  created_at timestamptz default now(),
  unique (source, citation, text)
);

create table if not exists sent_history (
  id uuid primary key default gen_random_uuid(),
  sent_at timestamptz not null default now(),
  sent_date date not null unique,
  passage_ids uuid[] not null,
  arm_key text not null,
  arm_tradition text not null,
  arm_tone text not null,
  arm_length text not null,
  arm_source_tier text not null,
  theme_of_day text,
  llm_output text not null,
  channels text[] not null,
  retrieval_trace jsonb
);

create table if not exists feedback (
  id uuid primary key default gen_random_uuid(),
  sent_id uuid references sent_history(id) on delete cascade,
  channel text,
  rating int check (rating between 1 and 5),
  tone_tag text,
  note text,
  created_at timestamptz default now()
);

create table if not exists mood_log (
  id uuid primary key default gen_random_uuid(),
  logged_at timestamptz default now(),
  score int check (score between 1 and 5) not null,
  note text
);

create table if not exists bandit_state (
  arm_key text primary key,
  alpha numeric not null default 1.0,
  beta numeric not null default 1.0,
  pulls int not null default 0,
  last_updated timestamptz default now()
);

create table if not exists prompt_versions (
  id uuid primary key default gen_random_uuid(),
  kind text not null,
  version int not null,
  body text not null,
  is_active boolean not null default false,
  created_at timestamptz default now(),
  unique (kind, version)
);

create index if not exists passages_embedding_idx on passages using ivfflat (embedding vector_cosine_ops) with (lists = 100);
create index if not exists passages_theme_idx on passages using gin (theme_tags);
create index if not exists sent_history_date_idx on sent_history (sent_date);
