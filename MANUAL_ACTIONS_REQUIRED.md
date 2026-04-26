# Manual Actions Required

These are the only steps that cannot be fully automated by the agent.

## Current status

- Last updated: 2026-04-26
- Strategy: core MVP is running locally; focus manual work on deliverability hardening and upcoming personalization rollout.

## 1) Google AI (Gemini) key

- [x] Create a new Google Cloud project dedicated to Gemini usage.
- [x] Ensure **billing is disabled** for that project.
- [x] Enable Gemini API access via AI Studio / Google AI API.
- [x] Create an API key and save it as `GEMINI_API_KEY`.
- [ ] Post-core-dev hardening: rotate exposed key before production cutover.

## 2) Gmail API OAuth credentials

- [x] In Google Cloud, create an OAuth Desktop app client.
- [x] Enable the Gmail API.
- [x] Keep the client ID and secret as:
  - `GMAIL_CLIENT_ID`
  - `GMAIL_CLIENT_SECRET`
- [x] Run local OAuth to generate `GMAIL_REFRESH_TOKEN`.
- [x] Set `GMAIL_FROM_ADDRESS`.
- [ ] Post-core-dev hardening: rotate OAuth credentials/tokens that were exposed during setup.

## 3) Google Calendar API OAuth credentials

- [x] Enable Google Calendar API in the same or separate project.
- [x] Use OAuth client credentials (same style as Gmail).
- [x] Run local OAuth to generate:
  - `GCAL_REFRESH_TOKEN`
- [x] Choose/create your calendar ID (`GCAL_CALENDAR_ID`).
- [ ] Post-core-dev hardening: rotate Calendar OAuth credentials/tokens that were exposed during setup.

## 4) Telegram bot

- [x] Open Telegram BotFather and create a bot (`/newbot`).
- [x] Save bot token as `TELEGRAM_BOT_TOKEN`.
- [x] Send one message to your bot, then capture your chat ID (`TELEGRAM_CHAT_ID`).
- [ ] Set webhook once backend URL is live (deferred until deployment phase).
- [ ] Optional UX upgrade (planned): provision Telegram Web App URL for richer check-in form flow.
- [ ] Post-core-dev hardening: rotate Telegram bot token that was exposed during setup.

## 5) Supabase project

- [x] Create Supabase project.
- [x] Copy:
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY`
  - `SUPABASE_SERVICE_ROLE_KEY`
- [x] Create/auth owner user and set `OWNER_UID`.
- [x] Configure auth redirect URL for local callback (`/auth/callback`).
- [x] Customize Supabase auth/security email templates and subject lines.
- [ ] Post-core-dev hardening: rotate Supabase secret key and DB password exposed during setup.

## 6) Gmail sender trust / anti-phishing hardening (high priority)

> Reason: Gmail warning `This message isn't authenticated and the sender can't be verified`.

- [ ] Decide production sender domain strategy:
  - Option A: custom domain mailbox (recommended), e.g. `hello@yourdomain.com`
  - Option B: continue personal Gmail for dev only
- [ ] Add SPF DNS record for sender domain (include all legitimate senders).
- [ ] Enable DKIM signing for sender domain and publish DKIM DNS records.
- [ ] Add DMARC DNS record (start with `p=none`), then tighten after verification.
- [ ] Verify alignment using Gmail original headers (`SPF=PASS`, `DKIM=PASS`, `DMARC=PASS`).
- [ ] Optional: set up Google Postmaster Tools for ongoing reputation/spam-rate monitoring.

## 7) Hosting account setup

- [x] Fly.io account + CLI login (for backend deploy).
- [ ] Vercel account + GitHub integration (for frontend deploy) — deferred until frontend wiring/deploy.
- [ ] GitHub repo secrets (for scheduled workflows and HMAC keys) — deferred until CI/deploy wiring.

## 8) Personalization 2.0 preparation (check-in flow, upcoming)

- [ ] Confirm desired reminder windows (default recommendation):
  - Morning: 08:30 IST
  - Midday: 13:30 IST
  - Evening: 20:30 IST
- [ ] Confirm preferred check-in frequency:
  - Default: 3/day for 14 days, then adapt based on completion rate
- [ ] Confirm acceptable question count and completion target:
  - Default: 6–8 questions, under 60 seconds
- [ ] Decide preferred response surfaces:
  - Email quick form links
  - Telegram inline / Web App (recommended for better UX)

---

All local environment setup and corpus ingestion/backfill have been completed at least once. Re-run ingestion as needed when new sources are added.
