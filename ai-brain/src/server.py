"""Flask application — replaces ThreadingHTTPServer (service.py)."""
from __future__ import annotations
from flask_cors import CORS
import argparse
import json
import queue
import sys
import threading
from mimetypes import guess_type
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_file, stream_with_context

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

ARTIFACTS = ROOT / "artifacts"
DEFAULT_APP_DATA = ARTIFACTS / "app_data.json"
DEFAULT_GRAPHS = ARTIFACTS / "graphs"

import db  # noqa: E402
from operations import PlannedImpactStats, allocate_resources, forecast_planned_event  # noqa: E402
from predict import _reconstruct_stats, load_artifacts, predict_event  # noqa: E402
from reporting import layer_descriptions  # noqa: E402
from scheduler import start_scheduler  # noqa: E402
from seed_db import seed_db_if_empty  # noqa: E402
from sse import broadcaster  # noqa: E402

app = Flask(
    __name__,
    template_folder=str(ROOT / "templates"),
    static_folder=str(ROOT / "static"),
)
CORS(app, origins=["https://flipkart-gridlock-frontend.onrender.com"])
_STATE: dict = {}
_STATE_LOCK = threading.Lock()


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_event(event: dict) -> dict:
    out = dict(event)
    if out.get("priority"):
        out["priority"] = str(out["priority"]).strip().lower()
    return out


def _ensure_state() -> dict:
    with _STATE_LOCK:
        if not _STATE:
            loaded = load_artifacts(ARTIFACTS)
            bundle = loaded["bundle"]
            report_path = ARTIFACTS / "report.txt"
            report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
            app_data = _load_json(DEFAULT_APP_DATA) if DEFAULT_APP_DATA.exists() else {}
            metrics = bundle.get("metrics") or app_data.get("metrics") or {}
            _STATE.update(
                {
                    **loaded,
                    "payload": {
                        "metrics": metrics,
                        "hotspots": bundle.get("train_hotspots", []),
                        "dbscan_hotspots": bundle.get("dbscan_hotspots", []),
                        "feature_weights": bundle.get("feature_weights", {}),
                        "residual_interval": bundle.get("residual_interval", {}),
                        "graph_paths": bundle.get("graph_paths", {}),
                        "dataset": app_data,
                    },
                    "report_text": report_text,
                    "app_data": app_data,
                }
            )
            start_scheduler(_STATE, db, interval=15)
        return _STATE


def _feature_weights(payload: dict, kind: str = "duration", top: int = 15) -> list[dict]:
    fw = payload.get("feature_weights") or {}
    feature_names = fw.get("feature_names") or []
    if kind == "severity":
        coefs = fw.get("severity_coef") or []
        class_names = fw.get("severity_classes") or []
        rows = []
        for class_name, coef_row in zip(class_names, coefs, strict=False):
            pairs = sorted(zip(feature_names, coef_row), key=lambda item: abs(item[1]), reverse=True)[:top]
            for feature_name, weight in pairs:
                rows.append({"class": class_name, "feature": feature_name, "weight": float(weight)})
        return rows
    importances = fw.get("duration_feature_importance") or []
    return [
        {
            "feature": row["feature"],
            "weight": float(row.get("gain", row.get("weight", 0))),
            "split": int(row.get("split", 0)),
        }
        for row in importances[:top]
    ]


def _graphs_payload() -> dict:
    state = _ensure_state()
    payload = state["payload"]
    app_data = state.get("app_data") or {}
    return {
        "event_type_distribution": app_data.get("event_types", {}),
        "cause_distribution": app_data.get("cause_counts", {}),
        "priority_distribution": app_data.get("priority", {}),
        "hotspots": (payload.get("hotspots") or [])[:12],
        "dbscan_hotspots": (payload.get("dbscan_hotspots") or [])[:12],
        "feature_weights": _feature_weights(payload, kind="duration", top=15),
        "severity_weights": _feature_weights(payload, kind="severity", top=8),
        "metrics": payload.get("metrics", {}),
        "residual_interval": payload.get("residual_interval", {}),
        "graph_paths": payload.get("graph_paths", {}),
    }


