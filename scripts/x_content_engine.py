#!/usr/bin/env python3
"""Production content engine for the official Know the Gulf X account.

Design goals:
- Safety-first: only publish current flag information when source data is fresh.
- Useful mix: safety, local conditions, marine knowledge, destination guidance.
- Cost-aware: most posts are URL-free; linked posts are intentionally sparse.
- Quiet by default: no post unless a scheduled slot or meaningful flag change exists.
- Duplicate-resistant: persistent state records recent fingerprints and budget estimates.

The script either prints a selected post to stdout or exits 0 with no post selected.
When --publish is used, it publishes through scripts.post_to_x and updates state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE_PATH = DATA / "x_posting_state.json"
TZ = ZoneInfo("America/Chicago")

# Planning values based on the current X pay-per-use rates supplied for this project.
STANDARD_POST_ESTIMATE = 0.015
URL_POST_ESTIMATE = 0.20
MONTHLY_SOFT_CAP_USD = 6.00
LIFETIME_BUDGET_USD = 30.00
MAX_POSTS_PER_DAY = 3
MIN_MINUTES_BETWEEN_POSTS = 90
LINK_POST_MIN_DAYS = 3

LOCATIONS = {
    "Panama City Beach": DATA / "current_flag.json",
    "Destin": DATA / "destin" / "current_flag.json",
    "Okaloosa Island": DATA / "okaloosa-island" / "current_flag.json",
    "Navarre Beach": DATA / "navarre-beach" / "current_flag.json",
    "Pensacola Beach": DATA / "pensacola-beach" / "current_flag.json",
}

EVERGREEN = [
    "Rip currents move water away from shore. If caught in one, stay calm, float or tread water, and move parallel to shore when you can. Never fight the current straight back toward the beach. 🌊",
    "Beach flags and rip-current forecasts are related, but they are not interchangeable. The flag posted by the local beach-safety authority is the signal to follow at the beach.",
    "A calm-looking patch of water can still contain a rip current. Gaps in breaking waves, channels of churning water, or foam moving seaward can be clues, but conditions are not always obvious.",
    "Gulf safety starts before your feet hit the sand: check the posted beach flag, look at marine weather, identify lifeguard locations, and make sure everyone in your group knows where to meet.",
    "Double-red flags mean the water is closed to the public where that flag system is in force. Treat the closure as a hard safety boundary, not a suggestion.",
    "Purple flags warn of dangerous marine life. They can be flown with another flag because marine-life hazards and surf hazards are separate conditions.",
    "Yellow flags do not mean 'safe.' They indicate moderate hazards. Weak swimmers and children still need extra caution, close supervision, and respect for local lifeguard guidance.",
    "The Florida Panhandle can change quickly: wind shifts, thunderstorms, tides, and swell can turn a comfortable beach morning into a very different afternoon. Re-check conditions during the day.",
]

DESTINATION_FACTS = [
    ("Panama City Beach", "PCB's beach day is best treated as a live system: posted flags, wind, waves, tides, and storms can all change independently. Check the official flag again before entering the Gulf."),
    ("Destin", "Destin's passes and nearshore currents can behave differently from an open beach. Respect posted flags and avoid treating nearby calm water as proof that every stretch of shoreline is equally safe."),
    ("Okaloosa Island", "Okaloosa Island sits between open Gulf shoreline and busy pass waters. Conditions can vary over short distances, so local flags and lifeguard direction matter more than what the water looked like earlier."),
    ("Navarre Beach", "Navarre Beach can look beautifully calm while currents remain present. Use the official Santa Rosa County beach-safety information and avoid relying on appearance alone."),
    ("Pensacola Beach", "Pensacola Beach weather and surf can change rapidly with Gulf storms and sea-breeze boundaries. Re-check flags and weather if thunder or darkening skies approach."),
]

LINK_POSTS = [
    "Florida beach flags are easier to use when you know what each color actually means. Know the Gulf's plain-language guide: https://knowthegulf.com/florida-beach-flag-meanings/",
    "Rip-current safety is worth learning before the emergency. Our Northwest Florida guide covers recognition, escape, and what to do if someone else is in trouble: https://knowthegulf.com/rip-current-safety/",
    "Planning a Northwest Florida beach day? Know the Gulf brings flags, safety resources, conditions, and historical context together at https://knowthegulf.com/",
]

@dataclass
class Candidate:
    kind: str
    text: str
    contains_url: bool = False
    priority: int = 10


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--publish", action="store_true")
    p.add_argument("--force-slot", choices=["morning", "afternoon", "evening"])
    p.add_argument("--now", help="ISO timestamp for tests")
    return p.parse_args()


def now_local(value: str | None) -> datetime:
    if value:
        dt = datetime.fromisoformat(value)
        return dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt.astimezone(TZ)
    return datetime.now(TZ)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def initial_state() -> dict:
    return {
        "version": 1,
        "last_posted_at": None,
        "last_link_post_at": None,
        "recent_fingerprints": [],
        "flag_state": {},
        "usage": {},
        "lifetime_estimated_spend_usd": 0.0,
        "sequence": 0,
    }


def load_state() -> dict:
    state = load_json(STATE_PATH, initial_state())
    for k, v in initial_state().items():
        state.setdefault(k, v)
    return state


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def dt_or_none(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).astimezone(TZ)
    except (ValueError, TypeError):
        return None


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()[:16]


def fresh_flag(path: Path, now: datetime) -> dict | None:
    data = load_json(path, {})
    label = data.get("label") or data.get("flag")
    verified = dt_or_none(data.get("last_verified_at"))
    stale_hours = data.get("stale_after_hours", 2)
    if not label or label.lower().startswith("check official") or not verified:
        return None
    # Give scheduled jobs a little tolerance beyond the site's own freshness threshold.
    max_age = max(float(stale_hours or 0), 2.0) + 1.0
    if now - verified > timedelta(hours=max_age):
        return None
    return {"label": str(label), "verified": verified, "source": data.get("source_name")}


def flag_change_candidate(state: dict, now: datetime) -> Candidate | None:
    changes = []
    for name, path in LOCATIONS.items():
        current = fresh_flag(path, now)
        if not current:
            continue
        old = state["flag_state"].get(name)
        state["flag_state"][name] = current["label"]
        if old and old != current["label"]:
            changes.append((name, old, current["label"]))
    if not changes:
        return None
    if len(changes) == 1:
        name, old, new = changes[0]
        text = f"⚠️ Beach flag update: {name} changed from {old} to {new}. Follow the flag currently posted at the beach and local lifeguard instructions. Conditions can change quickly."
    else:
        summary = "; ".join(f"{name}: {old} → {new}" for name, old, new in changes[:3])
        text = f"⚠️ Northwest Florida beach flag updates: {summary}. Follow locally posted flags and lifeguard instructions before entering the Gulf."
    return Candidate("flag-change", text, priority=100)


def morning_candidate(state: dict, now: datetime) -> Candidate | None:
    current = []
    for name, path in LOCATIONS.items():
        flag = fresh_flag(path, now)
        if flag:
            current.append(f"{name}: {flag['label']}")
    if not current:
        return Candidate("morning-safety", "Good morning from Know the Gulf. Before heading to a Northwest Florida beach today, check the locally posted flag, marine weather, and thunderstorm risk. Conditions can differ between beaches and change during the day. 🌊")
    joined = " | ".join(current[:4])
    return Candidate("morning-flags", f"Good morning, Gulf Coast. Fresh flag checks available to Know the Gulf: {joined}. Always follow the flag physically posted at your beach and local lifeguard direction. 🌊")


def educational_candidate(state: dict, now: datetime) -> Candidate:
    seq = int(state.get("sequence", 0))
    # Alternate general safety and destination-specific context for variety.
    if seq % 3 == 2:
        name, fact = DESTINATION_FACTS[(seq // 3) % len(DESTINATION_FACTS)]
        return Candidate("destination", f"{name} beach note: {fact}")
    return Candidate("education", EVERGREEN[seq % len(EVERGREEN)])


def link_candidate(state: dict, now: datetime) -> Candidate | None:
    last = dt_or_none(state.get("last_link_post_at"))
    if last and now - last < timedelta(days=LINK_POST_MIN_DAYS):
        return None
    seq = int(state.get("sequence", 0))
    return Candidate("link", LINK_POSTS[seq % len(LINK_POSTS)], contains_url=True)


def scheduled_slot(now: datetime, forced: str | None) -> str | None:
    if forced:
        return forced
    # Workflow runs hourly. Wide windows make delayed GitHub schedules safe.
    if 7 <= now.hour <= 9:
        return "morning"
    if 14 <= now.hour <= 16:
        return "afternoon"
    if 18 <= now.hour <= 20 and now.weekday() in {1, 4}:  # Tue/Fri optional third slot
        return "evening"
    return None


def usage_bucket(state: dict, now: datetime) -> dict:
    key = now.strftime("%Y-%m")
    bucket = state["usage"].setdefault(key, {"posts": 0, "url_posts": 0, "estimated_spend_usd": 0.0, "days": {}})
    return bucket


def guardrails_allow(state: dict, now: datetime, candidate: Candidate) -> tuple[bool, str]:
    last = dt_or_none(state.get("last_posted_at"))
    if last and now - last < timedelta(minutes=MIN_MINUTES_BETWEEN_POSTS) and candidate.priority < 100:
        return False, "minimum interval"
    bucket = usage_bucket(state, now)
    day = now.date().isoformat()
    if int(bucket["days"].get(day, 0)) >= MAX_POSTS_PER_DAY and candidate.priority < 100:
        return False, "daily post cap"
    estimated = URL_POST_ESTIMATE if candidate.contains_url else STANDARD_POST_ESTIMATE
    if float(bucket.get("estimated_spend_usd", 0)) + estimated > MONTHLY_SOFT_CAP_USD and candidate.priority < 100:
        return False, "monthly soft cost cap"
    if float(state.get("lifetime_estimated_spend_usd", 0)) + estimated > LIFETIME_BUDGET_USD:
        return False, "lifetime $30 budget guardrail"
    if fingerprint(candidate.text) in state.get("recent_fingerprints", []):
        return False, "duplicate fingerprint"
    return True, "ok"


def choose_candidate(state: dict, now: datetime, forced: str | None) -> Candidate | None:
    # Meaningful verified flag changes always win.
    change = flag_change_candidate(state, now)
    if change:
        return change
    slot = scheduled_slot(now, forced)
    if slot == "morning":
        return morning_candidate(state, now)
    if slot == "afternoon":
        return educational_candidate(state, now)
    if slot == "evening":
        return link_candidate(state, now) or educational_candidate(state, now)
    return None


def record_post(state: dict, now: datetime, candidate: Candidate) -> None:
    cost = URL_POST_ESTIMATE if candidate.contains_url else STANDARD_POST_ESTIMATE
    bucket = usage_bucket(state, now)
    day = now.date().isoformat()
    bucket["posts"] = int(bucket.get("posts", 0)) + 1
    bucket["url_posts"] = int(bucket.get("url_posts", 0)) + (1 if candidate.contains_url else 0)
    bucket["estimated_spend_usd"] = round(float(bucket.get("estimated_spend_usd", 0)) + cost, 3)
    bucket["days"][day] = int(bucket["days"].get(day, 0)) + 1
    state["lifetime_estimated_spend_usd"] = round(float(state.get("lifetime_estimated_spend_usd", 0)) + cost, 3)
    state["last_posted_at"] = now.isoformat()
    if candidate.contains_url:
        state["last_link_post_at"] = now.isoformat()
    recents = state.get("recent_fingerprints", []) + [fingerprint(candidate.text)]
    state["recent_fingerprints"] = recents[-40:]
    state["sequence"] = int(state.get("sequence", 0)) + 1


def main() -> int:
    args = parse_args()
    now = now_local(args.now)
    state = load_state()
    candidate = choose_candidate(state, now, args.force_slot)
    # Persist fresh observed flag state even when no post is sent; this prevents an
    # initial deployment from treating today's existing flag as a new change.
    if not candidate:
        save_state(state)
        print("NO_POST: no scheduled slot or verified flag change")
        return 0

    allowed, reason = guardrails_allow(state, now, candidate)
    if not allowed:
        save_state(state)
        print(f"NO_POST: {reason}")
        return 0

    if len(candidate.text) > 280:
        print(f"ERROR: generated post exceeds 280 characters ({len(candidate.text)})", file=sys.stderr)
        return 1

    print(f"SELECTED_KIND={candidate.kind}")
    print(f"ESTIMATED_COST_USD={'0.200' if candidate.contains_url else '0.015'}")
    print(candidate.text)

    if args.publish:
        from post_to_x import publish
        post_id, _ = publish(candidate.text)
        record_post(state, now, candidate)
        save_state(state)
        print(f"PUBLISHED_URL=https://x.com/knowthegulf/status/{post_id}")
    else:
        save_state(state)
        print("DRY_RUN_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
