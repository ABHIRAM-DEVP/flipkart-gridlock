from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

from astram_data import normalize_text, parse_dt, read_csv_rows
from train import train_and_save


DEFAULT_FEEDBACK_LOG = Path("artifacts") / "feedback_log.jsonl"


def load_feedback_entries(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    entries: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
    return entries


def append_feedback(path: Path, entry: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def synthetic_row_from_feedback(entry: dict[str, object], index: int) -> dict[str, str]:
    event = dict(entry.get("event", {}))
    start_dt = parse_dt(event.get("start_datetime"))
    actual_duration = float(entry.get("actual_duration_min", 0.0))
    if start_dt is not None:
        event["closed_datetime"] = (start_dt + timedelta(minutes=actual_duration)).isoformat(sep=" ")
    event["id"] = event.get("id") or f"FBK{index:06d}"
    event["status"] = normalize_text(event.get("status")) or "closed"
    if not event.get("event_type"):
        event["event_type"] = "unplanned"
    return {k: str(v) if v is not None else "" for k, v in event.items()}


def summarize_feedback(entries: list[dict[str, object]]) -> dict[str, object]:
    total = len(entries)
    if total == 0:
        return {"count": 0, "note": "No feedback entries logged yet."}

    abs_errors = []
    severity_hits = 0
    for entry in entries:
        predicted = float(entry.get("predicted_duration_min", 0.0))
        actual = float(entry.get("actual_duration_min", 0.0))
        abs_errors.append(abs(predicted - actual))
        if normalize_text(entry.get("predicted_severity")).lower() == normalize_text(entry.get("actual_severity")).lower():
            severity_hits += 1

    return {
        "count": total,
        "mae_min": round(sum(abs_errors) / total, 2),
        "severity_accuracy": round(severity_hits / total, 4),
        "avg_abs_error_min": round(sum(abs_errors) / total, 2),
    }


def retrain_from_feedback(csv_path: Path, feedback_path: Path, outdir: Path) -> dict[str, object]:
    base_rows = read_csv_rows(csv_path)
    entries = load_feedback_entries(feedback_path)
    synthetic_rows = [synthetic_row_from_feedback(entry, i) for i, entry in enumerate(entries)]
    merged_rows = base_rows + synthetic_rows
    summary = train_and_save(merged_rows, outdir)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Log feedback and retrain the Astram model.")
    sub = parser.add_subparsers(dest="command", required=True)

    log_cmd = sub.add_parser("log", help="Append a feedback entry.")
    log_cmd.add_argument("--event-json", required=True, help="Path to the original event JSON.")
    log_cmd.add_argument("--predicted-duration", type=float, required=True)
    log_cmd.add_argument("--predicted-severity", required=True)
    log_cmd.add_argument("--actual-duration", type=float, required=True)
    log_cmd.add_argument("--actual-severity", required=True)
    log_cmd.add_argument("--manpower-used", type=int, default=0)
    log_cmd.add_argument("--barricades-used", type=int, default=0)

    summary_cmd = sub.add_parser("summary", help="Summarize logged feedback.")
    summary_cmd.add_argument("--log", default=str(DEFAULT_FEEDBACK_LOG))

    retrain_cmd = sub.add_parser("retrain", help="Retrain using the feedback log.")
    retrain_cmd.add_argument("--csv", default=str(next(Path("dataset").glob("*.csv"))))
    retrain_cmd.add_argument("--log", default=str(DEFAULT_FEEDBACK_LOG))
    retrain_cmd.add_argument("--outdir", default="artifacts")

    args = parser.parse_args()

    if args.command == "log":
        event_path = Path(args.event_json)
        with event_path.open("r", encoding="utf-8") as f:
            event = json.load(f)
        append_feedback(
            DEFAULT_FEEDBACK_LOG,
            {
                "event": event,
                "predicted_duration_min": args.predicted_duration,
                "predicted_severity": args.predicted_severity,
                "actual_duration_min": args.actual_duration,
                "actual_severity": args.actual_severity,
                "manpower_used": args.manpower_used,
                "barricades_used": args.barricades_used,
            },
        )
        print(json.dumps({"status": "logged", "log": str(DEFAULT_FEEDBACK_LOG)}, indent=2))
        return 0

    if args.command == "summary":
        log_path = Path(args.log)
        entries = load_feedback_entries(log_path)
        print(json.dumps(summarize_feedback(entries), indent=2))
        return 0

    if args.command == "retrain":
        summary = retrain_from_feedback(Path(args.csv), Path(args.log), Path(args.outdir))
        print(json.dumps({"status": "retrained", "summary": summary["metrics"]}, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

