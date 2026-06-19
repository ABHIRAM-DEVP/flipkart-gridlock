from __future__ import annotations

import argparse
import json
from pathlib import Path

from operations import allocate_resources
from predict import predict_from_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Score and allocate resources for multiple events.")
    parser.add_argument("--bundle", default="artifacts/astram_model_bundle.json")
    parser.add_argument("--events-json", required=True, help="Path to a JSON list of event records.")
    parser.add_argument("--budget", type=int, default=50, help="Total personnel available.")
    args = parser.parse_args()

    with Path(args.bundle).open("r", encoding="utf-8") as f:
        bundle = json.load(f)
    with Path(args.events_json).open("r", encoding="utf-8") as f:
        events = json.load(f)
    if not isinstance(events, list):
        raise SystemExit("--events-json must contain a JSON list.")

    scored = [predict_from_bundle(bundle, event) | {"event": event} for event in events]
    allocation = allocate_resources(scored, total_personnel=args.budget)
    print(json.dumps({"scored_events": scored, "allocation": allocation}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