def _register_model_run_from_artifacts() -> None:
    if db.get_latest_model_run():
        return
    bundle_path = ARTIFACTS / "bundle.json"
    if not bundle_path.exists():
        return
    try:
        bundle = _load_json(bundle_path)
        metrics = bundle.get("metrics") or {}
        report_path = ARTIFACTS / "report.txt"
        classification_report = report_path.read_text(encoding="utf-8") if report_path.exists() else None
        rows_total = rows_with_duration = train_rows = test_rows = None
        if report_path.exists():
            for line in report_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("Rows total:"):
                    rows_total = int(line.split(":")[1].strip())
                elif line.startswith("Rows with duration:"):
                    rows_with_duration = int(line.split(":")[1].strip())
                elif line.startswith("Train rows:"):
                    train_rows = int(line.split(":")[1].strip())
                elif line.startswith("Test rows:"):
                    test_rows = int(line.split(":")[1].strip())
        db.insert_model_run(
            {
                "rows_total": rows_total,
                "rows_with_duration": rows_with_duration,
                "train_rows": train_rows,
                "test_rows": test_rows,
                "metrics": metrics,
                "classification_report": metrics.get("severity_classification_report") or classification_report,
                "model_version": "v1",
            }
        )
    except Exception as exc:
        print(f"[startup] model run registration skipped: {exc}")


def _startup() -> None:
    db.init_db()
    seed_db_if_empty()
    state = _ensure_state()
    _register_model_run_from_artifacts()
    snap = state
    db.insert_hotspot_snapshot("dbscan", snap["bundle"].get("dbscan_hotspots", []))
    db.insert_hotspot_snapshot("corridor", snap["bundle"].get("train_hotspots", []))


# ── Existing JSON endpoints ──────────────────────────────────────────────────

@app.get("/health")
def health():
    state = _ensure_state()
    model_loaded = bool(state.get("dur_model") is not None)
    return jsonify({"status": "ok", "model_loaded": model_loaded})


@app.get("/metrics")
def metrics():
    state = _ensure_state()
    return jsonify(state["payload"].get("metrics") or {})


@app.get("/graphs")
def graphs():
    return jsonify(_graphs_payload())


@app.get("/weights")
def weights():
    state = _ensure_state()
    kind = request.args.get("kind", "duration")
    top = int(request.args.get("top", "15"))
    return jsonify(_feature_weights(state["payload"], kind=kind, top=top))


@app.get("/hotspots")
def hotspots():
    state = _ensure_state()
    return jsonify(state["payload"]["hotspots"])


@app.get("/dbscan-hotspots")
def dbscan_hotspots():
    state = _ensure_state()
    return jsonify(state["payload"]["dbscan_hotspots"])


@app.get("/app-data")
def app_data():
    if DEFAULT_APP_DATA.exists():
        return jsonify(_load_json(DEFAULT_APP_DATA))
    return jsonify({"error": "app_data.json not found. Run training first."}), 404


@app.get("/summary")
def summary():
    path = ARTIFACTS / "training_summary.json"
    if path.exists():
        return jsonify(_load_json(path))
    return jsonify({})


@app.get("/files")
def files():
    items = []
    if ARTIFACTS.exists():
        for path in sorted(ARTIFACTS.rglob("*")):
            if path.is_file():
                items.append({"path": str(path.relative_to(ROOT)), "size": path.stat().st_size})
    return jsonify({"artifacts": items})


@app.get("/workflow")
def workflow():
    return jsonify(
        {
            "step_1": "Load CSV and build aggregate statistics",
            "step_2": "Generate feature matrix with temporal, location, and historical signals",
            "step_3": "Train HistGradientBoosting duration regressor and severity classifier",
            "step_4": "Build hotspot tables and DBSCAN clusters",
            "step_5": "Forecast planned-event spillover and derive resource plan",
            "step_6": "Write report.txt, graphs, and app_data.json",
            "step_7": "Serve prediction, plan, metrics, and report endpoints",
            "step_8": "Append feedback and retrain from actual outcomes",
        }
    )


@app.get("/layers")
def layers():
    return jsonify(layer_descriptions())


@app.get("/graph-files")
def graph_files():
    files_list = []
    if DEFAULT_GRAPHS.exists():
        for path_item in sorted(DEFAULT_GRAPHS.glob("*.png")):
            files_list.append(
                {
                    "name": path_item.name,
                    "path": str(path_item.relative_to(ROOT)),
                    "size": path_item.stat().st_size,
                }
            )
    return jsonify({"graphs": files_list})


