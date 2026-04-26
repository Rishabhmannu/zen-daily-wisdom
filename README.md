# Zen Daily Wisdom

Personalized daily wisdom service using FastAPI, Next.js, Supabase, and Gemini with RAG, mood check-ins, and email/Telegram delivery.

Zen Daily Wisdom is a personal full-stack project that delivers short, high-quality daily reflections through Gmail and Telegram. It combines retrieval-augmented generation over a curated wisdom corpus, style rotation, and feedback/check-in personalization to improve relevance over time.

Canonical implementation details live in:

- `IMPLEMENTATION_PLAN.md`

## Current status

- Manual credentials mostly completed (see `MANUAL_ACTIONS_REQUIRED.md`)
- Python environment + corpus assets downloaded
- Backend/FastAPI scaffold created
- Frontend/Next.js scaffold created
- Supabase migration skeleton added
- CI + daily cron + keepalive workflows added
- Check-in reminder cron workflow added (3x/day IST)
- Dashboard auth gate + allowlist enabled (Supabase magic-link)
- Telegram webhook endpoint added for inline rating and `/mood`
- Northflank migration started for backend hosting

## Quick start (backend scaffold)

```bash
source .venv/bin/activate
uv pip install -e "./apps/backend[dev]"
uvicorn zen_backend.main:app --app-dir apps/backend/src --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Apply Supabase migrations (after setting `SUPABASE_DB_DSN`):

```bash
source .venv/bin/activate
python scripts/apply_supabase_migrations.py
```

Seed passages from downloaded corpus assets:

```bash
source .venv/bin/activate
python scripts/seed_passages_to_supabase.py --include-silver
```

Backfill pgvector embeddings for seeded passages:

```bash
source .venv/bin/activate
python scripts/backfill_passage_embeddings.py
```

Trigger generation endpoint locally (when backend is running):

```bash
source .venv/bin/activate
python scripts/run_internal_generate.py --force
```

## Quick start (frontend scaffold)

1. Install pnpm (if missing): `corepack enable && corepack prepare pnpm@latest --activate`
2. Install deps: `pnpm install`
3. Run app: `pnpm frontend:dev`

Required auth env vars:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `ALLOWED_EMAILS` (backend check)
- `NEXT_PUBLIC_ALLOWED_EMAILS` (frontend pre-check)

Register Telegram webhook (after deploying backend over HTTPS):

```bash
source .venv/bin/activate
python scripts/register_telegram_webhook.py
```

Northflank deployment guide:

- `docs/NORTHFLANK_BACKEND_DEPLOY.md`

