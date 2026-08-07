# Safe2Swim PCB data schema

## Evidence tables

- `flag_observations_archive.csv`: immutable parsed records from the supplied ALERTBAY/PCBFLAGS export. This is the primary historical evidence tier.
- `flag_observations_auto.csv`: future automated Safe2Swim observations. One snapshot is retained per day plus each detected status change. This is also a primary evidence tier.
- `flag_observations_recovered.csv`: audited secondary observations recovered from explicit `Bay` flag reports in NWS Tallahassee `SRFTAE` products. A recovered row is included only when that date is absent from both primary sources. Each row retains its NWS/IEM product ID, URL, and `record_tier=recovered` provenance.
- `nws_flag_recovery.csv`: parsed explicit Bay flag reports before the non-overlap promotion rule is applied.
- `nws_srf_observations.csv`: parsed NWS Tallahassee Surf Zone Forecast products, including flag reports when present plus rip-current risk, surf, water temperature, winds, and related fields.
- `nws_srf_daily.csv`: representative daily NWS surf-zone context.

## Recovery quality-control tables

- `nws_srf_summary.json`: coverage and product counts for the recovered NWS surf-zone archive.
- `nws_flag_overlap_audit.csv`: date-by-date comparison of recovered NWS Bay flags against primary PCBFLAGS/Safe2Swim observations on overlapping dates.
- `nws_flag_overlap_audit.json`: summary agreement statistics for that audit.
- `flag_recovery_summary.json`: counts, date range, flag mix, and provenance policy for observations actually promoted into the recovered tier.

## Derived tables

- `flag_observations_master.csv` / `.json`: unified primary and recovered observations with explicit `record_tier` and source provenance. Primary records always take precedence on overlap.
- `flag_daily_master.csv` / `.json`: one row per observed/recovered day; `peak_flag` is the highest base severity seen that day and `latest_flag` is the last observed base status. `record_tier` identifies primary versus recovered-only days.
- `flag_summary.json`: current coverage and provenance-aware historical summary.
- `environmental_daily.csv`: one environmental feature row per observed flag day. `data_quality` is either `provisional` or `finalized`.
- `model_training.csv`: finalized daily flag records joined to finalized environmental rows.
- `model_metrics.json`: time-aware validation and standardized feature associations when minimum sample thresholds are met.

## Flag severity and Purple handling

1 = Green, 2 = Yellow, 3 = Single Red, 4 = Double Red. Purple is an independent dangerous-marine-life overlay and is not treated as a higher numeric base severity.

Primary PCBFLAGS/Safe2Swim records have reliable Purple reporting. Recovered NWS records retain Purple when explicitly reported, but an NWS record that does not mention Purple is marked `purple_known=false`; absence of a Purple mention is not interpreted as evidence that no Purple flag was posted. Purple frequencies therefore use only records with reliable Purple status.
