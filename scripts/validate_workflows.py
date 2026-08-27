#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
POLICY = ROOT / ".github" / "recovery" / "policy.json"
CORE_RESEARCH = {
    "daily-refresh.yml",
    "backfill-nws-history.yml",
    "history-enrichment.yml",
}


def validate() -> list[str]:
    errors: list[str] = []
    policy = json.loads(POLICY.read_text(encoding="utf-8"))

    for lane, cfg in policy["lanes"].items():
        workflow = ROOT / cfg["workflow_path"]
        trigger = ROOT / cfg["trigger_path"]
        if not workflow.exists():
            errors.append(f"{lane}: configured workflow does not exist: {cfg['workflow_path']}")
            continue
        if not trigger.exists():
            errors.append(f"{lane}: configured trigger does not exist: {cfg['trigger_path']}")
        text = workflow.read_text(encoding="utf-8")
        if "workflow_dispatch:" not in text:
            errors.append(f"{lane}: workflow lacks workflow_dispatch recovery entry point")
        if cfg["trigger_path"] not in text:
            errors.append(f"{lane}: workflow does not listen for configured trigger path")

    # Overnight-paused lanes must allow their first normal schedule to run before
    # recovery becomes active, otherwise every morning begins with a false recovery.
    starts = {
        lane: cfg.get("active_window", {}).get("start_hour")
        for lane, cfg in policy["lanes"].items()
    }
    minimum_starts = {"pcb": 7, "western": 8, "x": 9}
    for lane, minimum in minimum_starts.items():
        if starts.get(lane) is None or int(starts[lane]) < minimum:
            errors.append(f"{lane}: active recovery window starts before normal morning schedule grace")

    recovery = (WORKFLOWS / "recover-stale-lanes.yml").read_text(encoding="utf-8")
    if "cron: '5,15,25,35,45,55 * * * *'" not in recovery:
        errors.append("recovery controller cron is not on the deconflicted 10-minute cadence")
    for noisy in ("Validate Know the Gulf site health", "Deploy Know the Gulf to GitHub Pages"):
        if re.search(r"workflow_run:[\s\S]*?workflows:[\s\S]*?- " + re.escape(noisy), recovery):
            errors.append(f"recovery controller redundantly subscribes to {noisy}")
    if "actions: write" not in recovery or "contents: read" not in recovery:
        errors.append("recovery controller permissions are not least-privilege read/actions-write")

    research_groups: dict[str, str] = {}
    for path in WORKFLOWS.glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        for action in ("actions/checkout", "actions/setup-python"):
            for match in re.findall(re.escape(action) + r"@v(\d+)", text):
                if int(match) < 6:
                    errors.append(f"{path.name}: {action}@v{match} should use v6")
        if path.name in CORE_RESEARCH:
            if "timeout-minutes:" not in text:
                errors.append(f"{path.name}: core research workflow lacks a job timeout")
            if re.search(r"persist_paths\.sh[^\n]*\sdata/\s*$", text, re.M):
                errors.append(f"{path.name}: broad data/ persistence violates explicit ownership")

            group_match = re.search(r"(?m)^\s*group:\s*([^\n]+)$", text)
            if not group_match:
                errors.append(f"{path.name}: core research workflow lacks a concurrency group")
            else:
                group = group_match.group(1).strip()
                if group in research_groups:
                    errors.append(
                        f"{path.name}: shares concurrency group {group} with {research_groups[group]}; "
                        "GitHub may replace pending runs in a shared group"
                    )
                research_groups[group] = path.name

            push_match = re.search(r"(?ms)^\s*push:\s*\n\s*branches:.*?\n\s*paths:\s*\n(.*?)(?=^\s*(?:schedule|workflow_dispatch|permissions|concurrency|jobs):)", text)
            if push_match:
                push_paths = re.findall(r"['\"]([^'\"]+)['\"]", push_match.group(1))
                unexpected = [value for value in push_paths if not value.startswith(".github/recovery/")]
                if unexpected:
                    errors.append(
                        f"{path.name}: production research push trigger includes non-recovery paths: "
                        + ", ".join(unexpected)
                    )

    nws_backfill = (WORKFLOWS / "backfill-nws-history.yml").read_text(encoding="utf-8")
    if "cron: '41 3 * * 1'" not in nws_backfill:
        errors.append("NWS backfill schedule is not sufficiently separated from the daily research window")

    site_health = (WORKFLOWS / "site-health.yml").read_text(encoding="utf-8")
    if ".github/recovery/**" not in site_health:
        errors.append("site-health workflow does not validate recovery-policy changes")
    if "python scripts/validate_workflows.py" not in site_health:
        errors.append("site-health workflow does not enforce workflow architecture invariants")

    x_workflow = (WORKFLOWS / "x-production-publisher.yml").read_text(encoding="utf-8")
    if "scripts/mark_x_publisher_failure.py" not in x_workflow:
        errors.append("X workflow lacks fail-closed pre-publisher health recording")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("WORKFLOW ARCHITECTURE VALIDATION FAILED")
        for error in errors:
            print(f" - {error}")
        return 1
    print("workflow architecture validation ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
