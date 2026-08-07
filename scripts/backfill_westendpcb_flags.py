#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

try:
    from .common import DATA, session
except ImportError:
    from common import DATA, session

SITEMAP = "https://www.westendpcb.com/site-map/"
SOURCE_HOME = "https://www.westendpcb.com/"
MONTHS = {
    'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
}


def parse_date(title: str) -> str | None:
    m = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})\b",
        title, re.I,
    )
    if m:
        try:
            return datetime(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))).date().isoformat()
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b", title)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(1)), int(m.group(2))).date().isoformat()
        except ValueError:
            return None
    return None


def parse_flag(title: str):
    t = re.sub(r"\s+", " ", title).strip()
    lo = t.lower()
    if "test post" in lo:
        return None
    if re.search(r"\bdouble\s+red\b", lo):
        base = "Double Red"
    elif re.search(r"\bsingle\s+red\b", lo):
        base = "Single Red"
    elif re.search(r"\byellow\b", lo):
        base = "Yellow"
    elif re.search(r"\bgreen\b", lo):
        base = "Green"
    elif re.search(r"\bred\s+flag\b", lo):
        base = "Single Red"
    else:
        return None
    purple = bool(re.search(r"\bpurple\b", lo))
    return base, purple


def extract_posts(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for a in soup.find_all("a", href=True):
        title = " ".join(a.stripped_strings)
        if not title:
            continue
        dt = parse_date(title)
        f = parse_flag(title)
        if not dt or not f:
            continue
        base, purple = f
        href = urljoin(SOURCE_HOME, a["href"])
        rows.append({
            "date": dt,
            "base_flag": base,
            "purple_overlay": purple,
            "flag_label": base + (" + Purple" if purple else ""),
            "post_title": title,
            "source_url": href,
            "source": "West End PCB historical flag-status post title",
            "evidence_tier": "community_mirror_candidate",
        })
    if not rows:
        return pd.DataFrame(columns=["date","base_flag","purple_overlay","flag_label","post_title","source_url","source","evidence_tier"])
    return pd.DataFrame(rows).drop_duplicates(subset=["date","flag_label","source_url"]).sort_values(["date","source_url"])


def audit(posts: pd.DataFrame, master: pd.DataFrame):
    rows = []
    if posts.empty or master.empty:
        return pd.DataFrame(), {}
    known_dates = set(master.date.astype(str))
    overlap = posts[posts.date.astype(str).isin(known_dates)].copy()
    for _, p in overlap.iterrows():
        m = master[master.date.astype(str).eq(str(p.date))]
        any_base = bool(m.base_flag.astype(str).eq(str(p.base_flag)).any())
        any_label = bool(m.flag_label.astype(str).eq(str(p.flag_label)).any()) if 'flag_label' in m else False
        rows.append({
            "date": p.date,
            "post_flag": p.base_flag,
            "post_purple": bool(p.purple_overlay),
            "any_primary_or_recovered_base_match": any_base,
            "exact_label_match": any_label,
            "source_url": p.source_url,
        })
    a = pd.DataFrame(rows)
    summary = {
        "overlap_posts": int(len(a)),
        "base_match_posts": int(a.any_primary_or_recovered_base_match.sum()) if len(a) else 0,
        "base_match_pct": round(100 * a.any_primary_or_recovered_base_match.mean(), 2) if len(a) else None,
        "exact_label_match_pct": round(100 * a.exact_label_match.mean(), 2) if len(a) else None,
    }
    return a, summary


def main():
    r = session().get(SITEMAP, timeout=60)
    r.raise_for_status()
    posts = extract_posts(r.text)
    if posts.empty:
        raise RuntimeError("West End PCB sitemap loaded but no explicitly dated flag-status titles parsed.")
    posts.to_csv(DATA / "westendpcb_flag_posts.csv", index=False)

    pre = posts[pd.to_datetime(posts.date).dt.year < 2017].copy()
    pre["candidate_status"] = "candidate_unverified"
    pre["promotion_policy"] = "Not part of the master flag history unless separately audited/corroborated."
    pre.to_csv(DATA / "pre2017_westendpcb_candidates.csv", index=False)

    master_path = DATA / "flag_observations_master.csv"
    master = pd.read_csv(master_path) if master_path.exists() and master_path.stat().st_size else pd.DataFrame()
    audit_df, audit_summary = audit(posts, master)
    audit_df.to_csv(DATA / "westendpcb_flag_overlap_audit.csv", index=False)

    year_counts = posts.assign(year=pd.to_datetime(posts.date).dt.year).groupby('year').size().to_dict()
    pre_counts = pre.base_flag.value_counts().to_dict() if len(pre) else {}
    summary = {
        "source": "West End PCB public site-map index of historical Panama City Beach flag-status posts",
        "source_url": SITEMAP,
        "source_characterization": "Independent local/community site. Its current flag page says condition updates are posted when Beach & Surf Patrol sends a text, but it is not an official government archive.",
        "all_explicitly_dated_flag_posts": int(len(posts)),
        "first_post_date": str(posts.date.min()),
        "last_post_date": str(posts.date.max()),
        "posts_by_year": {str(int(k)): int(v) for k, v in year_counts.items()},
        "pre2017_candidate_posts": int(len(pre)),
        "pre2017_candidate_days": int(pre.date.nunique()) if len(pre) else 0,
        "pre2017_start": str(pre.date.min()) if len(pre) else None,
        "pre2017_end": str(pre.date.max()) if len(pre) else None,
        "pre2017_flag_counts": {str(k): int(v) for k, v in pre_counts.items()},
        "overlap_audit": audit_summary,
        "policy": "These records are preserved as a separately auditable community-mirror candidate tier. They do not overwrite or automatically extend primary/NWS recovered Safe2Swim labels.",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (DATA / "westendpcb_flag_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
