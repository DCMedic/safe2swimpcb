"""Fail-closed, decision-time validation shared by source adapters."""
from datetime import datetime, timezone
import math
import re

MAX_TTL_HOURS = 24


def parse_time(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)', value):
        return None
    if value[-1] != 'Z' and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except ValueError:
        return None


def valid_ttl(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and 0 < value <= MAX_TTL_HOURS)


def fresh_at(stamp, ttl, now):
    dt = parse_time(stamp)
    if dt is None or not valid_ttl(ttl):
        return False
    return 0 <= (now - dt).total_seconds() < ttl * 3600


def canonical_flag(flag):
    if not isinstance(flag, str):
        return None
    return 'Red' if flag == 'Single Red' else flag if flag in {'Green', 'Yellow', 'Red', 'Double Red'} else None


def observation_time(record):
    # An explicitly present invalid observation must not fall back to a check time.
    for key in ('observed_at', 'official_updated_at', 'last_verified_at'):
        if key in record:
            return record[key]
    return None


def visitbeaches_lineage(record):
    return any('visitbeaches' in str(record.get(k, '')).lower() for k in (
        'source_lineage', 'source_name', 'source_url', 'source_data_url', 'provenance_tier'))


def current_visitbeaches(record, now):
    """Recompute cached summaries; collection-time fresh booleans are not evidence."""
    result = dict(record)
    ttl = record.get('freshness_hours')
    observations = record.get('observations')
    if isinstance(observations, list):
        fresh = [o for o in observations if isinstance(o, dict) and fresh_at(o.get('created_at'), ttl, now)]
        flags = sorted({canonical_flag(f) for o in fresh for f in ([o.get('flag')] + (o.get('reported_flags') or [])) if canonical_flag(f)})
        explicit = [o for o in fresh if canonical_flag(o.get('flag')) or o.get('reported_flags') or o.get('purple') is True]
        conflict = len(flags) > 1 or any(o.get('flag_conflict') is True for o in fresh)
        result.update(flag=flags[0] if len(flags) == 1 and not conflict else None,
                      purple=any(o.get('purple') is True for o in fresh),
                      flag_conflict=conflict, fresh_distinct_flags=flags,
                      fresh_observation_count=len(fresh),
                      report_at=min((o['created_at'] for o in explicit), key=parse_time, default=None),
                      report_ids=[o.get('report_id') for o in explicit])
    else:
        report = record.get('newest_flag_report') or {}
        stamp = record['report_at'] if 'report_at' in record else report.get('created_at')
        if not fresh_at(stamp, ttl, now):
            result.update(flag=None, purple=False, flag_conflict=False, fresh_distinct_flags=[], fresh_observation_count=0)
        else:
            result['flag'] = canonical_flag(record.get('flag'))
        result['report_at'] = stamp
    return result


def reset_primary_evidence(payload, stamp, source_url):
    """A new direct observation replaces old source identity and timestamp aliases."""
    from urllib.parse import urlparse
    payload['observed_at'] = stamp
    payload['source_lineage'] = ('visitbeaches' if 'visitbeaches' in str(source_url).lower()
                                 else urlparse(source_url or '').hostname or 'official_primary')
    for key in ('observation_at', 'official_updated_at', 'source_data_url',
                'visitbeaches_flag_conflict', 'visitbeaches_observations',
                'visitbeaches_fresh_distinct_flags', 'flag_conflict'):
        payload.pop(key, None)
