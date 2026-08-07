#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
import re
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import pandas as pd

try:
    from .common import DATA, TZ, session
except ImportError:
    from common import DATA, TZ, session

IEM_RETRIEVE = "https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py"
IEM_VIEW = "https://mesonet.agron.iastate.edu/p.php?pid={}"
PIL = "SRFTAE"
DEFAULT_START = date(2008, 1, 1)

FLAG_MAP = {
    "green": "Green",
    "yellow": "Yellow",
    "red": "Single Red",
    "single red": "Single Red",
    "double red": "Double Red",
}
RISK_SCORE = {"Low": 1, "Moderate": 2, "High": 3}


def _normalize_flag(value: str | None) -> str | None:
    if not value:
        return None
    v = re.sub(r"[.\s]+$", "", value.strip()).lower()
    if "not available" in v or v in {"n/a", "na"}:
        return None
    for key in ("double red", "single red", "yellow", "green", "red"):
        if key in v:
            return FLAG_MAP[key]
    return None


def _flag_entry(text: str, label: str) -> tuple[str | None, bool]:
    """Return base flag and Purple overlay from one NWS beach-official line.

    NWS products may use values such as "Yellow and Purple". Purple is an
    independent dangerous-marine-life overlay, so it is retained separately.
    """
    m = re.search(rf"(?mi)^\s*{re.escape(label)}\s*\.*\s*(.+?)\s*$", text)
    if not m:
        return None, False
    raw = re.sub(r"[.\s]+$", "", m.group(1).strip())
    if not raw or "not available" in raw.lower():
        return None, False
    return _normalize_flag(raw), bool(re.search(r"\bpurple\b", raw, re.I))


def _coastal_bay_section(text: str) -> str:
    m = re.search(
        r"(?ms)^FLZ112-[^\n]*\n.*?Coastal Bay-?\s*\n(.*?)(?=^\$\$|^FLZ\d{3}-|\Z)",
        text,
    )
    if m:
        return m.group(1)
    m = re.search(
        r"(?ms)Coastal Bay-?\s*\n(.*?)(?=^\$\$|^FLZ\d{3}-|\Z)",
        text,
    )
    return m.group(1) if m else ""


def _today_block(section: str) -> str:
    if not section:
        return ""
    m = re.search(
        r"(?ms)^\s*\.(?:REST OF TODAY|TODAY)\.\.\.\s*(.*?)(?=^\s*\.[A-Z][A-Z ]+\.\.\.|^\s*&&|\Z)",
        section,
    )
    return m.group(1) if m else section


def _field(block: str, label_regex: str) -> str | None:
    m = re.search(rf"(?mi)^\s*{label_regex}\.*\s*(.+?)\s*$", block)
    return m.group(1).strip() if m else None


def _numbers(value: str | None) -> list[float]:
    if not value:
        return []
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", value)]


def _surf_bounds(value: str | None) -> tuple[float | None, float | None]:
    nums = _numbers(value)
    if not nums:
        return None, None
    if len(nums) == 1:
        return nums[0], nums[0]
    return min(nums[:2]), max(nums[:2])


def _max_number(value: str | None) -> float | None:
    nums = _numbers(value)
    return max(nums) if nums else None


def _first_number(value: str | None) -> float | None:
    nums = _numbers(value)
    return nums[0] if nums else None


