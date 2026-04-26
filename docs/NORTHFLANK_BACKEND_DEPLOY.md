# Northflank Backend Deployment

This guide deploys the FastAPI backend (`apps/backend`) on Northflank using the existing Dockerfile.

## 1) Create service

In your Northflank project:

1. Click `Create resource` -> `Service` -> `Combined`.
2. Name: `zen-backend` (or any stable name).
3. Repository: select this GitHub repo.
4. Branch: use your main development branch.
5. Build options:
   - Build type: `Dockerfile`
   - Dockerfile path: `/apps/backend/Dockerfile`
   - Build context: `/apps/backend`

## 2) Configure runtime environment variables

Add the following keys in service runtime variables (copy values from your local `.env`):

- `ENVIRONMENT`
- `BACKEND_PORT`
- `GEMINI_API_KEY`
- `GEMINI_DAILY_CALL_CAP`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `OWNER_UID`
- `ALLOWED_EMAILS`
- `SUPABASE_DB_DSN`
- `SUPABASE_DB_DSN_POOLER`
- `INTERNAL_HMAC_SECRET`
- `FEEDBACK_LINK_SECRET`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_WEBHOOK_SECRET`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- `GMAIL_FROM_ADDRESS`
- `GCAL_CLIENT_ID`
- `GCAL_CLIENT_SECRET`
- `GCAL_REFRESH_TOKEN`
- `GCAL_CALENDAR_ID`
- `NEXT_PUBLIC_BACKEND_URL`
- `NEXT_PUBLIC_FRONTEND_URL`

Notes:

- Set `ENVIRONMENT=production`
- Set `BACKEND_PORT=8000`
- `NEXT_PUBLIC_BACKEND_URL` should be your Northflank public URL (https).
- `NEXT_PUBLIC_FRONTEND_URL` should be your frontend URL (`http://localhost:3000` until Vercel is live).

## 3) Configure networking

In the service ports section:

- Add/expose port `8000`
- Protocol: `HTTP`
- Public: enabled

Northflank should assign a `*.code.run` URL.

## 4) Configure health checks

Add:

- Type: `liveness`
- Protocol: `HTTP`
- Port: `8000`
- Path: `/health`
- Initial delay: `15`
- Interval: `30`
- Timeout: `5`
- Max failures: `3`

## 5) Deploy and verify

1. Trigger build/deploy.
2. Open service URL + `/health`.
3. Expected response: `{"status":"ok", ...}`.

## 6) Post-deploy actions

After backend URL is stable:

1. Update `NEXT_PUBLIC_BACKEND_URL` in:
   - local `.env`
   - frontend host env (Vercel later)
   - GitHub Action secret `BACKEND_URL`
2. Re-register Telegram webhook:
   - `python scripts/register_telegram_webhook.py`
3. Trigger one manual check-in reminder workflow run in GitHub Actions.
