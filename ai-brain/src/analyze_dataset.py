from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from astram_data import (
    build_hotspot_rows,
    duration_minutes,
    fit_aggregate_stats,
    normalize_text,
    read_csv_rows,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Print the key dataset insights used by the model.")
    parser.add_argument("--csv", default=str(next(Path("dataset").glob("*.csv"))), help="Path to the Astram CSV file.")
    parser.add_argument("--out", default="artifacts/dataset_insights.json", help="Where to write a JSON summary.")
    args = parser.parse_args()

    rows = read_csv_rows(args.csv)
    stats = fit_aggregate_stats(rows)
    hotspots = build_hotspot_rows(rows, stats)[:20]

    counter_event_type = Counter(normalize_text(r.get("event_type")) for r in rows)
    counter_cause = Counter(normalize_text(r.get("event_cause")) for r in rows)
    counter_priority = Counter(normalize_text(r.get("priority")) for r in rows)
    counter_closure = Counter(normalize_text(r.get("requires_road_closure")) for r in rows)

    duration_rows = [duration_minutes(r) for r in rows]
    valid_durations = [d for d in duration_rows if d is not None]
    summary = {
        "rows_total": len(rows),
        "rows_with_valid_duration": len(valid_durations),
        "event_type_counts": counter_event_type.most_common(),
        "event_cause_counts": counter_cause.most_common(15),
        "priority_counts": counter_priority.most_common(),
        "closure_counts": counter_closure.most_common(),
        "global_duration_median": stats.global_duration_median,
        "global_duration_mean": stats.global_duration_mean,
        "global_duration_p90": stats.global_duration_p90,
        "top_hotspots": hotspots,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
      json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

