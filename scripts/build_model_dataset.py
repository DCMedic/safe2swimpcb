#!/usr/bin/env python3
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit

try:
    from .common import DATA
except ImportError:
    from common import DATA

# Primary model features intentionally remain operationally reproducible reanalysis/context fields.
# Measured NDBC and retrospective HURDAT2 fields are joined into model_training.csv for research,
# but are not automatically promoted into the predictive feature set.
RAW = [
    'precip_in','wind_max_mph','gust_max_mph','wave_max_ft','wave_period_s',
    'swell_max_ft','swell_period_s','tide_range_ft','season_sin','season_cos',
    'wind_dir_sin','wind_dir_cos'
]
LABEL = {
    'precip_in':'Rain','wind_max_mph':'Max wind','gust_max_mph':'Max gust',
    'wave_max_ft':'Wave height','wave_period_s':'Wave period','swell_max_ft':'Swell height',
    'swell_period_s':'Swell period','tide_range_ft':'Tide range','season_sin':'Season (sin)',
    'season_cos':'Season (cos)','wind_dir_sin':'Wind direction (sin)','wind_dir_cos':'Wind direction (cos)'
}

MEASURED_COLS = [
    'pcbf1_obs_count','pcbf1_wind_max_mph','pcbf1_gust_max_mph','pcbf1_air_temp_max_f',
    'pcbf1_air_temp_min_f','pcbf1_water_temp_mean_f','pcbf1_pressure_min_mb',
    '42039_obs_count','ndbc42039_wave_max_ft','ndbc42039_wave_mean_ft',
    'ndbc42039_dominant_period_max_s','ndbc42039_average_period_mean_s',
    'ndbc42039_wind_max_mph','ndbc42039_gust_max_mph','ndbc42039_water_temp_mean_f',
    'ndbc42039_pressure_min_mb'
]
CYCLONE_COLS = [
    'nearest_storm_id','nearest_storm_name','nearest_storm_status','nearest_storm_category',
    'tc_min_distance_mi','tc_max_wind_kt_within_500mi','tc_active_storms_within_500mi',
    'tc_within_50mi','tc_within_100mi','tc_within_200mi','tc_within_300mi','tc_within_500mi'
]


def optional_merge(d: pd.DataFrame, filename: str, columns: list[str]) -> pd.DataFrame:
    p = DATA / filename
    if not p.exists() or not p.stat().st_size:
        return d
    try:
        x = pd.read_csv(p)
    except Exception:
        return d
    if x.empty or 'date' not in x:
        return d
    keep = ['date'] + [c for c in columns if c in x.columns]
    return d.merge(x[keep].drop_duplicates('date', keep='last'), on='date', how='left')


def coverage(d: pd.DataFrame, cols: list[str]) -> dict:
    out = {}
    for c in cols:
        if c in d.columns:
            n = int(d[c].notna().sum())
            out[c] = {'rows': n, 'pct': round(100 * n / len(d), 1) if len(d) else 0.0}
    return out


