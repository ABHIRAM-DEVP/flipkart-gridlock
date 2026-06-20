"""Background hotspot snapshot refresh every 15 seconds."""
from __future__ import annotations

import threading
import time
from typing import Any


def _refresh_hotspots(artifacts: dict[str, Any], db_module: Any) -> None:
    bundle = artifacts.get("bundle") or {}
    dbscan = bundle.get("dbscan_hotspots") or []
    corridor = bundle.get("train_hotspots") or []
    db_module.insert_hotspot_snapshot("dbscan", dbscan)
    db_module.insert_hotspot_snapshot("corridor", corridor)


def start_scheduler(artifacts: dict[str, Any], db_module: Any, interval: int = 15) -> None:
    def _loop() -> None:
        while True:
            try:
                _refresh_hotspots(artifacts, db_module)
            except Exception as exc:
                print(f"[scheduler] hotspot refresh error: {exc}")
            time.sleep(interval)

    t = threading.Thread(target=_loop, daemon=True, name="hotspot-refresh")
    t.start()
    print(f"[scheduler] hotspot refresh started (every {interval}s)")
