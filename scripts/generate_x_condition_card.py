#!/usr/bin/env python3
"""Generate a branded Know the Gulf condition card for X posts.

Creates a 1200x675 PNG using current repository flag snapshots. The output is
purposefully self-contained and safety-first: stale/unavailable flag data is not
presented as current.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TZ = ZoneInfo("America/Chicago")
W, H = 1200, 675

LOCATIONS = [
    ("Panama City Beach", DATA / "current_flag.json"),
    ("Destin", DATA / "destin" / "current_flag.json"),
    ("Okaloosa Island", DATA / "okaloosa-island" / "current_flag.json"),
    ("Navarre Beach", DATA / "navarre-beach" / "current_flag.json"),
    ("Pensacola Beach", DATA / "pensacola-beach" / "current_flag.json"),
]

FLAG_COLORS = {
    "green": "#22c55e",
    "yellow": "#facc15",
    "red": "#ef4444",
    "double red": "#b91c1c",
    "purple": "#a855f7",
}


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).astimezone(TZ)
    except Exception:
        return None


def read_flag(path: Path, now: datetime):
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    label = str(d.get("label") or d.get("flag") or "").strip()
    verified = parse_dt(d.get("last_verified_at"))
    stale_hours = float(d.get("stale_after_hours") or 0)
    if not label or label.lower().startswith("check official") or not verified:
        return None
    max_age = max(stale_hours, 2.0) + 1.0
    if now - verified > timedelta(hours=max_age):
        return None
    return {"label": label, "verified": verified}


def flag_color(label: str):
    lower = label.lower()
    for key, value in FLAG_COLORS.items():
        if key in lower:
            return value
    return "#64748b"


def draw_card(output: Path, title: str = "Northwest Florida Gulf Check") -> None:
    now = datetime.now(TZ)
    img = Image.new("RGB", (W, H), "#071a2d")
    d = ImageDraw.Draw(img)

    # Ocean-inspired layered background.
    d.rectangle((0, 0, W, H), fill="#071a2d")
    d.rectangle((0, 455, W, H), fill="#0b3552")
    d.ellipse((-120, 430, 500, 760), fill="#0e7490")
    d.ellipse((330, 470, 980, 790), fill="#0891b2")
    d.ellipse((780, 440, 1370, 760), fill="#06b6d4")

    d.text((64, 42), "KNOW THE GULF", font=font(34, True), fill="#f8fafc")
    d.text((64, 91), title, font=font(52, True), fill="#ffffff")
    d.text((64, 154), now.strftime("%A, %B %d · %-I:%M %p CT"), font=font(25), fill="#bae6fd")

    y = 222
    for name, path in LOCATIONS:
        current = read_flag(path, now)
        d.rounded_rectangle((64, y, 1136, y + 58), radius=16, fill="#0f2940")
        d.text((88, y + 15), name, font=font(25, True), fill="#f8fafc")
        if current:
            label = current["label"]
            c = flag_color(label)
            d.rounded_rectangle((780, y + 10, 1110, y + 48), radius=14, fill=c)
            text_color = "#111827" if c in {"#facc15", "#22c55e"} else "#ffffff"
            d.text((800, y + 17), label, font=font(20, True), fill=text_color)
        else:
            d.text((820, y + 17), "Check official flag", font=font(20, True), fill="#cbd5e1")
        y += 67

    d.text((64, 575), "Always follow the flag physically posted at your beach and local lifeguard instructions.", font=font(21, True), fill="#ffffff")
    d.text((64, 612), "Independent public-information project · knowthegulf.com · @knowthegulf", font=font(19), fill="#cffafe")

    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, format="PNG", optimize=True)
    if output.stat().st_size > 5 * 1024 * 1024:
        raise RuntimeError("Generated image exceeds X's 5 MB image upload limit")
    print(output)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="tmp/x-condition-card.png")
    p.add_argument("--title", default="Northwest Florida Gulf Check")
    args = p.parse_args()
    draw_card(ROOT / args.output, args.title)


if __name__ == "__main__":
    main()
