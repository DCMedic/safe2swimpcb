#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

try:
    from .common import DATA, session
except ImportError:
    from common import DATA, session

CDX = "https://web.archive.org/cdx/search/cdx"
WAYBACK = "https://web.archive.org/web/{timestamp}id_/{original}"
TARGETS = [
    "www.visitpanamacitybeach.com/beach-alerts-iframe/",
    "www.visitpanamacitybeach.com/stay-pcb-current/",
    "www.visitpanamacitybeach.com/partners/resources/beach-safety/",
]

BASE_PATTERNS = [
    ("Double Red", re.compile(r"\bdouble\s+red(?:\s+flag)?\b", re.I)),
    ("Single Red", re.compile(r"\bsingle\s+red(?:\s+flag)?\b", re.I)),
    ("Yellow", re.compile(r"\byellow(?:\s+flag)?\b", re.I)),
    ("Green", re.compile(r"\bgreen(?:\s+flag)?\b", re.I)),
    ("Single Red", re.compile(r"\bred\s+flag\b", re.I)),
]


def parse_current_condition(html: str):
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    low = text.lower()
    anchors = [
        low.find("current beach conditions"),
        low.find("current beach flag"),
        low.find("flag warning status"),
    ]
    anchors = [x for x in anchors if x >= 0]
    if not anchors:
        return None
    i = min(anchors)
    # Keep the evidence window tight enough to avoid reading the later legend as the current flag.
    window = text[i : i + 550]
    legend_markers = ["beach warning flags", "what the warning status means", "flag colors", "double red flag:"]
    wl = window.lower()
    cut = min([wl.find(m) for m in legend_markers if wl.find(m) > 60] or [len(window)])
    window = window[:cut]

    base = None
    match_pos = 10**9
    for label, pat in BASE_PATTERNS:
        m = pat.search(window)
        if m and m.start() < match_pos:
            base = label
            match_pos = m.start()
    if not base:
        return None
    purple = bool(re.search(r"\bpurple(?:\s+flag)?\b", window, re.I))
    return base, purple, re.sub(r"\s+", " ", window).strip()[:500]


def cdx_captures(target: str):
    params = {
        "url": target,
        "from": "2008",
        "to": "2016",
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "collapse": "digest",
        "limit": "500",
    }
    r = session().get(CDX, params=params, timeout=90)
    r.raise_for_status()
    z = r.json()
    if not z or len(z) < 2:
        return []
    header = z[0]
    return [dict(zip(header, row)) for row in z[1:]]


def main():
    s = session()
    rows = []
    target_stats = {}
    errors = []

    for target in TARGETS:
        try:
            caps = cdx_captures(target)
        except Exception as exc:
            errors.append(f"CDX {target}: {exc}")
            target_stats[target] = {"captures": 0, "parsed_candidates": 0, "status": "cdx_unavailable"}
            continue

        # At most one capture per calendar day per target, preferring the latest timestamp.
        per_day = {}
        for cap in caps:
            ts = str(cap.get("timestamp", ""))
            if len(ts) >= 8:
                per_day[ts[:8]] = cap
        parsed = 0
        for cap in sorted(per_day.values(), key=lambda x: x.get("timestamp", "")):
            ts = str(cap.get("timestamp", ""))
            original = cap.get("original") or target
            if not ts.startswith(tuple(str(y) for y in range(2008, 2017))):
                continue
            url = WAYBACK.format(timestamp=ts, original=original)
            try:
                r = s.get(url, timeout=45)
                if r.status_code != 200:
                    continue
                p = parse_current_condition(r.text)
                if not p:
                    continue
                base, purple, evidence = p
                capture_dt = datetime.strptime(ts[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                rows.append({
                    "capture_timestamp_utc": capture_dt.isoformat(),
                    "capture_date": capture_dt.date().isoformat(),
                    "base_flag": base,
                    "purple_overlay": purple,
                    "flag_label": base + (" + Purple" if purple else ""),
                    "original_url": original,
                    "archive_url": url,
                    "evidence_text": evidence,
                    "source": "Internet Archive capture of Visit Panama City Beach page",
                    "candidate_status": "candidate_unverified",
                    "promotion_policy": "Never automatically promoted; requires independent date/source audit.",
                })
                parsed += 1
            except Exception as exc:
                errors.append(f"snapshot {ts} {original}: {exc}")
        target_stats[target] = {"captures": int(len(caps)), "unique_capture_days": int(len(per_day)), "parsed_candidates": int(parsed), "status": "checked"}

    out = pd.DataFrame(rows)
    if len(out):
        out = out.drop_duplicates(subset=["capture_date", "flag_label", "original_url"], keep="last").sort_values(["capture_date", "capture_timestamp_utc"])
    else:
        out = pd.DataFrame(columns=[
            "capture_timestamp_utc", "capture_date", "base_flag", "purple_overlay", "flag_label",
            "original_url", "archive_url", "evidence_text", "source", "candidate_status", "promotion_policy",
        ])
    out.to_csv(DATA / "pre2017_flag_candidates.csv", index=False)

    nws_first = None
    nws_summary = DATA / "nws_srf_summary.json"
    if nws_summary.exists():
        try:
            nws_first = json.loads(nws_summary.read_text()).get("first_product_date")
        except Exception:
            pass

    summary = {
        "goal": "Recover Panama City Beach flag evidence before the NWS SRFTAE explicit Bay-flag record begins.",
        "candidate_count": int(len(out)),
        "candidate_days": int(out.capture_date.nunique()) if len(out) else 0,
        "candidate_start": str(out.capture_date.min()) if len(out) else None,
        "candidate_end": str(out.capture_date.max()) if len(out) else None,
        "nws_srf_first_product_date": nws_first,
        "targets": target_stats,
        "errors_sample": errors[:20],
        "evidence_policy": "Wayback captures are discovery evidence only. No candidate is merged into the Safe2Swim flag master until independently audited against an authoritative or contemporaneous source.",
        "next_sources_to_pursue": [
            "City of Panama City Beach / Beach & Surf Patrol retained operational logs",
            "Bay County emergency-management or beach-safety retained flag logs",
            "Legacy ALERTBAY/888777 message exports from residents or agencies",
            "Archived Visit Panama City Beach current-condition pages and embedded flag widgets",
            "Contemporaneous local media reports only as corroborating evidence, not primary labels",
        ],
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (DATA / "pre2017_flag_hunt_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
