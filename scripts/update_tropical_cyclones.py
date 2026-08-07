#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

try:
    from .common import DATA, TZ, session
except ImportError:
    from common import DATA, TZ, session

NHC_DATA_PAGE = "https://www.nhc.noaa.gov/data/"
PCB_LAT = 30.125
PCB_LON = -85.730
NEARBY_MILES = 500.0


def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.7613
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parse_coord(v: str) -> float:
    v = v.strip().upper()
    sign = -1 if v.endswith(("S", "W")) else 1
    return sign * float(v[:-1])


def saffir_simpson(wind_kt: float | int | None) -> str:
    if wind_kt is None or pd.isna(wind_kt):
        return "Unknown"
    w = float(wind_kt)
    if w < 34:
        return "Tropical Depression"
    if w < 64:
        return "Tropical Storm"
    if w < 83:
        return "Category 1"
    if w < 96:
        return "Category 2"
    if w < 113:
        return "Category 3"
    if w < 137:
        return "Category 4"
    return "Category 5"


def discover_hurdat2_url() -> str:
    s = session()
    r = s.get(NHC_DATA_PAGE, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    candidates = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(" ", strip=True)
        joined = f"{href} {text}".lower()
        if "hurdat2" in joined and "1851" in joined and href.lower().endswith(".txt"):
            candidates.append(urljoin(NHC_DATA_PAGE, href))
    if not candidates:
        # NHC filenames are versioned by the latest season/date, so use the directory listing
        # only as a discovery fallback rather than hard-coding a year-specific filename.
        idx = s.get("https://www.nhc.noaa.gov/data/hurdat/", timeout=60)
        idx.raise_for_status()
        links = re.findall(r'href=["\']([^"\']*hurdat2-1851-[^"\']+\.txt)["\']', idx.text, flags=re.I)
        candidates = [urljoin("https://www.nhc.noaa.gov/data/hurdat/", x) for x in links]
    if not candidates:
        raise RuntimeError("Could not discover the current Atlantic HURDAT2 text file from NHC.")
    # Filenames encode the most recent season. Lexicographic max selects the newest current archive.
    return sorted(set(candidates))[-1]


def parse_hurdat2(text: str) -> pd.DataFrame:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    rows = []
    storm_id = storm_name = None
    remaining = 0
    for ln in lines:
        if re.match(r"^[A-Z]{2}\d{6},", ln):
            parts = [x.strip() for x in ln.split(",")]
            storm_id = parts[0]
            storm_name = parts[1]
            try:
                remaining = int(parts[2])
            except Exception:
                remaining = 0
            continue
        if not storm_id or remaining <= 0:
            continue
        parts = [x.strip() for x in ln.split(",")]
        remaining -= 1
        if len(parts) < 8:
            continue
        try:
            ts = datetime.strptime(parts[0] + parts[1].zfill(4), "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
            lat = parse_coord(parts[4])
            lon = parse_coord(parts[5])
            wind = int(parts[6]) if parts[6] not in {"", "-999"} else None
            pressure = int(parts[7]) if parts[7] not in {"", "-999"} else None
        except Exception:
            continue
        dist = haversine_miles(PCB_LAT, PCB_LON, lat, lon)
        rows.append({
            "storm_id": storm_id,
            "storm_name": storm_name,
            "timestamp_utc": ts.isoformat(),
            "timestamp_local": ts.astimezone(TZ).isoformat(),
            "date": ts.astimezone(TZ).date().isoformat(),
            "record_identifier": parts[2],
            "status": parts[3],
            "lat": lat,
            "lon": lon,
            "max_wind_kt": wind,
            "min_pressure_mb": pressure,
            "category": saffir_simpson(wind),
            "distance_to_pcb_mi": round(dist, 2),
        })
    return pd.DataFrame(rows)


def build_storm_summary(track: pd.DataFrame) -> pd.DataFrame:
    out = []
    for sid, g in track.groupby("storm_id", sort=True):
        g = g.sort_values("timestamp_utc")
        nearest = g.loc[g.distance_to_pcb_mi.idxmin()]
        within = g[g.distance_to_pcb_mi <= NEARBY_MILES]
        if within.empty:
            continue
        wind_near = pd.to_numeric(within.max_wind_kt, errors="coerce")
        out.append({
            "storm_id": sid,
            "storm_name": nearest.storm_name,
            "season": int(str(sid)[-4:]),
            "first_track_utc": g.iloc[0].timestamp_utc,
            "last_track_utc": g.iloc[-1].timestamp_utc,
            "closest_approach_utc": nearest.timestamp_utc,
            "closest_approach_local": nearest.timestamp_local,
            "closest_distance_mi": float(nearest.distance_to_pcb_mi),
            "status_at_closest": nearest.status,
            "wind_at_closest_kt": nearest.max_wind_kt,
            "category_at_closest": nearest.category,
            "max_wind_within_500mi_kt": float(wind_near.max()) if wind_near.notna().any() else None,
            "n_track_points_within_500mi": int(len(within)),
        })
    return pd.DataFrame(out).sort_values(["closest_approach_utc", "storm_id"]) if out else pd.DataFrame()


def build_daily(track: pd.DataFrame) -> pd.DataFrame:
    near = track[track.distance_to_pcb_mi <= NEARBY_MILES].copy()
    rows = []
    if near.empty:
        return pd.DataFrame()
    for dt, day in near.groupby("date", sort=True):
        nearest = day.loc[day.distance_to_pcb_mi.idxmin()]
        winds = pd.to_numeric(day.max_wind_kt, errors="coerce")
        rows.append({
            "date": dt,
            "nearest_storm_id": nearest.storm_id,
            "nearest_storm_name": nearest.storm_name,
            "nearest_storm_status": nearest.status,
            "nearest_storm_category": nearest.category,
            "tc_min_distance_mi": float(nearest.distance_to_pcb_mi),
            "tc_max_wind_kt_within_500mi": float(winds.max()) if winds.notna().any() else None,
            "tc_active_storms_within_500mi": int(day.storm_id.nunique()),
            "tc_within_50mi": bool((day.distance_to_pcb_mi <= 50).any()),
            "tc_within_100mi": bool((day.distance_to_pcb_mi <= 100).any()),
            "tc_within_200mi": bool((day.distance_to_pcb_mi <= 200).any()),
            "tc_within_300mi": bool((day.distance_to_pcb_mi <= 300).any()),
            "tc_within_500mi": True,
        })
    return pd.DataFrame(rows).sort_values("date")


def main():
    url = discover_hurdat2_url()
    r = session().get(url, timeout=120)
    r.raise_for_status()
    track = parse_hurdat2(r.text)
    if track.empty:
        raise RuntimeError("HURDAT2 downloaded but no track records parsed.")

    near_track = track[track.distance_to_pcb_mi <= NEARBY_MILES].copy().sort_values(["timestamp_utc", "storm_id"])
    storms = build_storm_summary(track)
    daily = build_daily(track)

    near_track.to_csv(DATA / "tropical_cyclone_track_points_near_pcb.csv", index=False)
    storms.to_csv(DATA / "tropical_cyclone_events_near_pcb.csv", index=False)
    daily.to_csv(DATA / "tropical_cyclone_daily.csv", index=False)

    summary = {
        "source": "NOAA National Hurricane Center Atlantic HURDAT2 best-track database",
        "source_url": url,
        "pcb_reference_point": {"lat": PCB_LAT, "lon": PCB_LON},
        "nearby_threshold_miles": NEARBY_MILES,
        "track_start": str(track.timestamp_utc.min()),
        "track_end": str(track.timestamp_utc.max()),
        "all_track_points": int(len(track)),
        "nearby_track_points": int(len(near_track)),
        "storms_within_500mi": int(len(storms)),
        "days_with_storm_within_500mi": int(len(daily)),
        "method_note": "Distance is great-circle distance from each six-hourly HURDAT2 best-track point to the Safe2Swim PCB reference point. This is retrospective best-track history, not a forecast product.",
        "modeling_note": "Best-track proximity is published for retrospective analysis. It should not be used as a future operational predictor unless replaced by contemporaneously available forecast-track features.",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (DATA / "tropical_cyclone_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
