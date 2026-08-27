#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
HEALTH_PATH = ROOT / "data" / "x_publisher_health.json"
TZ = ZoneInfo("America/Chicago")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detail", required=True)
    parser.add_argument("--publish-requested", action="store_true")
    args = parser.parse_args()

    previous = {}
    try:
        previous = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    now = datetime.now(TZ)
    payload = {
        "version": 1,
        "last_evaluated_at": now.isoformat(),
        "last_outcome": "failed",
        "last_outcome_detail": args.detail[:1000],
        "publish_requested": args.publish_requested,
        "forced_slot": previous.get("forced_slot"),
        "exit_code": 1,
        "last_published_at": previous.get("last_published_at"),
        "last_failure_at": now.isoformat(),
    }
    HEALTH_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PUBLISHER_HEALTH=failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
