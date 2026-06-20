"""Seed events table from dataset/events.csv."""
from __future__ import annotations

import csv
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
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO events
                    (external_id, event_type, event_cause, corridor, zone, junction,
                     latitude, longitude, priority, requires_road_closure, address,
                     start_datetime, end_datetime, closed_datetime, resolved_datetime,
                     status, description, direction, veh_type, police_station)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        row.get("id"),
                        row.get("event_type"),
                        row.get("event_cause"),
                        row.get("corridor"),
                        row.get("zone"),
                        row.get("junction"),
                        lat,
                        lon,
                        priority,
                        rrc,
                        row.get("address"),
                        row.get("start_datetime"),
                        row.get("end_datetime"),
                        row.get("closed_datetime"),
                        row.get("resolved_datetime"),
                        row.get("status"),
                        row.get("description"),
                        row.get("direction"),
                        row.get("veh_type"),
                        row.get("police_station"),
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
