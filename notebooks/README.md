# Evaluation notebooks

Companion notebooks for the writeup in [`../EVALUATION.md`](../EVALUATION.md).

| Notebook | Reads from | Runs from a clean clone? |
|---|---|---|
| `bandit_convergence.ipynb` | nothing (synthetic simulation) | ✅ |
| `corpus_stats.ipynb` | `assets/corpus/gold/*.txt` | ✅ |
| `faithfulness.ipynb` | `assets/eval/sent_history.json` (gitignored snapshot) | needs Supabase export |
| `rag_eval.ipynb` | `assets/eval/rag_eval_queries.jsonl` + live pgvector + Gemini | needs Gemini + pgvector |

Run with the backend's uv-managed venv:

```bash
uv run --project apps/backend jupyter lab
```

To populate the Supabase-derived snapshots first:

```bash
uv run --project apps/backend python scripts/export_eval_data.py
```

See `EVALUATION.md` §5 for the full reproducibility runbook.
