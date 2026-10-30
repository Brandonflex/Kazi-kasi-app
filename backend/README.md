# Kazi-Kasi API

The API reuses the production ranking, graph, and profile modules in `src/kazikasi`.

## Run locally

From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e .
pip install -r backend/requirements.txt
uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8001
```

For local development, set `KAZIKASI_API_SERVER_URL=http://127.0.0.1:8001` in the Next.js environment. The browser calls same-origin `/api` paths and Next proxies them to FastAPI, avoiding browser `localhost` calls and local CORS surprises. The API defaults to an ignored SQLite file at the repository root. Existing fixture or production data must be seeded intentionally; the API does not silently create demo job listings.

## Production configuration

Deploy the API as a separate ASGI service (Vercel is configured for the Next.js app). Provide:

- `APP_ENV=production`
- `KAZIKASI_SECRET_KEY`: random value of at least 32 characters. Generate with `python -c 'import secrets; print(secrets.token_urlsafe(48))'`.
- `DATABASE_URL`: managed PostgreSQL URL. Do not rely on SQLite on an ephemeral serverless filesystem.
- `KAZIKASI_CORS_ORIGINS`: comma-separated exact frontend origins, including the production URL and any preview URLs that need API access.
- `NEXT_PUBLIC_API_URL`: set on the Vercel frontend to the deployed API origin.

The app refuses to start in production without a signing key. Tokens use a 60-minute expiry by default. Passwords use PBKDF2-SHA256; legacy salted SHA-256 hashes are upgraded on the user's next successful login. Keep secrets in the hosting provider's environment-variable manager, not in Git.

## Profile and CV APIs

- `GET /api/profile` reads the signed-in user's saved profile; `PUT /api/profile` updates skills, role families, experience fit, county/area, commute, salary, work mode, employment type, and deadline preferences.
- `GET /api/profile/cv` returns the most recently extracted CV details.
- `POST /api/profile/cv` accepts a multipart `file` PDF up to 5 MB, extracts text and evidence with `pypdf`, and uses deterministic field extraction. The original PDF is discarded after processing; only extracted fields and short evidence snippets are stored.
- CV-derived skills feed the same profile ranking used by `/api/jobs`. Extracted role and location suggestions are presented for confirmation rather than silently replacing preferences.
- `DELETE /api/profile/cv` removes the latest extracted CV record. Skills already saved in the profile remain available until edited.

Scanned/image-only PDFs are rejected with a clear message; OCR is not yet implemented.

## Live job ingestion

The production FastAPI lifespan runs a bounded source sweep at startup and every six hours. It reads and writes through the configured `DATABASE_URL`, so the authenticated `/api/jobs` feed reads the same persistent jobs graph. Set `KAZIKASI_AUTO_SYNC=false` to pause it, or tune `KAZIKASI_SOURCE_SYNC_INTERVAL_SECONDS` (minimum 3600). Only sources marked `active` in the registry are automatically fetched; unverified sources remain skipped until their live parser and terms are reviewed. ReliefWeb additionally needs `RELIEFWEB_APPNAME`. See [the source-sync guide](../docs/source-sync.md) for the source-safety rules and checks.
