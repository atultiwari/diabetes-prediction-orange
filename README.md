# Orange Model Demo

A small web-app that showcases prediction models trained in
[Orange Data Mining](https://orangedatamining.com/) (`.pkcls` files). Drop a
trained classifier in, the app inspects it, renders the right form fields,
runs predictions, and shows the top contributors. Built around doctor-trained
diabetes models, but works for any Orange classifier.

> Educational demo only. Not for clinical use.

## Stack

- Backend — FastAPI + Orange3 3.40.0 + PyQt5 (offscreen) on Python 3.11
- Frontend — Next.js 14 (App Router) + TypeScript + Tailwind
- Two example models bundled: `DM2 with glucose workflo.pkcls`, `DM2 without glucose workflo.pkcls`

See `CLAUDE.md` for the full design contract.

## Quick start with `./dev.sh`

The repo ships with a single helper script that wraps every common task —
venv creation, dependency installs, running each service, running both
together, tests, builds, and the Docker workflow. **Use this for local dev.**

Requirements on your machine:

- [`uv`](https://github.com/astral-sh/uv) (installs Python 3.11 automatically the first time)
- `pnpm` and `node` 20+
- `docker` (only for the `docker:*` subcommands)

First time:

```bash
./dev.sh setup            # backend venv + frontend node_modules + .env.local
./dev.sh start            # backend + frontend together, Ctrl-C stops both
```

Then open <http://localhost:3000>. The backend health check lives at
<http://localhost:8000/api/health>.

### All commands

| Command | What it does |
| --- | --- |
| `./dev.sh setup` | One-time install for both stacks |
| `./dev.sh setup:backend` | Backend venv + deps only |
| `./dev.sh setup:frontend` | `pnpm install` + writes `.env.local` if missing |
| `./dev.sh start` | Run **backend + frontend together**, prefixed logs, Ctrl-C stops both |
| `./dev.sh backend` | Backend only (uvicorn with `--reload`) |
| `./dev.sh frontend` | Frontend only (`next dev`) |
| `./dev.sh test [pytest args]` | Backend pytest with full arg passthrough — e.g. `./dev.sh test -k introspect -v` |
| `./dev.sh build` | Production frontend build (`next build`) |
| `./dev.sh shell` | Python REPL with the backend deps loaded |
| `./dev.sh docker:up` | `docker compose up --build` |
| `./dev.sh docker:down` | `docker compose down` |
| `./dev.sh docker:logs [svc]` | Tail compose logs for one or all services |
| `./dev.sh docker:ps` | `docker compose ps` |
| `./dev.sh status` | Show setup state + bundled model count |
| `./dev.sh clean` | Remove backend `.venv` and frontend `node_modules` / `.next` |
| `./dev.sh clean:backend` / `clean:frontend` | One side only |
| `./dev.sh help` | Print the full reference |

`up` / `down` / `logs` / `ps` are accepted as shortcuts for the `docker:` versions.

### Environment overrides

Every command honours these env vars:

| Var | Default | Effect |
| --- | --- | --- |
| `BACKEND_PORT` | `8000` | Uvicorn port |
| `FRONTEND_PORT` | `3000` | `next dev` port |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:$BACKEND_PORT` | What the frontend points at |
| `PYTHON_VERSION` | `3.11` | Passed to `uv python install` / `uv venv` |
| `PKG_MGR` | `pnpm` | Use `npm` or `yarn` instead if you prefer |
| `UV_BIN` | `uv` | Path to the `uv` executable |

Examples:

```bash
BACKEND_PORT=8001 ./dev.sh backend
NEXT_PUBLIC_API_BASE_URL=https://my-backend.example.com ./dev.sh frontend
PKG_MGR=npm ./dev.sh setup:frontend
```

## Run locally with Docker

```bash
./dev.sh docker:up          # same as: docker compose up --build
```

- Frontend: <http://localhost:3000>
- Backend:  <http://localhost:8000/api/health>

The first build pulls Orange3 + PyQt5 system libs, so it takes a few minutes.

## Run locally without the helper script

If you'd rather not use `./dev.sh`, the equivalent raw commands are:

### Backend

Requires Python 3.11. The easiest way is [uv](https://github.com/astral-sh/uv):

```bash
cd backend
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
QT_QPA_PLATFORM=offscreen .venv/bin/uvicorn app.main:app --reload --port 8000
```

Or with plain pip on a 3.11 interpreter:

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen uvicorn app.main:app --reload --port 8000
```

Test it:

```bash
cd backend
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -v
```

### Frontend

```bash
cd frontend
cp .env.example .env.local       # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
pnpm install
pnpm dev
```

## API

| Method | Path                              | Purpose                                              |
| ------ | --------------------------------- | ---------------------------------------------------- |
| GET    | `/api/health`                     | `{"status": "ok"}`                                   |
| GET    | `/api/models`                     | List every model with its `ModelSchema`              |
| GET    | `/api/models/{id}`                | Single `ModelSchema`                                 |
| POST   | `/api/models`                     | Multipart upload field `file` — returns the schema   |
| POST   | `/api/models/{id}/predict`        | Body `{"inputs": {...}}` — returns `PredictionResult` |
| DELETE | `/api/models/{id}`                | Deletes uploaded models only (bundled → 403)         |

`{id}` is the filename stem, URL-encoded. Example:

```bash
curl http://localhost:8000/api/models
curl -X POST http://localhost:8000/api/models/DM2%20without%20glucose%20workflo/predict \
  -H 'Content-Type: application/json' \
  -d '{"inputs":{"age":30,"gender":"Female","pulse_rate":72,"systolic_bp":120,"diastolic_bp":80,"height":165,"weight":60,"bmi":22,"family_diabetes":"0","hypertensive":"0","family_hypertension":"0","cardiovascular_disease":"0","stroke":"0"}}'
```

## Adding more bundled models

Drop the `.pkcls` into `backend/models/` and restart the backend. The
filename stem becomes the `model_id`. The two `.ows` files alongside are the
original Orange workflows — kept for reference, not parsed by the app.

## Deploying

### Backend → Coolify (or any Docker host)

1. New app → Docker → build context `backend/`.
2. Mount a persistent volume at `/app/uploads` so user-uploaded models survive redeploys.
3. Env vars:
   - `FRONTEND_ORIGIN=https://<your-vercel-domain>` (comma-separated if you need multiple)
   - `QT_QPA_PLATFORM=offscreen`
4. Healthcheck: GET `/api/health`.
5. 1 vCPU / 1 GB RAM is enough for the two bundled models; scale up if you load many large models.

### Frontend → Vercel

1. Import this repo on Vercel and set **Root Directory** to `frontend/`.
2. Env var: `NEXT_PUBLIC_API_BASE_URL=https://<backend-domain>`.
3. Default build command (`next build`).

Vercel **cannot** host the backend — Orange3 + PyQt5 + scipy is far over the
serverless function size limit. Use Coolify (or any VPS / container host) for
the Python API and Vercel just for the Next.js app.

## Security notes — please read before exposing publicly

- `.pkcls` is a Python pickle. Loading it executes arbitrary Python.
- The upload endpoint has filename sanitisation, a 50 MB cap, and an Orange-classifier shape check, **but there is no authentication**.
- Do **not** expose this deployment to the public internet without adding an upload allowlist, an auth layer, or disabling uploads entirely (drop the POST route).
- The bundled models are trusted because they ship in this repo and you control what's there.

## Project layout

```
├── CLAUDE.md
├── README.md
├── dev.sh                # local-dev entrypoint — see "Quick start" above
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── schemas.py
│   │   ├── core/
│   │   │   ├── introspect.py
│   │   │   ├── registry.py
│   │   │   ├── predict.py
│   │   │   └── contributions.py
│   │   └── routes/
│   │       ├── models.py
│   │       └── predict.py
│   ├── models/        # bundled .pkcls + reference .ows
│   ├── uploads/       # runtime uploads (mounted volume in prod)
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
└── frontend/
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx
    │   ├── globals.css
    │   └── api-client.ts
    ├── components/
    │   ├── ModelDemo.tsx
    │   ├── ModelPicker.tsx
    │   ├── UploadTile.tsx
    │   ├── DynamicForm.tsx
    │   ├── ResultsPanel.tsx
    │   └── ContributionsChart.tsx
    ├── tailwind.config.ts
    └── package.json
```
