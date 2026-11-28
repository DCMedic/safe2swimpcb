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
RECOVERY_BRANCH = "main"
COMPLETED_RUN_CONCLUSIONS = {
    "success", "failure", "neutral", "cancelled", "skipped", "timed_out",
    "action_required", "stale", "startup_failure",
}


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
        # A waiting run can be paused for a protected-environment approval.
        # Do not turn an intentional human gate into an automatic cancellation.
        if run.get("_recovery_purpose") == "unknown" or run.get("status") == "waiting" or age is None or age < stuck_run_minutes:
            recent.append(run)
        else:
            stuck.append(run)
    return recent, stuck


def classify_run_purposes(runs: list[dict], run_titles: dict | None) -> list[dict]:
    """Exclude known previews; never auto-cancel an ambiguous mixed-mode run."""
    if run_titles is None:
        return runs
    production = run_titles.get("production")
    preview = run_titles.get("preview")
    if not production or not preview or production == preview:
        raise RuntimeError("mixed-mode workflow requires distinct production and preview run titles")
    result = []
    for run in runs:
        title = run.get("display_title")
        if title == preview:
            continue
        result.append({**run, "_recovery_purpose": "production" if title == production else "unknown"})
    return result


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
    cancelled_by_watchdog: set[int] | None = None,
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
        if (run.get("id") in (cancelled_by_watchdog or set())
                and run.get("status") == "completed" and run.get("conclusion") == "cancelled"):
            # Ignore only this evaluation's confirmed cancellations. A racing
            # successful run, unrelated cancellation, or new attempt still counts.
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
        if run.get("_recovery_purpose") == "unknown":
            delay = cooldown_minutes if conclusion == "success" else failure_retry_minutes
            if conclusion is not None and 0 <= age < delay:
                return f"unclassified legacy dispatch {run.get('id', 'unknown')} is {age:.1f}m old within conservative {delay}m delay"
            continue
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
    run_titles: dict | None = None,
    cancelled_by_watchdog: set[int] | None = None,
) -> tuple[str | None, list[dict]]:
    encoded = urllib.parse.quote(Path(workflow_path).name, safe="")
    workflow_url = f"https://api.github.com/repos/{repo}/actions/workflows/{encoded}"
    workflow = github_json(workflow_url, token)
    # Respect intentional pauses. Recovery never enables a disabled workflow.
    if workflow.get("state") != "active":
        return f"workflow is not active ({workflow.get('state', 'unknown')})", []
    if workflow.get("path") != workflow_path or not isinstance(workflow.get("id"), int):
        raise RuntimeError("workflow metadata does not match configured path")

    def scoped_runs(status: str | None = None) -> list[dict]:
        runs = []
        for page in range(1, 11):
            query = {"branch": RECOVERY_BRANCH, "per_page": 100, "page": page}
            if status:
                query["status"] = status
            data = github_json(f"{workflow_url}/runs?{urllib.parse.urlencode(query)}", token)
            batch = data.get("workflow_runs")
            if not isinstance(batch, list):
                raise RuntimeError("workflow run list is missing or malformed")
            for run in batch:
                if not isinstance(run, dict) or not all((
                    run.get("head_branch"), run.get("event"), run.get("workflow_id"),
                    run.get("id"), (run.get("head_repository") or {}).get("full_name"),
                )):
                    raise RuntimeError("workflow run scope is missing or malformed")
                if run.get("status") not in ACTIVE_RUN_STATES | {"completed"}:
                    raise RuntimeError("workflow run status is missing or unsupported")
                if not run.get("created_at"):
                    raise RuntimeError("workflow run creation time is missing")
                parse_time(str(run["created_at"]))
                if run["status"] == "completed" and run.get("conclusion") not in COMPLETED_RUN_CONCLUSIONS:
                    raise RuntimeError("completed workflow run conclusion is missing or unsupported")
            # Defense in depth: never cancel or suppress based on a PR, fork,
            # or development-branch run, even if the API filter is ignored.
            runs.extend(run for run in batch if (
                run.get("head_branch") == RECOVERY_BRANCH
                and run.get("head_repository", {}).get("full_name") == repo
                and run.get("event") in {"push", "schedule", "workflow_dispatch"}
                and run.get("workflow_id") == workflow.get("id")
            ))
            if not status or len(batch) < 100:
                return runs
        raise RuntimeError("active workflow runs exceed pagination safety limit")

    runs = scoped_runs()
    # The recent-run page can hide a long-stuck run behind completed runs.
    by_id = {run["id"]: run for run in runs}
    for status in sorted(ACTIVE_RUN_STATES):
        by_id.update({run["id"]: run for run in scoped_runs(status)})
    runs = classify_run_purposes(list(by_id.values()), run_titles)
    suppression = recovery_suppression_reason(
        runs,
        cooldown_minutes,
        failure_retry_minutes,
        now,
        heartbeat_at,
        stuck_run_minutes,
        cancelled_by_watchdog,
    )
    _, stuck_runs = split_active_runs(runs, stuck_run_minutes, now)
    return suppression, stuck_runs


