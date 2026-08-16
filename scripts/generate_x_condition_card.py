#!/usr/bin/env python3
"""Generate polished Know the Gulf safety cards for X."""
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
 for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf']:
  if Path(p).exists():return ImageFont.truetype(p,size=size)
 return ImageFont.load_default()
def parse_dt(v):
 if not v:return None
 try:return datetime.fromisoformat(v).astimezone(TZ)
 except Exception:return None
def read_flag(path,now):
 try:d=json.loads(path.read_text(encoding='utf-8'))
 except Exception:return None
 label=str(d.get('label') or d.get('flag') or '').strip(); verified=parse_dt(d.get('last_verified_at')); stale=float(d.get('stale_after_hours') or 0)
 if not label or label.lower().startswith('check official') or not verified:return None
 if now-verified>timedelta(hours=max(stale,2)+1):return None
 return {'label':label,'verified':verified}
def flag_color(label):
 low=label.lower()
 for k,v in FLAG_COLORS.items():
  if k in low:return v
 return '#64748b'
def draw_card(output,title='Northwest Florida Beach Check',urgent=False):
 now=datetime.now(TZ); img=Image.new('RGB',(W,H),'#06223a'); d=ImageDraw.Draw(img)
 # Gulf/sand visual identity
 d.rectangle((0,0,W,H),fill='#06223a'); d.ellipse((-160,-290,560,430),fill='#0e7490'); d.ellipse((760,-330,1420,330),fill='#fbbf24'); d.rectangle((0,620,W,H),fill='#f4d7a1')
 # Brand mark: sun + wave + wordmark, intentionally vector-drawn so CI needs no binary asset.
 d.ellipse((68,40,126,98),fill='#fbbf24'); d.arc((60,64,144,128),0,180,fill='#67e8f9',width=7); d.text((155,42),'KNOW THE GULF',font=font(35,True),fill='#ffffff'); d.text((155,83),'Northwest Florida • Safety • Beaches • Marine Life',font=font(18),fill='#bae6fd')
 header='#ef4444' if urgent else '#ffffff'; d.text((64,133),title,font=font(48,True),fill=header); d.text((66,191),now.strftime('%A, %B %d · %-I:%M %p CT'),font=font(22),fill='#dbeafe')
 y=235
 for name,path in LOCATIONS:
  cur=read_flag(path,now); d.rounded_rectangle((64,y,1136,y+60),radius=18,fill='#0b304d'); d.text((88,y+16),name,font=font(24,True),fill='#f8fafc')
  if cur:
   label=cur['label']; c=flag_color(label); d.rounded_rectangle((775,y+10,1110,y+50),radius=15,fill=c); tc='#111827' if c in {'#facc15','#22c55e'} else '#ffffff'; d.text((797,y+18),label,font=font(19,True),fill=tc)
  else:
   d.rounded_rectangle((775,y+10,1110,y+50),radius=15,outline='#64748b',width=2); d.text((806,y+18),'CHECK OFFICIAL',font=font(17,True),fill='#cbd5e1')
  y+=68
 d.text((64,585),'VERIFY AT THE BEACH',font=font(19,True),fill='#ffffff'); d.text((295,585),'Always follow the physically posted flag and local lifeguard direction.',font=font(18),fill='#e0f2fe'); d.text((64,637),'knowthegulf.com  •  @knowthegulf',font=font(17,True),fill='#12324a')
 output.parent.mkdir(parents=True,exist_ok=True); img.save(output,format='PNG',optimize=True)
 if output.stat().st_size>5*1024*1024:raise RuntimeError("Generated image exceeds X's 5 MB image upload limit")
 print(output)
def main():
 p=argparse.ArgumentParser(); p.add_argument('--output',default='tmp/x-condition-card.png'); p.add_argument('--title',default='Northwest Florida Beach Check'); p.add_argument('--urgent',action='store_true'); a=p.parse_args(); draw_card(ROOT/a.output,a.title,a.urgent)
if __name__=='__main__':main()
