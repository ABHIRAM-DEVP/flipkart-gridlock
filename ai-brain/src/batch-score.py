"""
batch_score.py  –  Score a list of events and run MILP resource allocation.

Usage:
    python batch_score.py --events-json events.json --budget 50
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from operations import allocate_resources
from predict import load_artifacts, predict_event, ARTIFACTS_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch score events and allocate resources.")
    parser.add_argument("--artifacts", default=str(ARTIFACTS_DIR))
    parser.add_argument("--events-json", required=True, help="JSON list of event records.")
    parser.add_argument("--budget", type=int, default=50, help="Total personnel budget.")
    args = parser.parse_args()

    artifacts = load_artifacts(Path(args.artifacts))
    with open(args.events_json, "r", encoding="utf-8") as f:
        events = json.load(f)

    if not isinstance(events, list):
        raise SystemExit("--events-json must contain a JSON list.")

    scored = []
    for i, event in enumerate(events):
        result = predict_event(event, artifacts)
        result["event"] = event
        result["event_index"] = i
        scored.append(result)

    allocation = allocate_resources(scored, total_personnel=args.budget)

    output = {"scored_events": scored, "allocation": allocation}
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())