from __future__ import annotations
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data';TZ=ZoneInfo('America/Chicago')
FLAG_SEVERITY={'Green':1,'Yellow':2,'Single Red':3,'Double Red':4}
def session():
    s=requests.Session();retry=Retry(total=4,backoff_factor=.8,status_forcelist=[429,500,502,503,504],allowed_methods=['GET'])
    s.mount('https://',HTTPAdapter(max_retries=retry));s.headers['User-Agent']='KnowTheGulf/1.0 (+https://knowthegulf.com; public coastal-safety research)';return s
def now_local(): return datetime.now(TZ)
def get_json(url,params=None,timeout=60):
    r=session().get(url,params=params,timeout=timeout);r.raise_for_status();return r.json()
