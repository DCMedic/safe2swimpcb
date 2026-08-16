#!/usr/bin/env python3
"""Publish a single post to the official Know the Gulf X account."""
from __future__ import annotations
import argparse, base64, os, sys
from pathlib import Path
import requests
from requests_oauthlib import OAuth1
API_URL='https://api.x.com/2/tweets'; MEDIA_V2_URL='https://api.x.com/2/media/upload'; MEDIA_LEGACY_URL='https://upload.x.com/1.1/media/upload.json'; ACCOUNT_HANDLE='knowthegulf'; MAX_POST_LENGTH=280
REQUIRED_ENV=('X_API_KEY','X_API_KEY_SECRET','X_ACCESS_TOKEN','X_ACCESS_TOKEN_SECRET')
def parse_args():
 p=argparse.ArgumentParser(description='Publish one Know the Gulf post to X'); p.add_argument('--text',required=True); p.add_argument('--media'); p.add_argument('--dry-run',action='store_true'); return p.parse_args()
def validate_text(text):
 text=text.strip()
 if not text:raise ValueError('Post text cannot be empty')
 if len(text)>MAX_POST_LENGTH:raise ValueError(f'Post is {len(text)} characters; limit is {MAX_POST_LENGTH}')
 return text
def get_auth():
 missing=[n for n in REQUIRED_ENV if not os.getenv(n)]
 if missing:raise RuntimeError('Missing required GitHub Actions secrets: '+', '.join(missing))
 return OAuth1(os.environ['X_API_KEY'],os.environ['X_API_KEY_SECRET'],os.environ['X_ACCESS_TOKEN'],os.environ['X_ACCESS_TOKEN_SECRET'])
def maybe_generate_condition_card(text):
 lowered=text.lower(); triggers=('northwest florida beach flag check','flag change','beach flag update','beach flag updates')
 if not any(t in lowered for t in triggers):return None
 try:
  from generate_x_condition_card import draw_card
  out=Path(__file__).resolve().parents[1]/'tmp'/'x-condition-card.png'; urgent='flag change' in lowered; draw_card(out,'FLAG CHANGE' if urgent else 'Northwest Florida Beach Check',urgent=urgent); return out
 except Exception as exc:print(f'WARNING: condition card generation failed; continuing text-only: {exc}',file=sys.stderr); return None
def upload_media_v2(path,token):
 raw=path.read_bytes()
 if len(raw)>5*1024*1024:raise RuntimeError("Image exceeds X's 5 MB image upload limit")
 mime='image/png' if path.suffix.lower()=='.png' else 'image/jpeg'; r=requests.post(MEDIA_V2_URL,headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'},json={'media':base64.b64encode(raw).decode('ascii'),'media_category':'tweet_image','media_type':mime,'shared':False},timeout=45)
 if r.status_code not in {200,201}:raise RuntimeError(f'X v2 media upload returned HTTP {r.status_code}: {r.text[:1000]}')
 mid=r.json().get('data',{}).get('id')
 if not mid:raise RuntimeError('X v2 media upload response did not include a media id')
 return str(mid)
def upload_media_legacy(path):
 if path.stat().st_size>5*1024*1024:raise RuntimeError("Image exceeds X's 5 MB image upload limit")
 mime='image/png' if path.suffix.lower()=='.png' else 'image/jpeg'
 with path.open('rb') as fh:r=requests.post(MEDIA_LEGACY_URL,auth=get_auth(),files={'media':(path.name,fh,mime)},data={'media_category':'tweet_image'},timeout=45)
 if r.status_code not in {200,201,202}:raise RuntimeError(f'X legacy media upload returned HTTP {r.status_code}: {r.text[:1000]}')
 p=r.json(); mid=p.get('media_id_string') or p.get('media_id') or p.get('data',{}).get('id')
 if not mid:raise RuntimeError('X legacy media upload response did not include a media id')
 return str(mid)
def upload_media(path):
 oauth2=os.getenv('X_OAUTH2_ACCESS_TOKEN','').strip(); return upload_media_v2(path,oauth2) if oauth2 else upload_media_legacy(path)
def publish(text,media_path=None):
 text=validate_text(text); resolved=Path(media_path) if media_path else None
 if resolved is None:
  env=os.getenv('X_MEDIA_PATH','').strip(); resolved=Path(env) if env else maybe_generate_condition_card(text)
 body={'text':text}
 if resolved and resolved.exists():
  try:body['media']={'media_ids':[upload_media(resolved)]}; print(f'Attached condition card: {resolved.name}')
  except Exception as exc:print(f'WARNING: media upload failed; publishing text-only: {exc}',file=sys.stderr)
 r=requests.post(API_URL,auth=get_auth(),json=body,headers={'Content-Type':'application/json'},timeout=30)
 if r.status_code!=201:raise RuntimeError(f'X API returned HTTP {r.status_code}: {r.text[:2000]}')
 p=r.json(); return str(p['data']['id']),str(p['data'].get('text',text))
def main():
 a=parse_args()
 try:
  text=validate_text(a.text)
  if a.dry_run:print(f'DRY RUN: validated {len(text)} characters'); print(text); return 0
  post_id,_=publish(text,a.media); print('Post published successfully.'); print(f'Post ID: {post_id}'); print(f'URL: https://x.com/{ACCOUNT_HANDLE}/status/{post_id}'); return 0
 except Exception as exc:print(f'ERROR: {exc}',file=sys.stderr); return 1
if __name__=='__main__':raise SystemExit(main())