@app.get("/graph/<path:graph_name>")
def graph_image(graph_name: str):
    if ".." in graph_name or graph_name.startswith("/"):
        return jsonify({"error": "invalid graph name"}), 400
    graph_path = DEFAULT_GRAPHS / graph_name
    if not graph_path.exists() or not graph_path.is_file():
        return jsonify({"error": f"graph not found: {graph_name}"}), 404
    mime = guess_type(graph_path.name)[0] or "application/octet-stream"
    return send_file(graph_path, mimetype=mime)


@app.get("/report.txt")
def report_txt():
    state = _ensure_state()
    return Response(state.get("report_text") or "", mimetype="text/plain; charset=utf-8")


@app.get("/feedback/summary")
def feedback_summary():
    feedback_log = ARTIFACTS / "feedback_log.jsonl"
    if feedback_log.exists():
        from feedback import load_feedback_entries, summarize_feedback

        return jsonify(summarize_feedback(load_feedback_entries(feedback_log)))
    return jsonify({"count": 0, "note": "No feedback entries logged yet."})


@app.post("/predict")
def predict():
    event = _normalize_event(request.get_json(force=True) or {})
    state = _ensure_state()
    model_loaded = bool(state.get("dur_model") is not None)
    if not model_loaded:
        return jsonify({"error": "models not loaded"}), 503
    result = predict_event(event, state)
    insert_prediction(event, result)
    broadcaster.publish("prediction", {**result, "event": event})
    return jsonify(result)


@app.post("/plan")
def plan():
    body = request.get_json(force=True) or {}
    if isinstance(body, list):
        events = body
        budget = 50
    else:
        events = body.get("events", [])
        budget = int(body.get("budget", 50))
    state = _ensure_state()
    model_loaded = bool(state.get("dur_model") is not None)
    if not model_loaded:
        return jsonify({"error": "models not loaded"}), 503
    scored = [predict_event(_normalize_event(e), state) | {"event": e} for e in events]
    allocation = allocate_resources(scored, total_personnel=budget)
    result = {"scored_events": scored, "allocation": allocation}
    db.insert_batch_plan(events, budget, scored, allocation)
    broadcaster.publish("plan", result)
    return jsonify(result)


@app.post("/planned-impact")
def planned_impact():
    event = _normalize_event(request.get_json(force=True) or {})
    state = _ensure_state()
    model_loaded = bool(state.get("dur_model") is not None)
    if not model_loaded:
        return jsonify({"error": "models not loaded"}), 503
    bundle = state["bundle"]
    stats = _reconstruct_stats(bundle["stats"])
    planned_stats = PlannedImpactStats(**bundle["planned_stats"])
    result = forecast_planned_event(event, stats, planned_stats)
    db.insert_planned_impact(event, result)
    broadcaster.publish("planned_impact", {**result, "event": event})
    return jsonify(result)


@app.post("/sample-predict")
def sample_predict():
    from seed_db import _resolve_csv_path
    import csv

    csv_path = _resolve_csv_path()
    if not csv_path:
        return jsonify({"error": "No CSV in dataset/"}), 404
    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        sample = next(csv.DictReader(f))
    state = _ensure_state()
    model_loaded = bool(state.get("dur_model") is not None)
    if not model_loaded:
        return jsonify({"error": "models not loaded"}), 503
    prediction = predict_event(_normalize_event(sample), state)
    return jsonify({"sample_event": sample, "prediction": prediction})


# ── New API endpoints ────────────────────────────────────────────────────────

@app.get("/api/live-feed")
def live_feed():
    limit = int(request.args.get("limit", "20"))
    return jsonify(db.get_recent_predictions(limit=limit))


@app.get("/api/plans")
def recent_plans():
    limit = int(request.args.get("limit", "10"))
    return jsonify(db.get_recent_plans(limit=limit))


@app.get("/api/planned-impacts")
def recent_planned_impacts():
    limit = int(request.args.get("limit", "10"))
    return jsonify(db.get_recent_planned_impacts(limit=limit))


@app.get("/api/model-runs")
def model_runs():
    return jsonify(db.get_all_model_runs())


@app.get("/api/event-stats")
def event_stats():
    return jsonify(db.get_event_stats())


