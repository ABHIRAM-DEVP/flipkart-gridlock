"""SQLite schema and CRUD helpers for Astram."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "astram.db"
_WRITE_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id           TEXT UNIQUE,
    event_type            TEXT,
    event_cause           TEXT,
    corridor              TEXT,
    zone                  TEXT,
    junction              TEXT,
    latitude              REAL,
    longitude             REAL,
    priority              TEXT,
    requires_road_closure INTEGER DEFAULT 0,
    address               TEXT,
    start_datetime        TEXT,
    end_datetime          TEXT,
    closed_datetime       TEXT,
    resolved_datetime     TEXT,
    status                TEXT,
    description           TEXT,
    direction             TEXT,
    veh_type              TEXT,
    police_station        TEXT,
    created_at            TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_corridor ON events(corridor);
CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_datetime);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

CREATE TABLE IF NOT EXISTS predictions (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    input_payload          TEXT NOT NULL,
    predicted_duration_min REAL,
    predicted_severity     TEXT,
    prediction_interval    TEXT,
    resource_plan          TEXT,
    planned_impact         TEXT,
    model_version          TEXT DEFAULT 'v1',
    corridor               TEXT,
    created_at             TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pred_created ON predictions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pred_severity ON predictions(predicted_severity);
CREATE INDEX IF NOT EXISTS idx_pred_corridor ON predictions(corridor);

CREATE TABLE IF NOT EXISTS batch_plans (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    input_events     TEXT NOT NULL,
    personnel_budget INTEGER NOT NULL,
    scored_events    TEXT,
    allocation       TEXT,
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS planned_impact_forecasts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    input_payload       TEXT NOT NULL,
    planned_key         TEXT,
    baseline_rate       REAL,
    spillover_per_event REAL,
    impact_multiplier   REAL,
    risk_score          REAL,
    corridor            TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS model_runs (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    rows_total            INTEGER,
    rows_with_duration    INTEGER,
    train_rows            INTEGER,
    test_rows             INTEGER,
    duration_mae_min      REAL,
    duration_rmse_min     REAL,
    duration_r2           REAL,
    severity_accuracy     REAL,
    severity_f1_macro     REAL,
    severity_f1_weighted  REAL,
    classification_report TEXT,
    model_version         TEXT,
    trained_at            TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS hotspot_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_type TEXT,
    data          TEXT NOT NULL,
    computed_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS live_feed_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT,
    payload     TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def _json_loads(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def init_db() -> None:
    with _WRITE_LOCK:
        conn = get_conn()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()


def insert_prediction(input_payload: dict, result: dict) -> int:
    corridor = (input_payload.get("corridor") or "").strip()
    interval = result.get("prediction_interval_min") or result.get("prediction_interval")
    with _WRITE_LOCK:
        conn = get_conn()
        try:
            cur = conn.execute(
                """
                INSERT INTO predictions
                (input_payload, predicted_duration_min, predicted_severity,
                 prediction_interval, resource_plan, planned_impact, corridor)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    json.dumps(input_payload),
                    result.get("predicted_duration_min"),
                    result.get("predicted_severity"),
                    json.dumps(interval) if interval else None,
                    json.dumps(result.get("resource_plan")) if result.get("resource_plan") else None,
                    json.dumps(result.get("planned_impact")) if result.get("planned_impact") else None,
                    corridor or None,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()


def get_recent_predictions(limit: int = 20) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM predictions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for row in rows:
            d = _row_to_dict(row) or {}
            d["input_payload"] = _json_loads(d.get("input_payload"), {})
            d["prediction_interval"] = _json_loads(d.get("prediction_interval"))
            d["resource_plan"] = _json_loads(d.get("resource_plan"))
            d["planned_impact"] = _json_loads(d.get("planned_impact"))
            out.append(d)
        return out
    finally:
        conn.close()


