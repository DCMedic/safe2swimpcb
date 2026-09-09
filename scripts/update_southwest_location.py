#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from update_southwest_locations import DATA, FLAG_SEVERITY, LOCATIONS, collect
from visitbeaches_graphql import collect_location


def visitbeaches_payload(slug: str, cfg: dict) -> dict:
    vb = collect_location(cfg["beaches"], freshness_hours=24)
    newest_flag_report = vb.get("newest_flag_report") or {}
    fresh_flag = vb.get("flag")
    conflict = bool(vb.get("flag_conflict"))

    if conflict:
        flag = None
        purple = False
        label = "Conflicting fresh Beach Ambassador flag reports"
        status = "visitbeaches_ambassador_conflict"
        provenance = "primary_observational_conflict"
        verified_at = vb.get("newest_report_at")
    elif fresh_flag:
        flag = fresh_flag
        purple = bool(vb.get("purple"))
        label = f"{flag}{' + Purple' if purple else ''}"
        status = "explicit_flag_verified"
        provenance = "primary_visitbeaches_ambassador"
        verified_at = vb.get("newest_report_at")
    elif newest_flag_report.get("flag"):
        # Preserve useful last-known information. The old report timestamp remains the
        # verification timestamp so the UI automatically renders "Last verified flag".
        flag = newest_flag_report.get("flag")
        purple = bool(newest_flag_report.get("purple"))
        label = f"{flag}{' + Purple' if purple else ''}"
        status = "visitbeaches_last_verified_flag"
        provenance = "last_verified_visitbeaches_ambassador"
        verified_at = newest_flag_report.get("created_at")
    else:
        flag = None
        purple = False
        label = "Official conditions available — no explicit flag published"
        status = "official_conditions_source_reachable"
        provenance = "primary_visitbeaches_ambassador_no_flag"
        verified_at = vb.get("newest_report_at")

    now = datetime.now(timezone.utc).isoformat()
    return {
        "location": cfg["name"],
        "county": cfg["county"],
        "beaches": cfg["beaches"],
        "flag": flag,
        "primary_flag": flag,
        "purple": purple,
        "label": label,
        "severity": FLAG_SEVERITY.get(flag),
        "status": status,
        "provenance_tier": provenance,
        "last_verified_at": verified_at or now,
        "last_checked_at": now,
        "source_check_status": "verified",
        "source_name": cfg["source_system"],
        "source_url": "https://visitbeaches.org/map",
        "source_data_url": "https://api.visitbeaches.org/graphql",
        "official_authority": cfg["authority"],
        "official_authority_url": cfg["official_url"],
        "source_reachable": True,
        "explicit_flag_evidence": (
            f"VisitBeaches Beach Ambassador report(s): {', '.join(vb.get('fresh_distinct_flags') or [])}"
            if fresh_flag or conflict else
            (f"VisitBeaches last explicit Ambassador flag report {newest_flag_report.get('report_id')}" if newest_flag_report.get("flag") else None)
        ),
        "flag_expected_from_source": cfg["flag_expected"],
        "stale_after_hours": 24,
        "update_note": cfg["update_note"],
        "visitbeaches_source_class": vb.get("source_class"),
        "visitbeaches_matched_beaches": vb.get("matched_beaches"),
        "visitbeaches_fresh_observation_count": vb.get("fresh_observation_count"),
        "visitbeaches_flag_conflict": conflict,
        "visitbeaches_fresh_distinct_flags": vb.get("fresh_distinct_flags"),
        "visitbeaches_observations": vb.get("observations"),
        "method": "Structured Mote Marine Laboratory BCRS GraphQL Beach Ambassador reports. Community Reports are excluded. A regional flag is published only when fresh explicit Ambassador flag observations agree; stale explicit reports remain visible as last verified information.",
        "safety_note": "Only an explicit Beach Ambassador warning-flag observation is displayed as a flag. Community Reports, rip-current risk, weather, surf, red-tide status, water quality, legends, and generic hazard scores are never converted into a Florida warning flag. Posted flags and lifeguard instructions control.",
    }


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in LOCATIONS:
        choices = ", ".join(sorted(LOCATIONS))
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} <slug>; choices: {choices}")

    slug = sys.argv[1]
    cfg = LOCATIONS[slug]
    if str(cfg.get("source_url", "")).rstrip("/") == "https://visitbeaches.org":
        try:
            payload = visitbeaches_payload(slug, cfg)
        except Exception as exc:
            print(f"VisitBeaches GraphQL adapter failed for {slug}: {type(exc).__name__}: {exc}; falling back to legacy source discovery", file=sys.stderr)
            payload = collect(slug, cfg)
    else:
        payload = collect(slug, cfg)

    out = DATA / slug
    out.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2) + "\n"
    (out / "current_status.json").write_text(encoded, encoding="utf-8")
    (out / "current_flag.json").write_text(encoded, encoding="utf-8")
    print(slug, payload["status"], payload["flag"] or "no-explicit-flag", payload.get("explicit_flag_evidence"))


if __name__ == "__main__":
    main()
