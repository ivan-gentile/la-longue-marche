# Opus 4.7 vs Gemini 3.1 Pro benchmark — summary

Run: 2026-04-17T15:02:17

## Cost + latency totals

| Model | Pages | Input tok | Output tok | Cost (USD) | Avg latency (s) |
|-------|-------|-----------|------------|------------|-----------------|
| gemini_pbp | 5 | 8,940 | 3,402 | $0.059 | n/a (cached) |
| claude_pbp | 5 | 31,700 | 8,452 | $1.109 | 26.1 |

## Ground-truth slice (Section 49.1, 140-3 p.495-499)

Scored with the `diagnose_49_1` categorization against `49.1new.tex`.
Higher `quality` = closer to Mateo's publishable conventions.

| Variant | length (chars) | raw residue/kc | notation drift/kc | structure coverage | composite quality |
|---------|----------------|----------------|-------------------|--------------------|-------------------|
| shipped_49_1_old | 12,535 | 4.71 | 5.42 | 7% | **0.113** |
| gemini_pbp | 9,020 | 3.33 | 7.1 | 14% | **0.132** |
| claude_pbp | 14,125 | 0.71 | 1.42 | 79% | **0.743** |

See [`49_1_error_profile.md`](49_1_error_profile.md) for the category definitions.

## Blind A/B slice

See [`benchmark_opus_vs_gemini.html`](benchmark_opus_vs_gemini.html) — open in a browser, click A/B on each pair. Votes persist in localStorage; the 'export my votes' button produces a JSON we can incorporate.

