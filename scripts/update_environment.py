#!/usr/bin/env python3
from __future__ import annotations

import calendar
from datetime import timedelta

import pandas as pd
import requests

try:
    from .common import DATA, get_json, now_local
except ImportError:
    from common import DATA, get_json, now_local

LAT, LON = 30.125, -85.730
STATION = "8729136"
OPEN_METEO_TIMEOUT = 20
COLS = [
    "date",
    "data_quality",
    "weather_source",
    "marine_source",
    "tide_source",
    "temp_max_f",
    "temp_min_f",
    "precip_in",
    "wind_max_mph",
    "gust_max_mph",
    "wind_dir_deg",
    "wave_max_ft",
    "wave_dir_deg",
    "wave_period_s",
    "swell_max_ft",
    "swell_dir_deg",
    "swell_period_s",
    "tide_low_ft",
    "tide_high_ft",
    "tide_range_ft",
    "updated_at",
]


def weather(start: str, end: str, final: bool) -> pd.DataFrame:
    if final:
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": LAT,
            "longitude": LON,
            "start_date": start,
            "end_date": end,
            "models": "era5",
            "daily": (
                "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                "wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant"
            ),
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "America/Chicago",
        }
        source = "Open-Meteo ERA5"
    else:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": LAT,
            "longitude": LON,
            "past_days": 7,
            "forecast_days": 1,
            "daily": (
                "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                "wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant"
            ),
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "America/Chicago",
        }
        source = "Open-Meteo forecast/archive window"

    daily = get_json(url, params, timeout=OPEN_METEO_TIMEOUT)["daily"]
    return pd.DataFrame(
        {
            "date": daily["time"],
            "temp_max_f": daily["temperature_2m_max"],
            "temp_min_f": daily["temperature_2m_min"],
            "precip_in": daily["precipitation_sum"],
            "wind_max_mph": daily["wind_speed_10m_max"],
            "gust_max_mph": daily["wind_gusts_10m_max"],
            "wind_dir_deg": daily["wind_direction_10m_dominant"],
            "weather_source": source,
        }
    )


def marine(start: str, end: str, final: bool) -> pd.DataFrame:
    params = {
        "latitude": LAT,
        "longitude": LON,
        "daily": (
            "wave_height_max,wave_direction_dominant,wave_period_max,"
            "swell_wave_height_max,swell_wave_direction_dominant,swell_wave_period_max"
        ),
        "length_unit": "imperial",
        "timezone": "America/Chicago",
    }
    if final:
        params["start_date"] = start
        params["end_date"] = end
        params["models"] = "era5_ocean"
        source = "Open-Meteo ERA5-Ocean"
    else:
        params["past_days"] = 7
        params["forecast_days"] = 1
        source = "Open-Meteo best-match marine"

    daily = get_json(
        "https://marine-api.open-meteo.com/v1/marine",
        params,
        timeout=OPEN_METEO_TIMEOUT,
    )["daily"]
    return pd.DataFrame(
        {
            "date": daily["time"],
            "wave_max_ft": daily["wave_height_max"],
            "wave_dir_deg": daily["wave_direction_dominant"],
            "wave_period_s": daily["wave_period_max"],
            "swell_max_ft": daily["swell_wave_height_max"],
            "swell_dir_deg": daily["swell_wave_direction_dominant"],
            "swell_period_s": daily["swell_wave_period_max"],
            "marine_source": source,
        }
    )


def tides_for_dates(dates: list[str]) -> pd.DataFrame:
    date_series = pd.to_datetime(pd.Series(sorted(set(dates))))
    groups: dict[tuple[int, int], list[str]] = {}
    for value in date_series:
        groups.setdefault((value.year, value.month), []).append(value.strftime("%Y-%m-%d"))

    rows = []
    for (year, month), wanted in groups.items():
        last = calendar.monthrange(year, month)[1]
        begin = f"{year}{month:02d}01"
        end = f"{year}{month:02d}{last:02d}"
        payload = get_json(
            "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter",
            {
                "begin_date": begin,
                "end_date": end,
                "station": STATION,
                "product": "predictions",
                "datum": "MLLW",
                "time_zone": "lst_ldt",
                "interval": "hilo",
                "units": "english",
                "application": "Safe2SwimPCB",
                "format": "json",
            },
            timeout=60,
        )
        predictions = pd.DataFrame(payload.get("predictions", []))
        if predictions.empty:
            continue
        predictions["date"] = predictions["t"].str.slice(0, 10)
        predictions["v"] = pd.to_numeric(predictions["v"], errors="coerce")
        for day, group in predictions[predictions.date.isin(wanted)].groupby("date"):
            low = float(group.v.min())
            high = float(group.v.max())
            rows.append(
                {
                    "date": day,
                    "tide_low_ft": low,
                    "tide_high_ft": high,
                    "tide_range_ft": high - low,
                    "tide_source": "NOAA CO-OPS 8729136 predictions",
                }
            )
    return pd.DataFrame(rows)


def upsert(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if old.empty:
        return new
    old = old[~old.date.isin(set(new.date))]
    return pd.concat([old, new], ignore_index=True)


def refresh_dates(
    old: pd.DataFrame,
    dates: list[str],
    *,
    final: bool,
) -> pd.DataFrame:
    if not dates:
        return old

    start, end = min(dates), max(dates)
    quality = "finalized" if final else "provisional"
    try:
        weather_rows = weather(start, end, final)
        marine_rows = marine(start, end, final)
        tide_rows = tides_for_dates(dates)
    except requests.RequestException as exc:
        # Environmental enrichment is ancillary research context. A transient
        # upstream transport failure must not abort the entire daily pipeline
        # or overwrite the last good row. Finalization will be retried on the
        # next cycle, while schema/contract errors still fail loudly.
        print(
            f"WARNING: {quality} environmental refresh deferred for "
            f"{start}..{end}: {type(exc).__name__}: {exc}"
        )
        return old

    new = (
        pd.DataFrame({"date": dates})
        .merge(weather_rows, on="date", how="left")
        .merge(marine_rows, on="date", how="left")
        .merge(tide_rows, on="date", how="left")
    )
    new["data_quality"] = quality
    new["updated_at"] = now_local().isoformat()
    return upsert(old, new)


def main() -> None:
    flags = pd.read_csv(DATA / "flag_daily_master.csv")
    dates = sorted(flags.date.astype(str).unique())
    today = now_local().date()
    cutoff = (today - timedelta(days=6)).isoformat()
    final_dates = [day for day in dates if day <= cutoff]
    recent_dates = [day for day in dates if day > cutoff]

    try:
        old = pd.read_csv(DATA / "environmental_daily.csv")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        old = pd.DataFrame(columns=COLS)

    finalized = set(
        old.loc[old.data_quality.eq("finalized"), "date"].astype(str)
        if "data_quality" in old.columns and "date" in old.columns
        else []
    )
    final_need = [day for day in final_dates if day not in finalized]

    # Preserve provisional/last-known rows if reanalysis sources are
    # temporarily unreachable; never relabel forecast data as finalized ERA5.
    old = refresh_dates(old, final_need, final=True)

    # Recent observed flag days get provisional context and are replaced later.
    old = refresh_dates(old, recent_dates, final=False)

    for column in COLS:
        if column not in old:
            old[column] = None

    old[COLS].sort_values("date").to_csv(DATA / "environmental_daily.csv", index=False)
    print(
        "environment rows",
        len(old),
        "finalized",
        sum(old.data_quality.eq("finalized")),
    )


if __name__ == "__main__":
    main()
