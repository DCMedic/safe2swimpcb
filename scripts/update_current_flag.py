#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import re

import requests
from bs4 import BeautifulSoup

try:
    from .collector_resilience import fresh_cached_payload, mark_cached_official, retry_call
    from .common import DATA, FLAG_SEVERITY, session, now_local
except ImportError:
    from collector_resilience import fresh_cached_payload, mark_cached_official, retry_call
    from common import DATA, FLAG_SEVERITY, session, now_local

URL = 'https://www.visitpanamacitybeach.com/stay-pcb-current/'
FIELDS = ['observed_at', 'date', 'time', 'base_flag', 'purple_overlay', 'flag_label', 'severity', 'source', 'source_url', 'observation_type', 'message']
CURRENT = DATA / 'current_flag.json'
CACHE_HOURS = 2


def parse_status(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    strings = list(soup.stripped_strings)
    windows = []
    for i, value in enumerate(strings):
        if re.search(r'Current Beach Conditions', value, re.I):
            window = []
            for item in strings[i + 1:i + 8]:
                if re.search(r'Beach conditions are provided', item, re.I) or re.search(r'Beach Warning Flags', item, re.I):
                    break
                window.append(item)
            windows.append(window)
    for window in windows:
        text = ' | '.join(window)
        base = None
        if re.search(r'Double\s+Red\s+Flags?', text, re.I):
            base = 'Double Red'
        elif re.search(r'\bRed\s+Flags?', text, re.I):
            base = 'Single Red'
        elif re.search(r'Yellow\s+Flags?', text, re.I):
            base = 'Yellow'
        elif re.search(r'Green\s+Flags?', text, re.I):
            base = 'Green'
        if base:
            purple = bool(re.search(r'Purple\s+Flags?', text, re.I))
            return base, purple, base + (' + Purple' if purple else '')
    raise RuntimeError('Could not identify a flag within the Current Beach Conditions section')


def load_old():
    try:
        value = json.loads(CURRENT.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def read_log():
    path = DATA / 'flag_observations_auto.csv'
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def fetch_live_status():
    def operation():
        response = session().get(URL, timeout=(5, 20))
        response.raise_for_status()
        return parse_status(response.text)

    return retry_call(
        operation,
        attempts=3,
        base_delay_seconds=1,
        retry_exceptions=(requests.RequestException, RuntimeError),
        on_error=lambda attempt, exc: print(f'PCB source attempt {attempt} failed: {type(exc).__name__}: {exc}'),
    )


def write_degraded_status(now, old: dict, exc: BaseException) -> None:
    cached, age = fresh_cached_payload(CURRENT, now, max_age_hours=CACHE_HOURS)
    if cached:
        out = mark_cached_official(
            cached,
            now,
            exc,
            method='Cached last-known official PCB flag after bounded live-source retries failed',
        )
        out['cache_age_hours'] = round(age, 2) if age is not None else None
        CURRENT.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
        print('PCB live verification degraded; retained fresh cached official flag', out.get('label'), 'age_hours=', out.get('cache_age_hours'))
        return

    out = {
        'flag': None,
        'purple': False,
        'label': 'Official flag status unavailable',
        'severity': None,
        'provenance_tier': 'unavailable',
        'last_verified_at': old.get('last_verified_at'),
        'last_checked_at': now.isoformat(),
        'status_changed_at': old.get('status_changed_at'),
        'source_name': 'Visit Panama City Beach / Beach & Surf Patrol',
        'source_url': URL,
        'source_check_status': 'unavailable',
        'source_error': str(exc)[:500],
        'method': 'No current authoritative PCB flag could be verified after bounded retries; forecast conditions are never converted into a flag',
        'stale_after_hours': 0,
        'stale_reason': 'The previous official observation exceeded its freshness window and the live source could not be verified.',
        'note': 'last_verified_at is never advanced by a failed source check. Posted flags and Beach & Surf Patrol instructions control.',
    }
    CURRENT.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
    print('PCB official flag unavailable after retries and cached evidence expired')


def main():
    now = now_local()
    old = load_old()
    fixture = os.getenv('SAFE2SWIM_FIXTURE')
    if fixture:
        html = open(fixture, encoding='utf-8').read()
        base, purple, label = parse_status(html)
    else:
        try:
            base, purple, label = fetch_live_status()
        except (requests.RequestException, RuntimeError) as exc:
            write_degraded_status(now, old, exc)
            return

    rows = read_log()
    today = now.date().isoformat()
    changed = bool(old.get('label')) and old.get('label') != label
    first = not any(row.get('date') == today for row in rows)
    if changed or first:
        with (DATA / 'flag_observations_auto.csv').open('a', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            if handle.tell() == 0:
                writer.writeheader()
            writer.writerow({
                'observed_at': now.isoformat(),
                'date': today,
                'time': now.strftime('%H:%M:%S'),
                'base_flag': base,
                'purple_overlay': purple,
                'flag_label': label,
                'severity': FLAG_SEVERITY[base],
                'source': 'Visit PCB / Beach & Surf Patrol',
                'source_url': URL,
                'observation_type': 'status_change' if changed else 'daily_snapshot',
                'message': f'Current Beach Conditions: {label} Flag',
            })

    status_changed_at = now.isoformat() if changed or not old.get('status_changed_at') else old.get('status_changed_at')
    out = {
        'flag': base,
        'purple': purple,
        'label': label,
        'severity': FLAG_SEVERITY[base],
        'provenance_tier': 'primary_official',
        'cached': False,
        'last_verified_at': now.isoformat(),
        'last_checked_at': now.isoformat(),
        'status_changed_at': status_changed_at,
        'source_name': 'Visit Panama City Beach / Beach & Surf Patrol',
        'source_url': URL,
        'source_check_status': 'verified',
        'method': 'Scheduled public current-condition snapshot with bounded fetch-and-parse retries',
        'stale_after_hours': CACHE_HOURS,
        'stale_reason': None,
        'note': 'last_verified_at is the most recent successful Know the Gulf poll. status_changed_at is when Know the Gulf first observed the current flag status. Polling time is not guaranteed to equal the exact official issuance time.',
    }
    CURRENT.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
    print(label, now.isoformat(), 'changed=', changed, 'first_today=', first, 'verification_refreshed=true')


if __name__ == '__main__':
    main()
