#!/usr/bin/env python3
"""Verify a staged build or explicitly named serving target without deploying it."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

try:
    from .write_build_health import CHECKS, MARKER, file_hash, validate_release_identity
except ImportError:
    from write_build_health import CHECKS, MARKER, file_hash, validate_release_identity

ROOT = Path(__file__).resolve().parents[1]
PAGES_HOST = 'dcmedic.github.io'
PAGES_PATH = '/safe2swimpcb/'


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if origin(req.full_url) != origin(newurl):
            raise ValueError(f'Redirect left the requested serving target: {newurl}')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def origin(url: str) -> tuple:
    parsed = urlsplit(url)
    return parsed.scheme, parsed.hostname, parsed.port


def fetch(url: str) -> tuple[bytes, dict[str, str]]:
    parsed = urlsplit(url)
    query = parsed.query + ('&' if parsed.query else '') + f'release_verify={time.time_ns()}'
    url = urlunsplit(parsed._replace(query=query))
    request = Request(url, headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache',
                                   'User-Agent': 'KnowTheGulf-release-verifier/1.0'})
    with build_opener(SameOriginRedirect()).open(request, timeout=20) as response:
        return response.read(), {key.lower(): value for key, value in response.headers.items()}


def validate_marker(marker: dict) -> None:
    validate_release_identity(marker.get('commit_sha'), marker.get('run_id'), marker.get('run_attempt'))
    if marker.get('schema_version') != 2 or marker.get('build_status') != 'passed':
        raise ValueError('Release does not have passing schema-v2 build evidence')
    if any(marker.get('validation', {}).get(check) != 'passed' for check in CHECKS):
        raise ValueError('Release has incomplete validation evidence')
    if marker.get('deployment', {}).get('target') not in {'github-pages', 'vps'}:
        raise ValueError('Unknown release target')
    inventory = marker.get('artifact_sha256', {})
    if not {'index.html', 'data/current_flag.json'}.issubset(inventory):
        raise ValueError('Release inventory is incomplete')
    for name, digest in inventory.items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError('Unsafe or malformed release inventory')


def verify_build(site: Path) -> dict:
    marker = json.loads((site / MARKER).read_text(encoding='utf-8'))
    validate_marker(marker)
    actual = set()
    for path in site.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlink in staged artifact')
        if path.is_file() and path.relative_to(site).as_posix() != MARKER:
            actual.add(path.relative_to(site).as_posix())
    if actual != set(marker['artifact_sha256']):
        raise ValueError('Artifact file inventory changed after build')
    for name, digest in marker['artifact_sha256'].items():
        if file_hash(site / name) != digest:
            raise ValueError(f'Artifact contents changed after build: {name}')
    return marker


def validate_target_url(url: str, target: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Serving target must be an explicit HTTPS base URL without credentials, query or fragment')
    if target == 'github-pages' and (parsed.hostname != PAGES_HOST or parsed.port not in (None, 443)
                                     or parsed.path.rstrip('/') + '/' != PAGES_PATH):
        raise ValueError('GitHub Pages origin is not isolated; custom-domain/proxy hosting remains unverified')
    if target == 'vps' and parsed.hostname.endswith('.github.io'):
        raise ValueError('A GitHub Pages hostname cannot verify a VPS target')

def preflight_target(site: Path, url: str, target: str, expected: dict) -> dict:
    validate_target_url(url, target)
    validate_marker(expected)
    if expected['deployment']['target'] != target:
        raise ValueError('Build was prepared for a different deployment target')
    cname = site / 'CNAME'
    if target == 'github-pages' and cname.exists() and cname.read_text(encoding='utf-8').strip():
        raise ValueError('Staged CNAME configures a custom domain; Pages origin isolation must be resolved before publication')
    return {'target': target, 'url': url.rstrip('/') + '/', 'preflight': 'passed',
            'deployment_status': 'not_verified'}


def verify_target(url: str, target: str, expected: dict, *, read=fetch) -> dict:
    validate_target_url(url, target)
    validate_marker(expected)
    if expected['deployment']['target'] != target:
        raise ValueError('Build was prepared for a different deployment target')
    base = url.rstrip('/') + '/'
    raw, headers = read(urljoin(base, MARKER))
    observed = json.loads(raw)
    validate_marker(observed)
    for key in ('commit_sha', 'run_id', 'run_attempt', 'artifact_sha256'):
        if observed.get(key) != expected.get(key):
            raise ValueError(f'Serving target has different release {key}')
    if observed['deployment']['target'] != target:
        raise ValueError('Serving target marker has the wrong deployment target')
    if target == 'github-pages' and headers.get('server', '').lower() != 'github.com':
        raise ValueError('Requested URL did not identify GitHub Pages; custom-domain/VPS verification is separate')
    policy = json.loads((ROOT / 'infra/policy.json').read_text()) if target == 'vps' else None
    # Validate the homepage and every safety-data response, not just a label that
    # can recur across different releases. No target gets credit for another.
    paths = ['index.html'] + [name for name in expected['artifact_sha256']
                              if name.startswith('data/') and Path(name).name in {'current_flag.json', 'current_status.json'}]
    requests = [('', 'index.html')] + [(name, name) for name in paths]
    for route, name in requests:
        body, response_headers = read(urljoin(base, route))
        if hashlib.sha256(body).hexdigest() != expected['artifact_sha256'][name]:
            raise ValueError(f"Serving target bytes differ from build: {route or '/'}")
        if target == 'github-pages' and response_headers.get('server', '').lower() != 'github.com':
            raise ValueError(f'Response did not identify GitHub Pages: {name}')
        if policy:
            for key, value in policy['security_headers'].items():
                if response_headers.get(key.lower()) != value:
                    raise ValueError(f'VPS response violates {key} policy: {name}')
            cache_key = 'current_condition_json' if name.startswith('data/') else 'html'
            if response_headers.get('cache-control') != policy['cache_policy'][cache_key]:
                raise ValueError(f'VPS cache policy mismatch: {name}')
    if policy and headers.get('cache-control') != policy['cache_policy']['health_state_json']:
        raise ValueError('VPS build-health response is not freshness protected')
    return {'target': target, 'url': base, 'status': 'verified', 'commit_sha': expected['commit_sha'],
            'run_id': expected['run_id'], 'run_attempt': expected['run_attempt'], 'verified_files': [route or '/' for route, _ in requests]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-dir', type=Path, required=True)
    parser.add_argument('--target', choices=('build', 'github-pages', 'vps'), required=True)
    parser.add_argument('--url')
    parser.add_argument('--preflight', action='store_true', help='Check target configuration before publication; does not verify a deployed release')
    parser.add_argument('--attempts', type=int, default=1)
    parser.add_argument('--delay', type=float, default=15)
    args = parser.parse_args()
    if args.preflight and args.target == 'build':
        parser.error('--preflight requires a serving target')
    if args.attempts < 1 or args.delay < 0 or (args.target != 'build' and not args.url) or (args.target == 'build' and args.url):
        parser.error('Use --url only for a serving target, with positive attempts and nonnegative delay')
    try:
        expected = verify_build(args.site_dir)
    except (ValueError, OSError) as exc:
        print(f'Build verification failed: {exc}', file=sys.stderr)
        return 1
    if args.target == 'build':
        print(json.dumps({'target': 'build', 'status': 'verified', 'commit_sha': expected['commit_sha'],
                          'deployment_status': 'not_verified'}))
        return 0
    if args.preflight:
        try:
            print(json.dumps(preflight_target(args.site_dir, args.url, args.target, expected)))
            return 0
        except (ValueError, OSError) as exc:
            print(f'{args.target} preflight blocked publication: {exc}', file=sys.stderr)
            return 1
    for attempt in range(1, args.attempts + 1):
        try:
            print(json.dumps(verify_target(args.url, args.target, expected)))
            return 0
        except Exception as exc:
            print(f'{args.target} verification {attempt}/{args.attempts} failed: {exc}', file=sys.stderr)
            if attempt < args.attempts:
                time.sleep(args.delay)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
