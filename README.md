TagMatch Tools — standalone, stateless, no-auth utilities reusing logic from the [`tagmatch`](https://github.com/Edudonini/TagMatch) package.

## Live

https://tagmatch-tools.vercel.app

## Tools

- `/extract-map` — extract a TagMatch spec from a Whimsical SVG export, read it in a clean Map view (events grouped by screen; expand a row for its parameters), review/edit it, then continue straight into Query Builder or Matching with the spec in hand.
- `/extract-logs` — parse and merge Logcat/NDJSON/Dev JSON/Firebase log files into one deduplicated events table.
- `/build-query` — generate Databricks SQL (validation, volumetry, funnel, custom) from an extracted spec.
- `/match` — compare an extracted spec against extracted logs (coverage, confidence, per-event divergences, unmatched logs).

## Getting Started

### Prerequisites

`tagmatch` (the core extraction library) lives in a **private** repo (`Edudonini/TagMatch`), while this repo is public. `requirements.txt` installs it from a wheel in `vendor/` that is built locally and **never committed** (`/vendor/*.whl` is gitignored); `vendor/TAGMATCH_COMMIT` records the pinned TagMatch commit. Before the first `pip install`, and whenever the pin moves, build it from a local clone of TagMatch:

```bash
scripts/build-tagmatch-wheel.sh "$(cat vendor/TAGMATCH_COMMIT)" [path-to-TagMatch-clone]   # default clone: ../TagMatch
```

To move the pin, run the script with the new commit and commit the updated `vendor/TAGMATCH_COMMIT`.

### Local development

This is a Next.js app with a Python (Flask) API function. Locally, without the Vercel CLI's Python emulation (`vercel dev` requires interactive OAuth login), run both processes separately:

```bash
# Terminal 1: Python API
python -m venv .venv
source .venv/Scripts/activate  # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
flask --app api/extract-map.py run --port 5328

# Terminal 2: Next.js frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). `next.config.ts` proxies `/api/extract-map` requests to `http://127.0.0.1:5328` when `NODE_ENV=development`, so the frontend talks to the local Flask process transparently.

### Running tests

```bash
source .venv/Scripts/activate
python -m pytest api/tests/ -v
```

### Deployment

Deployed via `vercel --prod` from a working copy that has the wheel built (see Prerequisites). The CLI uploads the gitignored wheel with the deployment and the build installs `tagmatch` from it, so no private-repo credential is needed (the old `GIT_CONFIG_*` PAT variables are no longer used).
