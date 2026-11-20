#!/usr/bin/env python3
"""Write build evidence. A build marker is never proof of a live deployment."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ('javascript', 'python', 'repository_tests', 'prerender', 'site_health',
          'workflow_architecture', 'infrastructure', 'artifact')
MARKER = 'data/site_build_health.json'
OUTCOMES = {'success': 'passed', 'failure': 'failed', 'cancelled': 'cancelled', 'skipped': 'not_run', '': 'not_run'}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_out_sha(root: Path) -> str:
    # GITHUB_SHA may identify the triggering workflow rather than this checkout.
    return subprocess.check_output(['git', 'rev-parse', '--verify', 'HEAD^{commit}'], cwd=root, text=True).strip()


def validate_release_identity(sha: str, run_id: str, run_attempt: str) -> None:
    if not isinstance(sha, str) or re.fullmatch(r'[0-9a-f]{40}', sha) is None:
        raise ValueError('Release commit_sha must be a full 40-character hexadecimal SHA')
    for name, value in (('run_id', run_id), ('run_attempt', run_attempt)):
        if not isinstance(value, str) or re.fullmatch(r'[1-9][0-9]*', value) is None:
            raise ValueError(f'Release {name} must be a positive workflow identity; local builds cannot attest to a workflow run')


def write_health(site: Path, target: str, *, root: Path = ROOT, expected_sha: str | None = None) -> dict:
    if target not in {'github-pages', 'vps'}:
        raise ValueError('Unknown deployment target')
    sha = checked_out_sha(root)
    if expected_sha is not None and sha != expected_sha:
        raise ValueError('Checkout SHA changed after validation began')
    run_id, run_attempt = os.getenv('GITHUB_RUN_ID'), os.getenv('GITHUB_RUN_ATTEMPT')
    validate_release_identity(sha, run_id, run_attempt)
    validation = {}
    for check in CHECKS:
        outcome = os.getenv(f'BUILD_{check.upper()}_RESULT', '')
        if outcome not in OUTCOMES:
            raise ValueError(f'Invalid result for {check}: {outcome!r}')
        validation[check] = OUTCOMES[outcome]
    inventory = {}
    for path in sorted(site.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'Symlink in artifact: {path}')
        if path.is_file() and path.relative_to(site).as_posix() != MARKER:
            inventory[path.relative_to(site).as_posix()] = file_hash(path)
    for required in ('index.html', 'data/current_flag.json'):
        if required not in inventory:
            raise ValueError(f'Artifact missing {required}')
    payload = {
        'schema_version': 2,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'commit_sha': sha,
        'trigger_sha': os.getenv('GITHUB_SHA'),
        'run_id': run_id,
        'run_attempt': run_attempt,
        'event': os.getenv('GITHUB_EVENT_NAME'),
        'validation': validation,
        'build_status': 'passed' if all(v == 'passed' for v in validation.values()) else 'not_passed',
        'deployment': {'target': target, 'status': 'not_verified'},
        'artifact_sha256': inventory,
        'purpose': 'Build evidence only. Live target verification is a separate operation; collector freshness is independent.',
    }
    path = site / MARKER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-dir', type=Path, required=True)
    parser.add_argument('--target', choices=('github-pages', 'vps'), required=True)
    parser.add_argument('--expected-sha', required=True)
    args = parser.parse_args()
    payload = write_health(args.site_dir, args.target, expected_sha=args.expected_sha)
    print(f"Wrote build marker for {payload['commit_sha']}: {payload['build_status']}; deployment not verified")
    if payload['build_status'] != 'passed':
        raise SystemExit('Refusing deployment: required validation did not pass')


if __name__ == '__main__':
    main()
