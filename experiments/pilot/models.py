"""Single source of truth for Gemini model ids and prices.

Model ids and prices were previously copied into every runner, so a new
model release meant editing five files and the prices drifted from
reality. Everything now reads this table.

Prices are USD per 1M tokens, from Google's published Gemini API
pricing (checked 2026-08-14). **Thinking tokens bill at the output
rate** and are reported separately by the API — every cost computation
in this repo must add them to the output count (see
`recompute_costs.py` for what happens when it does not).

Note on Pro: prompts above 200K tokens are billed at a higher tier
($4.00/$18.00). Our page-by-page prompts are ~3K tokens, so the base
rate applies.

Verified available on 2026-08-14 via `client.models.list()`; the
`*-latest` aliases then resolved to:
    gemini-flash-latest       -> gemini-3.7-flash
    gemini-flash-lite-latest  -> gemini-3.5-flash-lite
    gemini-pro-latest         -> gemini-3.1-pro-preview
"""

from __future__ import annotations

MODELS: dict[str, dict] = {
    # --- current defaults -------------------------------------------------
    "flash": {
        "id": "gemini-3.7-flash",
        "cost_input": 0.75,
        "cost_output": 3.75,
        "released": "2026-08-13",
        "note": "newest Flash, and the cost-effective draft model: on the "
                "Section 49.1 ground truth it reaches 0.562 word similarity "
                "against Pro's 0.573, at a sixth of the cost "
                "(bench_models_2026_08/summary.md). Introductory pricing "
                "through 2026-12-31; reverts to $1.50/$7.50 on 2027-01-01.",
    },
    "flash-lite": {
        # Deliberately NOT the newest Flash-Lite: see "flash-lite-3.5" below.
        # This is the model that produced the shipped drafts, and it measures
        # better than its successor on the Section 49.1 ground truth.
        "id": "gemini-3.1-flash-lite-preview",
        "cost_input": 0.25,
        "cost_output": 1.50,
        "released": "2026-01",
        "note": "produced the complete flash-lite-mateo draft and the "
                "Préschémas transcription; 0.449 word similarity on Section "
                "49.1, better than the newer 3.5 Flash-Lite (0.313).",
    },
    "flash-lite-3.5": {
        "id": "gemini-3.5-flash-lite",
        "cost_input": 0.30,
        "cost_output": 2.50,
        "released": "2026-07",
        "note": "newest Flash-Lite, but NOT adopted: on Section 49.1 it scores "
                "0.313 word similarity and omits 244 of 763 reference tokens, "
                "markedly worse than the older 3.1 Flash-Lite it would replace "
                "(bench_models_2026_08/summary.md).",
    },
    "pro": {
        "id": "gemini-3.1-pro-preview",
        "cost_input": 2.00,
        "cost_output": 12.00,
        "released": "2026-01",
        "note": "still the newest Pro as of 2026-08-14 and the most faithful "
                "model measured; produced the canonical La Longue Marche "
                "corpus and remains the default for full runs.",
    },
    # --- superseded, kept so past runs stay reproducible and costable -----
    "flash-3.6": {
        "id": "gemini-3.6-flash",
        "cost_input": 1.50,
        "cost_output": 7.50,
        "released": "2026-07",
        "note": "superseded by gemini-3.7-flash.",
    },
    "flash-3.5": {
        "id": "gemini-3.5-flash",
        "cost_input": 1.50,
        "cost_output": 7.50,
        "released": "2026-05",
        "note": "superseded by gemini-3.7-flash.",
    },
}

# Historical ids that appear in stored run configs, so costs of past runs
# can still be recomputed from their recorded token counts.
PRICES_BY_ID: dict[str, dict[str, float]] = {
    spec["id"]: {"in": spec["cost_input"], "out": spec["cost_output"]}
    for spec in MODELS.values()
}
PRICES_BY_ID.setdefault("gemini-3.1-flash-lite-preview", {"in": 0.25, "out": 1.50})


def resolve(key_or_id: str) -> dict:
    """Accept either a short key ('flash') or a full model id."""
    if key_or_id in MODELS:
        return MODELS[key_or_id]
    for spec in MODELS.values():
        if spec["id"] == key_or_id:
            return spec
    raise KeyError(f"unknown model: {key_or_id}")
