#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / ".github" / "recovery" / "policy.json"
ACTIVE_RUN_STATES = {"queued", "in_progress", "waiting", "requested", "pending"}


def parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def in_active_window(now: datetime, window: dict | None) -> bool:
    if not window:
        return True
    local = now.astimezone(ZoneInfo(window["timezone"]))
    start = int(window["start_hour"])
    end = int(window["end_hour"])
    if start <= end:
        return start <= local.hour < end
    return local.hour >= start or local.hour < end


def heartbeat_age_minutes(path: Path, field: str, now: datetime) -> float | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        stamp = payload.get(field)
        if not stamp:
            return None
        return (now - parse_time(stamp).astimezone(now.tzinfo)).total_seconds() / 60.0
    except Exception:
        return None


def github_json(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "knowthegulf-recovery-watchdog",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def recovery_suppression_reason(
    runs: list[dict],
    cooldown_minutes: int,
    failure_retry_minutes: int,
    now: datetime,
) -> str | None:
    for run in runs:
        if run.get("status") in ACTIVE_RUN_STATES:
            return f"workflow run {run.get('id', 'unknown')} already {run.get('status')}"

    for run in runs:
        if run.get("event") != "workflow_dispatch":
            continue
        created = run.get("created_at")
        if not created:
            continue
        age = (now - parse_time(created).astimezone(now.tzinfo)).total_seconds() / 60.0
        conclusion = run.get("conclusion")
        if conclusion == "success" and 0 <= age < cooldown_minutes:
            return f"successful recovery dispatch {run.get('id', 'unknown')} is {age:.1f}m old within {cooldown_minutes}m cooldown"
        if conclusion not in (None, "success") and 0 <= age < failure_retry_minutes:
            return f"failed recovery dispatch {run.get('id', 'unknown')} is {age:.1f}m old within {failure_retry_minutes}m failure retry delay"

    return None


def workflow_recovery_suppression(
    repo: str,
    workflow_path: str,
    cooldown_minutes: int,
    failure_retry_minutes: int,
    now: datetime,
    token: str,
) -> str | None:
    encoded = urllib.parse.quote(workflow_path, safe="")
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{encoded}/runs?per_page=20"
    data = github_json(url, token)
    return recovery_suppression_reason(
        data.get("workflow_runs", []),
        cooldown_minutes,
        failure_retry_minutes,
        now,
    )


def dispatch_workflow(repo: str, workflow_path: str, inputs: dict, token: str) -> None:
    encoded = urllib.parse.quote(workflow_path, safe="")
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{encoded}/dispatches"
    body = json.dumps({"ref": "main", "inputs": inputs}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "knowthegulf-recovery-watchdog",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status not in (201, 204):
            raise RuntimeError(f"workflow dispatch returned HTTP {response.status}")


def evaluate(policy_path: Path, now: datetime, repo: str, token: str | None, dry_run: bool) -> int:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    failures = 0

    for lane, cfg in policy["lanes"].items():
        if not in_active_window(now, cfg.get("active_window")):
            print(f"{lane}: outside active window")
            continue

        heartbeat = ROOT / cfg["heartbeat_path"]
        age = heartbeat_age_minutes(heartbeat, cfg["heartbeat_field"], now)
        overdue = int(cfg["overdue_minutes"])
        if age is not None and age <= overdue:
            print(f"{lane}: healthy age={age:.1f}m threshold={overdue}m")
            continue

        age_text = "unreadable" if age is None else f"{age:.1f}m"
        workflow_path = cfg.get("workflow_path")
        if not workflow_path:
            failures += 1
            print(f"{lane}: stale age={age_text}; no workflow_path configured", file=sys.stderr)
            continue

        if dry_run:
            print(f"{lane}: stale age={age_text}; would dispatch {workflow_path}")
            continue

        if not token:
            failures += 1
            print(f"{lane}: stale age={age_text}; GITHUB_TOKEN missing", file=sys.stderr)
            continue

        cooldown = int(cfg.get("cooldown_minutes", 120))
        failure_retry = int(cfg.get("failure_retry_minutes", min(90, cooldown)))
        try:
            suppression = workflow_recovery_suppression(
                repo,
                workflow_path,
                cooldown,
                failure_retry,
                now,
                token,
            )
            if suppression:
                print(f"{lane}: stale age={age_text}; recovery suppressed because {suppression}")
                continue
            dispatch_workflow(repo, workflow_path, cfg.get("dispatch_inputs", {}), token)
            print(f"{lane}: stale age={age_text}; dispatched {workflow_path}")
        except Exception as exc:
            failures += 1
            print(f"{lane}: recovery dispatch failed: {type(exc).__name__}: {exc}", file=sys.stderr)

    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY", "DCMedic/safe2swimpcb"))
    parser.add_argument("--now", help="ISO-8601 override for tests/manual validation")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    token = os.getenv("GITHUB_TOKEN")
    return evaluate(args.policy, now, args.repo, token, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
