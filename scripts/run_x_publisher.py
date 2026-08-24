#!/usr/bin/env python3
"""Run the X content engine while recording a durable publisher health heartbeat."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
HEALTH_PATH = ROOT / "data" / "x_publisher_health.json"
TZ = ZoneInfo("America/Chicago")
MAX_POST_LENGTH = 280


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--force-slot", choices=["morning", "afternoon", "evening"])
    known, unknown = parser.parse_known_args()
    forwarded: list[str] = []
    if known.publish:
        forwarded.append("--publish")
    if known.force_slot:
        forwarded.extend(["--force-slot", known.force_slot])
    forwarded.extend(unknown)
    return known, forwarded


def _trim_words(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    clipped = text[: limit - 1].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0].rstrip()
    return clipped + "…"


def fit_post(text: str, kind: str = "", contains_url: bool = False) -> str:
    """Compact generated text to X's 280-character limit without breaking URLs."""
    if len(text) <= MAX_POST_LENGTH:
        return text

    if contains_url and " → " in text:
        prefix, url = text.rsplit(" → ", 1)
        suffix = f" → {url}"
        if len(suffix) < MAX_POST_LENGTH:
            return _trim_words(prefix, MAX_POST_LENGTH - len(suffix)) + suffix

    if kind == "flag-change":
        suffix = " Follow locally posted flags and lifeguard instructions."
        base = text.split(". Follow", 1)[0].rstrip(" .")
        return _trim_words(base, MAX_POST_LENGTH - len(suffix)) + suffix

    return _trim_words(text, MAX_POST_LENGTH)


def classify(returncode: int, stdout: str, stderr: str) -> tuple[str, str | None]:
    if returncode != 0:
        detail = (stderr or stdout).strip().splitlines()
        return "failed", (detail[-1][:1000] if detail else f"exit code {returncode}")
    if "PUBLISHED_URL=" in stdout:
        return "published", None
    for line in stdout.splitlines():
        if line.startswith("NO_POST:"):
            return "no_post", line.partition(":")[2].strip() or None
    if "DRY_RUN_ONLY" in stdout:
        return "dry_run", None
    return "completed", None


def write_health(now: datetime, publish: bool, slot: str | None, returncode: int, outcome: str, detail: str | None) -> None:
    previous = {}
    try:
        previous = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    payload = {
        "version": 1,
        "last_evaluated_at": now.isoformat(),
        "last_outcome": outcome,
        "last_outcome_detail": detail,
        "publish_requested": publish,
        "forced_slot": slot,
        "exit_code": returncode,
        "last_published_at": previous.get("last_published_at"),
        "last_failure_at": previous.get("last_failure_at"),
    }
    if outcome == "published":
        payload["last_published_at"] = now.isoformat()
    if outcome == "failed":
        payload["last_failure_at"] = now.isoformat()
    HEALTH_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_engine(forwarded: list[str]) -> tuple[int, str, str]:
    import x_content_engine as engine

    original_choose = engine.choose_candidate
    original_fresh_flag = engine.fresh_flag

    def safe_fresh_flag(path, now):
        result = original_fresh_flag(path, now)
        if not result:
            return None
        label = str(result.get("label", "")).strip().lower()
        if "unavailable" in label or label.startswith("official flag status"):
            return None
        return result

    def safe_choose(state, now, forced):
        candidate = original_choose(state, now, forced)
        if candidate:
            candidate.text = fit_post(candidate.text, candidate.kind, candidate.contains_url)
        return candidate

    engine.fresh_flag = safe_fresh_flag
    engine.choose_candidate = safe_choose

    stdout = io.StringIO()
    stderr = io.StringIO()
    old_argv = sys.argv[:]
    sys.argv = [str(Path(engine.__file__)), *forwarded]
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                returncode = int(engine.main() or 0)
            except SystemExit as exc:
                returncode = int(exc.code or 0)
            except Exception as exc:
                print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
                returncode = 1
    finally:
        sys.argv = old_argv
        engine.choose_candidate = original_choose
        engine.fresh_flag = original_fresh_flag
    return returncode, stdout.getvalue(), stderr.getvalue()


def main() -> int:
    args, forwarded = parse_args()
    now = datetime.now(TZ)
    returncode, stdout, stderr = run_engine(forwarded)
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)
    outcome, detail = classify(returncode, stdout, stderr)
    write_health(now, args.publish, args.force_slot, returncode, outcome, detail)
    print(f"PUBLISHER_HEALTH={outcome}")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
