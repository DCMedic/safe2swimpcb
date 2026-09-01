#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DESTINATIONS = [
    "destin", "okaloosa-island", "navarre-beach", "pensacola-beach",
    "south-walton", "cape-san-blas", "st-george-island",
    "anna-maria-island", "siesta-key", "venice", "sanibel",
    "fort-myers-beach", "naples", "marco-island",
]
REQUIRED_ASSETS = [
    "assets/app.css", "assets/app.js", "assets/menu.js", "assets/beach-nav.js",
    "assets/site-ui.js", "assets/western-location.js", "assets/eastern-location.js",
    "assets/southwest-location.js", "assets/location-page.js",
]


def fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)


def local_target(page: Path, value: str) -> Path | None:
    if not value or value.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
        return None
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return None
    path = parsed.path
    if not path:
        return None
    if path.startswith("/"):
        target = ROOT / path.lstrip("/")
    else:
        target = page.parent / path
    if path.endswith("/"):
        target = target / "index.html"
    elif target.is_dir():
        target = target / "index.html"
    return target.resolve()


def validate_html(errors: list[str]) -> None:
    attr_re = re.compile(r"(?:href|src)=[\"']([^\"']+)[\"']", re.I)
    id_re = re.compile(r"\bid=[\"']([^\"']+)[\"']", re.I)
    for page in ROOT.rglob("*.html"):
        if ".git" in page.parts:
            continue
        text = page.read_text(encoding="utf-8")
        for needle in ("<meta name=\"viewport\"", "rel=\"canonical\"", "assets/app.css", "Content-Security-Policy", "name=\"referrer\""):
            if needle not in text:
                fail(f"{page.relative_to(ROOT)} missing required UI/SEO marker: {needle}", errors)
        ids = id_re.findall(text)
        dup = sorted({x for x in ids if ids.count(x) > 1})
        if dup:
            fail(f"{page.relative_to(ROOT)} duplicate element ids: {', '.join(dup)}", errors)
        for value in attr_re.findall(text):
            target = local_target(page, value)
            if target is not None and not target.exists():
                fail(f"{page.relative_to(ROOT)} references missing local resource {value}", errors)


def validate_destinations(errors: list[str]) -> None:
    for slug in DESTINATIONS:
        if not (ROOT / slug / "index.html").exists():
            fail(f"destination page missing: /{slug}/", errors)
    nav = (ROOT / "assets/beach-nav.js").read_text(encoding="utf-8")
    for slug in DESTINATIONS:
        if f"/{slug}/" not in nav:
            fail(f"beach navigation missing /{slug}/", errors)


def validate_sitemap(errors: list[str]) -> None:
    root = ET.parse(ROOT / "sitemap.xml").getroot()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [x.text or "" for x in root.findall("sm:url/sm:loc", ns)]
    for slug in DESTINATIONS:
        expected = f"https://knowthegulf.com/{slug}/"
        if expected not in urls:
            fail(f"sitemap missing {expected}", errors)


def validate_json(errors: list[str]) -> None:
    for p in ROOT.rglob("*.json"):
        if ".git" in p.parts:
            continue
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"invalid JSON {p.relative_to(ROOT)}: {exc}", errors)
    current_files = [ROOT / "data/current_flag.json"] + list((ROOT / "data").glob("*/current_flag.json"))
    valid_flags = {None, "Green", "Yellow", "Single Red", "Double Red"}
    severity = {"Green": 1, "Yellow": 2, "Single Red": 3, "Double Red": 4}
    now = datetime.now(timezone.utc)
    for p in current_files:
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        for key in ("label", "source_name", "source_url", "stale_after_hours"):
            if key not in d:
                fail(f"{p.relative_to(ROOT)} missing current-status key: {key}", errors)

        flag = d.get("flag")
        if flag not in valid_flags:
            fail(f"{p.relative_to(ROOT)} has invalid Florida flag value: {flag!r}", errors)
        if flag is None and d.get("severity") is not None:
            fail(f"{p.relative_to(ROOT)} has severity without an explicit flag", errors)
        if flag in severity and d.get("severity") is not None and d.get("severity") != severity[flag]:
            fail(f"{p.relative_to(ROOT)} severity contradicts flag {flag}", errors)

        primary = d.get("primary_flag")
        if primary is not None and flag is not None and primary != flag:
            fail(f"{p.relative_to(ROOT)} primary_flag contradicts flag", errors)

        try:
            stale_hours = float(d.get("stale_after_hours"))
            if stale_hours < 0:
                raise ValueError
        except (TypeError, ValueError):
            fail(f"{p.relative_to(ROOT)} has invalid stale_after_hours", errors)

        source_url = str(d.get("source_url") or "")
        if source_url and not source_url.startswith(("https://", "http://")):
            fail(f"{p.relative_to(ROOT)} has invalid source_url", errors)

        verified = d.get("last_verified_at")
        if not verified:
            fail(f"{p.relative_to(ROOT)} missing last_verified_at", errors)
        else:
            try:
                stamp = datetime.fromisoformat(str(verified).replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError("timezone required")
                if stamp.astimezone(timezone.utc) > now + timedelta(minutes=15):
                    fail(f"{p.relative_to(ROOT)} last_verified_at is implausibly in the future", errors)
            except ValueError:
                fail(f"{p.relative_to(ROOT)} has invalid last_verified_at", errors)

        label = str(d.get("label") or "").lower()
        if flag is None and d.get("source_check_status") == "verified" and "unavailable" in label:
            fail(f"{p.relative_to(ROOT)} claims verified source while flag is unavailable", errors)


def main() -> int:
    errors: list[str] = []
    for rel in REQUIRED_ASSETS:
        if not (ROOT / rel).exists():
            fail(f"required shared asset missing: {rel}", errors)
    validate_destinations(errors)
    validate_sitemap(errors)
    validate_json(errors)
    validate_html(errors)
    if errors:
        print("SITE HEALTH CHECK FAILED")
        for e in errors:
            print(f" - {e}")
        return 1
    print(f"SITE HEALTH CHECK PASSED: {len(list(ROOT.rglob('*.html')))} HTML pages, {len(DESTINATIONS)+1} beach destinations, JSON and local-link contracts valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
