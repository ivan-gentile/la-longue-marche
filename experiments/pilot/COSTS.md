# API cost of every production run

Generated 2026-08-15 by `experiments/pilot/recompute_costs.py` from the cached per-page token counts — no API calls.

Thinking tokens are reported separately from visible output tokens by the Gemini API but are billed at the output rate. The runners originally left them out of the arithmetic, so every figure this project published for a run with thinking enabled was several times below the real bill. The last column recomputes each run with that old thinking-free arithmetic, so the two columns are the same data priced both ways. (It is computed, not read back from summary.json — those files have already been corrected in place, so reading them would just print the fixed figure twice.)

| Document | Variant | Model | Pages | Tokens in | Tokens out | Thinking | **True cost** | Old arithmetic |
|---|---|---|---|---|---|---|---|---|
| La Longue Marche 140-3 | february-original (Pro, superseded) | gemini-3.1-pro-preview | 696 | 1,328,726 | 388,208 | 2,893,266 | **$42.04** | $7.32 |
| La Longue Marche 140-4 | february-original (Pro, superseded) | gemini-3.1-pro-preview | 280 | 543,198 | 126,355 | 1,094,849 | **$15.74** | $2.60 |
| La Longue Marche 140-3 | production-flash-lite (text-first-fewshot) | gemini-3.1-flash-lite-preview | 694 | 1,240,220 | 444,922 | 3,457,197 | **$6.16** | $0.98 |
| La Longue Marche 140-4 | production-flash-lite (text-first-fewshot) | gemini-3.1-flash-lite-preview | 280 | 499,988 | 146,679 | 1,346,235 | **$2.36** | $0.35 |
| La Longue Marche 140-3 | mateo-canonical (Pro) | gemini-3.1-pro-preview | 696 | 1,982,540 | 402,678 | 4,315,239 | **$60.58** | $8.80 |
| La Longue Marche 140-4 | mateo-canonical (Pro) | gemini-3.1-pro-preview | 280 | 791,172 | 129,148 | 1,512,158 | **$21.28** | $3.13 |
| La Longue Marche 140-3 | flash-lite-mateo | gemini-3.1-flash-lite-preview | 696 | 1,970,849 | 365,565 | 2,048,346 | **$4.11** | $1.04 |
| La Longue Marche 140-4 | flash-lite-mateo | gemini-3.1-flash-lite-preview | 280 | 791,172 | 121,517 | 711,215 | **$1.45** | $0.38 |
| Préschémas (Bourbaki Schémas) | page-by-page (Flash-Lite) | gemini-3.1-flash-lite-preview | 437 | 611,965 | 335,906 | 0 | **$0.66** | $0.66 |
| Catégories de variétés (U46) | page-by-page (Pro) | gemini-3.1-pro-preview | 100 | 198,833 | 68,909 | 382,902 | **$5.82** | $1.22 |

**Total across all runs: $160.20** (the old thinking-free arithmetic gave $26.48).

Prices assumed (USD per 1M tokens): `gemini-3.7-flash` in $0.75 / out $3.75; `gemini-3.1-flash-lite-preview` in $0.25 / out $1.50; `gemini-3.5-flash-lite` in $0.30 / out $2.50; `gemini-3.1-pro-preview` in $2.00 / out $12.00; `gemini-3.6-flash` in $1.50 / out $7.50; `gemini-3.5-flash` in $1.50 / out $7.50.

Note: the per-model benchmark tables in `README.md` come from `bench_*/results.json`, which never recorded thinking tokens, so those per-page costs cannot be recomputed here and remain understated for the Gemini rows.
