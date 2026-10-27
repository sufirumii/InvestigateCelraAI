# Running and deploying

## Requirements

Python 3.11+ and outbound HTTPS. Nothing else — no Node, no database server,
no model download.

## From an IDE (PyCharm, VS Code)

1. Open the project root.
2. Create an interpreter: `python -m venv .venv` and select it.
3. `pip install -r requirements-dev.txt`
4. `cp .env.example .env` and set `HTTP_USER_AGENT` to a real contact address —
   NCBI and ClinicalTrials.gov ask for one and may rate-limit anonymous callers.
5. Run `run.py`. It puts `backend/` on the path and starts uvicorn with reload,
   so pressing Run in the IDE is all that is required.
6. Open <http://127.0.0.1:8000>.

The first request shows "Building the first edition" while the initial fetch
runs in the background, then the page loads itself. This takes 20–60 seconds
depending on how the public APIs are responding.

## From a terminal

```bash
pip install -r requirements-dev.txt
make verify   # prove every source is reachable and returning real records
make run
make test
```

## Deploying to Render

The repository contains `render.yaml`, so:

1. Push to GitHub.
2. Render → **New** → **Blueprint** → select the repository.
3. Set `HTTP_USER_AGENT` (and `ACCESS_CODE`, if you want the gate) when prompted.
4. Deploy.

Build is `pip install -r requirements.txt`; start is
`uvicorn investigatecelra.main:app --host 0.0.0.0 --port $PORT --app-dir backend`.
Health checks hit `/api/health`.

Render's free tier has an ephemeral filesystem, so `DATABASE_PATH` points at
`/tmp` and the desk refetches on each cold start. That is by design — there is
no bundled corpus to lose. For a persistent store, attach a Render disk and
point `DATABASE_PATH` at it.

Free instances sleep after inactivity; the first request after a sleep pays the
cold-start fetch.

## Docker

```bash
docker build -t investigatecelra .
docker run -p 8000:8000 -e HTTP_USER_AGENT="you@yourdomain.com" investigatecelra
```

## Configuration

Every setting is an environment variable with a working default. See
`.env.example`. The ones that matter:

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_PATH` | `var/investigatecelra.db` | SQLite file |
| `ALLOW_NETWORK` | `true` | Set false only for tests; the desk cannot build an edition without it |
| `HTTP_USER_AGENT` | generic | **Set this.** Public APIs expect a contact address |
| `MAX_ITEMS_PER_SOURCE` | `40` | Per-feed cap per refresh |
| `RECENCY_HALF_LIFE_DAYS` | `9` | A story this old scores exactly half on recency |
| `ACCESS_CODE` | empty | Set to enable the access gate |

## Troubleshooting

**The page stays on "Building the first edition".** Run `make verify`. If every
source fails, outbound HTTPS is blocked. The desk will not fall back to
placeholder content.

**Some sources fail.** Normal — feeds move. Failures are recorded per run and
visible under **Method → Ingestion history**. The desk runs on the remainder.

**Few or no trials appear.** ClinicalTrials.gov v2 rate-limits anonymous
callers. Set `HTTP_USER_AGENT` and raise `HTTP_TIMEOUT`.
