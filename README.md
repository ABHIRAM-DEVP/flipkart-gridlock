# ASTRA M — Traffic Intelligence Command Platform

> Live event-driven congestion scoring + planned spillover forecasting for corridor operations.

This repo is **containerized**. It runs:
- **Astram ML service (Flask)** — scoring + planned impact + SSE live feed (port **8000**)
- **Backend (Spring Boot)** — API/orchestration + Postgres persistence (port **8080**)
- **Command Center UI (Next.js)** — dashboard modules + live overlays (port **3000**)
- **Postgres** — persists events, predictions, plans, and model run snapshots

---

## 1) System requirements

### Required
- **Docker Desktop** (and Docker Engine running)
- **Docker Compose v2** (ships with Docker Desktop)
- **At least 4 GB RAM** (8 GB recommended)
- **Windows 11** (tested) + WSL2 backend (recommended by Docker)

### Ports (ensure these are free)
- **8000** (astram-service)
- **8080** (backend)
- **3000** (frontend)
- **5432** (postgres)

---

## 2) Clone the repo

```bash
git clone https://github.com/ABHIRAM-DEVP/flipkart-gridlock
cd flipkart-grilock-round2
```

---

## 3) Configure environment variables (.env)

Docker Compose uses a root **.env** file.

Create/modify **`.env`** in the repo root with the following keys:

```env
POSTGRES_HOST=
POSTGRES_PORT=5432
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_URL=

# Backend / UI ports
BACKEND_PORT=8080
SPRING_DATASOURCE_USERNAME=
SPRING_DATASOURCE_PASSWORD=
```

### Recommended values
- `POSTGRES_HOST` can be left empty (Compose uses the internal service name `postgres`).
- `POSTGRES_URL` can be left empty (Spring Boot gets `SPRING_DATASOURCE_*` from Compose env).
- `SPRING_DATASOURCE_USERNAME` = `POSTGRES_USER`
- `SPRING_DATASOURCE_PASSWORD` = `POSTGRES_PASSWORD`

> If your `.env` already exists, update only the values (do not change variable names).

---

## 4) Run with Docker Compose (single command)

From the repo root:

```bash
docker compose up --build
```

What starts:
- **astram-service** (Flask) on **http://localhost:8000**
- **postgres** (DB)
- **backend** (Spring Boot) on **http://localhost:8080**
- **frontend** (Next.js) on **http://localhost:3000**

### Verify health
- Flask health: http://localhost:8000/health
- Backend health endpoint (if enabled): http://localhost:8080/api/health

### Open the UI
- Frontend: http://localhost:3000

---

## 5) Stop the app

```bash
docker compose down
```

To keep Postgres data, use:
```bash
docker compose down --remove-orphans
```

---

## 6) Run Astram ML service only (optional, non-container)

Use this only if you want to run Flask without Docker.

```powershell
cd ai-brain
python -m pip install -r requirements.txt
python src/train.py --csv "dataset/Astram event data_anonymized - Astram event data_anonymizedb40ac87 (2).csv" --outdir artifacts
python src/seed_db.py
python app.py
```

Then open:
- http://localhost:8000

---

## 7) Demo modules + 5-minute speaker script (content)

Use this narration while demoing pages like **Astram Dashboard**, **Command Center**, **Field HUD**, **Predict**, **Plan**, **Planned Impact**, **Reports**, and **Sign out**.

### Minute 0–1: Problem framing
“We operate corridors where traffic breakdowns come from both planned and unplanned events—political rallies, festivals, sports matches, construction, and sudden gatherings. The challenge is that we can’t reliably **quantify impact ahead of time**.

So response becomes experience-driven: manpower and barricades are deployed late, and after the event we often don’t have a closed-loop learning mechanism—so the same congestion patterns repeat.

Astram is built to change this: it’s an event-driven congestion intelligence platform that forecasts **how long an incident will last**, **how severe it will be**, and—most importantly—what response to deploy: **manpower**, **barricading**, and **diversion guidance**.”

### Minute 1–2: Live traffic intelligence + model performance
“Here in the dashboard, live intelligence refreshes every **15 seconds**. That lets us continuously update risk and predictions as conditions change.

We track both duration quality and severity tier quality—like MAE and R² for duration, and accuracy/F1 for severity classes. In the demo you’ll see the system surface clearance-time estimates, predicted severity, and confidence interval bounds.”

### Minute 2–3: Predict (single incident scoring)
“Now I’ll switch to **Predict**. The key idea is that the model scores using the same fields it was trained on—event timing, event type and cause, corridor and junction context, geographic signals like latitude/longitude, and whether a road closure is required.

When we submit an incident, Astram returns predicted duration in minutes, a severity tier, and a recommended operations bundle.”

### Minute 3–4: Plan + Planned Impact (agentic workflow)
“Next is **Plan**. Instead of one incident, we score multiple events and allocate limited manpower under a budget. This is where operational planning matters—higher risk events get prioritized for staffing, and lower priority items get staged or monitored.

Then we move to **Planned Impact**, where we forecast spillover for scheduled events. Planned events let us pre-stage: manpower, barricades, and diversion guidance before congestion spreads into adjacent road networks.”

### Minute 4–5: Closed-loop learning (why it’s hard today)
“Finally, the **Command Center** highlights the learning loop. After the post-event stage, the UI encourages operator feedback—so we can compare predicted vs observed congestion patterns and tune assumptions.

This closed-loop approach matters because the hard part isn’t only prediction accuracy; it’s also operational adaptation over time. Astram turns every event into a learning signal, so the system gets better—not just louder.”

---

## 8) Troubleshooting

- **Containers won’t start**: confirm Docker Desktop is running and ports 3000/8000/8080/5432 are free.
- **Database errors**: double-check `.env` values for `POSTGRES_USER`, `POSTGRES_PASSWORD`, and ensure they match `SPRING_DATASOURCE_USERNAME` and `SPRING_DATASOURCE_PASSWORD`.
- **Flask model not loaded**: ensure `ai-brain/artifacts/bundle.json` and model files exist in the mounted `artifacts/` directory (Docker volume uses that path).

---

## 9) Repo layout
- **`ai-brain/`** — Flask ML service
- **`backend/`** — Spring Boot API
- **`frontend/`** — Next.js UI
- **`docker-compose.yml`** — orchestration
- **`.env`** — environment variables for Compose

