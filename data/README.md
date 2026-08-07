# Safe2Swim PCB data schema

## Evidence tables

- `flag_observations_archive.csv`: immutable parsed records from the supplied ALERTBAY/PCBFLAGS export.
- `flag_observations_auto.csv`: future automated observations. One snapshot is retained per day plus each detected status change.

## Derived tables

- `flag_daily_master.csv`: one row per observed day; `peak_flag` is the highest base severity seen that day and `latest_flag` is the last observed base status. `purple_any` is tracked separately.
- `environmental_daily.csv`: one environmental feature row per observed flag day. `data_quality` is either `provisional` or `finalized`.
- `model_training.csv`: only finalized flag days joined to finalized environmental rows.
- `model_metrics.json`: time-aware validation and standardized feature associations when minimum sample thresholds are met.

## Flag severity encoding

1 = Green, 2 = Yellow, 3 = Single Red, 4 = Double Red. Purple is an overlay and is not treated as a higher numeric base severity.
