# La Longue Marche — Review Site

A password-protected web app for reviewing LLM transcriptions of
Grothendieck manuscripts side by side with the archive page scans.
Built for Mateo Carmona's review pass: scan on the left, LaTeX
transcription on the right, with an optional "second reading"
(Flash-Lite draft) for the two La Longue Marche volumes and a
one-click "Report anomaly" link that opens a pre-filled GitHub issue.

Minimal Next.js 15 (App Router, TypeScript), no UI framework. The
scans are **not** in the git repo and never may be: they live in a
**private** Vercel Blob store (unauthenticated reads get 403) and are
served only through the authenticated `/api/scan/<doc>/<page>` proxy —
the browser never sees the Blob URL or token.

Deployed: <https://longue-marche-review.vercel.app>
(Vercel project `longue-marche-review`, Blob store `longue-marche-scans`).

## Documents

| id | title | pages |
| --- | --- | --- |
| `140-3` | La Longue Marche — Volume 140-3 | 696 |
| `140-4` | La Longue Marche — Volume 140-4 | 280 |
| `preschemas` | Préschémas (Bourbaki, Schémas) | 437 |
| `varietes` | Catégories de variétés (U46) | 100 |

## Environment variables

| Variable | Used by | Purpose |
| --- | --- | --- |
| `REVIEW_PASSWORD` | app | The shared login password. |
| `SESSION_SECRET` | app | HMAC key signing the session JWT (cookie `lm_session`, HS256, 90-day expiry). Use a long random string. |
| `SCAN_BASE_URL` | app | Base URL of the Vercel Blob store (private store: `https://xxxxxxxx.private.blob.vercel-storage.com`), no trailing slash. Server-side only. |
| `BLOB_READ_WRITE_TOKEN` | app + upload script | Blob token: the upload script writes with it, and the app's scan proxy reads the private store with it (sent as a bearer header, server-side only). Auto-provisioned when the store is connected to the Vercel project. |

## Run locally

```bash
cd review-site
npm install
cat > .env.local <<'EOF'
REVIEW_PASSWORD=choose-a-password
SESSION_SECRET=a-long-random-string
SCAN_BASE_URL=https://xxxxxxxx.public.blob.vercel-storage.com
EOF
npm run dev
```

Then open http://localhost:3000 and log in with `REVIEW_PASSWORD`.
Without `SCAN_BASE_URL` the app still runs; the scan pane returns
503 until it is set. Without `data/` files the app still runs; the
document list shows "transcription data not yet loaded".

## How the data gets produced

- **`data/<id>.json`** — one JSON per document with the per-page
  canonical text, optional Flash-Lite alternate, word-level similarity
  score, and warnings. Generated from the pipeline run outputs by
  `scripts/prepare_data.py` (run from the repo root). Pages missing
  from `pages` simply have no transcription yet; the app shows a
  placeholder for them.
- **Scans** — each PDF page is rendered to JPEG and uploaded to
  Vercel Blob at `scans/<id>/<NNNN>.jpg` (1-indexed PDF page number,
  zero-padded to 4) by `scripts/upload_scans.py`, which needs
  `BLOB_READ_WRITE_TOKEN`.

## Deploy on Vercel

Deployed 2026-08-15 with the Vercel CLI from this directory (no git
integration; re-deploy with `vercel deploy --prod`). To reproduce from
scratch:

1. `vercel link --yes --project longue-marche-review` in `review-site/`.
2. `vercel blob create-store longue-marche-scans --access private --yes`
   — creates a **private** store, connects it to the project, and
   provisions `BLOB_READ_WRITE_TOKEN` in all environments.
3. Set `REVIEW_PASSWORD`, `SESSION_SECRET`, and `SCAN_BASE_URL`
   (`https://<store-id-lowercase>.private.blob.vercel-storage.com`)
   with `vercel env add`.
4. `vercel env pull .env.local`, then run `scripts/upload_scans.py`
   with that env to upload the scans.
5. Keep `data/<id>.json` committed in `review-site/data/` (they contain
   only transcription text, no scans); `next.config.mjs` declares them
   in `outputFileTracingIncludes` so the deployed lambdas can read
   them — without that they silently miss from the bundle.
6. `vercel deploy --prod`. Every path except `/login` is behind the
   password.
