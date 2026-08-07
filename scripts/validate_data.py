#!/usr/bin/env python3
from __future__ import annotations
import json,pandas as pd
try:
    from .common import DATA
except ImportError:
    from common import DATA
VALID={'Green','Yellow','Single Red','Double Red'}
def fail(msg):raise SystemExit('VALIDATION FAILED: '+msg)
def main():
    a=pd.read_csv(DATA/'flag_observations_archive.csv');d=pd.read_csv(DATA/'flag_daily_master.csv')
    unknown=a[~a.base_flag.isin(VALID)]
    if len(unknown)>1 or (len(unknown)==1 and unknown.iloc[0].base_flag!='Unknown'):fail('unexpected unknown archive flag records')
    if d.date.duplicated().any():fail('duplicate dates in daily master')
    if not d.date.is_monotonic_increasing:fail('daily master not sorted')
    if not set(d.peak_flag.dropna()).issubset(VALID):fail('unknown daily flag')
    if (DATA/'model_training.csv').exists():
        m=pd.read_csv(DATA/'model_training.csv')
        if len(m) and m.date.duplicated().any():fail('duplicate model dates')
    print('validation ok',len(a),'archive alerts',len(d),'daily rows')
if __name__=='__main__':main()
