# API cost of every production run

Generated 2026-08-15 by `experiments/pilot/recompute_costs.py` from the cached per-page token counts — no API calls.

Thinking tokens are reported separately from visible output tokens by the Gemini API but are billed at the output rate. The runners originally left them out of the arithmetic, so every figure this project published for a run with thinking enabled was several times below the real bill. The corrected totals are below; the last column is what was published before.

| Document | Variant | Model | Pages | Tokens in | Tokens out | Thinking | **True cost** | Previously stated |
|---|---|---|---|---|---|---|---|---|
| La Longue Marche 140-3 | mateo-canonical (Pro) | gemini-3.1-pro-preview | 696 | 1,979,564 | 403,012 | 4,261,687 | **$59.94** | $59.94 |
| La Longue Marche 140-4 | mateo-canonical (Pro) | gemini-3.1-pro-preview | 280 | 791,172 | 129,148 | 1,512,158 | **$21.28** | $21.26 |
| La Longue Marche 140-3 | flash-lite-mateo | gemini-3.1-flash-lite-preview | 696 | 1,970,849 | 365,565 | 2,048,346 | **$4.11** | $4.11 |
| La Longue Marche 140-4 | flash-lite-mateo | gemini-3.1-flash-lite-preview | 280 | 791,172 | 121,517 | 711,215 | **$1.45** | $1.45 |
| Préschémas (Bourbaki Schémas) | page-by-page (Flash-Lite) | gemini-3.1-flash-lite-preview | 437 | 611,965 | 335,906 | 0 | **$0.66** | $0.66 |
| Catégories de variétés (U46) | page-by-page (Pro) | gemini-3.1-pro-preview | 100 | 198,833 | 68,909 | 382,902 | **$5.82** | $5.82 |

**Total across all runs: $93.26** (the old thinking-free arithmetic gave $15.23).

Prices assumed (USD per 1M tokens): `gemini-3.7-flash` in $0.75 / out $3.75; `gemini-3.1-flash-lite-preview` in $0.25 / out $1.50; `gemini-3.5-flash-lite` in $0.30 / out $2.50; `gemini-3.1-pro-preview` in $2.00 / out $12.00; `gemini-3.6-flash` in $1.50 / out $7.50; `gemini-3.5-flash` in $1.50 / out $7.50.

Note: the per-model benchmark tables in `README.md` come from `bench_*/results.json`, which never recorded thinking tokens, so those per-page costs cannot be recomputed here and remain understated for the Gemini rows.
