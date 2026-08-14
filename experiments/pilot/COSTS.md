# API cost of every production run

Generated 2026-08-14 by `experiments/pilot/recompute_costs.py` from the cached per-page token counts — no API calls.

Thinking tokens are reported separately from visible output tokens by the Gemini API but are billed at the output rate. The runners originally left them out of the arithmetic, so every figure this project published for a run with thinking enabled was several times below the real bill. The corrected totals are below; the last column is what was published before.

| Document | Variant | Model | Pages | Tokens in | Tokens out | Thinking | **True cost** | Previously stated |
|---|---|---|---|---|---|---|---|---|
| La Longue Marche 140-3 | mateo-canonical (Pro) | gemini-3.1-pro-preview | 696 | 1,978,820 | 401,914 | 4,341,243 | **$60.88** | $8.78 |
| La Longue Marche 140-4 | mateo-canonical (Pro) | gemini-3.1-pro-preview | 280 | 791,172 | 129,602 | 1,524,706 | **$21.43** | $3.14 |
| La Longue Marche 140-3 | flash-lite-mateo | gemini-3.1-flash-lite-preview | 696 | 1,970,105 | 366,585 | 2,046,872 | **$4.11** | $1.05 |
| La Longue Marche 140-4 | flash-lite-mateo | gemini-3.1-flash-lite-preview | 280 | 791,172 | 121,517 | 711,215 | **$1.45** | $0.38 |
| Préschémas (Bourbaki Schémas) | page-by-page (Flash-Lite) | gemini-3.1-flash-lite-preview | 437 | 611,280 | 350,507 | 0 | **$0.68** | $0.68 |
| Catégories de variétés (U46) | page-by-page (Pro) | gemini-3.1-pro-preview | 23 | 45,294 | 15,699 | 77,834 | **$1.21** | $0.20 |

**Total across all runs: $89.76** (the old thinking-free arithmetic gave $14.30).

Prices assumed (USD per 1M tokens): `gemini-3.1-pro-preview` in $2.00 / out $12.00; `gemini-3.1-flash-lite-preview` in $0.25 / out $1.50.

Note: the per-model benchmark tables in `README.md` come from `bench_*/results.json`, which never recorded thinking tokens, so those per-page costs cannot be recomputed here and remain understated for the Gemini rows.
