"""Seed events table from dataset/events.csv."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from db import get_conn, init_db

CSV_PATH = Path(__file__).resolve().parent.parent / "dataset" / "events.csv"


def _resolve_csv_path() -> Path | None:
    if CSV_PATH.exists():
        return CSV_PATH
    dataset_dir = CSV_PATH.parent
    if dataset_dir.exists():
        for candidate in sorted(dataset_dir.glob("*.csv")):
            return candidate
    return None


def _clean_ts(value: object) -> object | None:
    """Convert CSV timestamp strings to either a valid ISO-ish datetime string or None.

    Prevents Postgres from receiving literal "NULL" (string), which breaks TIMESTAMP parsing.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"NULL", "NONE", "NAN", "NAT", ""}:
        return None

    # Normalize common variants; Postgres accepts 'YYYY-MM-DD HH:MM:SS[.ffffff]'
    cleaned = text.replace("T", " ").replace("Z", "").strip()
    if not cleaned or cleaned.upper() in {"NULL", "NONE", "NAN", "NAT"}:
        return None

    try:
        # Validate parsability (multiple formats supported)
        for fmt in (
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d-%m-%Y %H:%M:%S.%f",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
        ):
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S.%f").rstrip("0").rstrip(".")
            except ValueError:
                continue
        dt = datetime.fromisoformat(cleaned)
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f").rstrip("0").rstrip(".")
    except Exception:
        return None


def seed() -> tuple[int, int]:
    csv_path = _resolve_csv_path()
    if not csv_path:
        print(f"CSV not found in {CSV_PATH.parent}")
        return 0, 0

    init_db()
    conn = get_conn()
    inserted = skipped = 0
    with csv_path.open(newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            priority = (row.get("priority") or "").strip().lower()
            rrc_raw = (row.get("requires_road_closure") or "").strip().upper()
            rrc = 1 if rrc_raw in ("TRUE", "1", "YES", "Y") else 0
            try:
                lat = float(row["latitude"]) if row.get("latitude") else None
                lon = float(row["longitude"]) if row.get("longitude") else None

                start_dt = _clean_ts(row.get("start_datetime"))
                end_dt = _clean_ts(row.get("end_datetime"))
                closed_dt = _clean_ts(row.get("closed_datetime"))
                resolved_dt = _clean_ts(row.get("resolved_datetime"))

                def sanitize_param(v: object) -> object:
                    """Final safety check: ensure 'NULL' strings never reach the database."""
                    if isinstance(v, str):
                        s = v.strip()
                        if s.upper() in {"NULL", "NONE", "NAN", "NAT"} or not s:
                            return None
                    return v

                cur = conn.execute(
                    """
                    INSERT INTO events
                    (external_id, event_type, event_cause, corridor, zone, junction,
                     latitude, longitude, priority, requires_road_closure, address,
                     start_datetime, end_datetime, closed_datetime, resolved_datetime,
                     status, description, direction, veh_type, police_station)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT (external_id) DO NOTHING
                    """,
                    tuple(
                        sanitize_param(v) for v in (
                            row.get("id"),
                            row.get("event_type"),
                            row.get("event_cause"),
                            row.get("corridor"),
                            row.get("zone"),
                            row.get("junction"),
                            lat,
                            lon,
                            priority or None,
                            rrc,
                            row.get("address"),
                            start_dt,
                            end_dt,
                            closed_dt,
                            resolved_dt,
                            row.get("status"),
                            row.get("description"),
                            row.get("direction"),
                            row.get("veh_type"),
                            row.get("police_station"),
                        )
                    ),
                )
                if cur.rowcount:
                    inserted += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
    conn.commit()
    conn.close()
    print(f"Seeded {inserted} rows, skipped {skipped}")
    return inserted, skipped


def seed_db_if_empty() -> None:
    from db import events_table_empty

    init_db()
    if events_table_empty():
        seed()


if __name__ == "__main__":
    seed()

