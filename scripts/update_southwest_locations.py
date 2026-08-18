#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TZ = ZoneInfo("America/New_York")
VISIT_BEACHES = "https://visitbeaches.org/"
MANATEE_CONDITIONS = "https://www.mymanatee.org/services-and-amenities/service-listing/service-details/check-beach-conditions"
SARASOTA_LIFEGUARDS = "https://www.scgov.net/government/emergency-services/lifeguard-operations"
LEE_WATER = "https://www.leefl.gov/naturalresources/WaterQuality/WaterQualityStatus"
COLLIER_RED_TIDE = "https://www.collier.gov/County-Development/Transportation-Management/Pollution-Control/Red-Tide/Red-Tide-Status"

LOCATIONS = {
    "anna-maria-island": {
        "name": "Anna Maria Island",
        "county": "Manatee County",
        "beaches": ["Manatee Public Beach", "Coquina Beach", "Cortez Beach"],
        "source_url": "https://safebeachday.com/county/manatee-county/",
        "official_url": MANATEE_CONDITIONS,
        "authority": "Manatee County Beach Patrol",
        "source_system": "Safe Beach Day / Manatee County",
        "flag_expected": True,
        "update_note": "Manatee County says guarded-beach conditions are updated daily at 10:00 a.m. and 3:00 p.m.; physical tower flags override online information.",
    },
    "siesta-key": {
        "name": "Siesta Key",
        "county": "Sarasota County",
        "beaches": ["Siesta Beach"],
        "source_url": VISIT_BEACHES,
        "official_url": SARASOTA_LIFEGUARDS,
        "authority": "Sarasota County Fire Department Lifeguard Operations",
        "source_system": "Mote Beach Conditions Reporting System / VisitBeaches",
        "flag_expected": True,
        "update_note": "Sarasota County says VisitBeaches is updated twice daily by lifeguards and Mote Marine staff and is updated when flags change.",
    },
    "venice": {
        "name": "Venice / Nokomis",
        "county": "Sarasota County",
        "beaches": ["Venice Beach", "Nokomis Beach", "North Jetty", "Manasota Beach"],
        "source_url": VISIT_BEACHES,
        "official_url": SARASOTA_LIFEGUARDS,
        "authority": "Sarasota County Fire Department Lifeguard Operations",
        "source_system": "Mote Beach Conditions Reporting System / VisitBeaches",
        "flag_expected": True,
        "update_note": "Sarasota County says VisitBeaches is updated twice daily by lifeguards and Mote Marine staff and is updated when flags change.",
    },
    "sanibel": {
        "name": "Sanibel / Captiva",
        "county": "Lee County",
        "beaches": ["Sanibel", "Captiva"],
        "source_url": VISIT_BEACHES,
        "official_url": LEE_WATER,
        "authority": "Lee County Natural Resources / Mote Marine Laboratory",
        "source_system": "Mote Beach Conditions Reporting System / VisitBeaches",
        "flag_expected": False,
        "update_note": "Lee County directs the public to Mote Marine Laboratory for current beach conditions. Know the Gulf does not manufacture a flag where the upstream report does not explicitly publish one.",
    },
    "fort-myers-beach": {
        "name": "Fort Myers Beach",
        "county": "Lee County",
        "beaches": ["Fort Myers Beach"],
        "source_url": VISIT_BEACHES,
        "official_url": LEE_WATER,
        "authority": "Lee County Natural Resources / Mote Marine Laboratory",
        "source_system": "Mote Beach Conditions Reporting System / VisitBeaches",
        "flag_expected": False,
        "update_note": "Lee County directs the public to Mote Marine Laboratory for current beach conditions. Know the Gulf keeps conditions distinct from official flag evidence.",
    },
    "naples": {
        "name": "Naples",
        "county": "Collier County",
        "beaches": ["Vanderbilt Beach", "Seagate Beach", "Naples Pier", "Barefoot Beach"],
        "source_url": VISIT_BEACHES,
        "official_url": COLLIER_RED_TIDE,
        "authority": "Collier County Pollution Control / Mote Marine Laboratory",
        "source_system": "Mote Beach Conditions Reporting System / VisitBeaches",
        "flag_expected": False,
        "update_note": "Collier County directs users to VisitBeaches for current beach conditions. Red-tide sampling is retained as separate health context, not a beach-flag substitute.",
    },
    "marco-island": {
        "name": "Marco Island",
        "county": "Collier County",
        "beaches": ["South Marco Beach"],
        "source_url": VISIT_BEACHES,
        "official_url": COLLIER_RED_TIDE,
        "authority": "Collier County Pollution Control / Mote Marine Laboratory",
        "source_system": "Mote Beach Conditions Reporting System / VisitBeaches",
        "flag_expected": False,
        "update_note": "Collier County directs users to VisitBeaches for current beach conditions. Know the Gulf presents explicit observations only and does not derive swimming flags from red-tide or weather data.",
    },
}

