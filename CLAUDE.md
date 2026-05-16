# CLAUDE.md — Orange Model Demo Web-App

## 1. Project purpose

Build a small web-app whose only job is to **showcase prediction models trained in [Orange Data Mining](https://orangedatamining.com/) (`.pkcls` files)** in front of a non-technical audience. The models are built by doctors-in-training using Orange's no-code canvas; this app is the "real-world demo" layer on top of them.

The app must work for **any** `.pkcls` model the user drops in, not just one. When a model is selected, the app must:

1. Inspect the model to discover what input variables it needs.
2. Render a form whose fields match those variables (numeric input for continuous, dropdown for categorical).
3. Call the model and show: predicted class, per-class probability, and the top contributing features for the prediction.

Two example models are already in the repo (`models/` folder):

- `DM2 with glucose workflo.pkcls` — Logistic Regression, 14 raw inputs including `glucose`, target `diabetic` (No/Yes).
- `DM2 without glucose workflo.pkcls` — same as above but without `glucose` (13 raw inputs).

The `.ows` files in `models/` are the original Orange workflows — keep them in the repo as reference, the app does not need to parse them.

---

## 2. Background a developer needs to understand before writing code

`.pkcls` is a Python pickle of an `Orange.classification.*` classifier object. It is **not** a portable scikit-learn pickle. To load it you must `pip install Orange3` on the server; plain sklearn is not enough.

### Two non-obvious things about Orange models

**(a) The domain is one-hot expanded.** Orange's Preprocess widget (`Continuize`) converts every binary categorical column into two columns of the form `<name>=<value>`. After training, the model's `domain.attributes` contains the *expanded* columns (e.g. 19 columns for the without-glucose model), not the original 13 user-facing fields. The app must reconstruct the original raw inputs from these expanded names.

The reconstruction rule:

- If an attribute name contains `=`, split on the first `=`. The left side is the **raw variable name**, the right side is one of its **categorical values**. Collect all values that share the same raw name to build a dropdown.
- If the attribute name has no `=`, it's a **continuous** variable, used as-is.

Worked example (without-glucose model has these 19 expanded attributes):

```
age, gender=Female, gender=Male, pulse_rate, systolic_bp, diastolic_bp,
height, weight, bmi, family_diabetes=0, family_diabetes=1,
hypertensive=0, hypertensive=1, family_hypertension=0, family_hypertension=1,
cardiovascular_disease=0, cardiovascular_disease=1, stroke=0, stroke=1
```

Reconstructs to **13 raw inputs**:

```
age (number), gender (Female/Male), pulse_rate (number), systolic_bp (number),
diastolic_bp (number), height (number), weight (number), bmi (number),
family_diabetes (0/1), hypertensive (0/1), family_hypertension (0/1),
cardiovascular_disease (0/1), stroke (0/1)
```

Class variable: `diabetic` with values `(No, Yes)`. Read it from `model.domain.class_var.values`.

**(b) The "with glucose" model pulls in Qt at unpickle time.** It transitively imports `Orange.widgets.utils.colorpalettes`, which imports `AnyQt`. On a headless server `pickle.load` will fail with `ImportError: cannot import name 'QPainter' from 'AnyQt.QtGui'` unless Qt is installed. The Docker image **must** include `PyQt5` (or `AnyQt` with PyQt5 backend) and an X-less Qt platform plugin. Set `QT_QPA_PLATFORM=offscreen` in the container environment. Without this, the model load will crash on the first request.

### Inference contract Orange uses

Build an `Orange.data.Table` with the **raw** (pre-expansion) domain you reconstructed, then call the model — Orange applies the bound transforms automatically:

```python
pred_idx, probs = model(table, model.ValueProbs)
predicted_label = model.domain.class_var.values[int(pred_idx[0])]
class_probabilities = dict(zip(model.domain.class_var.values, probs[0].tolist()))
```

Do **not** call `model.skl_model.predict()` directly with raw user inputs — it will get the wrong shape because it expects the one-hot expanded matrix.

### Top contributing features

For Logistic Regression models the underlying `model.skl_model.coef_` is shape `(1, n_expanded_features)`. For a given prediction:

1. Get the one-hot expanded row Orange computed (`table.transform(model.domain).X[0]`).
2. Multiply elementwise by `model.skl_model.coef_[0]` → per-expanded-feature contribution to the log-odds.
3. Group contributions back to their **raw** variable name (sum the `=Female` and `=Male` contributions back into `gender`, etc.).
4. Sort by absolute value, return top 5 with sign (positive = pushed toward predicted class, negative = pushed away).

For non-LR models (RandomForest, GradientBoosting) fall back to `model.skl_model.feature_importances_` if present, otherwise skip the "top contributors" section silently.

---

## 3. Architecture

Split into two deployables:

```
┌────────────────────────┐         ┌─────────────────────────┐
│ Next.js frontend       │  HTTPS  │ FastAPI backend         │
│ Vercel (or local dev)  │ ──────▶ │ Coolify VPS via Docker  │
│ - model dropdown       │  JSON   │ - Orange3 + PyQt5       │
│ - dynamic form         │         │ - /models/ + uploads/   │
│ - results display      │         │ - cached model registry │
└────────────────────────┘         └─────────────────────────┘
```

**Backend (FastAPI):**
- Loads every `.pkcls` in `models/` at startup, plus anything in `uploads/`.
- Caches loaded model objects in memory keyed by filename.
- Exposes a small JSON API (spec in §6).
- Dockerised. Deployed on Coolify.

**Frontend (Next.js, App Router, TypeScript):**
- Static-friendly: prefers Server Components for the model list, Client Components for the form.
- Calls backend via `NEXT_PUBLIC_API_BASE_URL` env var.
- Deployed on Vercel.

---

## 4. Core feature: dynamic model introspection

This is the single most important piece of the app. Implement it as a pure backend function `introspect_model(model) -> ModelSchema` and unit-test it against both bundled models.

`ModelSchema` shape (JSON-serialisable):

```json
{
  "model_id": "DM2 without glucose workflo",
  "algorithm": "LogisticRegressionClassifier",
  "target": {
    "name": "diabetic",
    "type": "categorical",
    "values": ["No", "Yes"]
  },
  "inputs": [
    {"name": "age", "type": "continuous"},
    {"name": "gender", "type": "categorical", "values": ["Female", "Male"]},
    {"name": "pulse_rate", "type": "continuous"},
    {"name": "family_diabetes", "type": "categorical", "values": ["0", "1"]}
  ],
  "supports_contributions": true
}
```

Algorithm: walk `model.domain.attributes`, group by left-of-`=` (or use the attribute itself if no `=`), preserve original order of first appearance. Keep continuous and categorical sets in the order Orange stored them — doctors built the workflow with a specific column order and the form should respect it.

For categorical values, preserve Orange's order (so `Female` comes before `Male`, `0` before `1`).

If the introspection encounters an attribute Orange has marked as continuous but whose name looks like `name=value` (rare edge case from `Discretize`), treat as categorical.

---

## 5. UI / UX requirements

### Page: `/`

- **Header:** project title + short tagline ("Demo of Orange-trained models").
- **Model selector:** dropdown listing every model the backend exposes. Show filename without `.pkcls` extension and the algorithm name as a subtitle. Default to the first bundled model.
- **Upload tile:** "Have your own `.pkcls`? Upload it." Accepts `.pkcls`, POSTs to `/api/models`, on success refreshes the dropdown and selects the new model.
- **Form:** dynamically rendered from `ModelSchema.inputs`. Continuous → number input (allow decimals). Categorical → native `<select>` with the model's values. Every field required. Show the raw variable name as the label, prettified (snake_case → "Snake case"), and the original name in a small monospace hint underneath so doctors recognise it.
- **Predict button:** disabled until all required fields have values.

### Results panel (appears after a successful predict)

- Big predicted class label, colour-coded if it's a 2-class model (positive class = warning amber, negative = neutral). Make the colour mapping configurable in code but don't ship a hardcoded medical interpretation — the user explicitly does not want this app to look like a diagnostic tool.
- Probability bars for every class, with the percentage written to one decimal.
- **Top contributing features** (only if `supports_contributions`): up to 5 rows, each showing the raw variable name, the user's input value, and a signed bar indicating push toward / away from the predicted class. Add a short tooltip explaining "Higher = pushed result toward <predicted class>".
- A "Disclaimer" line at the bottom of the panel in muted text: *"Educational demo only. Not for clinical use."*

### Empty / error states

- No models in `models/` and `uploads/`: friendly empty state with instructions ("Drop a `.pkcls` file into `backend/models/` and restart, or upload one now").
- Backend unreachable: clear error with the API URL the frontend is trying to hit (useful when CORS/env vars are wrong).
- Upload rejected (not a real `.pkcls`, wrong Orange version, missing Qt): show the backend's error message verbatim — these are diagnostic for the user.

### Styling

- Tailwind CSS.
- Mobile-friendly single column on narrow viewports.
- Avoid heavy UI kits. Lightweight components only.

---

## 6. Backend API contract

All responses JSON. All errors are HTTP 4xx/5xx with `{"detail": "..."}` body (FastAPI default).

| Method | Path                       | Purpose                                         |
| ------ | -------------------------- | ----------------------------------------------- |
| GET    | `/api/health`              | `{"status": "ok"}`                              |
| GET    | `/api/models`              | List all models with their `ModelSchema`        |
| GET    | `/api/models/{model_id}`   | Single `ModelSchema`                            |
| POST   | `/api/models`              | Upload a new `.pkcls`. Multipart form, field `file`. Returns the saved `ModelSchema`. |
| POST   | `/api/models/{model_id}/predict` | Body: `{"inputs": {<raw_name>: <value>, ...}}`. Returns `PredictionResult` |
| DELETE | `/api/models/{model_id}`   | Only deletes uploaded models, never bundled ones (HTTP 403 if bundled) |

`PredictionResult`:

```json
{
  "predicted_class": "Yes",
  "probabilities": {"No": 0.21, "Yes": 0.79},
  "contributions": [
    {"feature": "glucose", "input_value": 180, "contribution": 1.42},
    {"feature": "bmi", "input_value": 31.2, "contribution": 0.88}
  ]
}
```

CORS: allow the Vercel frontend origin via env var `FRONTEND_ORIGIN` (comma-separated for multiple). Default in dev: `http://localhost:3000`.

---

## 7. Project structure

```
/
├── CLAUDE.md                         # this file
├── README.md                         # short user-facing readme
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI app, routers wired
│   │   ├── routes/
│   │   │   ├── models.py             # list / get / upload / delete
│   │   │   └── predict.py            # predict endpoint
│   │   ├── core/
│   │   │   ├── registry.py           # in-memory model cache, file watch
│   │   │   ├── introspect.py         # ModelSchema reconstruction
│   │   │   ├── predict.py            # raw inputs → Orange Table → result
│   │   │   └── contributions.py      # LR coefficient attribution
│   │   └── schemas.py                # pydantic models
│   ├── models/                       # bundled .pkcls (committed)
│   ├── uploads/                      # runtime uploads (gitignored, persisted volume in Coolify)
│   ├── tests/
│   │   ├── test_introspect.py        # asserts schema for both bundled models
│   │   └── test_predict.py           # sanity prediction with known input
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .dockerignore
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                  # model picker + form + results
│   │   └── api-client.ts             # typed fetch wrapper
│   ├── components/
│   │   ├── ModelPicker.tsx
│   │   ├── DynamicForm.tsx
│   │   ├── ResultsPanel.tsx
│   │   └── ContributionsChart.tsx
│   ├── public/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── .env.example                  # NEXT_PUBLIC_API_BASE_URL=
├── docker-compose.yml                # local dev: backend + (optional) frontend
└── .github/workflows/                # optional CI
```

Move the existing `.pkcls` and `.ows` files into `backend/models/` as the first step.

---

## 8. Backend implementation notes

- **Python 3.11**. Pin in `pyproject.toml`.
- Use `uv` or plain `pip` — pick one and be consistent.
- Dependencies: `fastapi`, `uvicorn[standard]`, `python-multipart`, `Orange3==3.40.0` (match the user's local Orange version), `PyQt5`, `numpy`, `scikit-learn` (Orange will install a compatible version, but pin if needed).
- At import time, set `os.environ["QT_QPA_PLATFORM"] = "offscreen"` **before** importing anything from `Orange.widgets`.
- The model registry should:
  - Scan `models/` and `uploads/` on startup.
  - Cache loaded models in memory (loading is slow).
  - Provide a reload endpoint for dev (`POST /api/admin/reload`, gate behind a debug flag).
- Uploaded filenames: sanitise to `[a-zA-Z0-9._-]`, reject if the resulting name collides with a bundled model.
- Validate uploads by attempting `pickle.load` *inside* a try/except, then check the loaded object has `domain` and `domain.class_var` attributes. If not, reject with HTTP 400 and a clear message.
- For predict requests, coerce inputs:
  - Continuous: `float(value)`, reject if not coercible.
  - Categorical: must be exactly one of the model's declared values for that variable. Compare as strings.

### Skeleton of the predict path

```python
def predict(model, raw_inputs: dict) -> PredictionResult:
    schema = introspect_model(model)
    domain = build_raw_domain(schema, target=model.domain.class_var)
    row = [raw_inputs[i.name] for i in schema.inputs]
    table = Orange.data.Table.from_list(domain, [row])
    pred, probs = model(table, model.ValueProbs)
    predicted_label = model.domain.class_var.values[int(pred[0])]
    return PredictionResult(
        predicted_class=predicted_label,
        probabilities=dict(zip(model.domain.class_var.values, probs[0].tolist())),
        contributions=compute_contributions(model, table, predicted_label),
    )
```

---

## 9. Frontend implementation notes

- Next.js 14+, App Router, TypeScript, Tailwind.
- Single page is enough. Resist the urge to add routing.
- Fetch model list server-side on the page load for fast first paint; the form interaction is client-side.
- Form state in `useState`; no need for React Hook Form for this scale.
- Type the API responses in `api-client.ts` and reuse those types across components.
- Use `fetch` directly, no extra HTTP client library.
- Show a small "Loading model…" spinner when switching between models (the schema fetch is fast but uploads aren't).

---

## 10. Docker + Coolify deployment

### `backend/Dockerfile` outline

```dockerfile
FROM python:3.11-slim

# Qt runtime for the "with glucose" model
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libegl1 libxkbcommon0 libdbus-1-3 libfontconfig1 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
    libxcb-render-util0 libxcb-shape0 libxcb-sync1 libxcb-xfixes0 \
    libxcb-xkb1 libxkbcommon-x11-0 \
 && rm -rf /var/lib/apt/lists/*

ENV QT_QPA_PLATFORM=offscreen \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY app ./app
COPY models ./models
RUN mkdir -p /app/uploads

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Coolify setup

- New application → Docker → point at this repo, build context `backend/`.
- **Persistent volume:** mount `/app/uploads` so user-uploaded models survive redeploys.
- **Environment variables:** `FRONTEND_ORIGIN=https://<your-vercel-domain>`, `QT_QPA_PLATFORM=offscreen`.
- **Healthcheck:** GET `/api/health`.
- **Resources:** start with 1 vCPU / 1 GB RAM. Orange + a few cached models comfortably fit; bump if you load many large models.

### Vercel setup (frontend)

- Import the GitHub repo, set **Root Directory** to `frontend/`.
- Env var: `NEXT_PUBLIC_API_BASE_URL=https://<backend-domain-on-coolify>`.
- Build command: default (`next build`). Output: default.

### Local dev

```bash
# Backend
cd backend && pip install -e .
uvicorn app.main:app --reload

# Frontend
cd frontend && pnpm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 pnpm dev
```

A `docker-compose.yml` at the repo root should spin up both for one-command local testing.

---

## 11. Gotchas — do not skip

1. **Pin `Orange3==3.40.0`.** The models were saved against 3.40.0. Newer Orange occasionally changes pickle internals.
2. **`QT_QPA_PLATFORM=offscreen` must be set before importing Orange.** Put it at the very top of `app/main.py`, before any Orange import.
3. **Bundled models are read-only.** The DELETE endpoint must distinguish bundled (`models/`) from uploaded (`uploads/`) and refuse to delete bundled.
4. **CORS.** Vercel frontend on a different domain → set `FRONTEND_ORIGIN` correctly or every request fails preflight.
5. **Pickle is unsafe.** Only load `.pkcls` files from the bundled folder or from authenticated uploads. There is no auth in scope here, so document clearly in the README that this deployment must not be exposed to the public internet without an upload allowlist or auth layer.
6. **Filename sanitisation.** Reject path traversal, reject non-`.pkcls` extensions, cap upload size at 50 MB.
7. **Vercel will not host the backend.** Orange3 + PyQt5 + scipy + numpy is far above Vercel's serverless function size limit. The frontend goes on Vercel; the backend goes on Coolify. Do not waste time trying to put the Python API on Vercel.

---

## 12. Out of scope (don't build these)

- User authentication / accounts.
- Storing prediction history.
- Editing or retraining models — this is a *demo* of doctor-trained models.
- Multi-language UI.
- Mobile native apps.
- Any clinical-decision-support styling or claims. Educational demo only.

---

## 13. Definition of done

The project is done when a fresh contributor can:

1. `docker compose up` and open `http://localhost:3000`.
2. See both bundled models in the dropdown.
3. Switch between them and watch the form re-render with different fields.
4. Submit a prediction and see class + probabilities + top contributing features.
5. Upload a third `.pkcls` and have it appear in the dropdown without restarting.
6. Deploy the backend to Coolify and the frontend to Vercel by following the README, with the demo working end-to-end on the public URL.

Both bundled models — including the "with glucose" one that needs Qt — must work in the Docker container.
