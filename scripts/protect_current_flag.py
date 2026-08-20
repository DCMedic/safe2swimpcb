#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from .collector_resilience import fresh_cached_payload, mark_cached_official
except ImportError:
    from collector_resilience import fresh_cached_payload, mark_cached_official

CENTRAL = ZoneInfo("America/Chicago")
DIAGNOSTIC_KEYS = (
    "source_reachable",
    "source_http_status",
    "adapter_diagnostics",
    "explicit_flag_evidence",
    "status",
)


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def should_fallback(current: dict, mode: str) -> bool:
    if current.get("flag") or current.get("primary_flag"):
        return False
    if mode == "missing-flag":
        return True
    status = str(current.get("status") or "").lower()
    tier = str(current.get("provenance_tier") or "").lower()
    return (
        current.get("source_reachable") is False
        or tier == "unavailable"
        or "source_unavailable" in status
        or "conditions_source_unavailable" in status
    )


def protect(
    previous_path: Path,
    current_path: Path,
    *,
    max_age_hours: float,
    mode: str,
    now: datetime | None = None,
) -> bool:
    now = now or datetime.now(CENTRAL)
    current = load_json(current_path)
    if not current or not should_fallback(current, mode):
        return False

    previous, age = fresh_cached_payload(previous_path, now, max_age_hours=max_age_hours)
    if not previous:
        return False

    reason = (
        current.get("source_error")
        or current.get("stale_reason")
        or current.get("status")
        or "new collector output did not contain a verifiable explicit flag"
    )
    cached = mark_cached_official(
        previous,
        now,
        str(reason),
        method="Last-known verified official flag retained by collector regression guard after degraded live-source output",
    )
    cached["cache_age_hours"] = round(age, 2) if age is not None else None
    cached["fallback_trigger"] = mode
    cached["guarded_current_output"] = True
    for key in DIAGNOSTIC_KEYS:
        if key in current:
            cached[key] = current[key]
    if "update_note" in current:
        cached["update_note"] = current["update_note"]
    current_path.write_text(json.dumps(cached, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Prevent a transient collector miss from erasing a still-fresh verified official flag.")
    parser.add_argument("--previous", required=True, type=Path)
    parser.add_argument("--current", required=True, type=Path)
    parser.add_argument("--max-age-hours", required=True, type=float)
    parser.add_argument("--mode", choices=("unavailable", "missing-flag"), default="unavailable")
    args = parser.parse_args()

    changed = protect(
        args.previous,
        args.current,
        max_age_hours=args.max_age_hours,
        mode=args.mode,
    )
    print(
        "collector regression guard",
        "retained cached official observation" if changed else "no fallback required",
        args.current,
    )


if __name__ == "__main__":
    main()
