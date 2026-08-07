#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import date
import pandas as pd
try:
    from .common import DATA
except ImportError:
    from common import DATA

def as_bool(v):
    return v is True or str(v).strip().lower()=='true'

def main():
    a=pd.read_csv(DATA/'flag_observations_archive.csv')
    auto=pd.read_csv(DATA/'flag_observations_auto.csv')
    rows=[]
    for _,r in a.iterrows():
        rows.append({
            'observed_at':r.get('datetime_ct'),'date':r['date'],'time':str(r['time']),
            'base_flag':r['base_flag'],'purple_overlay':as_bool(r['purple_overlay']),
            'flag_label':r['flag_label'],'severity':r['severity'],'source':'ALERTBAY/PCBFLAGS text archive',
            'source_url':r.get('url',''),'observation_type':'archived_alert','message':r['message'],
            'source_file':r.get('source_file','')
        })
    if len(auto):
        for _,r in auto.iterrows():
            rows.append({
                'observed_at':r['observed_at'],'date':r['date'],'time':str(r['time']),
                'base_flag':r['base_flag'],'purple_overlay':as_bool(r['purple_overlay']),
                'flag_label':r['flag_label'],'severity':r['severity'],'source':r['source'],
                'source_url':r['source_url'],'observation_type':r['observation_type'],'message':r['message'],
                'source_file':''
            })
    x=pd.DataFrame(rows).sort_values(['date','time','observed_at'],na_position='last')
    x['severity']=pd.to_numeric(x['severity'],errors='coerce')
    x.to_csv(DATA/'flag_observations_master.csv',index=False)
    (DATA/'flag_observations_master.json').write_text(x.where(pd.notnull(x),None).to_json(orient='records'))

    out=[]
    valid=x[x.base_flag.isin(['Green','Yellow','Single Red','Double Red'])].copy()
    for dt,g in valid.groupby('date'):
        g=g.sort_values('time');peak=g.loc[g['severity'].idxmax()];last=g.iloc[-1]
        sources=sorted(set(g.source.astype(str)))
        out.append({
            'date':dt,'latest_flag':last.base_flag,'latest_purple':as_bool(last.purple_overlay),
            'peak_flag':peak.base_flag,'peak_severity':float(peak.severity),'purple_any':bool(g.purple_overlay.map(as_bool).any()),
            'n_updates':int(len(g)),'first_time':str(g.iloc[0].time)[:5],'last_time':str(last.time)[:5],
            'latest_label':last.flag_label,'peak_label':peak.flag_label,'year':int(dt[:4]),'month_num':int(dt[5:7]),
            'month':pd.to_datetime(dt).strftime('%b'),'dow':pd.to_datetime(dt).strftime('%A'),
            'record_status':'provisional' if dt==date.today().isoformat() else 'finalized',
            'source_quality':' + '.join(sources)
        })
    d=pd.DataFrame(out).sort_values('date')
    d.to_csv(DATA/'flag_daily_master.csv',index=False)
    (DATA/'flag_daily_master.json').write_text(d.where(pd.notnull(d),None).to_json(orient='records'))

    ds=pd.to_datetime(d.date);calendar_days=(ds.max()-ds.min()).days+1
    summary={
        'start':str(ds.min().date()),'end':str(ds.max().date()),'days_with_data':int(len(d)),
        'calendar_days':int(calendar_days),'coverage_pct':round(100*len(d)/calendar_days,1),
        'classified_observations':int(valid.shape[0]),'unclassified_observations':int(x.shape[0]-valid.shape[0]),
        'red_or_worse_days':int((d.peak_severity>=3).sum()),
        'red_or_worse_pct':round(100*(d.peak_severity>=3).mean(),1),
        'double_red_days':int((d.peak_severity>=4).sum()),
        'purple_days':int(d.purple_any.map(as_bool).sum()),
        'multi_update_days':int((d.n_updates>1).sum()),
        'latest_record_status':str(d.iloc[-1].record_status)
    }
    (DATA/'flag_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('observations',len(x),'daily rows',len(d),'through',d.date.max())
if __name__=='__main__':main()
