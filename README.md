# Safe2Swim PCB

Public single-page dashboard for **safe2swimpcb.com**. It combines a user-supplied ALERTBAY/PCBFLAGS historical archive with automatically collected future PCB flag snapshots, Open-Meteo weather/wave context, NOAA tide predictions, and a modeling-ready finalized dataset.

## Data lifecycle

1. `flag_observations_archive.csv` is immutable historical evidence from the supplied archive.
2. `poll-current-flag.yml` checks the public PCB current-conditions page every 30 minutes from 06:00–22:59 America/Chicago. It logs the first observation of each day and any detected flag change.
3. `daily-refresh.yml` builds one daily flag row, enriches observed flag days with weather/wave/tide data, and marks recent environmental rows `provisional`.
4. After the ERA5/ERA5-Ocean lag has passed, provisional environmental rows are replaced with `finalized` reanalysis rows.
5. Only finalized rows enter `model_training.csv`.

## Safety design

The current official flag is visually separated from all historical statistics and research-model output. Predictions never override posted flags.

See `DEPLOYMENT.md` for the GitHub Actions-based Pages deployment, custom-domain verification, DNS setup, HTTPS, and first-run automation procedure.
