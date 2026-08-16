#!/usr/bin/env python3
"""Generate Know the Gulf morning/environmental cards for X."""
from __future__ import annotations
import argparse,json
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; TZ=ZoneInfo('America/Chicago'); W,H=1200,675
LOCATIONS=[('Panama City Beach',DATA/'current_flag.json'),('Destin',DATA/'destin'/'current_flag.json'),('Okaloosa Island',DATA/'okaloosa-island'/'current_flag.json'),('Navarre Beach',DATA/'navarre-beach'/'current_flag.json'),('Pensacola Beach',DATA/'pensacola-beach'/'current_flag.json')]
FLAG_COLORS={'double red':'#991b1b','green':'#22c55e','yellow':'#facc15','red':'#ef4444','purple':'#a855f7'}
def font(size,bold=False):
 p='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; return ImageFont.truetype(p,size=size) if Path(p).exists() else ImageFont.load_default()
def load(p):
 try:return json.loads(p.read_text())
 except:return {}
def parse_dt(v):
 try:return datetime.fromisoformat(v).astimezone(TZ) if v else None
 except:return None
def read_flag(path,now):
 d=load(path); label=str(d.get('label') or d.get('flag') or '').strip(); verified=parse_dt(d.get('last_verified_at')); stale=float(d.get('stale_after_hours') or 0)
 if not label or label.lower().startswith('check official') or not verified or now-verified>timedelta(hours=max(stale,2)+1):return None
 return label
def flag_color(label):
 for k,v in FLAG_COLORS.items():
  if k in label.lower():return v
 return '#64748b'
def metric(draw,x,y,label,value,source_note=''):
 draw.rounded_rectangle((x,y,x+245,y+102),radius=18,fill='#0b304d'); draw.text((x+18,y+15),label,font=font(17,True),fill='#93c5fd'); draw.text((x+18,y+43),value or 'Unavailable',font=font(27,True),fill='#ffffff');
 if source_note:draw.text((x+18,y+78),source_note,font=font(11),fill='#94a3b8')
def draw_card(output,title='Northwest Florida Beach Check',urgent=False):
 now=datetime.now(TZ); env=load(DATA/'x_environment.json'); pcb=env.get('pcb_observations',{}); offshore=env.get('regional_offshore',{}); loc=env.get('locations',{}).get('Panama City Beach',{})
 img=Image.new('RGB',(W,H),'#06223a'); d=ImageDraw.Draw(img); d.ellipse((-160,-290,560,430),fill='#0e7490'); d.ellipse((760,-330,1420,330),fill='#fbbf24'); d.rectangle((0,620,W,H),fill='#f4d7a1')
 d.ellipse((60,36,116,92),fill='#fbbf24'); d.arc((54,60,134,122),0,180,fill='#67e8f9',width=7); d.text((145,37),'KNOW THE GULF',font=font(34,True),fill='white'); d.text((145,78),'KNOW BEFORE YOU GO',font=font(17,True),fill='#bae6fd')
 d.text((60,124),title,font=font(43,True),fill='#ef4444' if urgent else 'white'); d.text((62,174),now.strftime('%A, %B %d · %-I:%M %p CT'),font=font(19),fill='#dbeafe')
 # Environmental snapshot: observed NOAA values preferred; NWS forecast fills air/wind when observation unavailable.
 air=pcb.get('air_temp_observed_f') or loc.get('air_temp_f'); air_v=f'{air}°F' if air is not None else None
 wind=pcb.get('wind_observed') or {}; wind_v=None
 if wind.get('speed_mph') is not None:wind_v=f"{wind.get('direction','')} {wind['speed_mph']} mph".strip()
 elif loc.get('wind_speed'):wind_v=f"{loc.get('wind_direction','')} {loc['wind_speed']}".strip()
 water=pcb.get('water_temp_f') if pcb.get('water_temp_f') is not None else offshore.get('water_temp_f'); water_v=f'{water}°F' if water is not None else None
 wave=offshore.get('wave_height_ft'); wave_v=f'{wave} ft offshore' if wave is not None else None
 metric(d,60,213,'AIR',air_v,'NOAA/NWS'); metric(d,325,213,'WIND',wind_v,'NOAA/NWS'); metric(d,590,213,'GULF WATER',water_v,'NOAA'); metric(d,855,213,'WAVES',wave_v,'NOAA/NDBC regional')
 # Flags occupy a compact regional strip.
 y=340
 for name,path in LOCATIONS:
  label=read_flag(path,now); d.text((64,y),name,font=font(18,True),fill='#f8fafc'); x=720
  if label:
   c=flag_color(label); d.rounded_rectangle((x,y-4,1120,y+31),radius=12,fill=c); d.text((x+18,y+3),label,font=font(15,True),fill='#111827' if c in {'#facc15','#22c55e'} else 'white')
  else:
   d.rounded_rectangle((x,y-4,1120,y+31),radius=12,outline='#64748b',width=2); d.text((x+32,y+3),'CHECK OFFICIAL FLAG',font=font(14,True),fill='#cbd5e1')
  y+=43
 # Risk: deliberately never derived from wave/wind. Show authoritative availability state only.
 risk=env.get('rip_current',{}); risk_text='CHECK NWS SURF-ZONE FORECAST' if not risk.get('risk') else str(risk['risk']).upper()+' RIP CURRENT RISK'
 d.rounded_rectangle((60,560,1140,610),radius=16,fill='#123b56'); d.text((82,574),'RIP CURRENT / MARINE SAFETY',font=font(16,True),fill='#7dd3fc'); d.text((405,572),risk_text,font=font(19,True),fill='white')
 d.text((60,637),'knowthegulf.com  •  @knowthegulf  •  Follow posted flags & lifeguards',font=font(16,True),fill='#12324a')
 output.parent.mkdir(parents=True,exist_ok=True); img.save(output,'PNG',optimize=True); print(output)
def main():
 p=argparse.ArgumentParser(); p.add_argument('--output',default='tmp/x-condition-card.png'); p.add_argument('--title',default='Northwest Florida Beach Check'); p.add_argument('--urgent',action='store_true'); a=p.parse_args(); draw_card(ROOT/a.output,a.title,a.urgent)
if __name__=='__main__':main()
