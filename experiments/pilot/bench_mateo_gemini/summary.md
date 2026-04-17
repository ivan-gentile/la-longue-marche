# Opus 4.7 vs Gemini 3.1 Pro benchmark — summary

Run: 2026-04-17T15:45:31

## Cost + latency totals

| Model | Pages | Input tok | Output tok | Cost (USD) | Avg latency (s) |
|-------|-------|-----------|------------|------------|-----------------|
| gemini_pbp | 5 | 14,525 | 3,734 | $0.074 | 67.8 |
| claude_pbp | 5 | 31,700 | 9,307 | $1.173 | 28.6 |

## Ground-truth slice (Section 49.1, 140-3 p.495-499)

Scored with the `diagnose_49_1` categorization against `49.1new.tex`.
Higher `quality` = closer to Mateo's publishable conventions.

| Variant | length (chars) | raw residue/kc | notation drift/kc | structure coverage | composite quality |
|---------|----------------|----------------|-------------------|--------------------|-------------------|
| shipped_49_1_old | 12,535 | 4.71 | 5.42 | 7% | **0.113** |
| gemini_pbp | 9,962 | 0.8 | 0.9 | 71% | **0.742** |
| claude_pbp | 15,548 | 1.48 | 0.84 | 71% | **0.661** |

See [`49_1_error_profile.md`](49_1_error_profile.md) for the category definitions.

## Blind A/B slice

See [`benchmark_opus_vs_gemini.html`](benchmark_opus_vs_gemini.html) — open in a browser, click A/B on each pair. Votes persist in localStorage; the 'export my votes' button produces a JSON we can incorporate.