@app.get("/api/hotspot-snapshot")
def hotspot_snapshot():
    dbscan = db.get_hotspot_snapshot_fresh_or_latest("dbscan")
    corridor = db.get_hotspot_snapshot_fresh_or_latest("corridor")
    if not dbscan or not corridor:
        state = _ensure_state()
        bundle = state["bundle"]
        dbscan = dbscan or bundle.get("dbscan_hotspots", [])
        corridor = corridor or bundle.get("train_hotspots", [])
    return jsonify({"dbscan": dbscan, "corridor": corridor})


# ── SSE ──────────────────────────────────────────────────────────────────────

@app.get("/sse/live")
def sse_live():
    def generate():
        client_q = broadcaster.subscribe()
        try:
            for item in db.get_recent_live_feed(limit=10):
                yield f"data: {json.dumps(item)}\n\n"
            while True:
                try:
                    msg = client_q.get(timeout=20)
                except queue.Empty:
                    yield 'data: {"type":"heartbeat"}\n\n'
                    continue
                yield f"data: {json.dumps(msg)}\n\n"
        except GeneratorExit:
            broadcaster.unsubscribe(client_q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/agent/run")
def agent_run():
    """Run an agentic workflow: Predict -> Plan -> Planned Impact for provided events.
    Accepts JSON { events: [...], budget?: int } or runs sample if empty.
    Emits SSE messages via `broadcaster.publish` for progress updates.
    """
    body = request.get_json(force=True) or {}
    events = body.get("events") or []
    budget = int(body.get("budget", 50))

    state = _ensure_state()
    if not events:
        # fallback: sample first few seeded events from artifacts dataset
        from seed_db import _resolve_csv_path
        import csv

        csv_path = _resolve_csv_path()
        if not csv_path:
            return jsonify({"error": "no events provided and no CSV available"}), 400
        with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= 6:
                    break
                events.append(_normalize_event(row))

    # Run predictions
    scored = []
    for i, ev in enumerate(events):
        broadcaster.publish("agent.progress", {"step": "predict", "index": i, "total": len(events), "event": ev})
        try:
            pred = predict_event(ev, state)
        except Exception as exc:
            pred = {"error": str(exc)}
        insert_prediction(ev, pred)
        broadcaster.publish("agent.prediction", {"index": i, "prediction": pred, "event": ev})
        scored.append(pred | {"event": ev})

    # Allocate resources (plan)
    broadcaster.publish("agent.progress", {"step": "plan", "total": len(events)})
    allocation = allocate_resources(scored, total_personnel=budget)
    db.insert_batch_plan(events, budget, scored, allocation)
    broadcaster.publish("agent.plan", {"allocation": allocation, "scored_events": scored})

    # Forecast planned impacts for each planned item
    impacts = []
    bundle = state.get("bundle") or {}
    stats = _reconstruct_stats(bundle.get("stats") or {})
    planned_stats = None
    try:
        planned_stats = type("P", (), {})()
        planned_stats.__dict__.update(bundle.get("planned_stats") or {})
    except Exception:
        planned_stats = None

    for i, scored_item in enumerate(scored):
        broadcaster.publish("agent.progress", {"step": "planned-impact", "index": i, "total": len(scored)})
        try:
            impact = forecast_planned_event(scored_item.get("event") or scored_item, stats, planned_stats)
        except Exception as exc:
            impact = {"error": str(exc)}
        db.insert_planned_impact(scored_item.get("event") or scored_item, impact)
        impacts.append(impact)
        broadcaster.publish("agent.planned_impact", {"index": i, "impact": impact})

    broadcaster.publish("agent.complete", {"plans": allocation, "impacts": impacts})
    return jsonify({"status": "ok", "plans": allocation, "impacts": impacts})


# ── HTML pages ───────────────────────────────────────────────────────────────

@app.get("/")
def page_dashboard():
    return render_template("dashboard.html")


@app.get("/predict-page")
def page_predict():
    return render_template("predict.html")


@app.get("/plan-page")
def page_plan():
    return render_template("plan.html")


@app.get("/planned-impact-page")
def page_planned():
    return render_template("planned_impact.html")


@app.get("/reports-page")
def page_reports():
    return render_template("reports.html")


def insert_prediction(event: dict, result: dict) -> None:
    db.insert_prediction(event, result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Astram Flask server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    _startup()
    print(f"Astram Flask running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
