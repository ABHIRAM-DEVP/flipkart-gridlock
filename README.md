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

## Troubleshooting

- **Containers won’t start**: confirm Docker Desktop is running and ports 3000/8000/8080/5432 are free.
- **Database errors**: double-check `.env` values for `POSTGRES_USER`, `POSTGRES_PASSWORD`, and ensure they match `SPRING_DATASOURCE_USERNAME` and `SPRING_DATASOURCE_PASSWORD`.
- **Flask model not loaded**: ensure `ai-brain/artifacts/bundle.json` and model files exist in the mounted `artifacts/` directory (Docker volume uses that path).

---

## Repo layout
- **`ai-brain/`** — Flask ML service
- **`backend/`** — Spring Boot API
- **`frontend/`** — Next.js UI
- **`docker-compose.yml`** — orchestration
- **`.env`** — environment variables for Compose

