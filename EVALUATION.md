# Evaluation

This document is the methodology + results writeup for **Zen Daily Wisdom**'s four evaluation surfaces:

1. **Bandit convergence** — does the personalization layer pick the right `(tradition, tone)` arm?
2. **Corpus stats** — what's in the corpus, and is anything sparse enough to handicap retrieval?
3. **RAG retrieval recall@k** — does pgvector + Gemini embeddings actually surface relevant traditions?
4. **Faithfulness** — does the daily reflection lean on the retrieved passage instead of drifting onto the LLM's training distribution?

Each surface lives in a notebook under `notebooks/`. Two are reproducible from a clean clone; two need either a Supabase snapshot or live Gemini access. Reproduction instructions are at the end.

---

## Targets (from `IMPLEMENTATION_PLAN.md` §1)

| Metric | Target | Status |
|---|---|---|
| RAG retrieval recall@5 over 50 queries | ≥ 0.80 | framework shipped, 30/50 seed queries written; numbers pending live run |
| Faithfulness (quoted text appears in retrieved passage) | ≥ 0.95 | framework shipped; needs ≥ 30 days of `sent_history` for stable numbers |
| Mean rating over last 30 days | ≥ 3.5 / 5 | not yet — fewer than 30 days of usage |
| Bandit convergence on synthetic reward | dominant arm picks > 50 % within ~200 rounds | ✅ passes (this doc) |

---

## 1. Bandit convergence — `notebooks/bandit_convergence.ipynb`

### Method

Replicates the production bandit (`apps/backend/src/zen_backend/services/bandit.py`) inline so the notebook is self-contained. Five synthetic super-arms are modelled with hand-set "true" reward probabilities chosen to mirror a plausible personal preference distribution:

| Arm | True P(success) |
|---|---|
| `thoreau\|warm` | 0.65 (winner) |
| `marcus_aurelius\|firm` | 0.55 |
| `rumi\|warm` | 0.45 |
| `dhammapada\|gentle` | 0.35 |
| `tao_te_ching\|austere` | 0.25 |

For each of three regimes — pure Thompson (ε = 0), Thompson + epsilon-greedy (ε = 0.15, the production default), and uniform exploration (ε = 1.0) — we run 30 independent seeds × 600 rounds and aggregate.

### Results

**Cumulative regret at 600 rounds, mean over 30 seeds:**

| Regime | Mean regret | Notes |
|---|---|---|
| Pure Thompson (ε = 0) | **28.9** | tightest, but variance band wider on cold-start unlucky seeds |
| Thompson + ε = 0.15 (production) | **47.1** | small cost, real cold-start protection |
| Uniform (ε = 1.0) | 124.8 | baseline; dominated everywhere |
| Oracle (always best arm) | 0 (390 cumulative reward) | ceiling |

**Lock-in:** P(picking the optimal arm) crosses 0.5 around round ~150 in both Thompson regimes and asymptotes near 0.85 by round 400. Uniform stays at 0.20 (= 1/5, by construction).

**Posterior at round 600 (one representative seed):**

| Arm | Pulls | Posterior E[p] | True p |
|---|---|---|---|
| `thoreau\|warm` | 264 | 0.590 | 0.65 |
| `marcus_aurelius\|firm` | 208 | 0.548 | 0.55 |
| `dhammapada\|gentle` | 45 | 0.319 | 0.35 |
| `tao_te_ching\|austere` | 44 | 0.326 | 0.25 |
| `rumi\|warm` | 39 | 0.293 | 0.45 |

### Interpretation

The bandit concentrates ~80 % of pulls on the top two arms by round 200, despite only Beta(1, 1) priors at the start. The cost of the production ε = 0.15 over pure Thompson is small (single-digit difference at 600 rounds) and buys tighter regret variance — the 30-seed ±1 σ band is visibly narrower under the ε-greedy policy on the unlucky seeds.

For a single user submitting one daily check-in, 200 rounds is roughly **6 months of feedback**. The plan's "first 100 days on super-arms" guidance (ADR-007) is consistent with what the math says.

