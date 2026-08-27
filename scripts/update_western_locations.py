#!/usr/bin/env python3
from __future__ import annotations
import io,json,re,zipfile
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import quote
import pandas as pd
from bs4 import BeautifulSoup
try:
    from .common import DATA,TZ,session,get_json,now_local
except ImportError:
    from common import DATA,TZ,session,get_json,now_local

IEM_RETRIEVE='https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py';IEM_VIEW='https://mesonet.agron.iastate.edu/p.php?pid={}';PIL='SRFMOB';DEFAULT_START=date(2008,1,1)
LOCATIONS={
'destin':{'name':'Destin','lat':30.3935,'lon':-86.4958,'station':'8729511','tide_name':'East Pass (Destin)','official':'https://www.destinfire.gov/today-s-warning-condition-beach-flags','authority':'Destin Fire Control District / Destin Beach Safety'},
'okaloosa-island':{'name':'Okaloosa Island','lat':30.39136,'lon':-86.59319,'station':'8729511','tide_name':'East Pass (Destin)','official':'https://www.myokaloosa.com/ps/beach-safety','authority':'Okaloosa County Beach Safety'},
'navarre-beach':{'name':'Navarre Beach','lat':30.3766,'lon':-86.8636,'station':'8729678','tide_name':'Navarre Beach','official':'https://santarosa.fl.gov/269/Water-Safety','authority':'Santa Rosa County / Navarre Beach Safety'},
'pensacola-beach':{'name':'Pensacola Beach','lat':30.3320,'lon':-87.1420,'station':'8729840','tide_name':'Pensacola','official':'https://myescambia.com/pensacola-beach/pensacola-beach-lifeguards','authority':'Escambia County / Pensacola Beach Lifeguards'}}
RISK_SCORE={'Low':1,'Moderate':2,'High':3};FLAG_SEVERITY={'Green':1,'Yellow':2,'Single Red':3,'Double Red':4}
HAZARD_TO_FLAG={'low hazard':'Green','medium hazard':'Yellow','moderate hazard':'Yellow','high hazard':'Single Red','water closed':'Double Red','water closed to public':'Double Red'}

def product_id(filename,issued,text):
    stem=Path(filename).name.rsplit('.',1)[0]
    if re.match(r'^\d{12}-[A-Z0-9]{4}-[A-Z0-9]{6}-',stem):return stem
    w=re.search(r'(?m)^([A-Z]{4}\d{2})\s+(KMOB)\s+\d{6}\s*$',text);return f"{issued:%Y%m%d%H%M}-KMOB-{w.group(1) if w else 'FZUS52'}-{PIL}"
def section(text):
    m=re.search(r'(?ms)^FLZ202-204-206-[^\n]*\n.*?Including the beaches of.*?Destin\s*\n(.*?)(?=^\$\$|\Z)',text)
    if m:return m.group(1)
    m=re.search(r'(?ms)Escambia Coastal-Santa Rosa Coastal-Okaloosa Coastal-.*?Including the beaches of.*?Destin\s*\n(.*?)(?=^\$\$|\Z)',text);return m.group(1) if m else ''
def today_block(s):
    m=re.search(r'(?ms)^\s*\.(?:REST OF TODAY|TODAY)\.\.\.\s*(.*?)(?=^\s*\.[A-Z][A-Z ]+\.\.\.|^\s*&&|\Z)',s or '');return m.group(1) if m else s
def field(block,label):
    m=re.search(rf'(?mi)^\s*{label}\.*\s*(.+?)\s*$',block or '');return m.group(1).strip() if m else None
