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
    return v is True or str(v).strip().lower() == 'true'


def main():
    a = pd.read_csv(DATA/'flag_observations_archive.csv')
    auto = pd.read_csv(DATA/'flag_observations_auto.csv')
    recovered_path = DATA/'flag_observations_recovered.csv'
    recovered = pd.read_csv(recovered_path) if recovered_path.exists() and recovered_path.stat().st_size else pd.DataFrame()

    rows=[]
    for _,r in a.iterrows():
        rows.append({
            'observed_at':r.get('datetime_ct'),'date':r['date'],'time':str(r['time']),
            'base_flag':r['base_flag'],'purple_overlay':as_bool(r['purple_overlay']),'purple_known':True,
            'flag_label':r['flag_label'],'severity':r['severity'],'source':'ALERTBAY/PCBFLAGS text archive',
            'source_url':r.get('url',''),'observation_type':'archived_alert','message':r['message'],
            'source_file':r.get('source_file',''),'source_product_id':'','record_tier':'primary_archive'
        })
    if len(auto):
        for _,r in auto.iterrows():
            rows.append({
                'observed_at':r['observed_at'],'date':r['date'],'time':str(r['time']),
                'base_flag':r['base_flag'],'purple_overlay':as_bool(r['purple_overlay']),'purple_known':True,
                'flag_label':r['flag_label'],'severity':r['severity'],'source':r['source'],
                'source_url':r['source_url'],'observation_type':r['observation_type'],'message':r['message'],
                'source_file':'','source_product_id':'','record_tier':'primary_auto'
            })
    if len(recovered):
        for _,r in recovered.iterrows():
            rows.append({
                'observed_at':r['observed_at'],'date':r['date'],'time':str(r['time']),
                'base_flag':r['base_flag'],'purple_overlay':as_bool(r.get('purple_overlay',False)),
                'purple_known':as_bool(r.get('purple_known',True)),
                'flag_label':r['flag_label'],'severity':r['severity'],'source':r['source'],
                'source_url':r['source_url'],'observation_type':r['observation_type'],'message':r['message'],
                'source_file':r.get('source_file',''),'source_product_id':r.get('source_product_id',''),
                'record_tier':'recovered'
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
        tiers=sorted(set(g.record_tier.astype(str)))
        purple_known=bool(g.purple_known.map(as_bool).any())
        out.append({
            'date':dt,'latest_flag':last.base_flag,'latest_purple':as_bool(last.purple_overlay),
            'peak_flag':peak.base_flag,'peak_severity':float(peak.severity),
            'purple_any':bool(g.purple_overlay.map(as_bool).any()),'purple_known':purple_known,
            'n_updates':int(len(g)),'first_time':str(g.iloc[0].time)[:5],'last_time':str(last.time)[:5],
            'latest_label':last.flag_label,'peak_label':peak.flag_label,'year':int(dt[:4]),'month_num':int(dt[5:7]),
            'month':pd.to_datetime(dt).strftime('%b'),'dow':pd.to_datetime(dt).strftime('%A'),
            'record_status':'provisional' if dt==date.today().isoformat() else 'finalized',
            'record_tier':'recovered' if tiers==['recovered'] else 'primary',
            'source_quality':' + '.join(sources)
        })
    d=pd.DataFrame(out).sort_values('date')
    d.to_csv(DATA/'flag_daily_master.csv',index=False)
    (DATA/'flag_daily_master.json').write_text(d.where(pd.notnull(d),None).to_json(orient='records'))

    ds=pd.to_datetime(d.date);calendar_days=(ds.max()-ds.min()).days+1
    primary_days=int((d.record_tier=='primary').sum())
    recovered_days=int((d.record_tier=='recovered').sum())
    purple_known_days=int(d.purple_known.map(as_bool).sum())
    purple_days=int(d.purple_any.map(as_bool).sum())
    summary={
        'start':str(ds.min().date()),'end':str(ds.max().date()),'days_with_data':int(len(d)),
        'calendar_days':int(calendar_days),'coverage_pct':round(100*len(d)/calendar_days,1),
        'primary_days':primary_days,'recovered_days':recovered_days,
        'classified_observations':int(valid.shape[0]),'unclassified_observations':int(x.shape[0]-valid.shape[0]),
        'red_or_worse_days':int((d.peak_severity>=3).sum()),
        'red_or_worse_pct':round(100*(d.peak_severity>=3).mean(),1),
        'double_red_days':int((d.peak_severity>=4).sum()),
        'purple_days':purple_days,'purple_known_days':purple_known_days,
        'purple_pct_known':round(100*purple_days/purple_known_days,1) if purple_known_days else None,
        'multi_update_days':int((d.n_updates>1).sum()),
        'latest_record_status':str(d.iloc[-1].record_status),
        'provenance_note':'Original ALERTBAY/PCBFLAGS and automatic project observations take precedence. Historical automatic rows may retain the legacy Safe2Swim collector label. Recovered NWS SRFTAE Bay flag reports are used only on dates with no primary observation.'
    }
    (DATA/'flag_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('observations',len(x),'daily rows',len(d),'primary days',primary_days,'recovered days',recovered_days,'through',d.date.max())


if __name__=='__main__':main()
