#!/usr/bin/env python3
from __future__ import annotations

import io, json, re, zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
import pandas as pd
from bs4 import BeautifulSoup

try:
    from .common import ROOT, DATA, TZ, session, get_json, now_local
except ImportError:
    from common import ROOT, DATA, TZ, session, get_json, now_local

IEM_RETRIEVE='https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py'
IEM_VIEW='https://mesonet.agron.iastate.edu/p.php?pid={}'
PIL='SRFMOB'
DEFAULT_START=date(2008,1,1)
NOAA_STATION='8729511'  # East Pass (Destin)
LOCATIONS={
 'destin': {'name':'Destin','lat':30.3935,'lon':-86.4958,'official':'https://www.destinfire.gov/today-s-warning-condition-beach-flags'},
 'okaloosa-island': {'name':'Okaloosa Island','lat':30.39136,'lon':-86.59319,'official':'https://www.myokaloosa.com/ps/beach-safety'},
}
RISK_SCORE={'Low':1,'Moderate':2,'High':3}
FLAG_SEVERITY={'Green':1,'Yellow':2,'Single Red':3,'Double Red':4}


def product_id(filename, issued_utc, text):
    stem=Path(filename).name.rsplit('.',1)[0]
    if re.match(r'^\d{12}-[A-Z0-9]{4}-[A-Z0-9]{6}-',stem): return stem
    wmo=re.search(r'(?m)^([A-Z]{4}\d{2})\s+(KMOB)\s+\d{6}\s*$',text)
    return f"{issued_utc:%Y%m%d%H%M}-KMOB-{wmo.group(1) if wmo else 'FZUS52'}-{PIL}"


def okaloosa_section(text):
    # NWS Mobile groups Escambia/Santa Rosa/Okaloosa coastal zones in one forecast block.
    m=re.search(r'(?ms)^FLZ202-204-206-[^\n]*\n.*?Including the beaches of.*?Destin\s*\n(.*?)(?=^\$\$|\Z)',text)
    if m: return m.group(1)
    m=re.search(r'(?ms)Escambia Coastal-Santa Rosa Coastal-Okaloosa Coastal-.*?Including the beaches of.*?Destin\s*\n(.*?)(?=^\$\$|\Z)',text)
    return m.group(1) if m else ''


def today_block(section):
    if not section:return ''
    m=re.search(r'(?ms)^\s*\.(?:REST OF TODAY|TODAY)\.\.\.\s*(.*?)(?=^\s*\.[A-Z][A-Z ]+\.\.\.|^\s*&&|\Z)',section)
    return m.group(1) if m else section


def field(block,label):
    m=re.search(rf'(?mi)^\s*{label}\*?\.*\s*(.+?)\s*$',block)
    return m.group(1).strip() if m else None


def nums(v): return [float(x) for x in re.findall(r'\d+(?:\.\d+)?',v or '')]
def bounds(v):
    n=nums(v)
    return (None,None) if not n else (n[0],n[0]) if len(n)==1 else (min(n[:2]),max(n[:2]))
def first(v):
    n=nums(v); return n[0] if n else None

def parse_srf(filename,text):
    tm=re.search(r'(\d{12})',Path(filename).name)
    if not tm:return None
    try: issued_utc=datetime.strptime(tm.group(1),'%Y%m%d%H%M').replace(tzinfo=timezone.utc)
    except ValueError:return None
    section=okaloosa_section(text)
    if not section:return None
    block=today_block(section)
    risk=field(block,r'Rip Current Risk')
    if risk:
        m=re.search(r'\b(Low|Moderate|High)\b',risk,re.I); risk=m.group(1).title() if m else risk
    surf=field(block,r'Surf Height')
    uv=field(block,r'UV Index\*\*') or field(block,r'UV Index')
    water=field(block,r'Water Temperature')
    winds=field(block,r'Winds')
    lo,hi=bounds(surf)
    loc=issued_utc.astimezone(TZ)
    pid=product_id(filename,issued_utc,text)
    return {'issued_utc':issued_utc.isoformat(),'issued_local':loc.isoformat(),'date':loc.date().isoformat(),'time_local':loc.strftime('%H:%M'),'rip_current_risk':risk,'rip_current_risk_score':RISK_SCORE.get(risk),'surf_height_text':surf,'surf_height_min_ft':lo,'surf_height_max_ft':hi,'uv_index_category':uv,'water_temperature_f':first(water),'winds_text':winds,'wind_speed_max_mph':max(nums(winds)) if nums(winds) else None,'source_product_id':pid,'source_url':IEM_VIEW.format(quote(pid)),'source':'NWS Mobile/Pensacola SRFMOB via Iowa Environmental Mesonet archive'}


