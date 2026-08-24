#!/usr/bin/env python3
"""Run the X content engine while recording a durable publisher health heartbeat."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
HEALTH_PATH = ROOT / "data" / "x_publisher_health.json"
ENGINE = ROOT / "scripts" / "x_content_engine.py"
TZ = ZoneInfo("America/Chicago")


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--force-slot", choices=["morning", "afternoon", "evening"])
    known, unknown = parser.parse_known_args()
    forwarded: list[str] = []
    if known.publish:
        forwarded.append("--publish")
    if known.force_slot:
        forwarded.extend(["--force-slot", known.force_slot])
    forwarded.extend(unknown)
    return known, forwarded


def classify(returncode: int, stdout: str, stderr: str) -> tuple[str, str | None]:
    if returncode != 0:
        detail = (stderr or stdout).strip().splitlines()
        return "failed", (detail[-1][:1000] if detail else f"exit code {returncode}")
    if "PUBLISHED_URL=" in stdout:
        return "published", None
    for line in stdout.splitlines():
        if line.startswith("NO_POST:"):
            return "no_post", line.partition(":")[2].strip() or None
    if "DRY_RUN_ONLY" in stdout:
        return "dry_run", None
    return "completed", None


def write_health(now: datetime, publish: bool, slot: str | None, returncode: int, outcome: str, detail: str | None) -> None:
    previous = {}
    try:
        previous = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    payload = {
        "version": 1,
        "last_evaluated_at": now.isoformat(),
        "last_outcome": outcome,
        "last_outcome_detail": detail,
        "publish_requested": publish,
        "forced_slot": slot,
        "exit_code": returncode,
        "last_published_at": previous.get("last_published_at"),
        "last_failure_at": previous.get("last_failure_at"),
    }
    if outcome == "published":
        payload["last_published_at"] = now.isoformat()
    if outcome == "failed":
        payload["last_failure_at"] = now.isoformat()
    HEALTH_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args, forwarded = parse_args()
    now = datetime.now(TZ)
    proc = subprocess.run([sys.executable, str(ENGINE), *forwarded], cwd=ROOT, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    outcome, detail = classify(proc.returncode, proc.stdout, proc.stderr)
    write_health(now, args.publish, args.force_slot, proc.returncode, outcome, detail)
    print(f"PUBLISHER_HEALTH={outcome}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