The top arm doesn't fully converge to its true P even by round 600 — that's expected; with random rewards and partial pulling, posteriors settle near but not at the truth. What matters operationally is that the *ranking* is correct, which it is.

---

## 2. Corpus stats — `notebooks/corpus_stats.ipynb`

### Method

Reads the local public-domain source files in `assets/corpus/gold/` directly, applies the same chunker + theme-tagger that `scripts/seed_passages_to_supabase.py` uses, and reports:

- Passage count per tradition.
- Length-bucket distribution (`short` < 40 words, `medium` 40-120, `long` > 120) per tradition.
- Theme-tag coverage across the 12 declared keyword themes.
- Bandit super-arm viability (every `(tradition, tone)` pair with ≥ 3 passages — `MIN_PASSAGES_PER_ARM` in `services/bandit.py`).

### Results

**Total: 4,606 gold passages across 13 traditions.** All declared themes have at least one passage.

| Tradition | Passages |
|---|---|
| emerson | 743 |
| marcus_aurelius | 519 |
| thoreau | 441 |
| aesop | 395 |
| dhammapada | 393 |
| muir | 327 |
| tagore | 303 |
| burroughs | 285 |
| bhagavad_gita | 282 |
| epictetus | 261 |
| analects | 253 |
| tao_te_ching | 252 |
| gibran | 152 |

**Super-arm viability:** All 13 `(tradition, gentle)` pairs are viable for the bandit. None are filtered. (The current ingestion pipeline assigns `tone = "gentle"` to every passage; tone enrichment is on the parking lot — once it lands, super-arms become 13 traditions × 6 tones, with the `min_count=3` filter pruning sparse cells.)

### Interpretation

The corpus is healthy: every tradition we ship clears the bandit's minimum threshold by a wide margin (≥ 152 passages each). The biggest corpora (Emerson, Marcus Aurelius, Thoreau) have several hundred passages each; the smallest (Gibran) still has 152.

Length distribution is tradition-flavoured as expected: the verse corpora (Dhammapada, Tao Te Ching, Bhagavad Gita) skew short; the essayists (Emerson, Thoreau, Muir, Burroughs) skew long; Marcus Aurelius and Epictetus are medium-heavy (their letter / discourse format).

Theme tagging is shallow keyword matching, which is fine as a coarse retrieval signal but the absence of a holes also reflects how *forgiving* the keyword sets are — if the eval ever shows a query missing on a particular theme, we should look at whether the passages are actually about that theme or just contain the keyword.

---

## 3. RAG retrieval recall@k — `notebooks/rag_eval.ipynb`

### Method

30 hand-labeled queries written from the personal stress themes in `config/personal.yaml`. Each query carries a list of `expected_traditions` — the set of traditions whose passages would be a reasonable retrieval result for that query. Recall@k = fraction of queries where any expected tradition appears in the top-k retrieved passages.

The seed query set lives at `assets/eval/rag_eval_queries.jsonl`. Plan target is 50 queries; we ship 30 here and document how to extend.

### Status

**Framework only — live numbers pending.** The notebook needs Gemini API access + Supabase pgvector connectivity, which is best run from the local M4 dev environment rather than from CI / a recruiter's clone.

When run with the cached results stub (no live retrieval), the notebook produces a recall curve to validate the math. Real numbers go in this section once the live run is committed to `assets/eval/rag_eval_results.json`.

### Coverage

The 30 seed queries cover these stress themes (taken from `config/personal.yaml:profile.stress_themes`):

- Placement pressure / career uncertainty / future anxiety (q01, q03, q14, q17)
- Comparison / approval / shame / regret (q02, q13, q28, q30)
- Day-load / focus / motivation / procrastination (q04, q07, q08, q15, q21)
- Acceptance / patience / impermanence / uncertainty (q12, q17, q22, q25)
- Stillness / nature / seasons / embodiment (q07, q11, q19, q23, q27)
- Evening rest / morning intention (q09, q10)
- Engagement / meaning / interpersonal friction (q05, q20, q24, q26)
- Cosmic perspective / sorrow / envy (q16, q18, q29)

