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

# These titles are seeded from the public West End PCB site-map index so the
# discovery record remains reproducible even when that site returns bot/challenge
# HTML to a GitHub Actions runner. They remain secondary candidates only.
SEED_TITLES = [
    # Pre-2017 candidates discovered in the public index.
    "PCB Beach Flags Yellow Today – December 18 2016",
    "PCB Beach Flags Yellow/Purple Today – October 7 2016",
    "PCB Beach Flags Yellow Today – September 5 2016",
    "PCB Beach Flags Downgrading to Single RED Today – September 2, 2016",
    "PCB Beach Flags set to DOUBLE RED Today – September 1, 2016",
    "PCB Beach Flags Yellow Today – 8-17-2016",
    "PCB Beach Flags Changing to Single RED Today – August 13, 2016",
    "PCB Beach Flags Yellow Today – 7-29-2016",
    "PCB Beach Flags Downgrading to Single RED Today – July 27, 2016",
    "UPDATED! PCB Beach Flags Changing from Single to DOUBLE RED Today – July 26, 2016",
    "PCB Beach Flags Changing to Yellow Today – July 6, 2016",
    "April 5, 2011 – Red Flag so far",
    "September 12, 2010 – Yellow Flag…Clear Water",
    "September 11, 2010 – Yellow Flag…Clear Water",
    "September 10, 2010 – Yellow Flag…Clear Water",
    "September 8, 2010 – Yellow Flag…Clear Water",
    "September 7, 2010 – Yellow Flag…Clear Water",
    "September 6, 2010 – Yellow Flag…Crystal Clear Water",
    "September 5, 2010 – Yellow Flag…Crystal Clear Water",
    "September 4, 2010 – Yellow Flag…Clear Water",
    "September 3, 2010 – Yellow Flag",
    "September 2, 2010 – Yellow Flag… Clear Water",
    "August 31, 2010 – Yellow Flag… Clear Water",
    "August 30, 2010 – Red Flag… Seaweed",
    "August 29, 2010 – Red Flag… Seaweed…And Rain Too!",
    "August 28, 2010 – Red Flag… Seaweed",
    "August 27, 2010 – Red Flag… Seaweed",
    "August 26, 2010 – Yellow Flag… Heavy Seaweed",
    "August 25, 2010 – Yellow Flag… Murky Water",
    "August 24, 2010 – Yellow Flag… Clear Water",
    "August 23, 2010 – Yellow Flag… Clear Water",
    "August 22, 2010 – Yellow Flag… Light Seaweed",
    "August 21, 2010 – Yellow Flag… Seaweed",
    "August 19, 2010 – Yellow Flag, Spotty Seaweed",
    "August 18, 2010 – Red Flag, Spotty Seaweed",
    "August 17, 2010 – Red Flag, Light Seaweed",
    "August 16, 2010 – Yellow Flag, Heavy Seaweed",
    "August 10, 2010 – Yellow Flag, Light Seaweed",
    "August 8, 2010 – Yellow flag and seaweed",
    "August 7, 2010 – Yellow flag and seaweed",
    "August 6, 2010 – Yellow flag",
    "August 5, 2010 – Yellow flag",
    "July 30, 2010 – Friday – Yellow Flag",
    "July 24, 2010 – Yellow Flag, but there is also a Rip Current warning",
    "July 10, 2010 – yellow flag",
    "July 8 2010 – Yellow Flag",
    "July 7, 2010 Single Red – Now Double Red Flag",
    "July 6 2010 – Single Red Flag",
    # Later overlap controls used to quantify how faithfully the mirror tracks
    # the authoritative/recovered Safe2Swim record.
    "PCB Beach Flags Changed to Single RED Today – July 24, 2017",
    "Beach Flags Returned to Yellow Today – July 27, 2017",
    "PCB Beach Flags Changed Back to Single RED Today – July 29, 2017",
    "Beach Flags Returned to Yellow Today – July 30, 2017",
    "PCB Beach Flags Changed to Single RED Today – August 9, 2017",
    "The beach flags are now DOUBLE RED. The Gulf is closed for swimming! – August 11, 2017",
    "Beach Flags Returned to Yellow Today – August 13, 2017",
    "PCB Beach Flags Changed to Single RED Today – August 26, 2017",
    "Beach Flags Returned to Yellow Today – August 27, 2017",
    "The beach flags are now DOUBLE RED. The Gulf is closed for swimming! – August 30, 2017",
    "The beach flags are now DOUBLE RED. The Gulf is closed – Thanks, Irma! – September 10, 2017",
    "The beach flags are now DOUBLE RED. The Gulf is closed – March 28, 2018",
    "PCB Beach Flags Changed to Single RED Today – June 24, 2018",
    "Panama City Beach Flag Report Today – Returned to Yellow – June 25, 2018",
    "PCB Beach Flags Changed to Single RED Today – July 21, 2018",
    "Panama City Beach Flag Report Today – Returned to Yellow – July 25, 2018",
    "The beach flags are now DOUBLE RED. The Gulf is closed – August 1, 2018",
    "PCB Beach Flags switched Single RED Today – August 2, 2018",
    "Panama City Beach Flag Update Today – Returned to Yellow – August 12, 2018",
    "Beach flags are now DOUBLE RED. The Gulf is closed – September 4, 2018",
    "PCB Beach Flags Updated To Single RED Today – September 5, 2018",
    "Panama City Beach Flag Update Today – Returned to Yellow – September 6, 2018",
    "PCB Beach Flags Bumped Up To Single RED Today – October 7, 2018",
    "Hurricane Michael Pushes Flags To DOUBLE RED. The Gulf is closed – October 8, 2018",
    "PCB Flags Back To DOUBLE RED. The Gulf is closed – November 1, 2018",
    "Panama City Beach Flag Update – Flags are now Yellow – November 28, 2018",
    "PCB Flags Are Now DOUBLE RED. The Gulf is closed – December 1, 2018",
    "PCB Beach Flags Reduced To Single RED Today – December 3, 2018",
    "PCB Flag Update – Flags Changed To Yellow – December 4, 2018",
    "PCB Flag Update – Flags Still Yellow – December 11, 2018",
    "PCB Beach Flags Raised To Single RED Today – December 16, 2018",
    "PCB Beach Flag Alert: Flags Remain Single RED Today – December 22, 2018",
    "PCB Beach Flag Alert: Flags Back To Single RED Today – December 27, 2018",
]


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


