# ASTRA M — Traffic Intelligence Command Platform

> Live event-driven congestion scoring + planned spillover forecasting for corridor operations.

This repo contains two UI layers plus a production-grade ML service:
- **Astram ML service (Flask)**: loads trained models, scores incidents, computes planned impact, serves reports, and streams live updates via **SSE**.
- **Command Center UI (Next.js)**: dashboard experience with modules like **Astram Dashboard, Command Center, Field HUD, Predict, Plan, Planned Impact, Reports, Sign out**, plus live intelligence overlays.
- **Backend (Spring Boot)**: optional orchestration layer for persisting and proxying data.

The most complete “single command” run path is **Docker Compose** (Section 2).

---

## 1) What you’re running (demo storyline)

Live traffic intelligence continuously:
- scores **unplanned** and **planned** events,
- forecasts **duration** and **severity**,
- recommends **manpower**, **barricading**, **diversion** guidance,
- supports an **agentic workflow**: **Predict → Plan → Planned Impact**,
- performs **closed-loop learning** after an event window (in the UI).

The demo pages are aligned to operational challenges:
- **Event-Driven Congestion**: both planned and unplanned incidents reduce corridor throughput and can spill into adjacent networks.
- **Operational Challenge**: rallies, festivals, sports events, construction, sudden gatherings.
- **Why it’s Hard Today**: impact is not quantified ahead of time; deployments are experience-driven; learning is often missing.

Live refresh updates every **15 seconds** (and the UI supports fallback mode).

---

## 2) Run everything (recommended): Docker Compose

### Prerequisites
- Docker Desktop installed and running.

### Start the platform
From the repo root:

```bash
docker compose up --build
```

What this starts:
- **`astram-service`** (Flask) on **http://localhost:8000**
- **`postgres`** (persistence for events/predictions/plans)
- **`backend`** (Spring Boot) on **http://localhost:8080**
- **`frontend`** (Next.js) on **http://localhost:3000**

### Verify health
Open:
- `http://localhost:8000/health`
- `http://localhost:8080/api/health` (if enabled)

### Open the demo UI
Open:
- **http://localhost:3000**

---

## 3) Run the Astram ML service only (Flask)

### Setup
```powershell
cd ai-brain
python -m pip install -r requirements.txt
```

### Train (optional if artifacts already exist)
```powershell
python src/train.py --csv "dataset/Astram event data_anonymized - Astram event data_anonymizedb40ac87 (2).csv" --outdir artifacts
```

### Seed events table (optional if DB already seeded)
```powershell
python src/seed_db.py
```

### Start server
```powershell
python app.py
```

Then open:
- **http://localhost:8000**

---

## 4) How to use each module during the 5-minute demo

### A) Astram Dashboard
What to show:
- **Live refresh every 15s**
- Model performance snapshot (examples from the app):
  - Duration: **R²**, **MAE**
  - Severity: **accuracy**, **F1 macro**
- Operational story blocks:
  - **Live traffic intelligence**
  - **Live refresh + fallback mode**
- Spatial intelligence:
  - **DBSCAN congestion clusters** on the map
  - Recurring corridor hotspots (e.g., Mysore Road, Bellary Road, Tumkur Road, ORR East 2)
- Live “Recent predictions” and live event feed / SSE

What to say (script-ready):
- “We’re not only predicting duration—we’re turning predictions into action: resources, barricading, diversion guidance, and post-event learning.”

---

### B) Command Center
What to show:
- **Field HUD + operator view**
- Real-time overlays (heatmaps, resource markers, CCTV layer)
- The map-driven timeline scrub (Pre-event → Peak → Post-event)
- The automated **Learning Loop** modal after the post-event stage

What to click:
- Toggle layers: **Heatmap**, **Adaptive Signals**, **Impact Rings**, **Officer & Cones**, **CCTV feeds**
- Scrub timeline to **Stage 2 (Peak)** and **Stage 3 (Post-event)**

---

### C) Field HUD
What to show:
- “One operational view for the field.”
- HUD-style cards for the recommended response:
  - clearance time estimate
  - predicted severity tier
  - recommended personnel and barricades
  - diversion guidance

---

### D) Predict (single incident scoring)
What to show:
- “Score a single incident using the same fields the model was trained on.”

