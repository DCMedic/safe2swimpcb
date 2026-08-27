#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TZ = ZoneInfo("America/New_York")
VISIT_BEACHES = "https://visitbeaches.org/"
BCRS_DATAFETCH = "https://datafetch.visitbeaches.org/"
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
        "update_note": "Manatee County directs the public to its daily conditions systems and uses Florida warning flags at guarded beaches; posted tower flags control.",
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
        "update_note": "Sarasota County directs visitors to VisitBeaches for lifeguard-updated beach conditions; posted flags and lifeguards control.",
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
        "update_note": "Sarasota County directs visitors to VisitBeaches for lifeguard-updated beach conditions; posted flags and lifeguards control.",
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
        "update_note": "Lee County directs the public to Mote for current beach conditions. A flag is displayed only if the upstream report explicitly supplies one.",
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
        "update_note": "Lee County directs the public to Mote for current beach conditions. A flag is displayed only if explicitly reported upstream.",
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
        "update_note": "Collier County directs users to VisitBeaches for current conditions. Red-tide or weather values are never converted into a warning flag.",
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
        "update_note": "Collier County directs users to VisitBeaches for current conditions. A flag is displayed only when explicitly reported upstream.",
    },
}

FLAG_SEVERITY = {"Green": 1, "Yellow": 2, "Red": 3, "Single Red": 3, "Double Red": 4}
TRUSTED_HOST_SUFFIXES = ("visitbeaches.org", "safebeachday.com")


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "KnowTheGulf/1.0 (+https://knowthegulf.com)",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    })
    return s


def normalize_flag(value: object) -> str | None:
    text = re.sub(r"[^a-z ]+", " ", str(value or "").lower()).strip()
    if re.search(r"\bdouble\s+red\b|\btwo\s+red\b|\bwater\s+closed\b", text):
        return "Double Red"
    if re.search(r"\bred\s+flag\b|\bhigh\s+hazard\b", text):
        return "Red"
    if re.search(r"\byellow\s+flag\b|\bmedium\s+hazard\b|\bmoderate\s+hazard\b", text):
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


def _contains_beach(obj: object, beach_names: list[str]) -> bool:
    for _, value in iter_json_values(obj):
        if isinstance(value, (dict, list)):
            continue
        text = str(value or "").lower()
        if any(name.lower() in text for name in beach_names):
            return True
    return False


def _explicit_flag_in_obj(obj: object, prefix="") -> tuple[str | None, str | None]:
    for path, value in iter_json_values(obj, prefix):
        if isinstance(value, (dict, list)):
            continue
        low_path = path.lower()
        low_value = str(value or "").lower()
        explicit = "flag" in low_path or "flag" in low_value or "water closed" in low_value
        if not explicit:
            continue
        flag = normalize_flag(value)
        if flag:
            return flag, f"json:{path}"
    return None, None


def extract_explicit_flag_from_json(obj: object, beach_names: list[str], require_beach=True) -> tuple[str | None, str | None]:
    if not require_beach:
        return _explicit_flag_in_obj(obj)
    if not _contains_beach(obj, beach_names):
        return None, None
    if isinstance(obj, list):
        for i, item in enumerate(obj):
            if _contains_beach(item, beach_names):
                flag, evidence = extract_explicit_flag_from_json(item, beach_names, require_beach=True)
                if flag:
                    suffix = evidence.removeprefix("json:") if evidence else ""
                    return flag, f"json:[{i}]{'.' if suffix and not suffix.startswith('[') else ''}{suffix}"
        return None, None
    if isinstance(obj, dict):
        direct_values = [v for v in obj.values() if not isinstance(v, (dict, list))]
        direct_text = " ".join(str(v or "").lower() for v in direct_values)
        if any(name.lower() in direct_text for name in beach_names):
            return _explicit_flag_in_obj(obj)
        for key, child in obj.items():
            if isinstance(child, (dict, list)) and _contains_beach(child, beach_names):
                flag, evidence = extract_explicit_flag_from_json(child, beach_names, require_beach=True)
                if flag:
                    suffix = evidence.removeprefix("json:") if evidence else ""
                    joiner = "" if suffix.startswith("[") else "."
                    return flag, f"json:{key}{joiner}{suffix}"
    return None, None


