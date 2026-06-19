from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import lightgbm as lgb

from astram_data import AggregateStats
from operations import PlannedImpactStats, allocate_resources, forecast_planned_event
from predict import predict_from_bundle
from reporting import build_service_payload, layer_descriptions
from train import load_supervised_rows, split_time_order


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
DEFAULT_BUNDLE = ARTIFACTS / "astram_model_bundle.json"
DEFAULT_PAYLOAD = ARTIFACTS / "service_payload.json"
DEFAULT_REPORT = ARTIFACTS / "report.txt"
DEFAULT_SUMMARY = ARTIFACTS / "training_summary.json"
DEFAULT_GRAPHS = ARTIFACTS / "graphs"
DEFAULT_APP_DATA = ARTIFACTS / "app_data.json"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_state(bundle_path: Path = DEFAULT_BUNDLE) -> dict[str, object]:
    if not bundle_path.exists():
        raise FileNotFoundError(f"Missing model bundle: {bundle_path}")

    bundle = _load_json(bundle_path)
    payload = _load_json(DEFAULT_PAYLOAD) if DEFAULT_PAYLOAD.exists() else None
    report_text = DEFAULT_REPORT.read_text(encoding="utf-8") if DEFAULT_REPORT.exists() else ""
    summary = _load_json(DEFAULT_SUMMARY) if DEFAULT_SUMMARY.exists() else {}

    stats = AggregateStats(**bundle["stats"])
    planned_stats = PlannedImpactStats(**bundle["planned_stats"])
    duration_model_path = Path(bundle["duration_model_file"])
    if not duration_model_path.is_absolute():
        duration_model_path = ROOT / duration_model_path
    duration_booster = lgb.Booster(model_file=str(duration_model_path))
    return {
        "bundle": bundle,
        "payload": payload,
        "report_text": report_text,
        "summary": summary,
        "stats": stats,
        "planned_stats": planned_stats,
        "duration_booster": duration_booster,
    }


def _json_response(handler: BaseHTTPRequestHandler, status: int, data: dict | list) -> None:
    encoded = json.dumps(data, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def _text_response(handler: BaseHTTPRequestHandler, status: int, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
    encoded = text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def _feature_weights(payload: dict[str, object], kind: str = "duration", top: int = 15) -> list[dict[str, float | str]]:
    feature_names = payload["feature_weights"]["feature_names"]
    if kind == "severity":
        coefs = payload["feature_weights"]["severity_coef"]
        class_names = payload["feature_weights"]["severity_classes"]
        rows = []
        for class_name, coef_row in zip(class_names, coefs, strict=False):
            pairs = sorted(zip(feature_names, coef_row), key=lambda item: abs(item[1]), reverse=True)[:top]
            for feature_name, weight in pairs:
                rows.append({"class": class_name, "feature": feature_name, "weight": float(weight)})
        return rows

    importances = payload["feature_weights"]["duration_feature_importance"]
    return [
        {"feature": row["feature"], "weight": float(row["gain"]), "split": int(row["split"])}
        for row in importances[:top]
    ]


def _graphs(payload: dict[str, object]) -> dict[str, object]:
    return {
        "event_type_distribution": payload["dataset"]["event_types"],
        "cause_distribution": payload["dataset"]["causes"],
        "priority_distribution": payload["dataset"]["priority"],
        "hotspots": payload["hotspots"][:12],
        "dbscan_hotspots": payload["dbscan_hotspots"][:12],
        "feature_weights": _feature_weights(payload, kind="duration", top=15),
        "severity_weights": _feature_weights(payload, kind="severity", top=8),
        "metrics": payload["metrics"],
        "residual_interval": payload["residual_interval"],
        "graph_paths": payload.get("graph_paths", {}),
    }


def _file_inventory() -> dict[str, object]:
    files = []
    if ARTIFACTS.exists():
        for path in sorted(ARTIFACTS.rglob("*")):
            if path.is_file():
                files.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "size": path.stat().st_size,
                    }
                )
    return {"artifacts": files}


