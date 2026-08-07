#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
import pandas as pd

try:
    from .common import DATA, FLAG_SEVERITY
except ImportError:
    from common import DATA, FLAG_SEVERITY

OUT_COLS = [
    "observed_at", "date", "time", "base_flag", "purple_overlay", "purple_known",
    "flag_label", "severity", "source", "source_url", "observation_type", "message",
    "source_file", "source_product_id", "record_tier",
]


def as_bool(v) -> bool:
    return v is True or str(v).strip().lower() == "true"


def main():
    archive = pd.read_csv(DATA / "flag_observations_archive.csv")
    auto_path = DATA / "flag_observations_auto.csv"
    auto = pd.read_csv(auto_path) if auto_path.exists() and auto_path.stat().st_size else pd.DataFrame()
    nws = pd.read_csv(DATA / "nws_flag_recovery.csv")

    primary_dates = set(archive["date"].astype(str))
    if len(auto) and "date" in auto:
        primary_dates |= set(auto["date"].astype(str))

    candidates = nws[
        nws["bay_flag"].isin(FLAG_SEVERITY) & ~nws["date"].astype(str).isin(primary_dates)
    ].copy().sort_values(["date", "issued_utc"])

    rows = []
    for _, r in candidates.iterrows():
        base = str(r["bay_flag"])
        purple = as_bool(r.get("bay_purple_overlay", False))
        state_flag = r.get("state_park_flag")
        risk = r.get("rip_current_risk")
        surf = r.get("surf_height_text")
        details = [f"NWS SRFTAE explicit Bay beach flag report: {base}{' + Purple' if purple else ''}."]
        if pd.notna(state_flag) and str(state_flag).strip():
            details.append(f"State Park Gulf Beaches: {state_flag}.")
        if pd.notna(risk) and str(risk).strip():
            details.append(f"Rip Current Risk: {risk}.")
        if pd.notna(surf) and str(surf).strip():
            details.append(f"Surf Height: {surf}")
        rows.append({
            "observed_at": r["issued_local"],
            "date": str(r["date"]),
            "time": str(r["time_local"]),
            "base_flag": base,
            "purple_overlay": purple,
            "purple_known": True,
            "flag_label": base + (" + Purple" if purple else ""),
            "severity": FLAG_SEVERITY[base],
            "source": "NWS Tallahassee SRFTAE recovered Bay flag via IEM",
            "source_url": r["source_url"],
            "observation_type": "recovered_nws_srf_flag",
            "message": " ".join(details),
            "source_file": "",
            "source_product_id": r["source_product_id"],
            "record_tier": "recovered",
        })

    out = pd.DataFrame(rows, columns=OUT_COLS)
    out.to_csv(DATA / "flag_observations_recovered.csv", index=False)

    counts = out["base_flag"].value_counts().to_dict() if len(out) else {}
    summary = {
        "record_tier": "recovered",
        "source": "NWS Tallahassee SRFTAE explicit Bay flag reports via Iowa Environmental Mesonet",
        "selection_rule": "Only NWS Bay flag reports from dates absent from both the immutable ALERTBAY/PCBFLAGS archive and automatic Safe2Swim observations are promoted. Primary records always win on overlap.",
        "observations": int(len(out)),
        "days": int(out["date"].nunique()) if len(out) else 0,
        "start": str(out["date"].min()) if len(out) else None,
        "end": str(out["date"].max()) if len(out) else None,
        "purple_observations": int(out["purple_overlay"].map(as_bool).sum()) if len(out) else 0,
        "flag_counts": {str(k): int(v) for k, v in counts.items()},
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "caution": "Recovered records are strong secondary evidence, not replacements for original PCBFLAGS messages. Each row retains its source product URL and record tier.",
    }
    (DATA / "flag_recovery_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