def extract_explicit_flag(html: str, beach_names: list[str]) -> tuple[str | None, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        raw = (script.string or script.get_text(" ") or "").strip()
        if not raw or raw[0] not in "[{":
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        flag, evidence = extract_explicit_flag_from_json(obj, beach_names)
        if flag:
            return flag, f"structured:{evidence.removeprefix('json:')}"
    text = " ".join(soup.stripped_strings)
    for beach in beach_names:
        beach_pattern = re.escape(beach)
        patterns = [
            rf"{beach_pattern}.{{0,180}}(?:current|today(?:'s)?|posted)\s+(?:beach\s+)?(?:warning\s+)?(?:flag|status)\s*[:\-]?\s*(double\s+red(?:\s+flag)?|red\s+flag|yellow\s+flag|green\s+flag|water\s+closed)",
            rf"(?:current|today(?:'s)?|posted)\s+(?:beach\s+)?(?:warning\s+)?(?:flag|status)\s+(?:for\s+)?{beach_pattern}\s*[:\-]?\s*(double\s+red(?:\s+flag)?|red\s+flag|yellow\s+flag|green\s+flag|water\s+closed)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.I)
            if not m:
                continue
            flag = normalize_flag(m.group(1))
            if flag:
                return flag, f"current-page-text:{beach}"
    return None, None


def trusted_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return any(host == suffix or host.endswith("." + suffix) for suffix in TRUSTED_HOST_SUFFIXES)


def candidate_links(html: str, base_url: str, beach_names: list[str]) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    for tag in soup.find_all(["a", "form"], limit=250):
        raw = tag.get("href") or tag.get("action")
        if not raw:
            continue
        url = urljoin(base_url, raw)
        label = " ".join(tag.stripped_strings)
        wanted = any(name.lower() in label.lower() for name in beach_names)
        path = urlparse(url).path.lower()
        apiish = any(token in path for token in ("api", "data", "report", "fetch", "condition"))
        if trusted_url(url) and (wanted or apiish) and url not in out:
            out.append(url)
    return out[:12]


def urls_from_javascript(js: str) -> list[str]:
    found = re.findall(r"https?://[^\s\"'`<>]+", js)
    out = []
    for raw in found:
        url = raw.rstrip(")]},.;")
        if trusted_url(url) and any(token in url.lower() for token in ("api", "datafetch", "report", "condition")) and url not in out:
            out.append(url)
    return out[:12]


def response_flag(r: requests.Response, beach_names: list[str], require_beach=True) -> tuple[str | None, str | None]:
    ctype = (r.headers.get("content-type") or "").lower()
    if "json" in ctype or r.text.lstrip().startswith(("{", "[")):
        try:
            obj = r.json()
        except Exception:
            obj = None
        if obj is not None:
            flag, evidence = extract_explicit_flag_from_json(obj, beach_names, require_beach=require_beach)
            if flag:
                return flag, evidence
    return extract_explicit_flag(r.text, beach_names)


def discover_client_flag(s: requests.Session, source_url: str, beach_names: list[str]) -> tuple[str | None, str | None, int | None, bool, list[str]]:
    queue = [source_url]
    if "visitbeaches.org" in source_url:
        queue.append(BCRS_DATAFETCH)
    seen: set[str] = set()
    diagnostics: list[str] = []
    first_status = None
    source_ok = False
    while queue and len(seen) < 20:
        url = queue.pop(0)
        if url in seen or not trusted_url(url):
            continue
        seen.add(url)
        try:
            r = s.get(url, timeout=25)
            if first_status is None:
                first_status = r.status_code
            r.raise_for_status()
            source_ok = True
            diagnostics.append(f"{r.status_code} {url}")
        except Exception as exc:
            diagnostics.append(f"error {url}: {type(exc).__name__}")
            continue
        scoped = any(re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") in url.lower() for name in beach_names)
        flag, evidence = response_flag(r, beach_names, require_beach=not scoped)
        if flag:
            return flag, f"{evidence}@{url}", first_status, source_ok, diagnostics
        ctype = (r.headers.get("content-type") or "").lower()
        if "html" not in ctype and not r.text.lstrip().startswith("<"):
            continue
        for link in candidate_links(r.text, url, beach_names):
            if link not in seen and link not in queue:
                queue.append(link)
        soup = BeautifulSoup(r.text, "html.parser")
        for script in soup.find_all("script", src=True)[:10]:
            script_url = urljoin(url, script.get("src"))
            if not trusted_url(script_url):
                continue
            try:
                jsr = s.get(script_url, timeout=20)
                jsr.raise_for_status()
            except Exception:
                continue
            for api_url in urls_from_javascript(jsr.text):
                if api_url not in seen and api_url not in queue:
                    queue.append(api_url)
    return None, None, first_status, source_ok, diagnostics


def verification_times(previous: dict, now: datetime, source_ok: bool) -> tuple[str | None, str]:
    """Advance verification only when the official conditions source was reachable."""
    verified = now.isoformat() if source_ok else previous.get("last_verified_at")
    return verified, now.isoformat()


def load_previous_flag(slug: str) -> dict:
    path = DATA / slug / "current_flag.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def collect(slug: str, cfg: dict) -> dict:
    now = datetime.now(TZ)
    previous = load_previous_flag(slug)
    s = session()
    flag, evidence, http_status, source_ok, diagnostics = discover_client_flag(s, cfg["source_url"], cfg["beaches"])
    if flag:
        status = "explicit_flag_verified"
        label = flag
        provenance = "officially_directed_public_source"
    elif source_ok:
        status = "official_conditions_source_reachable"
        label = "Official conditions available — no explicit flag published"
        provenance = "officially_directed_conditions_source"
    else:
        status = "official_conditions_source_unavailable"
        label = "Official current conditions unavailable"
        provenance = "unavailable"
    last_verified_at, last_checked_at = verification_times(previous, now, source_ok)
    return {
        "location": cfg["name"],
        "county": cfg["county"],
        "beaches": cfg["beaches"],
        "flag": flag,
        "label": label,
        "severity": FLAG_SEVERITY.get(flag),
        "status": status,
        "provenance_tier": provenance,
        "last_verified_at": last_verified_at,
        "last_checked_at": last_checked_at,
        "source_check_status": "verified" if source_ok else "unavailable",
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
        "adapter_diagnostics": diagnostics[-8:],
        "safety_note": "Only an explicit upstream warning flag is displayed as a flag. Know the Gulf never converts rip-current risk, weather, surf, red-tide status, water quality, a legend, or a generic hazard score into a Florida warning flag. Posted flags and lifeguard instructions control.",
    }


def main() -> None:
    for slug, cfg in LOCATIONS.items():
        payload = collect(slug, cfg)
        out = DATA / slug
        out.mkdir(parents=True, exist_ok=True)
        (out / "current_status.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        (out / "current_flag.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(slug, payload["status"], payload["flag"] or "no-explicit-flag", payload.get("explicit_flag_evidence"))


if __name__ == "__main__":
    main()
