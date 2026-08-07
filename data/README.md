# Safe2Swim PCB data schema

## Evidence tables

- `flag_observations_archive.csv`: immutable parsed records from the supplied ALERTBAY/PCBFLAGS export. This is the primary historical evidence tier.
- `flag_observations_auto.csv`: future automated Safe2Swim observations. One snapshot is retained per day plus each detected status change. This is also a primary evidence tier.
- `flag_observations_recovered.csv`: audited secondary observations recovered from explicit `Bay` flag reports in NWS Tallahassee `SRFTAE` products. A recovered row is included only when that date is absent from both primary sources. Each row retains its NWS/IEM product ID, URL, and `record_tier=recovered` provenance.
- `nws_flag_recovery.csv`: parsed explicit Bay flag reports before the non-overlap promotion rule is applied.
- `nws_srf_observations.csv`: parsed NWS Tallahassee Surf Zone Forecast products, including flag reports when present plus rip-current risk, surf, water temperature, winds, and related fields.
- `nws_srf_daily.csv`: representative daily NWS surf-zone context.

## Recovery quality-control and candidate tables

- `nws_srf_summary.json`: coverage and product counts for the recovered NWS surf-zone archive.
- `nws_flag_overlap_audit.csv`: date-by-date comparison of recovered NWS Bay flags against primary PCBFLAGS/Safe2Swim observations on overlapping dates.
- `nws_flag_overlap_audit.json`: summary agreement statistics for that audit.
- `flag_recovery_summary.json`: counts, date range, flag mix, and provenance policy for observations actually promoted into the recovered tier.
- `pre2017_flag_candidates.csv`: unverified candidate observations found while searching archived copies of official PCB current-condition pages. These are discovery records only and are never promoted automatically.
- `pre2017_flag_hunt_summary.json`: search coverage, candidate counts, archive errors, and the next source families targeted for pre-2017 recovery.
- `westendpcb_flag_posts.csv`: explicitly dated historical Panama City Beach flag-status post titles indexed by the independent local West End PCB site.
- `pre2017_westendpcb_candidates.csv`: pre-2017 West End PCB records preserved as community-mirror candidates only.
- `westendpcb_flag_overlap_audit.csv`: comparison of later West End PCB posts against dates already represented by primary or NWS-recovered Safe2Swim evidence.
- `westendpcb_flag_summary.json`: counts, date coverage, overlap agreement, and evidence policy for the community-mirror source.

## Measured NOAA / NDBC tables

- `ndbc_measured_daily.csv`: derived daily measured fields from local station `PCBF1` / NOAA NOS `8729210` and offshore NDBC buoy `42039`, including local wind/gust/air/water temperature/pressure and offshore significant wave height/period/wind/water temperature.
- `ndbc_measured_summary.json`: station metadata, measured coverage, source URL patterns, source/quality notes, and refresh time.

Safe2Swim does **not** mirror the full timestamp-level NDBC archive into GitHub. Raw observations remain at NOAA/NDBC as the authoritative upstream source. The enrichment job reads those observations in memory and publishes compact daily derived features plus source metadata. Historical annual NDBC standard-meteorological files are quality-controlled; recent `realtime2` observations have undergone NDBC gross-error checking only and should be treated as provisional context until archived.

## Tropical-cyclone tables

- `tropical_cyclone_track_points_near_pcb.csv`: Atlantic HURDAT2 six-hourly best-track points within 500 miles of the Safe2Swim PCB reference point.
- `tropical_cyclone_events_near_pcb.csv`: one row per Atlantic tropical cyclone passing within 500 miles, including closest approach and intensity context.
- `tropical_cyclone_daily.csv`: one row per local calendar day with a tropical cyclone within 500 miles, including nearest storm, minimum distance, maximum nearby wind, and 50/100/200/300/500-mile proximity indicators.
- `tropical_cyclone_summary.json`: HURDAT2 source version, coverage, counts, and methodology.

HURDAT2 is retrospective best-track history, not a forecast. Cyclone-history variables are published for retrospective association analysis and are not automatically used as operational prediction features.

## Derived tables

- `flag_observations_master.csv` / `.json`: unified primary and recovered observations with explicit `record_tier` and source provenance. Primary records always take precedence on overlap.
- `flag_daily_master.csv` / `.json`: one row per observed/recovered day; `peak_flag` is the highest base severity seen that day and `latest_flag` is the last observed base status. `record_tier` identifies primary versus recovered-only days.
- `flag_summary.json`: current coverage and provenance-aware historical summary.
- `environmental_daily.csv`: one environmental feature row per observed flag day. `data_quality` is either `provisional` or `finalized`.
- `model_training.csv`: finalized daily flag records joined to finalized reanalysis environmental rows plus any available measured NDBC and retrospective cyclone context.
- `model_metrics.json`: time-aware validation and standardized feature associations. The operational feature set remains the reproducible environmental/reanalysis feature set; measured and retrospective cyclone fields are retained for research until separately validated.

## Flag severity and Purple handling

1 = Green, 2 = Yellow, 3 = Single Red, 4 = Double Red. Purple is an independent dangerous-marine-life overlay and is not treated as a higher numeric base severity.

Primary PCBFLAGS/Safe2Swim records have reliable Purple reporting. Recovered NWS records retain Purple when explicitly reported, but an NWS record that does not mention Purple is marked `purple_known=false`; absence of a Purple mention is not interpreted as evidence that no Purple flag was posted. Purple frequencies therefore use only records with reliable Purple status.