def main():
    f = pd.read_csv(DATA / 'flag_daily_master.csv')
    e = pd.read_csv(DATA / 'environmental_daily.csv')
    e = e[e.data_quality.eq('finalized')]
    d = f[f.record_status.eq('finalized')].merge(e, on='date', how='inner').sort_values('date')

    d['peak_severity'] = pd.to_numeric(d.peak_severity, errors='coerce')
    d['red_or_worse'] = (d.peak_severity >= 3).astype(int)
    dt = pd.to_datetime(d.date)
    d['day_of_year'] = dt.dt.dayofyear
    d['season_sin'] = np.sin(2 * np.pi * d.day_of_year / 365.25)
    d['season_cos'] = np.cos(2 * np.pi * d.day_of_year / 365.25)
    r = np.deg2rad(pd.to_numeric(d.wind_dir_deg, errors='coerce'))
    d['wind_dir_sin'] = np.sin(r)
    d['wind_dir_cos'] = np.cos(r)
    sev_map = dict(zip(f.date.astype(str), pd.to_numeric(f.peak_severity, errors='coerce')))
    d['prev_day_severity'] = [
        sev_map.get((pd.to_datetime(x) - pd.Timedelta(days=1)).strftime('%Y-%m-%d'), np.nan)
        for x in d.date
    ]

    # Add measured and storm-history context without using it as an operational predictor by default.
    d = optional_merge(d, 'ndbc_measured_daily.csv', MEASURED_COLS)
    d = optional_merge(d, 'tropical_cyclone_daily.csv', CYCLONE_COLS)

    base_cols = [
        'date','red_or_worse','peak_severity','purple_any','record_tier','source_quality','month',
        'day_of_year','season_sin','season_cos','prev_day_severity','temp_max_f','temp_min_f',
        'precip_in','wind_max_mph','gust_max_mph','wind_dir_sin','wind_dir_cos','wave_max_ft',
        'wave_period_s','swell_max_ft','swell_period_s','tide_range_ft'
    ]
    cols = [c for c in base_cols + MEASURED_COLS + CYCLONE_COLS if c in d.columns]
    d[cols].to_csv(DATA / 'model_training.csv', index=False)

    context = {
        'measured_ndbc': coverage(d, MEASURED_COLS),
        'retrospective_tropical_cyclone': coverage(d, CYCLONE_COLS),
        'policy': 'Measured NDBC and HURDAT2 fields are retained in model_training.csv for research. HURDAT2 best-track fields are retrospective and are not included in the operational feature set.'
    }

    out = {
        'status':'insufficient_data',
        'n_training':int(len(d)),
        'positive_days':int(d.red_or_worse.sum()),
        'research_context':context,
        'note':'At least 300 finalized days and 50 red-or-worse days are required before publishing model validation.'
    }
    if len(d) >= 300 and d.red_or_worse.sum() >= 50 and d.red_or_worse.nunique() == 2:
        X = d[RAW]
        y = d.red_or_worse
        pipe = Pipeline([
            ('imp', SimpleImputer(strategy='median')),
            ('std', StandardScaler()),
            ('lr', LogisticRegression(max_iter=3000, class_weight='balanced')),
        ])
        ts = TimeSeriesSplit(n_splits=5)
        pred = np.full(len(d), np.nan)
        for tr, te in ts.split(X):
            if y.iloc[tr].nunique() < 2:
                continue
            pipe.fit(X.iloc[tr], y.iloc[tr])
            pred[te] = pipe.predict_proba(X.iloc[te])[:, 1]
        ok = np.isfinite(pred)
        auc = roc_auc_score(y[ok], pred[ok])
        brier = brier_score_loss(y[ok], pred[ok])
        pipe.fit(X, y)
        coef = pipe.named_steps['lr'].coef_[0]
        assoc = sorted([
            {'key':k,'label':LABEL[k],'coefficient':float(c),'odds_ratio':float(math.exp(c))}
            for k, c in zip(RAW, coef)
        ], key=lambda x: abs(x['coefficient']), reverse=True)

        ev = d.loc[ok].copy()
        train_end = max(1, np.where(ok)[0][0])
        tmp = d.iloc[:train_end].copy()
        tmp['month_num'] = pd.to_datetime(tmp.date).dt.month
        month_rate = tmp.groupby('month_num').red_or_worse.mean()
        overall = float(y.mean())
        monthly = np.array([
            float(month_rate.get(pd.to_datetime(x).month, overall)) for x in ev.date
        ])
        prev = (pd.to_numeric(ev.prev_day_severity, errors='coerce').fillna(2) >= 3).astype(float).to_numpy()

        def sauc(v):
            try:
                return float(roc_auc_score(ev.red_or_worse, v))
            except Exception:
                return .5

        out = {
            'status':'ok',
            'n_training':int(len(d)),
            'positive_days':int(y.sum()),
            'validation':{
                'method':'5-split expanding-window time-series validation',
                'roc_auc':float(auc),
                'brier':float(brier),
                'status':'exploratory'
            },
            'baselines':{
                'monthly_auc':sauc(monthly),
                'persistence_auc':sauc(prev)
            },
            'associations':assoc,
            'research_context':context,
            'note':'Association/prediction research only. Never overrides posted beach flags. Measured NDBC fields are contextual; retrospective HURDAT2 best-track fields are not operational predictors.'
        }

    (DATA / 'model_metrics.json').write_text(json.dumps(out, indent=2) + '\n')
    print(out['status'], len(d))


if __name__ == '__main__':
    main()
