#!/usr/bin/env python3
from __future__ import annotations
from datetime import date,timedelta,datetime
import calendar,math
import pandas as pd
try:
    from .common import DATA,TZ,get_json,now_local
except ImportError:
    from common import DATA,TZ,get_json,now_local
LAT,LON=30.125,-85.730;STATION='8729136';COLS=['date','data_quality','weather_source','marine_source','tide_source','temp_max_f','temp_min_f','precip_in','wind_max_mph','gust_max_mph','wind_dir_deg','wave_max_ft','wave_dir_deg','wave_period_s','swell_max_ft','swell_dir_deg','swell_period_s','tide_low_ft','tide_high_ft','tide_range_ft','updated_at']
def weather(start,end,final):
    if final:
        u='https://archive-api.open-meteo.com/v1/archive';p={'latitude':LAT,'longitude':LON,'start_date':start,'end_date':end,'models':'era5','daily':'temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant','temperature_unit':'fahrenheit','wind_speed_unit':'mph','precipitation_unit':'inch','timezone':'America/Chicago'};src='Open-Meteo ERA5'
    else:
        u='https://api.open-meteo.com/v1/forecast';p={'latitude':LAT,'longitude':LON,'past_days':7,'forecast_days':1,'daily':'temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant','temperature_unit':'fahrenheit','wind_speed_unit':'mph','precipitation_unit':'inch','timezone':'America/Chicago'};src='Open-Meteo forecast/archive window'
    z=get_json(u,p)['daily'];return pd.DataFrame({'date':z['time'],'temp_max_f':z['temperature_2m_max'],'temp_min_f':z['temperature_2m_min'],'precip_in':z['precipitation_sum'],'wind_max_mph':z['wind_speed_10m_max'],'gust_max_mph':z['wind_gusts_10m_max'],'wind_dir_deg':z['wind_direction_10m_dominant'],'weather_source':src})
def marine(start,end,final):
    p={'latitude':LAT,'longitude':LON,'daily':'wave_height_max,wave_direction_dominant,wave_period_max,swell_wave_height_max,swell_wave_direction_dominant,swell_wave_period_max','length_unit':'imperial','timezone':'America/Chicago'}
    if final:
        p['start_date']=start;p['end_date']=end;p['models']='era5_ocean';src='Open-Meteo ERA5-Ocean'
    else:
        p['past_days']=7;p['forecast_days']=1;src='Open-Meteo best-match marine'
    z=get_json('https://marine-api.open-meteo.com/v1/marine',p)['daily'];return pd.DataFrame({'date':z['time'],'wave_max_ft':z['wave_height_max'],'wave_dir_deg':z['wave_direction_dominant'],'wave_period_s':z['wave_period_max'],'swell_max_ft':z['swell_wave_height_max'],'swell_dir_deg':z['swell_wave_direction_dominant'],'swell_period_s':z['swell_wave_period_max'],'marine_source':src})
def tides_for_dates(dates):
    ds=pd.to_datetime(pd.Series(sorted(set(dates))));groups={}
    for x in ds:groups.setdefault((x.year,x.month),[]).append(x.strftime('%Y-%m-%d'))
    rows=[]
    for (y,m),wanted in groups.items():
        last=calendar.monthrange(y,m)[1];b=f'{y}{m:02d}01';e=f'{y}{m:02d}{last:02d}'
        z=get_json('https://api.tidesandcurrents.noaa.gov/api/prod/datagetter',{'begin_date':b,'end_date':e,'station':STATION,'product':'predictions','datum':'MLLW','time_zone':'lst_ldt','interval':'hilo','units':'english','application':'Safe2SwimPCB','format':'json'},timeout=60)
        p=pd.DataFrame(z.get('predictions',[]))
        if p.empty:continue
        p['date']=p['t'].str.slice(0,10);p['v']=pd.to_numeric(p['v'],errors='coerce')
        for dt,g in p[p.date.isin(wanted)].groupby('date'):
            lo=float(g.v.min());hi=float(g.v.max());rows.append({'date':dt,'tide_low_ft':lo,'tide_high_ft':hi,'tide_range_ft':hi-lo,'tide_source':'NOAA CO-OPS 8729136 predictions'})
    return pd.DataFrame(rows)
def upsert(old,new):
    if old.empty:return new
    old=old[~old.date.isin(set(new.date))];return pd.concat([old,new],ignore_index=True)
def main():
    flags=pd.read_csv(DATA/'flag_daily_master.csv');dates=sorted(flags.date.astype(str).unique());today=now_local().date();cut=(today-timedelta(days=6)).isoformat();final_dates=[d for d in dates if d<=cut];recent_dates=[d for d in dates if d>cut]
    try:old=pd.read_csv(DATA/'environmental_daily.csv')
    except:old=pd.DataFrame(columns=COLS)
    # Finalized range: populate missing or replace any provisional rows now old enough.
    final_need=[d for d in final_dates if d not in set(old.loc[old.data_quality.eq('finalized'),'date'].astype(str))]
    if final_need:
        s,e=min(final_need),max(final_need);w=weather(s,e,True);m=marine(s,e,True);t=tides_for_dates(final_need);n=pd.DataFrame({'date':final_need}).merge(w,on='date',how='left').merge(m,on='date',how='left').merge(t,on='date',how='left');n['data_quality']='finalized';n['updated_at']=now_local().isoformat();old=upsert(old,n)
    # Recent observed flag days get provisional context and are replaced later.
    if recent_dates:
        s,e=min(recent_dates),max(recent_dates);w=weather(s,e,False);m=marine(s,e,False);t=tides_for_dates(recent_dates);n=pd.DataFrame({'date':recent_dates}).merge(w,on='date',how='left').merge(m,on='date',how='left').merge(t,on='date',how='left');n['data_quality']='provisional';n['updated_at']=now_local().isoformat();old=upsert(old,n)
    for c in COLS:
        if c not in old:old[c]=None
    old[COLS].sort_values('date').to_csv(DATA/'environmental_daily.csv',index=False);print('environment rows',len(old),'finalized',sum(old.data_quality.eq('finalized')))
if __name__=='__main__':main()