def nums(v):return [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?',v or '')]
def bounds(v):
    n=nums(v);return (None,None) if not n else (n[0],n[0]) if len(n)==1 else (min(n[:2]),max(n[:2]))
def parse_srf(filename,text):
    tm=re.search(r'(\d{12})',Path(filename).name)
    if not tm:return None
    try:issued=datetime.strptime(tm.group(1),'%Y%m%d%H%M').replace(tzinfo=timezone.utc)
    except ValueError:return None
    s=section(text)
    if not s:return None
    b=today_block(s);risk=field(b,r'Rip Current Risk\*?')
    if risk:
        m=re.search(r'\b(Low|Moderate|High)\b',risk,re.I);risk=m.group(1).title() if m else risk
    surf=field(b,r'Surf Height');lo,hi=bounds(surf);uv=field(b,r'UV Index\*\*') or field(b,r'UV Index');water=field(b,r'Water Temperature');winds=field(b,r'Winds');loc=issued.astimezone(TZ);pid=product_id(filename,issued,text)
    return {'issued_utc':issued.isoformat(),'issued_local':loc.isoformat(),'date':loc.date().isoformat(),'time_local':loc.strftime('%H:%M'),'rip_current_risk':risk,'rip_current_risk_score':RISK_SCORE.get(risk),'surf_height_text':surf,'surf_height_min_ft':lo,'surf_height_max_ft':hi,'uv_index_category':uv,'water_temperature_f':nums(water)[0] if nums(water) else None,'winds_text':winds,'wind_speed_max_mph':max(nums(winds)) if nums(winds) else None,'source_product_id':pid,'source_url':IEM_VIEW.format(quote(pid)),'source':'NWS Mobile/Pensacola SRFMOB via Iowa Environmental Mesonet archive'}
def fetch_srf(a,b):
    r=session().get(IEM_RETRIEVE,params={'limit':9999,'pil':PIL,'fmt':'zip','sdate':f'{a.isoformat()}T00:00Z','edate':f'{b.isoformat()}T00:00Z','order':'asc'},timeout=240);r.raise_for_status();bio=io.BytesIO(r.content)
    if not zipfile.is_zipfile(bio):return []
    rows=[]
    with zipfile.ZipFile(bio) as z:
        for n in z.namelist():
            if n.endswith('/'):continue
            row=parse_srf(n,z.read(n).decode('utf-8',errors='replace'))
            if row:rows.append(row)
    return rows
def srf_history(outdir):
    p=outdir/'nws_srf_observations.csv';old=pd.read_csv(p) if p.exists() and p.stat().st_size else pd.DataFrame();start=DEFAULT_START
    if not old.empty:
        last=pd.to_datetime(old.issued_utc,utc=True,errors='coerce').max();start=(last.date()-timedelta(days=3)) if pd.notna(last) else DEFAULT_START
    rows=[];cur=start;end=date.today()+timedelta(days=1)
    while cur<end:
        stop=min(date(cur.year+1,1,1),end);print('SRFMOB',cur,stop-timedelta(days=1));rows.extend(fetch_srf(cur,stop));cur=stop
    new=pd.DataFrame(rows);obs=new if old.empty else old if new.empty else pd.concat([old,new],ignore_index=True)
    if obs.empty:raise RuntimeError('No SRFMOB records recovered')
    obs=obs.drop_duplicates('source_product_id',keep='last').sort_values('issued_utc');obs.to_csv(p,index=False);daily=[]
    for _,g in obs.groupby('date',sort=True):
        g=g.sort_values('issued_utc');u=g[g.rip_current_risk.notna()];rep=(u.iloc[-1] if len(u) else g.iloc[-1]).to_dict();rep['n_products']=int(len(g));daily.append(rep)
    d=pd.DataFrame(daily).sort_values('date');d.to_csv(outdir/'nws_srf_daily.csv',index=False);return d
def weather(lat,lon,a,b):
    z=get_json('https://archive-api.open-meteo.com/v1/archive',{'latitude':lat,'longitude':lon,'start_date':a,'end_date':b,'models':'era5','daily':'temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant','temperature_unit':'fahrenheit','wind_speed_unit':'mph','precipitation_unit':'inch','timezone':'America/Chicago'},timeout=180)['daily'];return pd.DataFrame({'date':z['time'],'temp_max_f':z['temperature_2m_max'],'temp_min_f':z['temperature_2m_min'],'precip_in':z['precipitation_sum'],'wind_max_mph':z['wind_speed_10m_max'],'gust_max_mph':z['wind_gusts_10m_max'],'wind_dir_deg':z['wind_direction_10m_dominant']})
def marine(lat,lon,a,b):
    z=get_json('https://marine-api.open-meteo.com/v1/marine',{'latitude':lat,'longitude':lon,'start_date':a,'end_date':b,'models':'era5_ocean','daily':'wave_height_max,wave_direction_dominant,wave_period_max,swell_wave_height_max,swell_wave_direction_dominant,swell_wave_period_max','length_unit':'imperial','timezone':'America/Chicago'},timeout=180)['daily'];return pd.DataFrame({'date':z['time'],'wave_max_ft':z['wave_height_max'],'wave_dir_deg':z['wave_direction_dominant'],'wave_period_s':z['wave_period_max'],'swell_max_ft':z['swell_wave_height_max'],'swell_dir_deg':z['swell_wave_direction_dominant'],'swell_period_s':z['swell_wave_period_max']})
def tides(a,b,station):
    rows=[];cur=pd.Timestamp(a);end=pd.Timestamp(b)
    while cur<=end:
        stop=min(pd.Timestamp(f'{cur.year}-12-31'),end);data=get_json('https://api.tidesandcurrents.noaa.gov/api/prod/datagetter',{'begin_date':cur.strftime('%Y%m%d'),'end_date':stop.strftime('%Y%m%d'),'station':station,'product':'predictions','datum':'MLLW','time_zone':'lst_ldt','interval':'hilo','units':'english','application':'KnowTheGulf','format':'json'},timeout=90);p=pd.DataFrame(data.get('predictions',[]))
        if not p.empty:
            p['date']=p.t.str.slice(0,10);p['v']=pd.to_numeric(p.v,errors='coerce')
            for dt,g in p.groupby('date'):
                lo=float(g.v.min());hi=float(g.v.max());rows.append({'date':dt,'tide_low_ft':lo,'tide_high_ft':hi,'tide_range_ft':hi-lo})
        cur=stop+pd.Timedelta(days=1)
    return pd.DataFrame(rows)
def environment(outdir,cfg,daily):
    cutoff=(date.today()-timedelta(days=6)).isoformat();wanted=sorted(d for d in daily.date.astype(str).unique() if d<=cutoff)
    if not wanted:return pd.DataFrame()
    p=outdir/'environmental_daily.csv';old=pd.read_csv(p) if p.exists() and p.stat().st_size else pd.DataFrame();have=set(old.date.astype(str)) if not old.empty else set();need=[d for d in wanted if d not in have]
    if need:
        a,b=min(need),max(need);w=weather(cfg['lat'],cfg['lon'],a,b);m=marine(cfg['lat'],cfg['lon'],a,b);t=tides(a,b,cfg['station']);n=pd.DataFrame({'date':pd.date_range(a,b).strftime('%Y-%m-%d')}).merge(w,on='date',how='left').merge(m,on='date',how='left').merge(t,on='date',how='left');n=n[n.date.isin(set(need))];n['data_quality']='finalized';n['weather_source']='Open-Meteo ERA5';n['marine_source']='Open-Meteo ERA5-Ocean';n['tide_source']=f"NOAA CO-OPS {cfg['station']} {cfg['tide_name']} predictions";n['updated_at']=now_local().isoformat();old=n if old.empty else pd.concat([old[~old.date.astype(str).isin(set(need))],n],ignore_index=True);old.sort_values('date').to_csv(p,index=False)
    return old.sort_values('date')
def parse_hazard_flag(html):
    text=' '.join(BeautifulSoup(html,'html.parser').stripped_strings)
    m=re.search(r'(Water Closed(?: to Public)?|High Hazard|Medium Hazard|Moderate Hazard|Low Hazard)',text,re.I)
    return HAZARD_TO_FLAG.get(m.group(1).lower()) if m else None
def parse_destin_flag(html):
    text=' '.join(BeautifulSoup(html,'html.parser').stripped_strings);m=re.search(r'Current Status:\s*(Water Closed to Public|High Hazard|Medium Hazard|Low Hazard)',text,re.I)
    if not m:raise RuntimeError('Destin current status not found')
    return HAZARD_TO_FLAG[m.group(1).lower()]
def verified_direct(cfg):
    r=session().get(cfg['official'],timeout=30);r.raise_for_status();return parse_hazard_flag(r.text)
def verification_times(previous,now,flag):
    checked=now.isoformat()
    return (checked if flag else previous.get('last_verified_at')),checked
def current_file(outdir,slug,cfg,destin_flag=None):
    now=now_local();flag=None;method='';source_url=cfg['official'];source_name=cfg['authority'];source_ok=False
    try:
        previous=json.loads((outdir/'current_flag.json').read_text(encoding='utf-8'))
        if not isinstance(previous,dict):previous={}
    except (FileNotFoundError,json.JSONDecodeError):
        previous={}
    if slug=='destin':
        if destin_flag:
            flag=destin_flag;source_ok=True
        else:
            try:flag=verified_direct(cfg);source_ok=True
            except Exception:flag=None
        method='Scheduled direct official current-condition snapshot'
    elif slug=='okaloosa-island' and destin_flag:
        flag=destin_flag;source_ok=True;method='Synchronized Destin-Fort Walton Beach warning flag; Okaloosa County, City of Destin and Henderson Beach State Park use a common flag selection';source_name='Okaloosa County Beach Safety / Destin Fire Control District'
    else:
        try:flag=verified_direct(cfg);source_ok=True
        except Exception:flag=None
        method='Scheduled direct official page snapshot; accepts only an explicit Low/Medium/Moderate/High Hazard or Water Closed status'
    last_verified_at,last_checked_at=verification_times(previous,now,flag)
    source_check_status='verified' if flag else 'degraded' if source_ok else 'unavailable'
    payload={'flag':flag,'label':flag if flag else 'Official flag status unavailable','severity':FLAG_SEVERITY.get(flag),'last_verified_at':last_verified_at,'last_checked_at':last_checked_at,'source_check_status':source_check_status,'source_name':source_name,'source_url':source_url,'official_authority':cfg['authority'],'official_authority_url':cfg['official'],'method':method,'stale_after_hours':3 if flag else 0}
    (outdir/'current_flag.json').write_text(json.dumps(payload,indent=2)+'\n')
def summarize(outdir,cfg,daily,env):
    merged=daily.merge(env,on='date',how='left') if not env.empty else daily.copy();merged.to_csv(outdir/'history_daily.csv',index=False);merged.to_json(outdir/'history_daily.json',orient='records');n=len(daily);high=int((daily.rip_current_risk=='High').sum());mod=int(daily.rip_current_risk.isin(['Moderate','High']).sum());(outdir/'summary.json').write_text(json.dumps({'start':str(daily.date.min()),'end':str(daily.date.max()),'days_with_data':n,'high_rip_days':high,'high_rip_pct':round(100*high/n,1) if n else None,'moderate_or_worse_days':mod,'moderate_or_worse_pct':round(100*mod/n,1) if n else None,'source':f"NWS Mobile/Pensacola SRFMOB + Open-Meteo ERA5/ERA5-Ocean + NOAA CO-OPS {cfg['station']} {cfg['tide_name']}",'updated_at':now_local().isoformat()},indent=2)+'\n')
def main():
    shared=DATA/'western';shared.mkdir(parents=True,exist_ok=True);daily=srf_history(shared)
    destin_flag=None
    try:
        r=session().get(LOCATIONS['destin']['official'],timeout=30);r.raise_for_status();destin_flag=parse_destin_flag(r.text)
    except Exception as exc: print('Destin flag unavailable:',exc)
    for slug,cfg in LOCATIONS.items():
        out=DATA/slug;out.mkdir(parents=True,exist_ok=True);daily.to_csv(out/'nws_srf_daily.csv',index=False);env=environment(out,cfg,daily);summarize(out,cfg,daily,env);current_file(out,slug,cfg,destin_flag)
    print('western locations updated',now_local().isoformat())
if __name__=='__main__':main()
