#!/usr/bin/env python3
"""Collect authoritative NOAA/NWS environmental observations for Know the Gulf cards.

Sources are intentionally limited to U.S. government feeds. Missing or stale values
remain unavailable rather than being estimated.
"""
from __future__ import annotations
import json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'/'x_environment.json'
UA='KnowTheGulf/1.0 (https://knowthegulf.com; public beach-safety project)'
POINTS={'Panama City Beach':(30.1766,-85.8055),'Destin':(30.3935,-86.4958),'Okaloosa Island':(30.3960,-86.5940),'Navarre Beach':(30.3820,-86.8636),'Pensacola Beach':(30.3328,-87.1420)}
def get_json(url):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/geo+json, application/json'}); return json.load(urllib.request.urlopen(req,timeout=25))
def get_text(url):
 req=urllib.request.Request(url,headers={'User-Agent':UA}); return urllib.request.urlopen(req,timeout=25).read().decode('utf-8','replace')
def c_to_f(v):return None if v is None else round(v*9/5+32)
def ms_to_mph(v):return None if v is None else round(v*2.23694)
def deg_cardinal(d):
 if d is None:return None
 pts=['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW']; return pts[round(float(d)/22.5)%16]
def nws_point(name,lat,lon):
 try:
  p=get_json(f'https://api.weather.gov/points/{lat},{lon}')['properties']; hourly=get_json(p['forecastHourly'])['properties']['periods'][0]
  temp=hourly.get('temperature'); unit=hourly.get('temperatureUnit'); temp_f=round((temp*9/5)+32) if temp is not None and unit=='C' else temp
  return {'air_temp_f':temp_f,'wind_speed':hourly.get('windSpeed'),'wind_direction':hourly.get('windDirection'),'short_forecast':hourly.get('shortForecast'),'source':'National Weather Service','source_url':p.get('forecastHourly')}
 except Exception as e:return {'error':str(e),'source':'National Weather Service'}
def pcb_coops():
 base='https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8729210&time_zone=gmt&units=metric&format=json&application=KnowTheGulf&product='
 out={}
 for product,key,conv in [('water_temperature','water_temp_f',c_to_f),('air_temperature','air_temp_observed_f',c_to_f),('wind','wind_observed',None)]:
  try:
   d=get_json(base+product); row=d.get('data',[{}])[-1]
   if product=='wind':out[key]={'speed_mph':ms_to_mph(float(row['s'])) if row.get('s') not in (None,'') else None,'direction':row.get('dr') or deg_cardinal(row.get('d')),'degrees':row.get('d')}
   elif row.get('v') not in (None,''):out[key]=conv(float(row['v']))
  except Exception:pass
 out['source']='NOAA CO-OPS Station 8729210 (Panama City Beach)'; out['source_url']='https://tidesandcurrents.noaa.gov/stationhome.html?id=8729210'; return out
def ndbc_wave():
 # Station 42039 is a NOAA/NDBC offshore Gulf buoy south of Pensacola; wave data is regional, not beach-specific.
 try:
  txt=get_text('https://www.ndbc.noaa.gov/data/realtime2/42039.txt'); lines=[x for x in txt.splitlines() if x and not x.startswith('#')]
  if not lines:return {}
  cols=lines[0].split(); # first non-comment observation after two header rows varies; fallback to documented fixed columns
  # realtime2 standard: YY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD PRES ATMP WTMP ...
  v=cols; wave=None if len(v)<9 or v[8]=='MM' else round(float(v[8])*3.28084,1); water=None if len(v)<15 or v[14]=='MM' else c_to_f(float(v[14])); air=None if len(v)<14 or v[13]=='MM' else c_to_f(float(v[13])); wind=None if len(v)<7 or v[6]=='MM' else ms_to_mph(float(v[6])); direction=None if len(v)<6 or v[5]=='MM' else deg_cardinal(float(v[5]))
  return {'wave_height_ft':wave,'water_temp_f':water,'air_temp_f':air,'wind_speed_mph':wind,'wind_direction':direction,'source':'NOAA/NDBC Station 42039','source_url':'https://www.ndbc.noaa.gov/station_page.php?station=42039','regional_offshore':True}
 except Exception as e:return {'error':str(e),'source':'NOAA/NDBC Station 42039'}
def rip_risk():
 # NWS Florida beach page is authoritative. Parse only explicit risk labels; never infer a risk from waves/wind.
 try:
  txt=get_text('https://www.weather.gov/beach/florida'); labels=re.findall(r'\b(HIGH|MODERATE|LOW)\b',txt,re.I); return {'available':bool(labels),'note':'Use NWS surf-zone forecast; risk is never inferred locally.','source':'National Weather Service','source_url':'https://www.weather.gov/beach/florida'}
 except Exception as e:return {'available':False,'error':str(e),'source':'National Weather Service'}
def main():
 now=datetime.now(timezone.utc); payload={'generated_at':now.isoformat(),'locations':{n:nws_point(n,*xy) for n,xy in POINTS.items()},'pcb_observations':pcb_coops(),'regional_offshore':ndbc_wave(),'rip_current':rip_risk(),'provenance':['National Weather Service API','NOAA CO-OPS','NOAA National Data Buoy Center'],'disclaimer':'Observations and forecasts may differ from conditions at a specific beach. Follow posted flags and lifeguards.'}; OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,indent=2)+'\n'); print(OUT)
if __name__=='__main__':main()