def fetch_srf(start,end_exclusive):
    params={'limit':9999,'pil':PIL,'fmt':'zip','sdate':f'{start.isoformat()}T00:00Z','edate':f'{end_exclusive.isoformat()}T00:00Z','order':'asc'}
    r=session().get(IEM_RETRIEVE,params=params,timeout=240);r.raise_for_status(); bio=io.BytesIO(r.content)
    if not zipfile.is_zipfile(bio):return []
    rows=[]
    with zipfile.ZipFile(bio) as z:
        for name in z.namelist():
            if name.endswith('/'):continue
            row=parse_srf(name,z.read(name).decode('utf-8',errors='replace'))
            if row:rows.append(row)
    return rows


def srf_history(outdir):
    path=outdir/'nws_srf_observations.csv'
    existing=pd.read_csv(path) if path.exists() and path.stat().st_size else pd.DataFrame()
    if existing.empty:start=DEFAULT_START
    else:
        last=pd.to_datetime(existing.issued_utc,utc=True,errors='coerce').max(); start=(last.date()-timedelta(days=3)) if pd.notna(last) else DEFAULT_START
    fetched=[]; cur=start; end=date.today()+timedelta(days=1)
    while cur<end:
        stop=min(date(cur.year+1,1,1),end); fetched.extend(fetch_srf(cur,stop));cur=stop
    new=pd.DataFrame(fetched)
    obs=new if existing.empty else existing if new.empty else pd.concat([existing,new],ignore_index=True)
    if obs.empty: raise RuntimeError('No SRFMOB records recovered')
    obs=obs.drop_duplicates('source_product_id',keep='last').sort_values('issued_utc');obs.to_csv(path,index=False)
    daily=[]
    for dt,g in obs.groupby('date',sort=True):
        g=g.sort_values('issued_utc'); usable=g[g.rip_current_risk.notna()]; rep=(usable.iloc[-1] if len(usable) else g.iloc[-1]).to_dict(); rep['n_products']=len(g);daily.append(rep)
    d=pd.DataFrame(daily).sort_values('date'); d.to_csv(outdir/'nws_srf_daily.csv',index=False)
    return d


def weather_history(lat,lon,start,end):
    p={'latitude':lat,'longitude':lon,'start_date':start,'end_date':end,'models':'era5','daily':'temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant','temperature_unit':'fahrenheit','wind_speed_unit':'mph','precipitation_unit':'inch','timezone':'America/Chicago'}
    z=get_json('https://archive-api.open-meteo.com/v1/archive',p,timeout=120)['daily']
    return pd.DataFrame({'date':z['time'],'temp_max_f':z['temperature_2m_max'],'temp_min_f':z['temperature_2m_min'],'precip_in':z['precipitation_sum'],'wind_max_mph':z['wind_speed_10m_max'],'gust_max_mph':z['wind_gusts_10m_max'],'wind_dir_deg':z['wind_direction_10m_dominant']})


def marine_history(lat,lon,start,end):
    p={'latitude':lat,'longitude':lon,'start_date':start,'end_date':end,'models':'era5_ocean','daily':'wave_height_max,wave_direction_dominant,wave_period_max,swell_wave_height_max,swell_wave_direction_dominant,swell_wave_period_max','length_unit':'imperial','timezone':'America/Chicago'}
    z=get_json('https://marine-api.open-meteo.com/v1/marine',p,timeout=120)['daily']
    return pd.DataFrame({'date':z['time'],'wave_max_ft':z['wave_height_max'],'wave_dir_deg':z['wave_direction_dominant'],'wave_period_s':z['wave_period_max'],'swell_max_ft':z['swell_wave_height_max'],'swell_dir_deg':z['swell_wave_direction_dominant'],'swell_period_s':z['swell_wave_period_max']})


def tide_history(start,end):
    rows=[]; cur=pd.Timestamp(start); z=pd.Timestamp(end)
    while cur<=z:
        month_end=cur+pd.offsets.MonthEnd(0); stop=min(month_end,z)
        data=get_json('https://api.tidesandcurrents.noaa.gov/api/prod/datagetter',{'begin_date':cur.strftime('%Y%m%d'),'end_date':stop.strftime('%Y%m%d'),'station':NOAA_STATION,'product':'predictions','datum':'MLLW','time_zone':'lst_ldt','interval':'hilo','units':'english','application':'KnowTheGulf','format':'json'},timeout=60)
        p=pd.DataFrame(data.get('predictions',[]))
        if not p.empty:
            p['date']=p.t.str.slice(0,10);p['v']=pd.to_numeric(p.v,errors='coerce')
            for dt,g in p.groupby('date'):
                lo=float(g.v.min());hi=float(g.v.max());rows.append({'date':dt,'tide_low_ft':lo,'tide_high_ft':hi,'tide_range_ft':hi-lo})
        cur=stop+pd.Timedelta(days=1)
    return pd.DataFrame(rows)


