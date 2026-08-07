#!/usr/bin/env python3
from __future__ import annotations

import gzip
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .common import DATA, TZ, session
except ImportError:
    from common import DATA, TZ, session

NDBC_HIST = "https://www.ndbc.noaa.gov/data/historical/stdmet/{station}h{year}.txt.gz"
NDBC_RT = "https://www.ndbc.noaa.gov/data/realtime2/{station}.txt"

STATIONS = {
    "PCBF1": {
        "name": "Panama City Beach, FL / NOAA NOS 8729210",
        "lat": 30.213,
        "lon": -85.880,
        "start_year": 2005,
        "role": "local_coastal_meteorology",
    },
    "42039": {
        "name": "PENSACOLA - 115NM SSE of Pensacola, FL",
        "lat": 28.768,
        "lon": -86.024,
        "start_year": 1995,
        "role": "offshore_wave_meteorology",
    },
}


def _decode_response(content: bytes, url: str) -> str:
    if url.endswith(".gz"):
        try:
            content = gzip.decompress(content)
        except OSError:
            pass
    return content.decode("utf-8", errors="replace")


def _parse_ndbc_text(text: str, station: str, source_url: str) -> pd.DataFrame:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    header = None
    data_start = None
    for i, ln in enumerate(lines):
        stripped = ln.lstrip("#").strip()
        first = stripped.split()[0].upper() if stripped.split() else ""
        if first in {"YY", "YYYY"}:
            header = stripped.split()
            data_start = i + 1
            break
    if not header or data_start is None:
        return pd.DataFrame()

    rows = []
    for ln in lines[data_start:]:
        if ln.startswith("#"):
            continue
        parts = ln.split()
        if len(parts) < min(5, len(header)):
            continue
        if len(parts) > len(header):
            parts = parts[: len(header)]
        if len(parts) < len(header):
            parts += [None] * (len(header) - len(parts))
        rows.append(parts)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=header)
    year_col = "YYYY" if "YYYY" in df.columns else "YY"
    year = pd.to_numeric(df[year_col], errors="coerce")
    if year_col == "YY":
        # NDBC changed some standard-met files to four-digit year values while
        # retaining the legacy YY column name. Preserve already-four-digit years;
        # only expand true two-digit values.
        year = np.where(
            year >= 100,
            year,
            np.where(year < 70, year + 2000, year + 1900),
        )
    month = pd.to_numeric(df.get("MM"), errors="coerce")
    day = pd.to_numeric(df.get("DD"), errors="coerce")
    hour = pd.to_numeric(df.get("hh"), errors="coerce")
    minute_raw = pd.to_numeric(df.get("mm", 0), errors="coerce")
    minute = minute_raw.fillna(0) if hasattr(minute_raw, "fillna") else 0
    dt = pd.to_datetime(
        {"year": year, "month": month, "day": day, "hour": hour, "minute": minute},
        errors="coerce",
        utc=True,
    )
    df["observed_utc"] = dt
    df = df[df["observed_utc"].notna()].copy()
    if df.empty:
        return df
    df["observed_local"] = df["observed_utc"].dt.tz_convert(TZ)
    df["date"] = df["observed_local"].dt.date.astype(str)
    df["station"] = station
    df["source_url"] = source_url

    for c in ["WDIR", "WSPD", "GST", "WVHT", "DPD", "APD", "MWD", "PRES", "ATMP", "WTMP", "DEWP", "VIS", "TIDE"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # NDBC uses large sentinel values for missing observations. Apply physical plausibility filters too.
    bounds = {
        "WDIR": (0, 360), "WSPD": (0, 80), "GST": (0, 100), "WVHT": (0, 30),
        "DPD": (0, 40), "APD": (0, 40), "MWD": (0, 360), "PRES": (850, 1100),
        "ATMP": (-40, 50), "WTMP": (-5, 40), "DEWP": (-60, 45), "VIS": (0, 100),
    }
    for c, (lo, hi) in bounds.items():
        if c in df.columns:
            df.loc[(df[c] < lo) | (df[c] > hi), c] = np.nan
    return df


def _fetch_station(station: str, start_year: int) -> pd.DataFrame:
    s = session()
    frames = []
    this_year = datetime.now(timezone.utc).year
    for year in range(start_year, this_year):
        url = NDBC_HIST.format(station=station.lower(), year=year)
        try:
            r = s.get(url, timeout=60)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            d = _parse_ndbc_text(_decode_response(r.content, url), station, url)
            if len(d):
                frames.append(d)
                print(station, year, len(d))
        except Exception as exc:
            print("warning", station, year, exc)

    # Current/recent observations. This overlaps the most recent archived year by design;
    # duplicate timestamps are removed below.
    rt_url = NDBC_RT.format(station=station.upper())
    try:
        r = s.get(rt_url, timeout=60)
        r.raise_for_status()
        d = _parse_ndbc_text(r.text, station, rt_url)
        if len(d):
            frames.append(d)
    except Exception as exc:
        print("warning realtime", station, exc)

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    return out.drop_duplicates(subset=["station", "observed_utc"], keep="last").sort_values("observed_utc")


def _mph(x):
    return x * 2.2369362920544


def _ft(x):
    return x * 3.2808398950131


def _f(x):
    return x * 9 / 5 + 32


def _agg_station(df: pd.DataFrame, station: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = df[df["station"].eq(station)].copy()
    if g.empty:
        return pd.DataFrame()

    def agg_num(day, col, fn):
        if col not in day:
            return np.nan
        x = pd.to_numeric(day[col], errors="coerce").dropna()
        if x.empty:
            return np.nan
        return float(getattr(x, fn)())

    rows = []
    for dt, day in g.groupby("date", sort=True):
        row = {"date": dt, f"{station.lower()}_obs_count": int(len(day))}
        if station == "PCBF1":
            row.update({
                "pcbf1_wind_max_mph": _mph(agg_num(day, "WSPD", "max")),
                "pcbf1_gust_max_mph": _mph(agg_num(day, "GST", "max")),
                "pcbf1_air_temp_max_f": _f(agg_num(day, "ATMP", "max")),
                "pcbf1_air_temp_min_f": _f(agg_num(day, "ATMP", "min")),
                "pcbf1_water_temp_mean_f": _f(agg_num(day, "WTMP", "mean")),
                "pcbf1_pressure_min_mb": agg_num(day, "PRES", "min"),
            })
        else:
            row.update({
                "ndbc42039_wave_max_ft": _ft(agg_num(day, "WVHT", "max")),
                "ndbc42039_wave_mean_ft": _ft(agg_num(day, "WVHT", "mean")),
                "ndbc42039_dominant_period_max_s": agg_num(day, "DPD", "max"),
                "ndbc42039_average_period_mean_s": agg_num(day, "APD", "mean"),
                "ndbc42039_wind_max_mph": _mph(agg_num(day, "WSPD", "max")),
                "ndbc42039_gust_max_mph": _mph(agg_num(day, "GST", "max")),
                "ndbc42039_water_temp_mean_f": _f(agg_num(day, "WTMP", "mean")),
                "ndbc42039_pressure_min_mb": agg_num(day, "PRES", "min"),
            })
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    frames = []
    for station, meta in STATIONS.items():
        d = _fetch_station(station, meta["start_year"])
        if len(d):
            keep = [c for c in ["station", "observed_utc", "observed_local", "date", "WDIR", "WSPD", "GST", "WVHT", "DPD", "APD", "MWD", "PRES", "ATMP", "WTMP", "DEWP", "source_url"] if c in d.columns]
            frames.append(d[keep])
    if not frames:
        raise RuntimeError("No NDBC measured observations could be retrieved.")

    obs = pd.concat(frames, ignore_index=True, sort=False).sort_values(["station", "observed_utc"])
    obs.to_csv(DATA / "ndbc_measured_observations.csv", index=False)

    local = _agg_station(obs, "PCBF1")
    offshore = _agg_station(obs, "42039")
    if local.empty:
        daily = offshore
    elif offshore.empty:
        daily = local
    else:
        daily = local.merge(offshore, on="date", how="outer")
    daily = daily.sort_values("date")
    daily.to_csv(DATA / "ndbc_measured_daily.csv", index=False)

    availability = {}
    for station in STATIONS:
        s = obs[obs.station.eq(station)]
        availability[station] = {
            **STATIONS[station],
            "first_observation": str(s.date.min()) if len(s) else None,
            "last_observation": str(s.date.max()) if len(s) else None,
            "observations": int(len(s)),
            "days": int(s.date.nunique()) if len(s) else 0,
        }
    summary = {
        "source": "NOAA National Data Buoy Center quality-controlled historical standard meteorological files plus recent realtime2 observations",
        "stations": availability,
        "daily_rows": int(len(daily)),
        "units_note": "Published daily derived fields use mph, feet, degrees F, seconds, and millibars. Raw NDBC source observations are SI where applicable.",
        "quality_note": "Historical annual files are NDBC quality-controlled archives. Recent realtime2 values have undergone NDBC gross error checking only and should remain contextual until archived.",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (DATA / "ndbc_measured_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