def insert_batch_plan(events: list, budget: int, scored: list, allocation: dict) -> int:
    with _WRITE_LOCK:
        conn = get_conn()
        try:
            cur = conn.execute(
                """
                INSERT INTO batch_plans (input_events, personnel_budget, scored_events, allocation)
                VALUES (?, ?, ?, ?)
                """,
                (json.dumps(events), budget, json.dumps(scored), json.dumps(allocation)),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()


def get_recent_plans(limit: int = 10) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM batch_plans ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for row in rows:
            d = _row_to_dict(row) or {}
            d["input_events"] = _json_loads(d.get("input_events"), [])
            d["scored_events"] = _json_loads(d.get("scored_events"), [])
            d["allocation"] = _json_loads(d.get("allocation"), {})
            out.append(d)
        return out
    finally:
        conn.close()


def insert_planned_impact(input_payload: dict, result: dict) -> int:
    corridor = (input_payload.get("corridor") or "").strip()
    with _WRITE_LOCK:
        conn = get_conn()
        try:
            cur = conn.execute(
                """
                INSERT INTO planned_impact_forecasts
                (input_payload, planned_key, baseline_rate, spillover_per_event,
                 impact_multiplier, risk_score, corridor)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    json.dumps(input_payload),
                    result.get("planned_key"),
                    result.get("baseline_unplanned_rate"),
                    result.get("spillover_events_per_planned_event"),
                    result.get("impact_multiplier"),
                    result.get("compounding_risk_score"),
                    corridor or None,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()


def get_recent_planned_impacts(limit: int = 10) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM planned_impact_forecasts ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for row in rows:
            d = _row_to_dict(row) or {}
            d["input_payload"] = _json_loads(d.get("input_payload"), {})
            out.append(d)
        return out
    finally:
        conn.close()


def insert_model_run(summary: dict) -> int:
    metrics = summary.get("metrics") or summary
    with _WRITE_LOCK:
        conn = get_conn()
        try:
            cur = conn.execute(
                """
                INSERT INTO model_runs
                (rows_total, rows_with_duration, train_rows, test_rows,
                 duration_mae_min, duration_rmse_min, duration_r2,
                 severity_accuracy, severity_f1_macro, severity_f1_weighted,
                 classification_report, model_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.get("rows_total"),
                    summary.get("rows_with_duration"),
                    summary.get("train_rows"),
                    summary.get("test_rows"),
                    metrics.get("duration_mae_min"),
                    metrics.get("duration_rmse_min"),
                    metrics.get("duration_r2"),
                    metrics.get("severity_accuracy"),
                    metrics.get("severity_f1_macro"),
                    metrics.get("severity_f1_weighted"),
                    summary.get("classification_report") or metrics.get("severity_classification_report"),
                    summary.get("model_version", "v1"),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()


def get_latest_model_run() -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM model_runs ORDER BY trained_at DESC LIMIT 1"
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_all_model_runs() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM model_runs ORDER BY trained_at ASC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows if _row_to_dict(r)]
    finally:
        conn.close()


def insert_hotspot_snapshot(snapshot_type: str, data: list) -> None:
    with _WRITE_LOCK:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO hotspot_snapshots (snapshot_type, data) VALUES (?, ?)",
                (snapshot_type, json.dumps(data)),
            )
            conn.commit()
        finally:
            conn.close()


def get_latest_hotspot_snapshot(snapshot_type: str) -> list | None:
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT data, computed_at FROM hotspot_snapshots
            WHERE snapshot_type = ?
            ORDER BY computed_at DESC LIMIT 1
            """,
            (snapshot_type,),
        ).fetchone()
        if not row:
            return None
        computed_at = row["computed_at"]
        try:
            ts = datetime.fromisoformat(computed_at.replace("Z", "+00:00"))
        except ValueError:
            ts = datetime.strptime(computed_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - ts.replace(tzinfo=timezone.utc)).total_seconds()
        if age > 15:
            return None
        return _json_loads(row["data"], [])
    finally:
        conn.close()


def get_hotspot_snapshot_fresh_or_latest(snapshot_type: str) -> list:
    fresh = get_latest_hotspot_snapshot(snapshot_type)
    if fresh is not None:
        return fresh
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT data FROM hotspot_snapshots
            WHERE snapshot_type = ?
            ORDER BY computed_at DESC LIMIT 1
            """,
            (snapshot_type,),
        ).fetchone()
        if row:
            return _json_loads(row["data"], [])
        return []
    finally:
        conn.close()


