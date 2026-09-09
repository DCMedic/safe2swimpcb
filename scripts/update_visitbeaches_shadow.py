#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from visitbeaches_graphql import collect_location

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "visitbeaches"

LOCATIONS: dict[str, list[str]] = {
    "pcb": ["Panama City Beach", "Russell-Fields Pier", "M.B. Miller County Pier"],
    "destin": ["Destin", "Henderson Beach State Park"],
    "okaloosa-island": ["Okaloosa Island", "John Beasley Park"],
    "navarre-beach": ["Navarre Beach"],
    "pensacola-beach": ["Pensacola Beach"],
    "south-walton": ["Miramar Beach", "Grayton Beach", "Seaside", "Santa Rosa Beach"],
    "cape-san-blas": ["Cape San Blas", "St. Joseph Peninsula State Park"],
    "st-joe-beach": ["St. Joe Beach"],
    "franklin-county": ["St. George Island", "St George Island"],
    "anna-maria-island": ["Manatee Public Beach", "Coquina Beach", "Cortez Beach"],
    "siesta-key": ["Siesta Beach"],
    "venice": ["Venice Beach", "Nokomis Beach", "North Jetty", "Manasota Beach"],
    "sanibel": ["Sanibel", "Captiva"],
    "fort-myers-beach": ["Fort Myers Beach"],
    "naples": ["Vanderbilt Beach", "Seagate Beach", "Naples Pier", "Barefoot Beach"],
    "marco-island": ["South Marco Beach", "Marco Island"],
}

CURRENT_PATHS = {
    "pcb": DATA / "current_flag.json",
    "franklin-county": DATA / "franklin-county" / "current_flag.json",
}


def current_path(slug: str) -> Path:
    return CURRENT_PATHS.get(slug, DATA / slug / "current_flag.json")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def compare(existing: dict, shadow: dict) -> dict:
    current_flag = existing.get("flag")
    current_purple = bool(existing.get("purple"))
    vb_flag = shadow.get("flag")
    vb_purple = bool(shadow.get("purple"))
    if shadow.get("flag_conflict"):
        state = "visitbeaches_internal_conflict"
    elif vb_flag is None:
        state = "no_fresh_visitbeaches_flag"
    elif current_flag is None:
        state = "visitbeaches_fills_current_gap"
    elif current_flag == vb_flag and current_purple == vb_purple:
        state = "agree"
    elif current_flag == vb_flag:
        state = "primary_flag_agrees_overlay_differs"
    else:
        state = "flag_disagreement"
    return {
        "state": state,
        "knowthegulf_flag": current_flag,
        "knowthegulf_purple": current_purple,
        "knowthegulf_last_verified_at": existing.get("last_verified_at"),
        "visitbeaches_flag": vb_flag,
        "visitbeaches_purple": vb_purple,
        "visitbeaches_newest_report_at": shadow.get("newest_report_at"),
        "visitbeaches_fresh_observation_count": shadow.get("fresh_observation_count"),
        "visitbeaches_flag_conflict": shadow.get("flag_conflict"),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "mode": "shadow_only",
        "publication_effect": "none",
        "source": "Mote Marine Laboratory Beach Conditions Reporting System / VisitBeaches",
        "source_class": "Beach Ambassador Reports only; Community Reports excluded",
        "locations": {},
    }

    for slug, aliases in LOCATIONS.items():
        try:
            shadow = collect_location(aliases, freshness_hours=24)
            error = None
        except Exception as exc:
            shadow = {
                "source": "Mote Marine Laboratory Beach Conditions Reporting System / VisitBeaches",
                "source_url": "https://visitbeaches.org/map",
                "source_data_url": "https://api.visitbeaches.org/graphql",
                "aliases": aliases,
                "flag": None,
                "purple": False,
                "flag_conflict": False,
                "observations": [],
                "error": f"{type(exc).__name__}: {exc}",
            }
            error = shadow["error"]

        existing = read_json(current_path(slug))
        shadow["knowthegulf_comparison"] = compare(existing, shadow)
        shadow["shadow_mode"] = True
        shadow["publication_effect"] = "none"
        shadow["policy_note"] = "VisitBeaches Ambassador data is collected for comparison and coverage analysis. It does not override KnowTheGulf public current-status decisions in shadow mode. Community Reports are never used as authoritative warning-flag evidence."
        (OUT / f"{slug}.json").write_text(json.dumps(shadow, indent=2) + "\n", encoding="utf-8")

        summary["locations"][slug] = {
            "matched_beaches": len(shadow.get("matched_beaches") or []),
            "fresh_observations": shadow.get("fresh_observation_count", 0),
            "visitbeaches_flag": shadow.get("flag"),
            "visitbeaches_purple": shadow.get("purple"),
            "flag_conflict": shadow.get("flag_conflict"),
            "comparison": shadow["knowthegulf_comparison"]["state"],
            "error": error,
        }
        print(slug, summary["locations"][slug])

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
