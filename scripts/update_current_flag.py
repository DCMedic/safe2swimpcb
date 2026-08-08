#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re,os
from datetime import datetime
from bs4 import BeautifulSoup
try:
    from .common import ROOT,DATA,TZ,FLAG_SEVERITY,session,now_local
except ImportError:
    from common import ROOT,DATA,TZ,FLAG_SEVERITY,session,now_local
URL='https://www.visitpanamacitybeach.com/stay-pcb-current/'
FIELDS=['observed_at','date','time','base_flag','purple_overlay','flag_label','severity','source','source_url','observation_type','message']
def parse_status(html:str):
    soup=BeautifulSoup(html,'html.parser'); strings=list(soup.stripped_strings)
    windows=[]
    for i,s in enumerate(strings):
        if re.search(r'Current Beach Conditions',s,re.I):
            w=[]
            for item in strings[i+1:i+6]:
                if re.search(r'Beach conditions are provided',item,re.I) or re.search(r'Beach Warning Flags',item,re.I): break
                w.append(item)
            windows.append(w)
    for w in windows:
        text=' | '.join(w)
        base=None
        if re.search(r'Double\s+Red\s+Flags?',text,re.I):base='Double Red'
        elif re.search(r'\bRed\s+Flags?',text,re.I):base='Single Red'
        elif re.search(r'Yellow\s+Flags?',text,re.I):base='Yellow'
        elif re.search(r'Green\s+Flags?',text,re.I):base='Green'
        if base:
            purple=bool(re.search(r'Purple\s+Flags?',text,re.I));return base,purple,base+(' + Purple' if purple else '')
    raise RuntimeError('Could not identify a flag within the Current Beach Conditions section')
def load_old():
    p=DATA/'current_flag.json'
    try:return json.loads(p.read_text())
    except:return {}
def read_log():
    p=DATA/'flag_observations_auto.csv'
    if not p.exists():return []
    with p.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
def main():
    fixture=os.getenv('SAFE2SWIM_FIXTURE')
    if fixture:
        html=open(fixture,encoding='utf-8').read()
    else:
        resp=session().get(URL,timeout=30);resp.raise_for_status();html=resp.text
    base,purple,label=parse_status(html);now=now_local();old=load_old();rows=read_log();today=now.date().isoformat()
    changed=bool(old.get('label')) and old.get('label')!=label
    first=not any(r.get('date')==today for r in rows)
    if changed or first:
        with (DATA/'flag_observations_auto.csv').open('a',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS)
            if f.tell()==0:w.writeheader()
            w.writerow({'observed_at':now.isoformat(),'date':today,'time':now.strftime('%H:%M:%S'),'base_flag':base,'purple_overlay':purple,'flag_label':label,'severity':FLAG_SEVERITY[base],'source':'Visit PCB / Beach & Surf Patrol','source_url':URL,'observation_type':'status_change' if changed else 'daily_snapshot','message':f'Current Beach Conditions: {label} Flag'})
    status_changed_at=now.isoformat() if changed or not old.get('status_changed_at') else old.get('status_changed_at')
    out={
        'flag':base,
        'purple':purple,
        'label':label,
        'last_verified_at':now.isoformat(),
        'status_changed_at':status_changed_at,
        'source_name':'Visit Panama City Beach / Beach & Surf Patrol',
        'source_url':URL,
        'method':'Scheduled public current-condition snapshot',
        'stale_after_hours':2,
        'note':'last_verified_at is the most recent successful Know the Gulf poll. status_changed_at is when Know the Gulf first observed the current flag status. Polling time is not guaranteed to equal the exact official issuance time.'
    }
    (DATA/'current_flag.json').write_text(json.dumps(out,indent=2)+'\n')
    print(label,now.isoformat(),'changed=',changed,'first_today=',first,'verification_refreshed=true')
if __name__=='__main__':main()
