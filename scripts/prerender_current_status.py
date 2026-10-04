from pathlib import Path
import html,json,re
ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/"index.html"
DATA=ROOT/"data/current_flag.json"

FLAG_UI = {
    "Green": ("green", "Low hazard — exercise caution."),
    "Yellow": ("", "Medium hazard — moderate surf and/or currents."),
    "Red": ("red", "High hazard — high surf and/or strong currents."),
    "Single Red": ("red", "High hazard — high surf and/or strong currents."),
    "Double Red": ("double", "Water closed to the public."),
}

def main():
    if not INDEX.exists() or not DATA.exists(): return
    c=json.loads(DATA.read_text(encoding="utf-8"))
    flag=c.get("flag")
    label=c.get("label") or flag or "Verify official flag"
    verified=c.get("last_verified_at")
    css_class, meaning = FLAG_UI.get(flag, ("", "Verify the official PCB current-conditions source."))
    text=INDEX.read_text(encoding="utf-8")
    text=re.sub(r'(<div id="currentFlag" class="flagname">).*?(</div>)',lambda m:m.group(1)+html.escape(str(label))+m.group(2),text,count=1)
    text=re.sub(r'<div id="flagPole" class="flagpole(?: [^"]*)?">', f'<div id="flagPole" class="flagpole{(" "+css_class) if css_class else ""}">', text, count=1)
    text=re.sub(r'(<div id="currentMeaning" class="muted">).*?(</div>)',lambda m:m.group(1)+html.escape(meaning)+m.group(2),text,count=1)
    if flag == "Double Red":
        text=text.replace('<span class="flagshape" hidden></span>', '<span class="flagshape"></span>', 1)
    else:
        text=re.sub(r'<span class="flagshape"></span>(</div><div><div id="currentFlag")', r'<span class="flagshape" hidden></span>\1', text, count=1)
    if verified:
        msg=f'Last verified by automation: <strong>{html.escape(str(verified))}</strong>. Live JavaScript will refresh this timestamp for your locale.'
        text=re.sub(r'(<div id="flagFreshness" class="status flag-status">).*?(</div>)',lambda m:m.group(1)+msg+m.group(2),text,count=1)
    INDEX.write_text(text,encoding="utf-8")
    print(f"Pre-rendered current PCB status into deployment HTML: flag={flag!r} class={css_class!r}")
if __name__=="__main__": main()
