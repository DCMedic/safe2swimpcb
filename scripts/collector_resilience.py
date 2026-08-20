from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def parse_iso_datetime(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def hours_old(timestamp: datetime | None, now: datetime) -> float | None:
    if timestamp is None:
        return None
    if timestamp.tzinfo is None and now.tzinfo is not None:
        timestamp = timestamp.replace(tzinfo=now.tzinfo)
    if timestamp.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=timestamp.tzinfo)
    return max(0.0, (now.astimezone(timestamp.tzinfo) - timestamp).total_seconds() / 3600.0) if timestamp.tzinfo else max(0.0, (now - timestamp).total_seconds() / 3600.0)


def fresh_cached_payload(
    path: Path,
    now: datetime,
    *,
    max_age_hours: float | None = None,
    flag_keys: tuple[str, ...] = ("flag", "primary_flag"),
) -> tuple[dict | None, float | None]:
    """Return a previously verified flag only while its original evidence is fresh.

    This intentionally uses the previous successful verification timestamp. A failed
    source check must never manufacture a new last_verified_at value.
    """
    payload = load_json(path)
    if not any(payload.get(key) for key in flag_keys):
        return None, None

    verified = parse_iso_datetime(payload.get("last_verified_at") or payload.get("official_updated_at"))
    age = hours_old(verified, now)
    if age is None:
        return None, None

    limit = max_age_hours
    if limit is None:
        try:
            limit = float(payload.get("stale_after_hours"))
        except (TypeError, ValueError):
            return None, age
    if limit is None or limit <= 0 or age > limit:
        return None, age
    return payload, age


def mark_cached_official(
    payload: dict,
    now: datetime,
    error: BaseException | str,
    *,
    method: str | None = None,
) -> dict:
    """Mark a last-known-good official observation as cached without refreshing it."""
    out = dict(payload)
    previous_tier = out.get("provenance_tier")
    if previous_tier and previous_tier != "cached_official_observation":
        out["cached_from_provenance_tier"] = previous_tier
    out["provenance_tier"] = "cached_official_observation"
    out["cached"] = True
    out["last_checked_at"] = now.isoformat()
    out["source_check_status"] = "degraded"
    out["source_error"] = str(error)[:500]
    out["stale_reason"] = (
        "Live source verification failed; retaining the last successfully verified official observation "
        "only until its existing freshness window expires."
    )
    if method:
        out["method"] = method
    return out


def retry_call(
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 0.75,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
    on_error: Callable[[int, BaseException], None] | None = None,
) -> T:
    """Retry a bounded fetch-and-parse operation, including parser failures."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except retry_exceptions as exc:
            last_error = exc
            if on_error:
                on_error(attempt, exc)
            if attempt < attempts and base_delay_seconds > 0:
                time.sleep(base_delay_seconds * attempt)
    assert last_error is not None
    raise last_error