def insert_live_feed_event(event_type: str, payload: dict) -> None:
    with _WRITE_LOCK:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO live_feed_events (event_type, payload) VALUES (?, ?)",
                (event_type, json.dumps(payload)),
            )
            conn.commit()
        finally:
            conn.close()


def get_recent_live_feed(limit: int = 50) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM live_feed_events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for row in rows:
            d = _row_to_dict(row) or {}
            d["payload"] = _json_loads(d.get("payload"), {})
            out.append({"type": d.get("event_type"), "payload": d["payload"], "created_at": d.get("created_at")})
        return list(reversed(out))
    finally:
        conn.close()


def get_event_stats() -> dict:
    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
        if total == 0:
            return {
                "total_events": 0,
                "corridor_counts": {},
                "cause_counts": {},
                "hour_counts": {},
                "zone_counts": {},
            }

        corridor_counts = {
            r["corridor"]: r["c"]
            for r in conn.execute(
                "SELECT corridor, COUNT(*) AS c FROM events WHERE corridor IS NOT NULL AND corridor != '' GROUP BY corridor"
            ).fetchall()
        }
        cause_counts = {
            r["event_cause"]: r["c"]
            for r in conn.execute(
                """
                SELECT event_cause, COUNT(*) AS c FROM events
                WHERE event_cause IS NOT NULL AND event_cause != ''
                GROUP BY event_cause ORDER BY c DESC LIMIT 15
                """
            ).fetchall()
        }
        zone_counts = {
            r["zone"]: r["c"]
            for r in conn.execute(
                "SELECT zone, COUNT(*) AS c FROM events WHERE zone IS NOT NULL AND zone != '' GROUP BY zone"
            ).fetchall()
        }

        hour_counts: dict[str, int] = {}
        for row in conn.execute("SELECT start_datetime FROM events WHERE start_datetime IS NOT NULL").fetchall():
            dt_str = row["start_datetime"] or ""
            hour = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    hour = datetime.strptime(dt_str[:19], fmt[: len(dt_str)] if len(dt_str) < 19 else fmt).hour
                    break
                except ValueError:
                    continue
            if hour is None and "T" in dt_str:
                try:
                    hour = int(dt_str.split("T")[1][:2])
                except (ValueError, IndexError):
                    hour = 0
            if hour is not None:
                key = str(hour)
                hour_counts[key] = hour_counts.get(key, 0) + 1

        corridor_risk = []
        for row in conn.execute(
            """
            SELECT corridor,
                   COUNT(*) AS event_count,
                   AVG(CASE
                     WHEN closed_datetime IS NOT NULL AND start_datetime IS NOT NULL THEN
                       (julianday(closed_datetime) - julianday(start_datetime)) * 24 * 60
                     ELSE NULL END) AS avg_duration
            FROM events
            WHERE corridor IS NOT NULL AND corridor != ''
            GROUP BY corridor
            """
        ).fetchall():
            count = row["event_count"] or 0
            avg_dur = row["avg_duration"] or 0.0
            risk = min(100.0, count * 2.5 + (avg_dur or 0) / 5.0)
            corridor_risk.append(
                {
                    "corridor": row["corridor"],
                    "event_count": count,
                    "avg_duration_min": round(float(avg_dur or 0), 1),
                    "risk_score": round(risk, 1),
                }
            )
        corridor_risk.sort(key=lambda x: x["risk_score"], reverse=True)

        return {
            "total_events": total,
            "corridor_counts": corridor_counts,
            "cause_counts": cause_counts,
            "hour_counts": dict(sorted(hour_counts.items(), key=lambda x: int(x[0]))),
            "zone_counts": zone_counts,
            "corridor_risk": corridor_risk,
        }
    finally:
        conn.close()


def events_table_empty() -> bool:
    conn = get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
        return count == 0
    finally:
        conn.close()
