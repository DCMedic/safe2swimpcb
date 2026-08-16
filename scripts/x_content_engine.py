#!/usr/bin/env python3
"""Production content engine for the official Know the Gulf X account."""
from __future__ import annotations
import argparse, hashlib, json, sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; STATE_PATH=DATA/'x_posting_state.json'; TZ=ZoneInfo('America/Chicago')
STANDARD_POST_ESTIMATE=.015; URL_POST_ESTIMATE=.20; MONTHLY_SOFT_CAP_USD=6.00; LIFETIME_BUDGET_USD=30.00; MAX_POSTS_PER_DAY=3; MIN_MINUTES_BETWEEN_POSTS=90; LINK_POST_MIN_DAYS=3
LOCATIONS={'Panama City Beach':DATA/'current_flag.json','Destin':DATA/'destin'/'current_flag.json','Okaloosa Island':DATA/'okaloosa-island'/'current_flag.json','Navarre Beach':DATA/'navarre-beach'/'current_flag.json','Pensacola Beach':DATA/'pensacola-beach'/'current_flag.json'}
EVERGREEN=["Rip currents move water away from shore. If caught in one, stay calm, float or tread water, and move parallel to shore when you can. Never fight the current straight back toward the beach. 🌊","Beach flags and rip-current forecasts are related, but they are not interchangeable. The flag posted by the local beach-safety authority is the signal to follow at the beach.","A calm-looking patch of water can still contain a rip current. Gaps in breaking waves, channels of churning water, or foam moving seaward can be clues, but conditions are not always obvious.","Gulf safety starts before your feet hit the sand: check the posted beach flag, look at marine weather, identify lifeguard locations, and make sure everyone in your group knows where to meet.","Double-red flags mean the water is closed to the public where that flag system is in force. Treat the closure as a hard safety boundary, not a suggestion.","Purple flags warn of dangerous marine life. They can be flown with another flag because marine-life hazards and surf hazards are separate conditions.","Yellow flags do not mean 'safe.' They indicate moderate hazards. Weak swimmers and children still need extra caution, close supervision, and respect for local lifeguard guidance.","The Florida Panhandle can change quickly: wind shifts, thunderstorms, tides, and swell can turn a comfortable beach morning into a very different afternoon. Re-check conditions during the day."]
DESTINATION_FACTS=[('Panama City Beach',"PCB's beach day is best treated as a live system: posted flags, wind, waves, tides, and storms can all change independently. Check the official flag again before entering the Gulf."),('Destin',"Destin's passes and nearshore currents can behave differently from an open beach. Respect posted flags and avoid treating nearby calm water as proof that every stretch of shoreline is equally safe."),('Okaloosa Island',"Okaloosa Island sits between open Gulf shoreline and busy pass waters. Conditions can vary over short distances, so local flags and lifeguard direction matter more than what the water looked like earlier."),('Navarre Beach',"Navarre Beach can look beautifully calm while currents remain present. Use official beach-safety information and avoid relying on appearance alone."),('Pensacola Beach',"Pensacola Beach weather and surf can change rapidly with Gulf storms and sea-breeze boundaries. Re-check flags and weather if thunder or darkening skies approach.")]
LINK_POSTS=["Florida beach flags are easier to use when you know what each color actually means. Know the Gulf's plain-language guide: https://knowthegulf.com/florida-beach-flag-meanings/","Rip-current safety is worth learning before the emergency. Our Northwest Florida guide covers recognition, escape, and what to do if someone else is in trouble: https://knowthegulf.com/rip-current-safety/","Planning a Northwest Florida beach day? Know the Gulf brings flags, safety resources, conditions, and historical context together at https://knowthegulf.com/"]
@dataclass
class Candidate: kind:str; text:str; contains_url:bool=False; priority:int=10
def parse_args():
 p=argparse.ArgumentParser(); p.add_argument('--publish',action='store_true'); p.add_argument('--force-slot',choices=['morning','afternoon','evening']); p.add_argument('--now'); return p.parse_args()
def now_local(v):
 if v:
  d=datetime.fromisoformat(v); return d.replace(tzinfo=TZ) if d.tzinfo is None else d.astimezone(TZ)
 return datetime.now(TZ)
def load_json(p,d):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except (FileNotFoundError,json.JSONDecodeError):return d
def initial_state():return {'version':1,'last_posted_at':None,'last_link_post_at':None,'recent_fingerprints':[],'flag_state':{},'usage':{},'lifetime_estimated_spend_usd':0.0,'sequence':0}
def load_state():
 s=load_json(STATE_PATH,initial_state()); [s.setdefault(k,v) for k,v in initial_state().items()]; return s