class AstramHandler(BaseHTTPRequestHandler):
    state: dict[str, object] = {}

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _body_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        payload = self.state["payload"]

        if path == "/":
            home = {
                "service": "Astram backend microservice",
                "endpoints": ["/health", "/metrics", "/graphs", "/weights", "/report.txt", "/predict", "/plan", "/planned-impact", "/feedback/summary", "/files", "/workflow", "/layers", "/graph-files"],
            }
            return _json_response(self, HTTPStatus.OK, home)

        if path == "/health":
            return _json_response(self, HTTPStatus.OK, {"status": "ok", "model_loaded": True})

        if path == "/metrics":
            return _json_response(self, HTTPStatus.OK, self.state["payload"]["metrics"])

        if path == "/graphs":
            return _json_response(self, HTTPStatus.OK, _graphs(payload))

        if path == "/weights":
            query = parse_qs(parsed.query)
            kind = query.get("kind", ["duration"])[0]
            top = int(query.get("top", ["15"])[0])
            return _json_response(self, HTTPStatus.OK, _feature_weights(payload, kind=kind, top=top))

        if path == "/hotspots":
            return _json_response(self, HTTPStatus.OK, payload["hotspots"])

        if path == "/dbscan-hotspots":
            return _json_response(self, HTTPStatus.OK, payload["dbscan_hotspots"])

        if path == "/summary":
            return _json_response(self, HTTPStatus.OK, self.state["summary"])

        if path == "/files":
            return _json_response(self, HTTPStatus.OK, _file_inventory())

        if path == "/workflow":
            workflow = {
                "step_1": "Load CSV and build aggregate statistics",
                "step_2": "Generate feature matrix with temporal, location, and historical signals",
                "step_3": "Train LightGBM duration regressor and severity diagnostic model",
                "step_4": "Build hotspot tables and DBSCAN clusters",
                "step_5": "Forecast planned-event spillover and derive resource plan",
                "step_6": "Write report.txt, graphs, and service_payload.json",
                "step_7": "Serve prediction, plan, metrics, and report endpoints",
                "step_8": "Append feedback and retrain from actual outcomes",
            }
            return _json_response(self, HTTPStatus.OK, workflow)

        if path == "/layers":
            return _json_response(self, HTTPStatus.OK, layer_descriptions())

        if path == "/graph-files":
            graph_dir = ARTIFACTS / "graphs"
            files = []
            if graph_dir.exists():
                for path_item in sorted(graph_dir.glob("*.png")):
                    files.append({"name": path_item.name, "path": str(path_item.relative_to(ROOT)), "size": path_item.stat().st_size})
            return _json_response(self, HTTPStatus.OK, {"graphs": files})

        if path.startswith("/graph/"):
            graph_name = path.removeprefix("/graph/").strip("/")
            if not graph_name:
                return _json_response(self, HTTPStatus.BAD_REQUEST, {"error": "missing graph name"})
            graph_path = ARTIFACTS / "graphs" / graph_name
            if not graph_path.exists() or not graph_path.is_file():
                return _json_response(self, HTTPStatus.NOT_FOUND, {"error": f"graph not found: {graph_name}"})
            data = graph_path.read_bytes()
            content_type = guess_type(graph_path.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/report.txt":
            return _text_response(self, HTTPStatus.OK, self.state["report_text"])

        if path == "/app-data":
            if DEFAULT_APP_DATA.exists():
                return _json_response(self, HTTPStatus.OK, _load_json(DEFAULT_APP_DATA))
            return _json_response(self, HTTPStatus.NOT_FOUND, {"error": "app_data.json not found. Run training first."})

        if path == "/feedback/summary":
            feedback_log = ARTIFACTS / "feedback_log.jsonl"
            if feedback_log.exists():
                from feedback import summarize_feedback, load_feedback_entries

                return _json_response(self, HTTPStatus.OK, summarize_feedback(load_feedback_entries(feedback_log)))
            return _json_response(self, HTTPStatus.OK, {"count": 0, "note": "No feedback entries logged yet."})

        self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        body = self._body_json()
        bundle = self.state["bundle"]
        stats = self.state["stats"]
        planned_stats = self.state["planned_stats"]

        if path == "/predict":
            result = predict_from_bundle(bundle, body, duration_booster=self.state["duration_booster"])
            return _json_response(self, HTTPStatus.OK, result)

        if path == "/plan":
            events = body if isinstance(body, list) else body.get("events", [])
            budget = int(body.get("budget", 50)) if isinstance(body, dict) else 50
            scored = [predict_from_bundle(bundle, event, duration_booster=self.state["duration_booster"]) | {"event": event} for event in events]
            allocation = allocate_resources(scored, total_personnel=budget)
            return _json_response(self, HTTPStatus.OK, {"scored_events": scored, "allocation": allocation})

        if path == "/planned-impact":
            impact = forecast_planned_event(body, stats, planned_stats)
            return _json_response(self, HTTPStatus.OK, impact)

        if path == "/sample-predict":
            sample = _sample_event_payload()
            return _json_response(self, HTTPStatus.OK, sample)

        self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")


def create_app() -> ThreadingHTTPServer:
    state = _load_state()
    AstramHandler.state = state
    return ThreadingHTTPServer(("0.0.0.0", 8000), AstramHandler)


def _sample_event_payload() -> dict[str, object]:
    dataset = ROOT / "dataset"
    csv_files = sorted(dataset.glob("*.csv"))
    if not csv_files:
        return {}
    import csv

    with csv_files[0].open(newline="", encoding="utf-8", errors="replace") as f:
        row = next(csv.DictReader(f))
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Astram backend microservice.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    args = parser.parse_args()

    state = _load_state(Path(args.bundle))
    AstramHandler.state = state
    server = ThreadingHTTPServer((args.host, args.port), AstramHandler)
    print(f"Astram service running at http://{args.host}:{args.port}")
    print("Endpoints: /health /metrics /graphs /weights /report.txt /predict /plan /planned-impact /feedback/summary")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
