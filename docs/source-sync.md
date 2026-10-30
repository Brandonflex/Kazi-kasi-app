# Production job-source sync

The FastAPI backend now owns live ingestion. On startup it performs one bounded sweep, then repeats every six hours. It writes through the same `DATABASE_URL` as the API, so authenticated `/api/jobs` reads the real normalized job graph instead of an unrelated local SQLite file.

## Deployment requirements

1. Run the always-on FastAPI service from `backend.api.main:app` (not only the Vercel demo/WSGI function).
2. Set `APP_ENV=production` and the existing production `DATABASE_URL` on that service. Production startup already refuses to run without the database and signing key.
3. Keep `KAZIKASI_AUTO_SYNC` unset or set it to `true`. Set it to `false` only to pause automatic ingestion. `KAZIKASI_SOURCE_SYNC_INTERVAL_SECONDS` can adjust the interval; the minimum is one hour and the default is six hours.
4. Redeploy/restart the FastAPI service. Check `GET /api/sources` for each source's eligibility, last sync, health, and number of jobs seen. The API never returns internal fetch errors.

The worker makes a polite, bounded pass: at most ten detail pages per source per run, per-request timeouts, and the source manifest's rate limit. Failed sources are recorded as warnings and retried after their cadence. Database writes are idempotent, so restarting the service does not create duplicate jobs.

## Source safety

Only registry entries marked `active` are eligible for automatic ingestion. Sources marked `unverified` remain visible in `/api/sources`, but are skipped; they are not silently treated as live job providers. In particular, JobWeb Kenya, KenyaJobs, UN Careers, Devex, Career Point, Ajira, and TSC are not activated by this change. ReliefWeb requires `RELIEFWEB_APPNAME`; without it the source is reported as needing configuration and is skipped.

A successful HTTP response alone does not make a listing a job. The existing pipeline still validates parsed candidates before `write_job`, and the feed uses skill/profile matching. Application URLs and source URLs are retained separately from the source observation.

## Manual run

From the repository root, run a single bounded sweep against the configured database:

```bash
PYTHONPATH=src python -m kazikasi.cli sweep --timeout 20 --limit 10
```

The CLI reports per-source counts and errors. Do not use `--force` to ingest unverified sources in production: it explicitly bypasses the source verification gate.
