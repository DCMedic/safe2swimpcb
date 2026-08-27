#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
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


def heartbeat_timestamp(path: Path, field: str) -> datetime | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        stamp = payload.get(field)
        if not stamp:
            return None
        return parse_time(str(stamp))
    except Exception:
        return None


def heartbeat_age_minutes(path: Path, field: str, now: datetime) -> float | None:
    stamp = heartbeat_timestamp(path, field)
    if stamp is None:
        return None
    return (now - stamp.astimezone(now.tzinfo)).total_seconds() / 60.0


def run_age_minutes(run: dict, now: datetime) -> float | None:
    created = run.get("created_at") or run.get("run_started_at")
    if not created:
        return None
    created_at = parse_time(str(created))
    return (now - created_at.astimezone(now.tzinfo)).total_seconds() / 60.0


def split_active_runs(
    runs: list[dict],
    stuck_run_minutes: int,
    now: datetime,
) -> tuple[list[dict], list[dict]]:
    recent: list[dict] = []
    stuck: list[dict] = []
    for run in runs:
        if run.get("status") not in ACTIVE_RUN_STATES:
            continue
        age = run_age_minutes(run, now)
        if age is None or age < stuck_run_minutes:
            recent.append(run)
        else:
            stuck.append(run)
    return recent, stuck


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
    heartbeat_at: datetime | None = None,
    stuck_run_minutes: int = 60,
) -> str | None:
    recent_active, _ = split_active_runs(runs, stuck_run_minutes, now)
    if recent_active:
        run = recent_active[0]
        age = run_age_minutes(run, now)
        age_text = "unknown age" if age is None else f"{age:.1f}m old"
        return f"workflow run {run.get('id', 'unknown')} already {run.get('status')} ({age_text})"

    for run in runs:
        if run.get("event") != "workflow_dispatch":
            continue
        created = run.get("created_at")
        if not created:
            continue
        created_at = parse_time(created)
        if heartbeat_at is not None and created_at <= heartbeat_at:
            # This dispatch belongs to an earlier stale episode that already
            # self-healed. It must not suppress recovery if the heartbeat later
            # becomes stale again.
            continue
        age = (now - created_at.astimezone(now.tzinfo)).total_seconds() / 60.0
        conclusion = run.get("conclusion")
        if conclusion == "success" and 0 <= age < cooldown_minutes:
            return f"successful recovery dispatch {run.get('id', 'unknown')} is {age:.1f}m old within {cooldown_minutes}m cooldown"
        if conclusion not in (None, "success") and 0 <= age < failure_retry_minutes:
            return f"failed recovery dispatch {run.get('id', 'unknown')} is {age:.1f}m old within {failure_retry_minutes}m failure retry delay"

    return None


def workflow_recovery_state(
    repo: str,
    workflow_path: str,
    cooldown_minutes: int,
    failure_retry_minutes: int,
    stuck_run_minutes: int,
    now: datetime,
    token: str,
    heartbeat_at: datetime | None = None,
) -> tuple[str | None, list[dict]]:
    encoded = urllib.parse.quote(workflow_path, safe="")
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{encoded}/runs?per_page=20"
    data = github_json(url, token)
    runs = data.get("workflow_runs", [])
    suppression = recovery_suppression_reason(
        runs,
        cooldown_minutes,
        failure_retry_minutes,
        now,
        heartbeat_at,
        stuck_run_minutes,
    )
    _, stuck_runs = split_active_runs(runs, stuck_run_minutes, now)
    return suppression, stuck_runs


def cancel_workflow_run(repo: str, run_id: int, token: str) -> None:
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/cancel"
    req = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "knowthegulf-recovery-watchdog",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            if response.status not in (202, 204):
                raise RuntimeError(f"workflow cancel returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        # A run can finish between the state query and the cancel request. In
        # that race GitHub returns a conflict/unprocessable response; recovery
        # should continue because the stale run no longer needs cancellation.
        if exc.code not in (409, 422):
            raise


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
        heartbeat_at = heartbeat_timestamp(heartbeat, cfg["heartbeat_field"])
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
        stuck_run = int(cfg.get("stuck_run_minutes", 60))
        try:
            suppression, stuck_runs = workflow_recovery_state(
                repo,
                workflow_path,
                cooldown,
                failure_retry,
                stuck_run,
                now,
                token,
                heartbeat_at,
            )
            if suppression:
                print(f"{lane}: stale age={age_text}; recovery suppressed because {suppression}")
                continue

            for run in stuck_runs:
                run_id = int(run["id"])
                run_age = run_age_minutes(run, now)
                run_age_text = "unknown" if run_age is None else f"{run_age:.1f}m"
                cancel_workflow_run(repo, run_id, token)
                print(
                    f"{lane}: cancelled stuck {run.get('status')} run {run_id} "
                    f"age={run_age_text} before recovery"
                )

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
