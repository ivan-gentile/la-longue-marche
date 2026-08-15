"""Recompute the API cost of every production run from the cached JSON.

Why this exists: the runners originally priced a run as

    prompt_tokens * price_in + output_tokens * price_out

but on the Gemini API `candidates_token_count` (our `output_tokens`)
excludes `thoughts_token_count`, and thinking tokens are billed at the
output rate. Every run with thinking enabled therefore recorded a cost
several times below the real bill — on the Gemini Pro corpus, thinking
tokens outnumber visible output tokens about 11 to 1, so the recorded
$8.78 for 140-3 was really $60.88.

The per-page token counts were always stored, so the true costs are
recoverable without re-running anything. This script recomputes them,
rewrites each run's summary.json with a `tokens_thinking` field and a
corrected `estimated_cost`, and writes a consolidated report to
experiments/pilot/COSTS.md.

Prices are the repo's assumed USD-per-1M-token rates for the preview
models; they are declared here so the assumption is auditable.

Usage:
    python experiments/pilot/recompute_costs.py            # report only
    python experiments/pilot/recompute_costs.py --write    # + fix summaries
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

import sys

sys.path.insert(0, str(HERE))
from models import PRICES_BY_ID as PRICES  # noqa: E402

# Every run directory on disk that holds a transcriptions.json + config.json.
# The first version of this list covered only the runs behind the current
# deliverables, which meant the "true total" it published still omitted 41% of
# documented spend — including the February corpus, which is itself published.
RUNS = [
    ("La Longue Marche 140-3", "february-original (Pro, superseded)",
     HERE / "production" / "140-3"),
    ("La Longue Marche 140-4", "february-original (Pro, superseded)",
     HERE / "production" / "140-4"),
    ("La Longue Marche 140-3", "production-flash-lite (text-first-fewshot)",
     HERE / "production-flash-lite" / "140-3"),
    ("La Longue Marche 140-4", "production-flash-lite (text-first-fewshot)",
     HERE / "production-flash-lite" / "140-4"),
    ("La Longue Marche 140-3", "mateo-canonical (Pro)",
     HERE / "production-mateo-canonical" / "140-3"),
    ("La Longue Marche 140-4", "mateo-canonical (Pro)",
     HERE / "production-mateo-canonical" / "140-4"),
    ("La Longue Marche 140-3", "flash-lite-mateo",
     HERE / "production-flash-lite-mateo" / "140-3"),
    ("La Longue Marche 140-4", "flash-lite-mateo",
     HERE / "production-flash-lite-mateo" / "140-4"),
    ("Préschémas (Bourbaki Schémas)", "page-by-page (Flash-Lite)",
     REPO / "experiments" / "bourbaki" / "production-pages"),
    ("Catégories de variétés (U46)", "page-by-page (Pro)",
     REPO / "experiments" / "varietes" / "production-pages"),
]


def audit(run_dir: Path) -> dict | None:
    tpath = run_dir / "transcriptions.json"
    if not tpath.exists():
        return None
    data = json.loads(tpath.read_text(encoding="utf-8"))
    cpath = run_dir / "config.json"
    config = json.loads(cpath.read_text(encoding="utf-8")) if cpath.exists() else {}
    model = config.get("model", "unknown")
    price = PRICES.get(model)

    ok = [v for v in data.values() if v.get("status") == "success"]
    tok_in = sum(v.get("usage", {}).get("prompt_tokens") or 0 for v in ok)
    tok_out = sum(v.get("usage", {}).get("output_tokens") or 0 for v in ok)
    tok_think = sum(v.get("usage", {}).get("thinking_tokens") or 0 for v in ok)

    if price is None:
        return {"model": model, "pages": len(ok), "unknown_price": True}

    old_cost = (tok_in * price["in"] + tok_out * price["out"]) / 1_000_000
    true_cost = (tok_in * price["in"] + (tok_out + tok_think) * price["out"]) / 1_000_000

    spath = run_dir / "summary.json"
    recorded = None
    if spath.exists():
        recorded = json.loads(spath.read_text(encoding="utf-8")).get("estimated_cost")

    return {
        "model": model,
        "thinking_level": config.get("thinking_level"),
        "pages": len(ok),
        "tokens_in": tok_in,
        "tokens_out": tok_out,
        "tokens_thinking": tok_think,
        "cost_excluding_thinking": round(old_cost, 2),
        "cost_true": round(true_cost, 2),
        "previously_recorded": recorded,
        "summary_path": spath,
    }


def rewrite_summary(run_dir: Path, a: dict) -> None:
    spath = run_dir / "summary.json"
    summary = {}
    if spath.exists():
        summary = json.loads(spath.read_text(encoding="utf-8"))
    summary["tokens_in"] = a["tokens_in"]
    summary["tokens_out"] = a["tokens_out"]
    summary["tokens_thinking"] = a["tokens_thinking"]
    # Legacy key kept by the older runner schema; keep both in sync.
    if "total_tokens_in" in summary:
        summary["total_tokens_in"] = a["tokens_in"]
        summary["total_tokens_out"] = a["tokens_out"]
    summary["estimated_cost"] = a["cost_true"]
    summary["cost_note"] = (
        "includes thinking tokens billed at the output rate; recomputed by "
        "recompute_costs.py"
    )
    spath.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true",
                    help="Rewrite each run's summary.json with the corrected cost")
    args = ap.parse_args()

    rows = []
    total_old = total_true = 0.0
    for doc, variant, run_dir in RUNS:
        a = audit(run_dir)
        if a is None:
            print(f"skip (no data): {doc} — {variant}")
            continue
        if a.get("unknown_price"):
            print(f"skip (unknown price for {a['model']}): {doc} — {variant}")
            continue
        rows.append((doc, variant, run_dir, a))
        total_old += a["cost_excluding_thinking"]
        total_true += a["cost_true"]
        if args.write:
            rewrite_summary(run_dir, a)

    lines = [
        "# API cost of every production run",
        "",
        f"Generated {date.today().isoformat()} by "
        "`experiments/pilot/recompute_costs.py` from the cached per-page token "
        "counts — no API calls.",
        "",
        "Thinking tokens are reported separately from visible output tokens by "
        "the Gemini API but are billed at the output rate. The runners "
        "originally left them out of the arithmetic, so every figure this "
        "project published for a run with thinking enabled was several times "
        "below the real bill. The last column recomputes each run with that "
        "old thinking-free arithmetic, so the two columns are the same data "
        "priced both ways. (It is computed, not read back from summary.json — "
        "those files have already been corrected in place, so reading them "
        "would just print the fixed figure twice.)",
        "",
        "| Document | Variant | Model | Pages | Tokens in | Tokens out | Thinking | **True cost** | Old arithmetic |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for doc, variant, _, a in rows:
        lines.append(
            f"| {doc} | {variant} | {a['model']} | {a['pages']} "
            f"| {a['tokens_in']:,} | {a['tokens_out']:,} | {a['tokens_thinking']:,} "
            f"| **${a['cost_true']:.2f}** | ${a['cost_excluding_thinking']:.2f} |"
        )
    lines += [
        "",
        f"**Total across all runs: ${total_true:.2f}** "
        f"(the old thinking-free arithmetic gave ${total_old:.2f}).",
        "",
        "Prices assumed (USD per 1M tokens): "
        + "; ".join(f"`{m}` in ${p['in']:.2f} / out ${p['out']:.2f}"
                    for m, p in PRICES.items())
        + ".",
        "",
        "Note: the per-model benchmark tables in `README.md` come from "
        "`bench_*/results.json`, which never recorded thinking tokens, so those "
        "per-page costs cannot be recomputed here and remain understated for "
        "the Gemini rows.",
        "",
    ]
    out = HERE / "COSTS.md"
    out.write_text("\n".join(lines), encoding="utf-8")

    for doc, variant, _, a in rows:
        print(f"{doc} — {variant}: ${a['cost_true']:.2f} "
              f"(was ${a['cost_excluding_thinking']:.2f})")
    print(f"\nTOTAL: ${total_true:.2f} (was ${total_old:.2f})")
    print(f"wrote {out.relative_to(REPO)}")
    if args.write:
        print("summary.json files rewritten with corrected costs")


if __name__ == "__main__":
    main()
