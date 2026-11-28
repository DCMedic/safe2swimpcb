"""Conservative no-JavaScript snapshot. Runtime revalidates before claiming current."""
from pathlib import Path
import html
import json
import re

try:
    from .source_evidence import observation_time, parse_time
except ImportError:
    from source_evidence import observation_time, parse_time

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'index.html'
DATA = ROOT / 'data/current_flag.json'


def snapshot_label(record):
    def canonical(value):
        if not isinstance(value, str):
            return None
        return 'Red' if value == 'Single Red' else value if value in {'Green', 'Yellow', 'Red', 'Double Red'} else None
    primary, flag = canonical(record.get('primary_flag')), canonical(record.get('flag'))
    conflict = any(record.get(key) for key in ('flag_conflict', 'visitbeaches_flag_conflict', 'evidence_conflict')) or (primary and flag and primary != flag)
    if conflict:
        distinct = record.get('fresh_distinct_flags')
        flags = sorted({x for x in (primary, flag, *[canonical(x) for x in (distinct if isinstance(distinct, list) else [])]) if x})
        warnings = ' / '.join(flags) + (' + Purple' if record.get('purple') is True else '')
        return 'Conflicting cached flag reports' + (f': {warnings}' if warnings else '') + '. Check the official source.'
    if any(value is not None and value != '' and value != 'Purple' and canonical(value) is None for value in (record.get('primary_flag'), record.get('flag'))):
        return 'Current flag unavailable. Check the official source.'
    purple = record.get('purple') is True or record.get('flag') == 'Purple'
    label = ' + '.join(x for x in (primary or flag, 'Purple' if purple else None) if x)
    return f'Cached flag snapshot: {label}' if label else 'Current flag unavailable. Check the official source.'


def evidence_stamp(record):
    stamp = observation_time(record)
    return stamp if parse_time(stamp) is not None else None


def render_snapshot(text, record):
    label = snapshot_label(record)
    text = re.sub(r'(<div id="currentFlag" class="flagname">).*?(</div>)', lambda m: m[1] + html.escape(label) + m[2], text, count=1, flags=re.S)
    text = re.sub(r'<div id="flagPole"[^>]*>.*?</div>', '<div id="flagPole" class="flagpole" hidden></div>', text, count=1, flags=re.S)
    meaning = 'Cached information is not a current-status claim. Check the official source and posted flags before entering the water.'
    text = re.sub(r'(<div id="currentMeaning" class="muted">).*?(</div>)', lambda m: m[1] + meaning + m[2], text, count=1, flags=re.S)
    stamp = evidence_stamp(record)
    msg = f'Evidence time: {html.escape(str(stamp))}. ' if stamp else 'Evidence time unavailable. '
    msg += 'This snapshot may have expired. JavaScript must validate freshness before a current flag is displayed. Follow posted flags and lifeguards.'
    text = re.sub(r'<div id="flagFreshness"[^>]*>.*?</div>', '<div id="flagFreshness" class="status flag-status stale">' + msg + '</div>', text, count=1, flags=re.S)
    return text


def main():
    if not INDEX.exists() or not DATA.exists():
        return
    record = json.loads(DATA.read_text(encoding='utf-8'))
    INDEX.write_text(render_snapshot(INDEX.read_text(encoding='utf-8'), record), encoding='utf-8')
    print('Pre-rendered conservative PCB snapshot; runtime validation required for current status')


if __name__ == '__main__':
    main()
