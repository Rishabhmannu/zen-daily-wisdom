#!/usr/bin/env python3
"""Download initial project corpus assets and static design files."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List

import requests


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
GOLD_DIR = ASSETS_DIR / "corpus" / "gold"
SILVER_DIR = ASSETS_DIR / "corpus" / "silver"
DESIGN_DIR = ASSETS_DIR / "design"
MANIFEST = ASSETS_DIR / "download_manifest.json"


@dataclass
class DownloadResult:
    name: str
    source_url: str
    output_file: str
    status: str
    bytes: int
    error: str = ""


GOLD_TEXTS: List[Dict[str, str]] = [
    {
        "name": "bhagavad_gita_song_celestial",
        "url": "https://www.gutenberg.org/cache/epub/2388/pg2388.txt",
    },
    {
        "name": "tao_te_ching_legge",
        "url": "https://www.gutenberg.org/cache/epub/216/pg216.txt",
    },
    {
        "name": "analects_legge",
        "url": "https://www.gutenberg.org/cache/epub/3330/pg3330.txt",
    },
    {
        "name": "meditations_marcus_aurelius",
        "url": "https://www.gutenberg.org/cache/epub/2680/pg2680.txt",
    },
    {
        "name": "epictetus_discourses",
        "url": "https://www.gutenberg.org/cache/epub/10661/pg10661.txt",
    },
    {
        "name": "walden_thoreau",
        "url": "https://www.gutenberg.org/cache/epub/205/pg205.txt",
    },
    {
        "name": "emerson_essays_first_series",
        "url": "https://www.gutenberg.org/cache/epub/16643/pg16643.txt",
    },
    {
        "name": "gibran_the_prophet",
        "url": "https://www.gutenberg.org/cache/epub/58585/pg58585.txt",
    },
    {
        "name": "aesops_fables",
        "url": "https://www.gutenberg.org/cache/epub/21/pg21.txt",
    },
    {
        "name": "tagore_gitanjali",
        "url": "https://www.gutenberg.org/cache/epub/7164/pg7164.txt",
    },
    {
        "name": "dhammapada_muller",
        "url": "https://www.gutenberg.org/cache/epub/2017/pg2017.txt",
    },
    {
        "name": "my_first_summer_in_the_sierra_muir",
        "url": "https://www.gutenberg.org/cache/epub/32540/pg32540.txt",
    },
    {
        "name": "wake_robin_burroughs",
        "url": "https://www.gutenberg.org/cache/epub/6982/pg6982.txt",
    },
]


def _safe_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("_")


def _download_text_asset(name: str, url: str) -> DownloadResult:
    out_file = GOLD_DIR / f"{_safe_filename(name)}.txt"
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        out_file.write_text(resp.text, encoding="utf-8")
        return DownloadResult(
            name=name,
            source_url=url,
            output_file=str(out_file.relative_to(ROOT)),
            status="ok",
            bytes=out_file.stat().st_size,
        )
    except Exception as exc:  # pragma: no cover
        return DownloadResult(
            name=name,
            source_url=url,
            output_file=str(out_file.relative_to(ROOT)),
            status="failed",
            bytes=0,
            error=str(exc),
        )


def _download_hf_silver() -> DownloadResult:
    out_file = SILVER_DIR / "abirate_english_quotes.jsonl"
    source_url = "hf://datasets/Abirate/english_quotes"

    # Keep HF cache under workspace so this script works in sandboxed envs.
    hf_home = ROOT / ".hf_cache"
    os.environ.setdefault("HF_HOME", str(hf_home))
    os.environ.setdefault("HF_DATASETS_CACHE", str(hf_home / "datasets"))

    try:
        from datasets import load_dataset
    except Exception:
        return DownloadResult(
            name="abirate_english_quotes",
            source_url=source_url,
            output_file=str(out_file.relative_to(ROOT)),
            status="failed",
            bytes=0,
            error="datasets library not available",
        )

    try:
        ds = load_dataset("Abirate/english_quotes", split="train")
        rows = []
        for row in ds:
            rows.append(
                {
                    "quote": row.get("quote", ""),
                    "author": row.get("author", ""),
                    "tags": row.get("tags", []),
                    "source_tier": "silver",
                    "dataset": "Abirate/english_quotes",
                }
            )
        with out_file.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return DownloadResult(
            name="abirate_english_quotes",
            source_url=source_url,
            output_file=str(out_file.relative_to(ROOT)),
            status="ok",
            bytes=out_file.stat().st_size,
        )
    except Exception as exc:  # pragma: no cover
        return DownloadResult(
            name="abirate_english_quotes",
            source_url=source_url,
            output_file=str(out_file.relative_to(ROOT)),
            status="failed",
            bytes=0,
            error=str(exc),
        )


def _write_design_asset() -> DownloadResult:
    out_file = DESIGN_DIR / "enso.svg"
    source_url = "generated-local"
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="220" height="220" viewBox="0 0 220 220" fill="none">
  <circle cx="110" cy="110" r="82" stroke="#2E4A3C" stroke-width="12" stroke-linecap="round" stroke-dasharray="480 90"/>
</svg>
"""
    out_file.write_text(svg, encoding="utf-8")
    return DownloadResult(
        name="enso_svg",
        source_url=source_url,
        output_file=str(out_file.relative_to(ROOT)),
        status="ok",
        bytes=out_file.stat().st_size,
    )


def ensure_dirs() -> None:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    DESIGN_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    ensure_dirs()
    results: List[DownloadResult] = []

    for item in GOLD_TEXTS:
        results.append(_download_text_asset(item["name"], item["url"]))
    results.append(_download_hf_silver())
    results.append(_write_design_asset())

    payload = {
        "summary": {
            "ok": len([r for r in results if r.status == "ok"]),
            "failed": len([r for r in results if r.status != "ok"]),
        },
        "results": [asdict(r) for r in results],
    }
    MANIFEST.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload["summary"], indent=2))
    for r in results:
        marker = "OK" if r.status == "ok" else "FAIL"
        print(f"[{marker}] {r.name} -> {r.output_file}")
        if r.error:
            print(f"       error: {r.error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
