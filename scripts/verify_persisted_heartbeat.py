#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / ".github" / "recovery" / "policy.json"


def parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def lane_config(lane: str, policy_path: Path = POLICY) -> dict:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    try:
        return policy["lanes"][lane]
    except KeyError as exc:
        raise ValueError(f"unknown recovery lane: {lane}") from exc


def read_heartbeat_text(text: str, field: str) -> datetime:
    payload = json.loads(text)
    value = payload.get(field)
    if not value:
        raise ValueError(f"heartbeat field {field!r} is missing or empty")
    return parse_time(str(value))


def local_heartbeat(lane: str, policy_path: Path = POLICY) -> datetime:
    cfg = lane_config(lane, policy_path)
    path = ROOT / cfg["heartbeat_path"]
    return read_heartbeat_text(path.read_text(encoding="utf-8"), cfg["heartbeat_field"])


def remote_heartbeat(lane: str, remote_ref: str = "origin/main", policy_path: Path = POLICY) -> datetime:
    cfg = lane_config(lane, policy_path)
    path = cfg["heartbeat_path"]
    result = subprocess.run(
        ["git", "show", f"{remote_ref}:{path}"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return read_heartbeat_text(result.stdout, cfg["heartbeat_field"])


def verify_advanced(previous: datetime, current: datetime, lane: str) -> None:
    if current <= previous:
        raise RuntimeError(
            f"{lane} heartbeat did not advance on main: "
            f"previous={previous.isoformat()} current={current.isoformat()}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail closed unless a production lane heartbeat advanced after persistence."
    )
    parser.add_argument("lane")
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--previous")
    parser.add_argument("--remote-ref", default="origin/main")
    parser.add_argument("--no-fetch", action="store_true")
    args = parser.parse_args()

    if args.capture:
        print(local_heartbeat(args.lane).isoformat())
        return 0

    if not args.previous:
        parser.error("--previous is required unless --capture is used")

    previous = parse_time(args.previous)
    if not args.no_fetch:
        subprocess.run(["git", "fetch", "origin", "main"], cwd=ROOT, check=True)

    current = remote_heartbeat(args.lane, args.remote_ref)
    verify_advanced(previous, current, args.lane)
    print(
        f"{args.lane} persisted heartbeat advanced: "
        f"{previous.isoformat()} -> {current.isoformat()}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError, OSError) as exc:
        print(f"heartbeat persistence verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
