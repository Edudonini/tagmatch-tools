TagMatch Tools — standalone, stateless, no-auth utilities reusing logic from the [`tagmatch`](https://github.com/Edudonini/TagMatch) package.

## Live

https://tagmatch-tools.vercel.app

## Tools

- `/extract-map` — extract a TagMatch spec from a Whimsical SVG export, with an optional event-by-event review mode (visual crop preview, edit/delete/add).
- `/extract-logs` — parse and merge Logcat/NDJSON/Dev JSON/Firebase log files into one deduplicated events table.

## Getting Started

### Prerequisites

`tagmatch` (the core extraction library) lives in a **private** repo (`Edudonini/TagMatch`). You need a GitHub Personal Access Token with read access to it, configured via `~/.netrc`:

```
machine github.com
login x-access-token
password <your-PAT>
```

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

Deployed via `vercel --prod`. Production needs the same private-repo credential as local dev, provided via Vercel Environment Variables (Production + Preview scopes): `GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0` (contains the PAT, marked Sensitive), `GIT_CONFIG_VALUE_0` — this rewrites `https://github.com/...` git URLs to include the credential during the build only.