def save_state(s):STATE_PATH.write_text(json.dumps(s,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def dt_or_none(v):
 if not v:return None
 try:return datetime.fromisoformat(v).astimezone(TZ)
 except (ValueError,TypeError):return None
def fingerprint(t):return hashlib.sha256(t.strip().lower().encode()).hexdigest()[:16]
def fresh_flag(p,now):
 d=load_json(p,{}); label=d.get('label') or d.get('flag'); verified=dt_or_none(d.get('last_verified_at')); stale=d.get('stale_after_hours',2)
 if not label or str(label).lower().startswith('check official') or not verified:return None
 if now-verified>timedelta(hours=max(float(stale or 0),2)+1):return None
 return {'label':str(label),'verified':verified,'source':d.get('source_name')}
def flag_change_candidate(s,now):
 changes=[]
 for name,p in LOCATIONS.items():
  cur=fresh_flag(p,now)
  if not cur:continue
  old=s['flag_state'].get(name); s['flag_state'][name]=cur['label']
  if old and old!=cur['label']:changes.append((name,old,cur['label']))
 if not changes:return None
 if len(changes)==1:
  name,old,new=changes[0]; text=f"⚠️ FLAG CHANGE — {name}: {old} → {new}. Follow the flag physically posted at the beach and local lifeguard instructions. Conditions can change quickly."
 else:text='⚠️ NORTHWEST FLORIDA FLAG CHANGES — '+'; '.join(f'{n}: {o} → {x}' for n,o,x in changes[:3])+'. Follow locally posted flags and lifeguard instructions.'
 return Candidate('flag-change',text,priority=100)
def morning_candidate(s,now):
 current=[]
 for name,p in LOCATIONS.items():
  f=fresh_flag(p,now)
  if f:current.append(f"{name}: {f['label']}")
 date=now.strftime('%a, %b %-d')
 if not current:return Candidate('morning-safety',f"{date}: Good morning from Know the Gulf. Before heading to a Northwest Florida beach, check the locally posted flag, marine weather, and thunderstorm risk. Conditions can differ between beaches and change during the day. 🌊")
 joined=' | '.join(current[:4]); return Candidate('morning-flags',f"{date} Northwest Florida beach flag check: {joined}. Other destinations may require an official local check. Always follow the flag posted at your beach. 🌊")
def educational_candidate(s,now):
 seq=int(s.get('sequence',0))
 if seq%3==2:
  n,f=DESTINATION_FACTS[(seq//3)%len(DESTINATION_FACTS)]; return Candidate('destination',f'{n} beach note: {f}')
 return Candidate('education',EVERGREEN[seq%len(EVERGREEN)])
def link_candidate(s,now):
 last=dt_or_none(s.get('last_link_post_at'))
 if last and now-last<timedelta(days=LINK_POST_MIN_DAYS):return None
 return Candidate('link',LINK_POSTS[int(s.get('sequence',0))%len(LINK_POSTS)],True)
def scheduled_slot(now,forced):
 if forced:return forced
 if 7<=now.hour<=9:return 'morning'
 if 14<=now.hour<=16:return 'afternoon'
 if 18<=now.hour<=20 and now.weekday() in {1,4}:return 'evening'
def usage_bucket(s,now):return s['usage'].setdefault(now.strftime('%Y-%m'),{'posts':0,'url_posts':0,'estimated_spend_usd':0.0,'days':{}})
def guardrails_allow(s,now,c):
 last=dt_or_none(s.get('last_posted_at'))
 if last and now-last<timedelta(minutes=MIN_MINUTES_BETWEEN_POSTS) and c.priority<100:return False,'minimum interval'
 b=usage_bucket(s,now); day=now.date().isoformat()
 if int(b['days'].get(day,0))>=MAX_POSTS_PER_DAY and c.priority<100:return False,'daily post cap'
 cost=URL_POST_ESTIMATE if c.contains_url else STANDARD_POST_ESTIMATE
 if float(b.get('estimated_spend_usd',0))+cost>MONTHLY_SOFT_CAP_USD and c.priority<100:return False,'monthly soft cost cap'
 if float(s.get('lifetime_estimated_spend_usd',0))+cost>LIFETIME_BUDGET_USD:return False,'lifetime $30 budget guardrail'
 if fingerprint(c.text) in s.get('recent_fingerprints',[]):return False,'duplicate fingerprint'
 return True,'ok'
def choose_candidate(s,now,forced):
 change=flag_change_candidate(s,now)
 if change:return change
 slot=scheduled_slot(now,forced)
 if slot=='morning':return morning_candidate(s,now)
 if slot=='afternoon':return educational_candidate(s,now)
 if slot=='evening':return link_candidate(s,now) or educational_candidate(s,now)
def record_post(s,now,c):
 cost=URL_POST_ESTIMATE if c.contains_url else STANDARD_POST_ESTIMATE; b=usage_bucket(s,now); day=now.date().isoformat(); b['posts']=int(b.get('posts',0))+1; b['url_posts']=int(b.get('url_posts',0))+(1 if c.contains_url else 0); b['estimated_spend_usd']=round(float(b.get('estimated_spend_usd',0))+cost,3); b['days'][day]=int(b['days'].get(day,0))+1; s['lifetime_estimated_spend_usd']=round(float(s.get('lifetime_estimated_spend_usd',0))+cost,3); s['last_posted_at']=now.isoformat(); s['last_link_post_at']=now.isoformat() if c.contains_url else s.get('last_link_post_at'); s['recent_fingerprints']=(s.get('recent_fingerprints',[])+[fingerprint(c.text)])[-40:]; s['sequence']=int(s.get('sequence',0))+1
def main():
 a=parse_args(); now=now_local(a.now); s=load_state(); c=choose_candidate(s,now,a.force_slot)
 if not c:save_state(s); print('NO_POST: no scheduled slot or verified flag change'); return 0
 allowed,reason=guardrails_allow(s,now,c)
 if not allowed:save_state(s); print(f'NO_POST: {reason}'); return 0
 if len(c.text)>280:print(f'ERROR: generated post exceeds 280 characters ({len(c.text)})',file=sys.stderr); return 1
 print(f'SELECTED_KIND={c.kind}'); print(f"ESTIMATED_COST_USD={'0.200' if c.contains_url else '0.015'}"); print(c.text)
 if a.publish:
  from post_to_x import publish
  post_id,_=publish(c.text); record_post(s,now,c); save_state(s); print(f'PUBLISHED_URL=https://x.com/knowthegulf/status/{post_id}')
 else:save_state(s); print('DRY_RUN_ONLY')
 return 0
if __name__=='__main__':raise SystemExit(main())