def cancel_workflow_run(repo: str, run_id: int, token: str) -> bool:
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
        # A conflict may be a finished run, but is not evidence of completion.
        if exc.code not in (409, 422):
            raise
    current = github_json(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", token)
    return current.get("status") == "completed"


def dispatch_workflow(repo: str, workflow_path: str, inputs: dict, token: str) -> None:
    encoded = urllib.parse.quote(Path(workflow_path).name, safe="")
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{encoded}/dispatches"
    body = json.dumps({"ref": RECOVERY_BRANCH, "inputs": inputs}).encode("utf-8")
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


def effective_overdue_minutes(cfg: dict) -> int:
    """Return the earliest safe recovery threshold for a lane.

    expected_cadence_minutes + schedule_grace_minutes lets the watchdog act as
    scheduler-of-last-resort when GitHub drops or delays a cron event. The
    existing overdue_minutes remains a hard upper bound and backward-compatible
    fallback for lanes without explicit cadence metadata.
    """
    overdue = int(cfg["overdue_minutes"])
    cadence = cfg.get("expected_cadence_minutes")
    if cadence is None:
        return overdue
    grace = int(cfg.get("schedule_grace_minutes", 0))
    return min(overdue, int(cadence) + grace)


def decision_telemetry(lane: str, heartbeat_at: datetime | None, age: float | None, threshold: int, action: str, detail: str = "") -> None:
    payload = {
        "lane": lane,
        "heartbeat_at": heartbeat_at.isoformat() if heartbeat_at else None,
        "heartbeat_age_minutes": round(age, 1) if age is not None else None,
        "recovery_threshold_minutes": threshold,
        "action": action,
        "detail": detail,
    }
    print("RECOVERY_TELEMETRY " + json.dumps(payload, sort_keys=True))


def evaluate(policy_path: Path, now: datetime, repo: str, token: str | None, dry_run: bool) -> int:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if repo != policy.get("repository"):
        print("Repository must match the recovery policy; no actions taken", file=sys.stderr)
        return 1
    failures = 0

    for lane, cfg in policy["lanes"].items():
        if cfg.get("enabled", True) is not True:
            print(f"{lane}: disabled in recovery policy")
            decision_telemetry(lane, None, None, int(cfg["overdue_minutes"]), "disabled")
            continue
        if not in_active_window(now, cfg.get("active_window")):
            print(f"{lane}: outside active window")
            decision_telemetry(lane, None, None, int(cfg["overdue_minutes"]), "outside_active_window")
            continue

        heartbeat = ROOT / cfg["heartbeat_path"]
        heartbeat_at = heartbeat_timestamp(heartbeat, cfg["heartbeat_field"])
        age = heartbeat_age_minutes(heartbeat, cfg["heartbeat_field"], now)
        overdue = effective_overdue_minutes(cfg)
        if age is not None and age <= overdue:
            print(f"{lane}: healthy age={age:.1f}m threshold={overdue}m")
            decision_telemetry(lane, heartbeat_at, age, overdue, "healthy")
            continue

        age_text = "unreadable" if age is None else f"{age:.1f}m"
        workflow_path = cfg.get("workflow_path")
        if not workflow_path:
            failures += 1
            print(f"{lane}: stale age={age_text}; no workflow_path configured", file=sys.stderr)
            continue

        if dry_run:
            print(f"{lane}: stale age={age_text}; recovery candidate {workflow_path}; live workflow checks not performed")
            decision_telemetry(lane, heartbeat_at, age, overdue, "recovery_candidate", workflow_path)
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
                cfg.get("run_titles"),
            )
            if suppression:
                print(f"{lane}: stale age={age_text}; recovery suppressed because {suppression}")
                decision_telemetry(lane, heartbeat_at, age, overdue, "suppressed", suppression)
                continue

            cancellation_pending = False
            cancelled_by_watchdog = set()
            for run in stuck_runs:
                run_id = int(run["id"])
                run_age = run_age_minutes(run, now)
                run_age_text = "unknown" if run_age is None else f"{run_age:.1f}m"
                completed = cancel_workflow_run(repo, run_id, token)
                cancellation_pending = cancellation_pending or not completed
                if completed:
                    cancelled_by_watchdog.add(run_id)
                print(
                    f"{lane}: cancellation requested for stuck {run.get('status')} run {run_id} "
                    f"age={run_age_text}; completed={completed}"
                )

            if cancellation_pending:
                decision_telemetry(lane, heartbeat_at, age, overdue, "cancellation_pending", "dispatch deferred until a later evaluation")
                continue

            # Re-read after cancellation and immediately before dispatch so a
            # newer normal run or a newly disabled workflow prevents recovery.
            suppression, still_active = workflow_recovery_state(
                repo, workflow_path, cooldown, failure_retry, stuck_run, now, token, heartbeat_at,
                cfg.get("run_titles"), cancelled_by_watchdog,
            )
            if suppression or still_active:
                decision_telemetry(lane, heartbeat_at, age, overdue, "suppressed", suppression or "active runs remain")
                continue

            dispatch_workflow(repo, workflow_path, cfg.get("dispatch_inputs", {}), token)
            print(f"{lane}: stale age={age_text}; dispatched {workflow_path}")
            decision_telemetry(lane, heartbeat_at, age, overdue, "dispatched", workflow_path)
        except Exception as exc:
            failures += 1
            print(f"{lane}: recovery dispatch failed: {type(exc).__name__}: {exc}", file=sys.stderr)

    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY", "DCMedic/safe2swimpcb"))
    parser.add_argument("--now", help="ISO-8601 override for tests/manual validation")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Offline, read-only evaluation (the default)")
    mode.add_argument("--apply", action="store_true", help="Allow cancellation and dispatch of production workflows")
    args = parser.parse_args()

    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    token = os.getenv("GITHUB_TOKEN")
    if args.apply and os.getenv("GITHUB_REF", f"refs/heads/{RECOVERY_BRANCH}") != f"refs/heads/{RECOVERY_BRANCH}":
        parser.error("--apply is only allowed from the main ref in GitHub Actions")
    return evaluate(args.policy, now, args.repo, token, not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
