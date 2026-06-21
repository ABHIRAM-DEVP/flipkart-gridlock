# ASTRAM — Traffic Intelligence Command Platform
**By Abhiram Moreshwar Daflapurkar for Gridlock Hackathon 2.0 - Round 2 **

**Theme: Event-Driven Congestion (Planned & Unplanned) **
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
cd flipkart-grilock
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
ctrl+c
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

## 7) Tech stack

- **Astram ML service (Flask / Python)**: scikit-learn **HistGradientBoosting** models for **duration** (regression) and **severity** (multi-class classification), plus DBSCAN hotspot clustering.
- **Backend (Spring Boot / Java)**: API/orchestration layer that connects UI ↔ Postgres ↔ Astram service.
- **Frontend (Next.js / React + TypeScript)**: operational dashboards with map overlays, charts, and modules (Dashboard, Command Center, Field HUD, Predict, Plan, Planned Impact, Reports).
- **Database (PostgreSQL)**: stores events, predictions, plans, planned-impact forecasts, and metrics snapshots.
- **Live updates (SSE)**: server-sent events stream to keep the dashboard refreshing with real-time intelligence.

## 8) System architecture (high-level)

### Architecture diagram (container + data flow)

```text
Operator Browser / UI (Next.js :3000)
        |
        | REST calls + SSE subscription
        v
Backend (Spring Boot :8080)
        |
        | 1) calls
        v
Astram ML Service (Flask :8000)
        |
        | 2) predictions, plans, spillover forecast
        | 3) live updates via SSE
        v
PostgreSQL (astram :5432)
```




### Component flow (who talks to whom)
1. **UI Request** (Next.js)
   - User opens pages and submits events for **Predict** / **Plan** / **Planned Impact**.
2. **Backend Orchestration** (Spring Boot)
   - Validates inputs
   - Calls Astram endpoints
   - Persists results in PostgreSQL
3. **ML Inference & Forecasting** (Flask)
   - Loads trained artifacts
   - Predicts incident duration + severity tier
   - Generates operational recommendations (manpower, barricades, diversion guidance)
   - Forecasts spillover impact for planned events
4. **Live stream** (SSE)
   - Dashboard subscribes to updates
   - UI refreshes “Live traffic intelligence” automatically.
5. **Docker**
   -for containerization

## 9) Important container startup note (your current error)

Your terminal shows:
- `TypeError: int() argument must be ... POSTGRES_PORT ... NoneType`

This means the root `.env` is missing **`POSTGRES_PORT`** (or not being read by `astram-service`).

Fix:
1. Ensure repo-root `.env` contains at least:
   - `POSTGRES_PORT=5432`
   - `POSTGRES_USER=...`
   - `POSTGRES_PASSWORD=...`
2. Re-run:
```bash
docker compose up --build
```




## Repo layout
- **`ai-brain/`** — Flask ML service
- **`backend/`** — Spring Boot API
- **`frontend/`** — Next.js UI
- **`docker-compose.yml`** — orchestration
- **`.env`** — environment variables for Compose

