<div align="center">

# Zen Daily Wisdom

A personal RAG service that delivers one short, grounded reflection per day to email and Telegram, tuned by daily mood check-ins. Public-domain wisdom corpus, $0/month free-tier stack.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?logo=googlegemini&logoColor=white)](https://ai.google.dev)
[![Tailwind](https://img.shields.io/badge/Tailwind-4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Recharts](https://img.shields.io/badge/Recharts-3-22B5BF?logo=react&logoColor=white)](https://recharts.org)
[![Jupyter](https://img.shields.io/badge/Jupyter-Notebooks-F37626?logo=jupyter&logoColor=white)](https://jupyter.org)
[![Pytest](https://img.shields.io/badge/Pytest-87_passing-0A9EDC?logo=pytest&logoColor=white)](https://pytest.org)
[![Vercel](https://img.shields.io/badge/Vercel-Hosted-000000?logo=vercel&logoColor=white)](https://vercel.com)
[![Northflank](https://img.shields.io/badge/Northflank-Hosted-7C5CFC)](https://northflank.com)

</div>

---

## Demo

<table>
  <tr>
    <td width="50%" valign="top">
      <p align="center"><b>Landing page</b></p>
      <img src="screenshots/frontend-page.png" alt="Public landing page" width="100%"/>
    </td>
    <td width="50%" valign="top">
      <p align="center"><b>Dashboard</b></p>
      <img src="screenshots/dashboard.png" alt="Authenticated dashboard" width="100%"/>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <p align="center"><b>Daily reflection email</b></p>
      <img src="screenshots/email-reflections.png" alt="Daily reflection email" width="100%"/>
    </td>
    <td width="50%" valign="top">
      <p align="center"><b>Check-in reminder email</b></p>
      <img src="screenshots/email-checkin.png" alt="Check-in reminder email" width="100%"/>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center">
      <p><b>Telegram</b> — same daily reflection, plus check-in prompts with inline rating buttons.</p>
      <img src="screenshots/telegram-screenshot.png" alt="Telegram delivery" width="320"/>
    </td>
  </tr>
</table>

---

## What it does

- **Retrieval.** 4,606 public-domain passages from 13 traditions (Stoic, Indian, Sufi, Zen, naturalist) chunked and embedded into pgvector.
- **Generation.** Gemini 2.5 Flash composes a 30–60 word reflection grounded in one retrieved passage, with cliché-rejection and faithfulness checks.
- **Personalization.** A Thompson-sampling bandit over `(tradition, tone)` super-arms learns from ratings; time-aware check-ins (morning / midday / evening) feed a 0–100 weighted Mood Score that conditions retrieval.
- **Delivery.** Zen-styled HTML email, Telegram with inline rating buttons, and a no-login signed-link check-in form on Vercel.

---

## Architecture

```
                  GitHub Actions cron
                  · daily reflection (07:00 IST)
                  · check-in reminders (3×/day IST)
                  · keepalive (every 3 days)
                          │
                          ▼   HMAC-signed POST
       ┌─────────────────────────────────────────┐
       │  FastAPI on Northflank                  │
       │  /internal/*  /checkin/*  /feedback     │
       │  /dashboard/* (Supabase JWT)            │
       │  /telegram/webhook                      │
       └────┬─────────┬───────┬────────┬─────────┘
            ▼         ▼       ▼        ▼
        pgvector  Gemini    Gmail   Telegram
        Supabase  Flash     API     Bot API

       Vercel — Next.js 15 dashboard + public /checkin form
```

Bandit posteriors live in a `bandit_state` table and update via a Postgres trigger on each feedback insert. Check-in submissions return a Gemini observation + a related corpus passage in the same screen.

---

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 15 · TypeScript 5 · Tailwind 4 · Recharts 3 (Vercel Hobby) |
| Backend | FastAPI 0.115 · Python 3.12 · `uv` (Northflank Sandbox) |
| Data | Supabase Postgres + pgvector · Supabase Auth |
| LLM | Gemini 2.5 Flash + `text-embedding-004` |
| Delivery | Gmail API · Telegram Bot API · Google Calendar API |
| Scheduling | GitHub Actions cron |
| Tests | Pytest (87) · Vitest |
| Eval | Jupyter notebooks · matplotlib · scipy |

---

## Evaluation

Reproducible numbers in [`EVALUATION.md`](EVALUATION.md), backed by four committed notebooks:

| Notebook | Headline |
|---|---|
| [`bandit_convergence.ipynb`](notebooks/bandit_convergence.ipynb) | Mean cumulative regret 47.1 (production ε = 0.15) vs 124.8 (uniform baseline) over 30 seeds × 600 rounds |
| [`corpus_stats.ipynb`](notebooks/corpus_stats.ipynb) | 4,606 passages · 13 traditions · 13 viable bandit arms · every theme covered |
| [`rag_eval.ipynb`](notebooks/rag_eval.ipynb) | recall@5 = 0.767 over 30 hand-labeled queries (target ≥ 0.80; gap diagnosed in `EVALUATION.md`) |
| [`faithfulness.ipynb`](notebooks/faithfulness.ipynb) | Token-overlap framework; numbers fill in once `sent_history` accumulates more rows |

---

## Disclaimer

Built for personal use. Dashboard access is gated by an explicit email allowlist; magic-link / password auth is restricted to a small set of accounts I control. The corpus is entirely **public-domain English** (or PD English translations).

If you'd like access or to discuss any part of the architecture or evaluation, please reach out.

**Rishabh Kumar** — [rishabhkumards07@gmail.com](mailto:rishabhkumards07@gmail.com)