def _product_id(filename: str, issued_utc: datetime, text: str) -> str:
    stem = Path(filename).name
    for suffix in (".txt", ".TXT"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    if re.match(r"^\d{12}-[A-Z0-9]{4}-[A-Z0-9]{6}-[A-Z0-9]{3,6}", stem):
        return stem
    wmo = re.search(r"(?m)^([A-Z]{4}\d{2})\s+(KTAE)\s+\d{6}\s*$", text)
    return f"{issued_utc:%Y%m%d%H%M}-KTAE-{wmo.group(1) if wmo else 'FZUS52'}-{PIL}"


def parse_product(filename: str, text: str) -> dict | None:
    tm = re.search(r"(\d{12})", Path(filename).name)
    if not tm:
        return None
    try:
        issued_utc = datetime.strptime(tm.group(1), "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    issued_local = issued_utc.astimezone(TZ)
    product_id = _product_id(filename, issued_utc, text)

    bay_flag, bay_purple = _flag_entry(text, "Bay")
    state_flag, state_purple = _flag_entry(text, "State Park Gulf Beaches")
    section = _coastal_bay_section(text)
    block = _today_block(section)

    risk = _field(block, r"Rip Current Risk")
    if risk:
        risk_match = re.search(r"\b(Low|Moderate|High)\b", risk, re.I)
        risk = risk_match.group(1).title() if risk_match else risk
    surf = _field(block, r"Surf Height")
    uv = _field(block, r"UV Index\*\*")
    water = _field(block, r"Water Temperature")
    high_temp = _field(block, r"High Temperature")
    winds = _field(block, r"Winds")
    surf_min, surf_max = _surf_bounds(surf)

    if not any([bay_flag, state_flag, section]):
        return None

    return {
        "issued_utc": issued_utc.isoformat(),
        "issued_local": issued_local.isoformat(),
        "date": issued_local.date().isoformat(),
        "time_local": issued_local.strftime("%H:%M"),
        "bay_flag": bay_flag,
        "bay_purple_overlay": bay_purple,
        "state_park_flag": state_flag,
        "state_park_purple_overlay": state_purple,
        "rip_current_risk": risk,
        "rip_current_risk_score": RISK_SCORE.get(risk),
        "surf_height_text": surf,
        "surf_height_min_ft": surf_min,
        "surf_height_max_ft": surf_max,
        "uv_index_category": uv,
        "water_temperature_f": _first_number(water),
        "high_temperature_text": high_temp,
        "winds_text": winds,
        "wind_speed_max_mph": _max_number(winds),
        "source_product_id": product_id,
        "source_url": IEM_VIEW.format(quote(product_id)),
        "source": "NWS Tallahassee SRFTAE via Iowa Environmental Mesonet archive",
    }


def _fetch_range(start: date, end_exclusive: date) -> list[dict]:
    params = {
        "limit": 9999,
        "pil": PIL,
        "fmt": "zip",
        "sdate": f"{start.isoformat()}T00:00Z",
        "edate": f"{end_exclusive.isoformat()}T00:00Z",
        "order": "asc",
    }
    r = session().get(IEM_RETRIEVE, params=params, timeout=240)
    r.raise_for_status()
    bio = io.BytesIO(r.content)
    if not zipfile.is_zipfile(bio):
        return []
    rows: list[dict] = []
    with zipfile.ZipFile(bio) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            try:
                text = zf.read(name).decode("utf-8", errors="replace")
            except Exception:
                continue
            row = parse_product(name, text)
            if row:
                rows.append(row)
    return rows


def _date_windows(start: date, end: date):
    cur = start
    while cur <= end:
        nxt = date(cur.year + 1, 1, 1)
        stop = min(nxt, end + timedelta(days=1))
        yield cur, stop
        cur = stop


def _representative_daily(obs: pd.DataFrame) -> pd.DataFrame:
    if obs.empty:
        return pd.DataFrame()
    out = []
    for dt, g in obs.groupby("date", sort=True):
        g = g.sort_values("issued_utc")
        flagged = g[g["bay_flag"].notna()]
        usable = g[g["rip_current_risk"].notna()]
        rep = (flagged.iloc[-1] if len(flagged) else usable.iloc[-1] if len(usable) else g.iloc[-1]).to_dict()
        rep["n_products"] = int(len(g))
        rep["n_explicit_flag_reports"] = int(g["bay_flag"].notna().sum())
        out.append(rep)
    return pd.DataFrame(out).sort_values("date")


def _flag_recovery(obs: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "issued_utc", "issued_local", "date", "time_local", "bay_flag", "bay_purple_overlay",
        "state_park_flag", "state_park_purple_overlay", "rip_current_risk", "surf_height_text",
        "water_temperature_f", "winds_text", "source_product_id", "source_url", "source",
    ]
    if obs.empty:
        return pd.DataFrame(columns=cols)
    f = obs[obs["bay_flag"].notna()].sort_values(["date", "issued_utc"]).copy()
    keep = []
    for _, g in f.groupby("date", sort=True):
        last = None
        for idx, row in g.iterrows():
            state = (row["bay_flag"], bool(row.get("bay_purple_overlay", False)))
            if state != last:
                keep.append(idx)
                last = state
    return f.loc[keep, cols].reset_index(drop=True) if keep else pd.DataFrame(columns=cols)


def main():
    obs_path = DATA / "nws_srf_observations.csv"
    existing = pd.read_csv(obs_path) if obs_path.exists() and obs_path.stat().st_size else pd.DataFrame()

    full = os.getenv("NWS_SRF_FULL_BACKFILL", "0") == "1" or existing.empty
    if full:
        start = DEFAULT_START
    else:
        last = pd.to_datetime(existing["issued_utc"], utc=True, errors="coerce").max()
        start = (last.date() - timedelta(days=3)) if pd.notna(last) else DEFAULT_START
    end = date.today()

    fetched: list[dict] = []
    for a, b in _date_windows(start, end):
        print(f"fetching {PIL}: {a} through {b - timedelta(days=1)}")
        fetched.extend(_fetch_range(a, b))

    new = pd.DataFrame(fetched)
    if full:
        # A full parser refresh intentionally replaces prior derived rows so schema/parser upgrades
        # are applied consistently across the complete archive.
        obs = new
    elif existing.empty:
        obs = new
    elif new.empty:
        obs = existing
    else:
        obs = pd.concat([existing, new], ignore_index=True)
    if obs.empty:
        raise RuntimeError("No NWS SRFTAE products were recovered.")

    obs = obs.drop_duplicates(subset=["source_product_id"], keep="last").sort_values("issued_utc")
    obs.to_csv(obs_path, index=False)

    daily = _representative_daily(obs)
    daily.to_csv(DATA / "nws_srf_daily.csv", index=False)
    recovery = _flag_recovery(obs)
    recovery.to_csv(DATA / "nws_flag_recovery.csv", index=False)

    summary = {
        "source": "National Weather Service Tallahassee SRFTAE, retrieved from the Iowa Environmental Mesonet NWS text-product archive",
        "retrieval_endpoint": IEM_RETRIEVE,
        "archive_start_requested": DEFAULT_START.isoformat(),
        "first_product_date": str(obs["date"].min()),
        "last_product_date": str(obs["date"].max()),
        "products_parsed": int(len(obs)),
        "daily_records": int(len(daily)),
        "days_with_explicit_bay_flag": int(recovery["date"].nunique()) if len(recovery) else 0,
        "explicit_bay_flag_observations": int(len(recovery)),
        "days_with_explicit_bay_purple": int(recovery.loc[recovery["bay_purple_overlay"].astype(str).str.lower().eq("true"), "date"].nunique()) if len(recovery) else 0,
        "note": "Supplemental research source. Explicit Bay flag reports come from NWS products stating they were based on communication with area beach officials. Purple is preserved when the NWS line explicitly includes it. This dataset remains provenance-labeled and never overwrites original ALERTBAY/PCBFLAGS evidence.",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (DATA / "nws_srf_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
