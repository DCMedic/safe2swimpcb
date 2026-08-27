#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_health(path: Path, workflow: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    payload = {
        "version": 1,
        "workflow": workflow,
        "status": "success",
        "last_success_at": now.isoformat(),
        "run_id": os.getenv("GITHUB_RUN_ID"),
        "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        "event_name": os.getenv("GITHUB_EVENT_NAME"),
        "head_sha": os.getenv("GITHUB_SHA"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_health(ROOT / args.output, args.workflow)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
