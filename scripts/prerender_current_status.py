from pathlib import Path
import html,json,re
ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/"index.html"
DATA=ROOT/"data/current_flag.json"

def main():
    if not INDEX.exists() or not DATA.exists(): return
    c=json.loads(DATA.read_text(encoding="utf-8"))
    label=c.get("label") or c.get("flag") or "Verify official flag"
    verified=c.get("last_verified_at")
    text=INDEX.read_text(encoding="utf-8")
    text=re.sub(r'(<div id="currentFlag" class="flagname">).*?(</div>)',lambda m:m.group(1)+html.escape(str(label))+m.group(2),text,count=1)
    if verified:
        msg=f'Last verified by automation: <strong>{html.escape(str(verified))}</strong>. Live JavaScript will refresh this timestamp for your locale.'
        text=re.sub(r'(<div id="flagFreshness" class="status flag-status">).*?(</div>)',lambda m:m.group(1)+msg+m.group(2),text,count=1)
    INDEX.write_text(text,encoding="utf-8")
    print("Pre-rendered current PCB status into deployment HTML")
if __name__=="__main__": main()
