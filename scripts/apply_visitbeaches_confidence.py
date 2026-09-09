#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
VB = DATA / "visitbeaches"

LOCATIONS = [
    "pcb", "destin", "okaloosa-island", "navarre-beach", "pensacola-beach",
    "south-walton", "cape-san-blas", "st-joe-beach", "franklin-county",
    "anna-maria-island", "siesta-key", "venice", "sanibel",
    "fort-myers-beach", "naples", "marco-island",
]

CURRENT_PATHS = {
    "pcb": DATA / "current_flag.json",
    "franklin-county": DATA / "franklin-county" / "current_flag.json",
}

SEVERITY = {"Green": 1, "Yellow": 2, "Red": 3, "Single Red": 3, "Double Red": 4}


def current_path(slug: str) -> Path:
    return CURRENT_PATHS.get(slug, DATA / slug / "current_flag.json")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_fresh(record: dict[str, Any], now: datetime) -> bool:
    stamp = parse_time(record.get("last_verified_at"))
    if not stamp:
        return False
    try:
        hours = float(record.get("stale_after_hours", 24))
    except (TypeError, ValueError):
        hours = 24
    age = (now - stamp).total_seconds() / 3600
    return -0.25 <= age <= max(0.0, hours)


def newest_vb_time(vb: dict[str, Any]) -> str | None:
    report = vb.get("newest_flag_report") or {}
    return report.get("created_at") or vb.get("newest_report_at")


def confidence(existing: dict[str, Any], vb: dict[str, Any], now: datetime) -> tuple[str, str]:
    primary = existing.get("flag")
    purple = bool(existing.get("purple"))
    vb_flag = vb.get("flag")
    vb_purple = bool(vb.get("purple"))
    if vb.get("flag_conflict"):
        return "conflict", "VisitBeaches has conflicting fresh Ambassador flag observations"
    if not vb_flag:
        return "primary_only", "No fresh explicit VisitBeaches Ambassador flag is available"
    if primary and is_fresh(existing, now):
        if primary == vb_flag and purple == vb_purple:
            return "corroborated", "Primary current-status source agrees with fresh VisitBeaches Ambassador observation"
        if primary == vb_flag:
            return "partial_corroboration", "Primary warning flag agrees; Purple overlay differs between sources"
        return "source_disagreement", "Fresh primary source and fresh VisitBeaches Ambassador flag disagree"
    if primary:
        return "visitbeaches_newer_than_stale_primary", "Primary observation is stale and a fresh consistent VisitBeaches Ambassador flag is available"
    return "visitbeaches_gap_fill", "No primary flag is available and a fresh consistent VisitBeaches Ambassador flag is available"


def apply(slug: str, *, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    path = current_path(slug)
    existing = read_json(path)
    vb = read_json(VB / f"{slug}.json")
    if not existing or not vb:
        return "missing-input"

    state, reason = confidence(existing, vb, now)
    vb_flag = vb.get("flag")
    vb_purple = bool(vb.get("purple"))
    evidence = {
        "source": "Mote Marine Laboratory Beach Conditions Reporting System / VisitBeaches",
        "source_url": "https://visitbeaches.org/map",
        "source_data_url": "https://api.visitbeaches.org/graphql",
        "source_class": "Beach Ambassador Reports only; Community Reports excluded",
        "state": state,
        "reason": reason,
        "flag": vb_flag,
        "purple": vb_purple,
        "report_at": newest_vb_time(vb),
        "fresh_observation_count": vb.get("fresh_observation_count", 0),
        "matched_beaches": [
            {"id": b.get("id"), "name": b.get("name"), "location": b.get("location")}
            for b in vb.get("matched_beaches") or []
        ],
        "flag_conflict": bool(vb.get("flag_conflict")),
        "fresh_distinct_flags": vb.get("fresh_distinct_flags") or [],
        "checked_at": vb.get("checked_at"),
    }
    existing["visitbeaches_evidence"] = evidence
    existing["multi_source_confidence"] = state

    # Gap fill is permitted only when no fresh primary warning flag exists and the
    # Ambassador observations are fresh, explicit, and internally consistent.
    promote = state in {"visitbeaches_gap_fill", "visitbeaches_newer_than_stale_primary"} and vb_flag and not vb.get("flag_conflict")
    if promote:
        existing["flag"] = vb_flag
        existing["primary_flag"] = vb_flag
        existing["purple"] = vb_purple
        existing["label"] = vb_flag + (" + Purple" if vb_purple else "")
        existing["severity"] = SEVERITY.get(vb_flag)
        existing["last_verified_at"] = newest_vb_time(vb) or vb.get("checked_at")
        existing["source_check_status"] = "verified"
        existing["status"] = "explicit_flag_verified"
        existing["provenance_tier"] = "primary_visitbeaches_ambassador_gap_fill"
        existing["source_name"] = "Mote Beach Conditions Reporting System / VisitBeaches"
        existing["source_url"] = "https://visitbeaches.org/map"
        existing["source_data_url"] = "https://api.visitbeaches.org/graphql"
        existing["explicit_flag_evidence"] = f"Fresh consistent VisitBeaches Beach Ambassador report(s): {vb_flag}"
        existing["stale_after_hours"] = max(float(existing.get("stale_after_hours") or 0), 24.0)
        existing["multi_source_confidence"] = "visitbeaches_gap_filled"
        existing["visitbeaches_evidence"]["publication_action"] = "filled_missing_or_stale_primary"
    else:
        existing["visitbeaches_evidence"]["publication_action"] = "corroboration_only"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return existing["multi_source_confidence"]


def main() -> None:
    for slug in LOCATIONS:
        print(slug, apply(slug))


if __name__ == "__main__":
    main()