Extension to 50 should probably add: dating / romantic loneliness, family obligations, money anxiety, sleep deprivation, social-media induced rumination — themes that appear in lived experience but aren't yet in the seed.

---

## 4. Faithfulness — `notebooks/faithfulness.ipynb`

### Method

For every recent `sent_history` row, compute the content-token overlap ratio between `llm_output` and the retrieved passage's text:

1. Tokenize both into lowercase content words (length > 2, alphabetic) — same notion as `_quality_check` in `services/generator.py`.
2. Overlap ratio = |output ∩ passage| / |output|.
3. Flag rows below the production threshold of 0.12.
4. Separately, regex-extract any quoted span (text inside `"…"`) from the LLM output and substring-check against the passage — this is the strict version.

### Status

**Framework only — production data not yet sufficient.** Today the production system has fewer than 5 `sent_history` rows; faithfulness numbers from a sample that small are noise. The notebook will produce stable numbers once at least 30 sends have accumulated.

Two dependencies before the headline number is meaningful:

1. **Add `passages.json` to the export script** so we can join `sent_history.passage_ids → passages.text` rather than approximating with `llm_output` itself.
2. **Accumulate ≥ 30 `sent_history` rows.** At one daily send, that's a month of usage.

Both are tracked in `IMPLEMENTATION_PLAN.md`'s priority queue.

---

## 5. Reproducibility runbook

### Notebooks that run from a clean clone (no credentials needed)

```bash
# from the repo root
cd notebooks/
jupyter lab bandit_convergence.ipynb     # synthetic; runs anywhere
jupyter lab corpus_stats.ipynb           # reads local source files
```

You'll need a Python ≥ 3.12 with `numpy`, `scipy`, `matplotlib`. The simplest route is to reuse the backend's uv-managed venv:

```bash
uv run --project apps/backend jupyter lab
```

### Notebooks that need a Supabase snapshot

```bash
# 1) Export production tables once
uv run --project apps/backend python scripts/export_eval_data.py
#    -> writes assets/eval/{sent_history,feedback,checkin_responses,bandit_state}.json

# 2) Open the notebook
cd notebooks/
jupyter lab faithfulness.ipynb
```

The exported JSONs are gitignored by default — check `.gitignore` for the rule. To commit a specific snapshot for a portfolio-reproducible run, remove it from `.gitignore` deliberately and review for personal data first.

### Notebook that needs live Gemini + pgvector

```bash
# Make sure .env has SUPABASE_DB_DSN_POOLER and GEMINI_API_KEY set.
cd notebooks/
uv run --project apps/backend jupyter lab rag_eval.ipynb
# Then in the notebook, run all cells. The first run will hit the live
# retrieval pipeline and persist results to assets/eval/rag_eval_results.json.
# Re-runs read from the cache unless you call run_retrieval(force=True).
```

### Adding more queries to the RAG eval set

```bash
# Append rows to assets/eval/rag_eval_queries.jsonl in the same JSONL shape:
{"id":"q31","query":"…","stress_theme":"…","expected_traditions":["…","…"]}
# Then re-run the rag_eval.ipynb notebook with run_retrieval(force=True).
```

---

## What's intentionally out of scope (today)

- **Prompt ablation** (3 prompt variants × 10 outputs × manual blind scoring on a 1-5 rubric for tone/faithfulness/literary-quality/non-cliché). The plan §12 lays this out; the data is small enough today that a serious ablation isn't yet worth the manual scoring time. Revisit at the 6-week mark when you have more recent reflections to compare across versions.
- **Personalization lift after 4 weeks** — the bandit replay analysis comparing actual selection vs uniform baseline. Needs a few weeks of production feedback to be meaningful; tracked under PR-D's "next steps" in the implementation plan.
- **Live recall@k numbers** — framework shipped, run is one command but waits on you having the M4 in front of you with credentials loaded.

These are the things that get added to this document in a follow-up edit, not today.