def row_from_title(title: str, href: str, discovery_method: str):
    dt = parse_date(title)
    f = parse_flag(title)
    if not dt or not f:
        return None
    base, purple = f
    return {
        "date": dt,
        "base_flag": base,
        "purple_overlay": purple,
        "flag_label": base + (" + Purple" if purple else ""),
        "post_title": title,
        "source_url": href,
        "source": "West End PCB historical flag-status post title",
        "evidence_tier": "community_mirror_candidate",
        "discovery_method": discovery_method,
    }


def extract_posts(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for a in soup.find_all("a", href=True):
        title = " ".join(a.stripped_strings)
        if not title:
            continue
        row = row_from_title(title, urljoin(SOURCE_HOME, a["href"]), "live_site_map")
        if row:
            rows.append(row)
    for title in SEED_TITLES:
        row = row_from_title(title, SITEMAP, "public_site_map_seed")
        if row:
            rows.append(row)
    if not rows:
        return pd.DataFrame(columns=["date","base_flag","purple_overlay","flag_label","post_title","source_url","source","evidence_tier","discovery_method"])
    return pd.DataFrame(rows).drop_duplicates(subset=["date","flag_label","post_title"]).sort_values(["date","post_title"])


def audit(posts: pd.DataFrame, master: pd.DataFrame):
    rows = []
    if posts.empty or master.empty:
        return pd.DataFrame(columns=["date","post_flag","post_purple","any_primary_or_recovered_base_match","exact_label_match","source_url"]), {}
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
    live_status = "not_checked"
    try:
        r = session().get(SITEMAP, timeout=60)
        r.raise_for_status()
        html = r.text
        live_status = "loaded"
    except Exception as exc:
        print("warning: live West End PCB site-map fetch failed:", exc)
        html = ""
        live_status = "unavailable"

    posts = extract_posts(html)
    if posts.empty:
        raise RuntimeError("No West End PCB seed or live historical titles could be parsed.")
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
        "live_site_map_status": live_status,
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