Typical input fields:
- Start DateTime
- Event Type (planned/unplanned)
- Event Cause (e.g., vehicle_breakdown)
- Corridor / Zone / Junction
- Latitude / Longitude
- Priority / address
- requires_road_closure

What to say:
- “Predict returns duration in minutes, a severity tier, and a resource recommendation bundle.”

---

### E) Plan (batch resource planning)
What to show:
- Submit 2–5 incidents and show:
  - scored events list
  - resource allocation under a personnel budget

What to say:
- “Planning converts risk forecasts into a constrained operations plan—so manpower is deployed where it matters most.”

---

### F) Planned Impact (spillover forecast)
What to show:
- For a planned event, show:
  - forecast impact on the corridor
  - expected duration window
  - how spillover risk informs pre-staging resources

What to say:
- “Planned events let us pre-stage. Unplanned incidents force reactive response.”

---

### G) Reports
What to show:
- Graphs generated from training evaluation (examples visible in the artifacts):
  - Actual vs Predicted duration
  - Residual distribution
  - Confusion matrix for severity tiers
  - Top feature importance (permutation importance)
  - Error trend
  - Severity distribution
- End-to-end workflow description:
  - Train → score → plan → planned impact → report → closed loop

---

### H) Sign out
What to show:
- UI-level auth flow (demo users) and clean exit.

---

## 5) 5-minute demo talk track (content to speak)

Use this as your narration while you click through the modules.

### Minute 0–1: Problem framing (why this exists)
“We operate corridors where traffic breakdowns come from both **planned** and **unplanned** events: political rallies, festivals, sports matches, construction, and sudden gatherings. The issue is that we usually can’t **quantify impact ahead of time**. So resource deployment becomes experience-driven, and after the event there’s often no closed-loop learning—meaning the same congestion patterns repeat.

Astram is built to change that: it’s an event-driven congestion intelligence platform that forecasts **how long an incident will last**, **how severe it will be**, and—most importantly—what response to deploy: **manpower**, **barricading**, and **diversion guidance**.”


### Minute 1–2: Live traffic intelligence + model outputs
“Here, the dashboard is refreshing every 15 seconds. That means we continuously ingest the latest live context, compute a risk score, and surface predictions as actionable intelligence.

For the model, we track duration accuracy with metrics like MAE and R², and severity tier quality using F1 macro and classification accuracy. In the demo, you can see the model’s live outputs including estimated clearance time, severity, and confidence interval bounds.”

### Minute 2–3: Predict module demo (single incident)
“Now I’ll switch to Predict and score a single incident. The critical point is that we use the same fields the model was trained on—start time, event type and cause, corridor and zone, junction, latitude/longitude, and whether road closure is required.

When we submit, Astram returns predicted duration in minutes, a severity tier, and a recommended resource plan. This is what converts forecasting into operations.”

### Minute 3–4: Plan + Planned Impact (agentic workflow)
“Next is Plan. Instead of one incident, we score multiple events and allocate limited manpower under a budget. This is where operational planning matters—high-risk events get staffed first, and lower priority ones get staged or monitored.

Then we move to Planned Impact, which focuses on spillover. Planned events let us simulate corridor impact before the crowd peaks. That means we can pre-stage barricades, manpower, and diversion guidance, so congestion doesn’t spread across adjacent road networks.”

### Minute 4–5: Learning loop + why it’s hard today (closed loop)
“Finally, the Command Center shows the learning loop. After the post-event stage, the UI prompts an operator feedback/report card—so we can compare predicted vs observed congestion and tune system assumptions for future deployments.

This closed-loop approach matters because the hard part isn’t only prediction accuracy—it’s also operational adaptation over time. Astram turns every event into training signal, so the system gets better, not just louder.”

---

## 6) Troubleshooting
- **Models not loaded (Flask)**: ensure you ran training at least once so `ai-brain/artifacts/bundle.json` and model pkl files exist.
- **No live events appear**: run the seeding step (or ensure the Docker container volume has data in `ai-brain/artifacts/`).
- **Port conflicts**: if 3000/8000/8080 are in use, stop the conflicting services.

---

## 7) Repository quick references
- ML service: `ai-brain/`
- Next.js UI: `frontend/`
- Spring Boot: `backend/`
- Compose orchestration: `docker-compose.yml`

