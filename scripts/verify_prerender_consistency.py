#!/usr/bin/env python3
from __future__ import annotations
import argparse,html,json,re,sys,time
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data/current_flag.json"; INDEX=ROOT/"index.html"
def expected():
 d=json.loads(DATA.read_text(encoding="utf-8")); label=str(d.get("label") or d.get("flag") or "Verify official flag"); verified=str(d.get("last_verified_at") or "")
 if not verified: raise ValueError("data/current_flag.json missing last_verified_at")
 return label,verified
def check_text(text):
 label,verified=expected(); errors=[]; m=re.search(r'<div id="currentFlag" class="flagname">(.*?)</div>',text,re.S)
 rendered=html.unescape(re.sub(r"<[^>]+>","",m.group(1))).strip() if m else None
 if rendered!=label: errors.append(f"rendered PCB flag {rendered!r} != authoritative label {label!r}")
 if verified not in text: errors.append(f"authoritative PCB verification timestamp {verified!r} missing from rendered HTML")
 if "Checking the locally cached official status" in text: errors.append("neutral PCB loading placeholder remains in rendered HTML")
 return errors
def fetch(url):
 req=Request(url,headers={"Cache-Control":"no-cache","Pragma":"no-cache","User-Agent":"KnowTheGulf-deployment-verifier/1.0"})
 with urlopen(req,timeout=20) as r:return r.read().decode("utf-8","replace")
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--url");ap.add_argument("--attempts",type=int,default=1);ap.add_argument("--delay",type=int,default=15);args=ap.parse_args()
 for attempt in range(1,args.attempts+1):
  try:
   text=fetch(f"{args.url}?deployment_verify={int(time.time())}") if args.url else INDEX.read_text(encoding="utf-8");errors=check_text(text)
  except Exception as exc:errors=[f"verification request failed: {exc}"]
  if not errors:print(f"PCB prerender consistency verified ({'production' if args.url else 'local artifact'})");return 0
  print(f"Attempt {attempt}/{args.attempts}: "+"; ".join(errors),file=sys.stderr)
  if attempt<args.attempts:time.sleep(args.delay)
 return 1
if __name__=="__main__":raise SystemExit(main())
