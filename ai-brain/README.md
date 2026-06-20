# Astram – Flask Full-Stack ML Platform

Astram forecasts traffic incident duration, severity, resource needs, and planned-event spillover for Bangalore corridors. This service combines:

- **HistGradientBoosting** ML models (scikit-learn)
- **SQLite** persistence for events, predictions, and model runs
- **Flask** REST + HTML UI (vanilla JS, Chart.js, Leaflet)
- **SSE** live feed for real-time dashboard updates

## Quick Start

```powershell
cd ai-brain
python -m pip install -r requirements.txt

# Train (uses any CSV in dataset/)
python src/train.py --csv "dataset/Astram event data_anonymized - Astram event data_anonymizedb40ac87 (2).csv" --outdir artifacts

# Seed SQLite from CSV
python src/seed_db.py

# Run Flask server
python app.py
```

Open **http://localhost:8000** for the dashboard.

## Docker

```bash
docker compose up astram-service --build
```

The container auto-trains if artifacts are missing, seeds the database, and starts Flask on port 8000.

## Project Layout

```
ai-brain/
├── src/
│   ├── astram_data.py      # CSV parsing, aggregate stats
│   ├── features.py         # Feature engineering
│   ├── operations.py       # DBSCAN, MILP allocation, planned impact
│   ├── train.py            # HistGBM training pipeline
│   ├── predict.py          # Inference
│   ├── server.py           # Flask app (API + UI)
│   ├── db.py               # SQLite schema + CRUD
│   ├── seed_db.py          # CSV → events table
│   ├── sse.py              # SSE broadcaster
│   └── scheduler.py        # 15s hotspot refresh
├── templates/              # Jinja2 HTML pages
├── static/                 # CSS + vanilla JS
├── dataset/                # events CSV (8173 rows)
└── artifacts/              # models, graphs, astram.db (generated)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health |
| GET | `/metrics` | Model metrics |
| GET | `/graphs` | Dashboard graph data |
| POST | `/predict` | Score single event |
| POST | `/plan` | Batch score + allocate personnel |
| POST | `/planned-impact` | Planned event spillover forecast |
| GET | `/api/live-feed` | Recent predictions |
| GET | `/api/event-stats` | Aggregated event statistics |
| GET | `/api/hotspot-snapshot` | Cached DBSCAN/corridor hotspots |
| GET | `/sse/live` | Server-Sent Events stream |

## UI Pages

| URL | Page |
|-----|------|
| `/` | Dashboard |
| `/predict-page` | Single event prediction |
| `/plan-page` | Batch resource planning |
| `/planned-impact-page` | Planned event impact |
| `/reports-page` | Model reports & graphs |

## Tech Stack

- Flask 3.1.3, SQLite (stdlib), scikit-learn HistGradientBoosting
- Chart.js 4 + Leaflet 1.9 (CDN)
- Tailwind CSS (CDN)
- SSE for live updates, threading for 15s hotspot refresh

## Related Services

This repo also includes optional **Spring Boot** (`backend/`) and **Next.js** (`frontend/`) layers that proxy the same ML API. The Flask app on port 8000 is the self-contained full-stack implementation.
