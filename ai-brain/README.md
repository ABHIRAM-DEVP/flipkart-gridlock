# Astram Event Impact Model

This repository turns the anonymized Astram event CSV into a working AI model for the Flipkart Gridlock Round 2 problem statement.

## What it does

- Forecasts event clearance duration from historical event data.
- Derives a severity tier from predicted duration.
- Recommends manpower, barricades, and diversion guidance.
- Ranks recurring hotspots from the dataset.
- Detects geospatial hotspots with DBSCAN.
- Forecasts planned-event spillover impact.
- Allocates personnel across multiple simultaneous events.
- Logs feedback and retrains from actual outcomes.
- Supports a closed-loop retraining story through the saved training bundle.

## Data-driven design

The dataset has 8,173 event records and 46 columns.

What mattered most in the actual file:

- Strong signal columns: `event_type`, `event_cause`, `requires_road_closure`, `start_datetime`, `closed_datetime`, `corridor`, `zone`, `junction`, `priority`
- Weak or sparse columns: `assigned_to_police_id`, `resolved_by_id`, `resolved_datetime`, `end_datetime`
- Target availability: only rows with both `start_datetime` and `closed_datetime` can be used for supervised duration training

The duration target is extremely skewed, so the model trains on `log1p(duration_min)` and caps the operational forecast window at 12 hours. That keeps the model focused on actionable response time instead of extreme tail records.

## Outputs

The training script writes:

- `artifacts/astram_model_bundle.json`
- `artifacts/bundle.json`
- `artifacts/lightgbm_duration.txt`
- `artifacts/lgb_model.txt`
- `artifacts/vec.pkl`
- `artifacts/training_summary.json`
- `artifacts/training_summary.txt`
- `artifacts/report.txt`
- `artifacts/service_payload.json`
- `artifacts/app_data.json`
- `artifacts/hotspots.json`
- `artifacts/graphs/`
- `artifacts/feedback_log.jsonl` when feedback is logged

## How the model works

1. Build time-based train/test splits from rows with valid durations.
2. Engineer operational features:
   - time-of-day, weekday, weekend, peak hour
   - event type, cause, corridor, zone, junction, vehicle type
   - road closure flag, priority, planned/unplanned flag
   - learned historical aggregates such as median duration and hotspot score
3. Train the core duration model:
   - `LightGBM` regressor for duration prediction
   - `SGDClassifier` kept as a diagnostic severity classifier
4. Convert duration into actions:
   - severity tier
   - manpower
   - barricades
   - diversion hint

The operator-facing severity tier is derived from the predicted duration bands. The separate severity classifier is kept as a diagnostic signal and for comparison during retraining.

## Extra modules

- `src/operations.py`: DBSCAN hotspots, planned-event impact forecasting, and multi-event manpower allocation.
- `src/feedback.py`: feedback logging, feedback summaries, and retraining from actual outcomes.
- `src/plan_events.py`: scores a batch of events and allocates personnel across them.

## Run it

If you hit a NumPy / SciPy binary mismatch, create a fresh virtual environment first. On Windows:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Then run with the venv interpreter explicitly:

```powershell
.\.venv\Scripts\python.exe src\analyze_dataset.py
.\.venv\Scripts\python.exe src\train.py
.\.venv\Scripts\python.exe app.py
```

To score one event:

```bash
.\.venv\Scripts\python.exe src\predict.py --json path\to\event.json
```

To score and allocate a batch of events:

```bash
.\.venv\Scripts\python.exe src\plan_events.py --events-json path\to\events.json --budget 12
```

To log feedback:

```bash
.\.venv\Scripts\python.exe src\feedback.py log --event-json path\to\event.json --predicted-duration 42 --predicted-severity medium --actual-duration 55 --actual-severity medium
```

To retrain from feedback:

```bash
.\.venv\Scripts\python.exe src\feedback.py retrain
```

## Backend microservice

Run the HTTP backend:

```bash
.\.venv\Scripts\python.exe src\service.py
```

Useful endpoints:

- `GET /health`
- `GET /metrics`
- `GET /graphs`
- `GET /weights?kind=duration`
- `GET /report.txt`
- `GET /app-data`
- `GET /files`
- `GET /workflow`
- `GET /layers`
- `GET /graph-files`
- `GET /graph/event_type_distribution.png`
- `POST /predict`
- `POST /plan`
- `POST /planned-impact`
- `GET /feedback/summary`

## Folder Purpose

| Path | Purpose |
| --- | --- |
| `dataset/` | Raw anonymized Astram CSV input. |
| `src/astram_data.py` | CSV parsing, datetime cleanup, duration target creation, aggregate statistics, hotspot scoring helpers. |
| `src/operations.py` | DBSCAN hotspots, planned-event impact logic, diversion hints, and multi-event resource allocation. |
| `src/train.py` | Full training pipeline, artifact generation, report writing, graph generation, and saved model bundle creation. |
| `src/reporting.py` | Report text builder, service payload builder, and graph generation orchestration. |
| `src/plots.py` | `matplotlib.pyplot` chart helpers used by training to save PNG graphs. |
| `src/predict.py` | Single-event inference using the saved JSON bundle. |
| `src/plan_events.py` | Batch inference plus resource allocation across simultaneous events. |
| `src/feedback.py` | Feedback logging, summary, and retraining from logged outcomes. |
| `src/service.py` | Lightweight HTTP backend microservice exposing prediction, metrics, graphs, report, and workflow APIs. |
| `app.py` | Root launcher for the HTTP backend so you can run `python app.py` directly. |
| `src/analyze_dataset.py` | Dataset EDA and summary generation for presentation use. |
| `artifacts/` | Generated report, charts, metrics, model bundle, and service payloads. |

## Workflow

1. Load the CSV from `dataset/`.
2. Clean timestamps and derive duration labels.
3. Build temporal, location, historical, hotspot, and planned-event features.
4. Train the models and compute metrics.
5. Generate `report.txt`, PNG graphs, `training_summary.json`, and `service_payload.json`.
6. Serve the artifacts through `app.py` or `src/service.py` for testing and demoing.
7. Collect feedback and retrain from logged outcomes when new results arrive.

## Why this is hackathon-ready

- It uses the real dataset, not assumptions.
- It is honest about missing manpower labels.
- It closes the loop from prediction to action.
- It produces judge-friendly outputs: prediction, severity, resources, and hotspots.