FLAG_SEVERITY = {"Green": 1, "Yellow": 2, "Red": 3, "Double Red": 4}


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "KnowTheGulf/1.0 (+https://knowthegulf.com)"})
    return s


def normalize_flag(value: object) -> str | None:
    text = re.sub(r"[^a-z ]+", " ", str(value or "").lower()).strip()
    if re.search(r"\bdouble\s+red\b|\btwo\s+red\b|\bwater\s+closed\b", text):
        return "Double Red"
    if re.search(r"\bred\s+flag\b|\bhigh\s+hazard\b", text):
        return "Red"
    if re.search(r"\byellow\s+flag\b|\bmedium\s+hazard\b", text):
        return "Yellow"
    if re.search(r"\bgreen\s+flag\b|\blow\s+hazard\b", text):
        return "Green"
    return None


def iter_json_values(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            yield p, v
            yield from iter_json_values(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_json_values(v, f"{path}[{i}]")


def extract_explicit_flag(html: str, beach_names: list[str]) -> tuple[str | None, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    # Prefer structured state when a client-rendered site serializes it into the page.
    for script in soup.find_all("script"):
        raw = script.string or script.get_text(" ")
        raw = raw.strip()
        if not raw or raw[0] not in "[{":
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        flat = list(iter_json_values(obj))
        beach_hit = any(any(name.lower() in str(v).lower() for name in beach_names) for _, v in flat)
        if not beach_hit:
            continue
        for path, value in flat:
            if any(token in path.lower() for token in ("flag", "hazard", "swim", "condition")):
                flag = normalize_flag(value)
                if flag:
                    return flag, f"structured:{path}"

    text = " ".join(soup.stripped_strings)
    # Only accept an explicit flag/hazard phrase near a named target beach.
    for beach in beach_names:
        m = re.search(rf"{re.escape(beach)}(.{{0,500}})", text, re.I)
        if not m:
            continue
        flag = normalize_flag(m.group(1))
        if flag:
            return flag, f"page-text-near:{beach}"
    return None, None


def collect(slug: str, cfg: dict) -> dict:
    now = datetime.now(TZ)
    source_ok = False
    http_status = None
    flag = None
    evidence = None
    error = None
    try:
        r = session().get(cfg["source_url"], timeout=30)
        http_status = r.status_code
        r.raise_for_status()
        source_ok = True
        flag, evidence = extract_explicit_flag(r.text, cfg["beaches"])
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    if flag:
        status = "explicit_flag_verified"
        label = flag
        provenance = "officially_directed_public_source"
    elif source_ok:
        status = "official_conditions_source_reachable"
        label = "Open official current conditions"
        provenance = "officially_directed_conditions_source"
    else:
        status = "official_conditions_source_unavailable"
        label = "Official current conditions unavailable"
        provenance = "unavailable"

    return {
        "location": cfg["name"],
        "county": cfg["county"],
        "beaches": cfg["beaches"],
        "flag": flag,
        "label": label,
        "severity": FLAG_SEVERITY.get(flag),
        "status": status,
        "provenance_tier": provenance,
        "last_verified_at": now.isoformat(),
        "source_name": cfg["source_system"],
        "source_url": cfg["source_url"],
        "official_authority": cfg["authority"],
        "official_authority_url": cfg["official_url"],
        "source_reachable": source_ok,
        "source_http_status": http_status,
        "explicit_flag_evidence": evidence,
        "flag_expected_from_source": cfg["flag_expected"],
        "stale_after_hours": 18,
        "update_note": cfg["update_note"],
        "error": error,
        "safety_note": "Only an explicit upstream flag is displayed as a flag. Know the Gulf never converts rip-current risk, weather, surf, red-tide status, water quality, or a generic hazard score into a beach flag. Physical posted flags and lifeguard instructions control.",
    }


def main() -> None:
    for slug, cfg in LOCATIONS.items():
        payload = collect(slug, cfg)
        out = DATA / slug
        out.mkdir(parents=True, exist_ok=True)
        (out / "current_status.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        # Keep the same filename contract used by existing location pages.
        (out / "current_flag.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(slug, payload["status"], payload["flag"] or "no-explicit-flag")


if __name__ == "__main__":
    main()