def environment(outdir,cfg,daily):
    if daily.empty:return pd.DataFrame()
    start=str(daily.date.min()); end=min(str(daily.date.max()),(date.today()-timedelta(days=6)).isoformat())
    if start>end:return pd.DataFrame()
    w=weather_history(cfg['lat'],cfg['lon'],start,end);m=marine_history(cfg['lat'],cfg['lon'],start,end);t=tide_history(start,end)
    env=pd.DataFrame({'date':pd.date_range(start,end).strftime('%Y-%m-%d')}).merge(w,on='date',how='left').merge(m,on='date',how='left').merge(t,on='date',how='left')
    env['data_quality']='finalized';env['weather_source']='Open-Meteo ERA5';env['marine_source']='Open-Meteo ERA5-Ocean';env['tide_source']=f'NOAA CO-OPS {NOAA_STATION} East Pass predictions';env['updated_at']=now_local().isoformat();env.to_csv(outdir/'environmental_daily.csv',index=False);return env


def parse_destin_flag(html):
    text=' '.join(BeautifulSoup(html,'html.parser').stripped_strings)
    m=re.search(r'Current Status:\s*(Water Closed to Public|High Hazard|Medium Hazard|Low Hazard)',text,re.I)
    if not m:raise RuntimeError('Destin current status not found')
    status=m.group(1).title(); mp={'Water Closed To Public':'Double Red','High Hazard':'Single Red','Medium Hazard':'Yellow','Low Hazard':'Green'}
    return mp[status]


def current_destin(outdir):
    cfg=LOCATIONS['destin']; r=session().get(cfg['official'],timeout=30);r.raise_for_status();flag=parse_destin_flag(r.text);now=now_local();out={'flag':flag,'label':flag,'severity':FLAG_SEVERITY[flag],'last_verified_at':now.isoformat(),'source_name':'Destin Fire Control District / Destin Beach Safety','source_url':cfg['official'],'method':'Scheduled public current-condition snapshot','stale_after_hours':2}
    (outdir/'current_flag.json').write_text(json.dumps(out,indent=2)+'\n');return out


def summaries(outdir,daily,env):
    merged=daily.merge(env,on='date',how='left') if not env.empty else daily.copy(); merged.to_csv(outdir/'history_daily.csv',index=False); merged.to_json(outdir/'history_daily.json',orient='records')
    n=len(daily); high=int((daily.rip_current_risk=='High').sum()); mod=int(daily.rip_current_risk.isin(['Moderate','High']).sum())
    s={'start':str(daily.date.min()),'end':str(daily.date.max()),'days_with_data':n,'high_rip_days':high,'high_rip_pct':round(100*high/n,1) if n else None,'moderate_or_worse_days':mod,'moderate_or_worse_pct':round(100*mod/n,1) if n else None,'source':'NWS Mobile/Pensacola SRFMOB + Open-Meteo ERA5/ERA5-Ocean + NOAA CO-OPS East Pass','updated_at':now_local().isoformat()}
    (outdir/'summary.json').write_text(json.dumps(s,indent=2)+'\n')


def main():
    shared=DATA/'western';shared.mkdir(parents=True,exist_ok=True)
    daily=srf_history(shared)
    for slug,cfg in LOCATIONS.items():
        outdir=DATA/slug;outdir.mkdir(parents=True,exist_ok=True)
        # Same NWS coastal forecast zone, separate environmental coordinates and provenance directories.
        daily.to_csv(outdir/'nws_srf_daily.csv',index=False)
        env=environment(outdir,cfg,daily);summaries(outdir,daily,env)
        if slug=='destin':current_destin(outdir)
        else:
            (outdir/'current_flag.json').write_text(json.dumps({'flag':None,'label':'Check official county flag','last_verified_at':None,'source_name':'Okaloosa County Beach Safety','source_url':cfg['official'],'method':'Official daily flag is published via county Facebook/text alert; no stable machine-readable county webpage is currently available.','stale_after_hours':0},indent=2)+'\n')
    print('western locations updated',now_local().isoformat())

if __name__=='__main__':main()
