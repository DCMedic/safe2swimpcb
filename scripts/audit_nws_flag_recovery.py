#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
import pandas as pd

try:
    from .common import DATA, FLAG_SEVERITY
except ImportError:
    from common import DATA, FLAG_SEVERITY


def main():
    primary = pd.read_csv(DATA / "flag_observations_master.csv")
    nws = pd.read_csv(DATA / "nws_flag_recovery.csv")
    primary = primary[primary["base_flag"].isin(FLAG_SEVERITY)].copy()
    nws = nws[nws["bay_flag"].isin(FLAG_SEVERITY)].copy()

    rows = []
    p_dates = set(primary["date"].astype(str))
    n_dates = set(nws["date"].astype(str))
    overlap = sorted(p_dates & n_dates)

    for dt in overlap:
        p = primary[primary["date"].astype(str) == dt].copy().sort_values(["time", "observed_at"])
        n = nws[nws["date"].astype(str) == dt].copy().sort_values("issued_utc")
        p_flags = list(dict.fromkeys(p["base_flag"].astype(str).tolist()))
        n_flags = list(dict.fromkeys(n["bay_flag"].astype(str).tolist()))
        p_latest = p.iloc[-1]["base_flag"]
        n_latest = n.iloc[-1]["bay_flag"]
        p_peak = max(p_flags, key=lambda x: FLAG_SEVERITY[x])
        n_peak = max(n_flags, key=lambda x: FLAG_SEVERITY[x])
        rows.append({
            "date": dt,
            "primary_flags": " | ".join(p_flags),
            "nws_flags": " | ".join(n_flags),
            "primary_latest": p_latest,
            "nws_latest": n_latest,
            "primary_peak": p_peak,
            "nws_peak": n_peak,
            "latest_match": bool(p_latest == n_latest),
            "peak_match": bool(p_peak == n_peak),
            "any_flag_match": bool(set(p_flags) & set(n_flags)),
            "primary_updates": int(len(p)),
            "nws_explicit_reports": int(len(n)),
        })

    audit = pd.DataFrame(rows)
    audit.to_csv(DATA / "nws_flag_overlap_audit.csv", index=False)

    earliest_primary = str(primary["date"].min()) if len(primary) else None
    candidate_dates = sorted(n_dates - p_dates)
    pre_primary = [d for d in candidate_dates if earliest_primary and d < earliest_primary]
    summary = {
        "primary_flag_days": int(len(p_dates)),
        "nws_explicit_bay_flag_days": int(len(n_dates)),
        "overlap_days": int(len(overlap)),
        "candidate_additional_days_not_in_primary": int(len(candidate_dates)),
        "candidate_days_before_primary_archive": int(len(pre_primary)),
        "earliest_primary_date": earliest_primary,
        "earliest_nws_flag_date": str(nws["date"].min()) if len(nws) else None,
        "latest_nws_flag_date": str(nws["date"].max()) if len(nws) else None,
        "latest_flag_agreement_pct": round(100 * audit["latest_match"].mean(), 2) if len(audit) else None,
        "peak_flag_agreement_pct": round(100 * audit["peak_match"].mean(), 2) if len(audit) else None,
        "any_flag_agreement_pct": round(100 * audit["any_flag_match"].mean(), 2) if len(audit) else None,
        "latest_mismatch_days": int((~audit["latest_match"]).sum()) if len(audit) else 0,
        "peak_mismatch_days": int((~audit["peak_match"]).sum()) if len(audit) else 0,
        "method": "Primary ALERTBAY/PCBFLAGS observations are compared with explicit Bay flag reports recovered from NWS Tallahassee SRFTAE products. Latest and peak status are compared per calendar date; no recovered records are merged by this audit.",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (DATA / "nws_flag_overlap_audit.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
