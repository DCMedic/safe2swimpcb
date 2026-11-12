import copy
import json
from pathlib import Path
import subprocess
import shutil
from urllib.request import Request
from urllib.parse import urlsplit

import pytest

from scripts import stage_public_artifact as staging
from scripts import verify_release as verify
from scripts import write_build_health as health

ROOT = Path(__file__).resolve().parents[1]
PAGES_URL = 'https://dcmedic.github.io/safe2swimpcb/'
VPS_URL = 'https://example.invalid/'


@pytest.fixture
def site(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    root.mkdir()
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                    'commit', '--allow-empty', '-qm', 'fixture'], check=True)
    output = tmp_path / 'site'
    (output / 'data').mkdir(parents=True)
    (output / 'index.html').write_text('<html>release fixture</html>')
    (output / 'data/current_flag.json').write_text('{"flag":"Red"}')
    for check in health.CHECKS:
        monkeypatch.setenv(f'BUILD_{check.upper()}_RESULT', 'success')
    monkeypatch.setenv('GITHUB_RUN_ID', '123')
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '2')
    return root, output


def test_identity_is_actual_checkout_not_trigger(site, monkeypatch):
    root, output = site
    monkeypatch.setenv('GITHUB_SHA', 'different-event-sha')
    marker = health.write_health(output, 'github-pages', root=root)
    assert marker['commit_sha'] == health.checked_out_sha(root)
    assert marker['trigger_sha'] == 'different-event-sha'
    assert marker['build_status'] == 'passed'
    assert marker['deployment'] == {'target': 'github-pages', 'status': 'not_verified'}
    with pytest.raises(ValueError, match='changed'):
        health.write_health(output, 'github-pages', root=root, expected_sha='other')


@pytest.mark.parametrize('outcome,expected', [('failure', 'failed'), ('skipped', 'not_run'), ('cancelled', 'cancelled'), ('', 'not_run')])
def test_missing_failed_or_skipped_tests_are_never_passed(site, monkeypatch, outcome, expected):
    root, output = site
    monkeypatch.setenv('BUILD_REPOSITORY_TESTS_RESULT', outcome)
    marker = health.write_health(output, 'github-pages', root=root)
    assert marker['validation']['repository_tests'] == expected
    assert marker['build_status'] == 'not_passed'
    with pytest.raises(ValueError, match='passing'):
        verify.verify_build(output)


def test_unrecognized_step_outcome_rejected(site, monkeypatch):
    root, output = site
    monkeypatch.setenv('BUILD_REPOSITORY_TESTS_RESULT', 'passed')
    with pytest.raises(ValueError, match='Invalid result'):
        health.write_health(output, 'github-pages', root=root)


@pytest.mark.parametrize('mutation', ['add', 'remove', 'modify', 'symlink'])
def test_build_tampering_fails_closed(site, mutation):
    root, output = site
    health.write_health(output, 'github-pages', root=root)
    assert verify.verify_build(output)['build_status'] == 'passed'
    if mutation == 'add':
        (output / 'secret.txt').write_text('do not publish')
    elif mutation == 'remove':
        (output / 'index.html').unlink()
    elif mutation == 'modify':
        (output / 'index.html').write_text('different')
    else:
        (output / 'unexpected').symlink_to(root)
    with pytest.raises(ValueError):
        verify.verify_build(output)


def response_reader(site, marker, target='github-pages', mutation=None):
    def read(url):
        name = urlsplit(url).path.removeprefix('/safe2swimpcb').lstrip('/')
        headers = {'server': 'GitHub.com'}
        if target == 'vps':
            policy = json.loads((ROOT / 'infra/policy.json').read_text())
            headers = {key.lower(): value for key, value in policy['security_headers'].items()}
            headers['cache-control'] = policy['cache_policy']['html' if name in {'', 'index.html'} else 'current_condition_json']
            headers['server'] = 'Caddy'
        body = json.dumps(marker).encode() if name == health.MARKER else (site / (name or 'index.html')).read_bytes()
        if mutation:
            body, headers = mutation(name, body, headers)
        return body, headers
    return read


def test_pages_verification_checks_release_and_bytes(site):
    root, output = site
    marker = health.write_health(output, 'github-pages', root=root)
    result = verify.verify_target(PAGES_URL, 'github-pages', marker, read=response_reader(output, marker))
    assert result['target'] == 'github-pages'
    assert result['status'] == 'verified'
    assert result['verified_files'] == ['/', 'index.html', 'data/current_flag.json']
    assert marker['deployment']['status'] == 'not_verified'


@pytest.mark.parametrize('key,value', [('commit_sha', '0' * 40), ('run_id', '124'), ('run_attempt', '1')])
def test_stale_target_identity_fails(site, key, value):
    root, output = site
    expected = health.write_health(output, 'github-pages', root=root)
    old = copy.deepcopy(expected)
    old[key] = value
    with pytest.raises(ValueError, match=key):
        verify.verify_target(PAGES_URL, 'github-pages', expected, read=response_reader(output, old))


def test_same_flag_label_does_not_hide_wrong_html(site):
    root, output = site
    marker = health.write_health(output, 'github-pages', root=root)
    def mutate(name, body, headers):
        return (b'<html>old release</html>' if name == 'index.html' else body), headers
    with pytest.raises(ValueError, match='bytes differ'):
        verify.verify_target(PAGES_URL, 'github-pages', marker, read=response_reader(output, marker, mutation=mutate))


def test_pages_cannot_claim_vps_or_proxy_success(site):
    root, output = site
    marker = health.write_health(output, 'github-pages', root=root)
    with pytest.raises(ValueError, match='different deployment target'):
        verify.verify_target(VPS_URL, 'vps', marker)
    with pytest.raises(ValueError, match='did not identify GitHub Pages'):
        verify.verify_target(PAGES_URL, 'github-pages', marker, read=response_reader(output, marker, target='vps'))


def test_vps_requires_security_and_freshness_policy(site):
    root, output = site
    marker = health.write_health(output, 'vps', root=root)
    result = verify.verify_target(VPS_URL, 'vps', marker, read=response_reader(output, marker, target='vps'))
    assert result['target'] == 'vps'
    def bad_cache(name, body, headers):
        headers['cache-control'] = 'public, max-age=86400'
        return body, headers
    with pytest.raises(ValueError, match='cache policy'):
        verify.verify_target(VPS_URL, 'vps', marker, read=response_reader(output, marker, target='vps', mutation=bad_cache))
    def no_headers(name, body, headers):
        headers.pop('strict-transport-security', None)
        return body, headers
    with pytest.raises(ValueError, match='Strict-Transport-Security'):
        verify.verify_target(VPS_URL, 'vps', marker, read=response_reader(output, marker, target='vps', mutation=no_headers))


def test_cross_origin_redirect_is_not_verification():
    with pytest.raises(ValueError, match='left the requested serving target'):
        verify.SameOriginRedirect().redirect_request(Request('https://pages.invalid/'), None, 301, '', {}, 'https://vps.invalid/')


@pytest.mark.parametrize('bad', ['https://user:pass@example.invalid/', 'http://example.invalid/', 'https://example.invalid/?x=y'])
def test_ambiguous_or_insecure_target_rejected(site, bad):
    root, output = site
    marker = health.write_health(output, 'github-pages', root=root)
    with pytest.raises(ValueError, match='explicit HTTPS'):
        verify.verify_target(bad, 'github-pages', marker)


def test_real_artifact_uses_only_allowlist(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    output = tmp_path / 'public'
    manifest = ROOT / 'infra/public-artifact.json'
    from scripts.inject_social_meta import inject_or_replace
    for name in staging.public_paths(manifest):
        dest = source / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
        if dest.suffix == '.html':
            dest.write_text(inject_or_replace(dest.read_text(encoding='utf-8')), encoding='utf-8')
    paths = staging.stage(source, output, manifest)
    assert set(paths) == {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
    assert not any(p.startswith(('.git', 'scripts/', 'tests/', 'docs/', 'infra/')) for p in paths)
    assert 'data/x_posting_state.json' not in paths
    assert all(p.relative_to(ROOT).as_posix() in paths for p in (ROOT / 'assets').glob('*.js'))
    assert set(staging.public_paths(manifest)).issubset(paths)
    # Inspect the untouched final artifact, never reconstruct transformed HTML.
    for page in output.rglob('*.html'):
        for src in staging.script_sources(page.read_text(encoding='utf-8')):
            if src.startswith(('https:', 'http:', '//')):
                continue
            assert __import__('re').search(r'\.[0-9a-f]{64}\.js$', src), src
    from scripts import site_health_check
    monkeypatch.setattr(site_health_check, 'ROOT', output)
    errors = []
    site_health_check.validate_html(errors)
    site_health_check.validate_destinations(errors)
    site_health_check.validate_sitemap(errors)
    assert errors == []
    with pytest.raises(ValueError, match='already exist'):
        staging.stage(source, output, manifest)


@pytest.mark.parametrize('bad', ['../outside', '/absolute', '.git/config', 'scripts/leak.py', 'docs/index.html', 'data/../../leak.json', 'data\\leak.json'])
def test_allowlist_cannot_smuggle_private_paths(tmp_path, bad):
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'schema_version': 1, 'files': [*staging.ROOT_FILES, 'data/current_flag.json', bad]}))
    with pytest.raises(ValueError):
        staging.public_paths(manifest)


def test_allowlisted_symlink_rejected(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    paths = [*staging.ROOT_FILES, 'data/current_flag.json']
    for name in paths:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture')
    (root / 'index.html').unlink()
    (root / 'index.html').symlink_to(root / 'robots.txt')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'schema_version': 1, 'files': paths}))
    with pytest.raises(ValueError, match='symlink'):
        staging.stage(root, tmp_path / 'public', manifest)


def test_deploy_workflow_keeps_all_evidence_and_safety_gates():
    workflow = (ROOT / '.github/workflows/deploy-pages.yml').read_text()
    assert 'path: ${{ runner.temp }}/public-site' in workflow
    assert "path: '.'" not in workflow
    assert 'python -m pytest -q' in workflow
    assert 'node --test "$test_file"' in workflow
    assert 'git rev-parse --verify HEAD^{commit}' in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert '--target github-pages --url "$PAGES_URL"' in workflow
    for check in health.CHECKS:
        assert f'BUILD_{check.upper()}_RESULT: ${{{{ steps.{check}.outcome }}}}' in workflow
    for script in ['verify_prerender_consistency', 'site_health_check', 'validate_workflows', 'validate_infrastructure']:
        assert f'python scripts/{script}.py' in workflow


def test_custom_domain_cannot_prove_pages_origin(site):
    root, output = site
    marker = health.write_health(output, 'github-pages', root=root)
    with pytest.raises(ValueError, match='origin is not isolated'):
        verify.verify_target('https://knowthegulf.com/', 'github-pages', marker)


@pytest.mark.parametrize('field', ['commit_sha', 'run_id', 'run_attempt'])
@pytest.mark.parametrize('value', [None, '', ' ', 0])
def test_missing_release_identity_fails_closed(site, field, value):
    root, output = site
    marker = health.write_health(output, 'github-pages', root=root)
    marker[field] = value
    with pytest.raises(ValueError, match=field):
        verify.verify_target(PAGES_URL, 'github-pages', marker, read=response_reader(output, marker))


def test_marker_writer_requires_real_workflow_identity(site, monkeypatch):
    root, output = site
    monkeypatch.delenv('GITHUB_RUN_ID', raising=False)
    with pytest.raises(ValueError, match='run_id'):
        health.write_health(output, 'github-pages', root=root)
    assert not (output / health.MARKER).exists()


def test_different_root_homepage_is_not_verified(site):
    root, output = site
    marker = health.write_health(output, 'github-pages', root=root)
    def mutate(name, body, headers):
        return (b'wrong root homepage' if name == '' else body), headers
    with pytest.raises(ValueError, match='bytes differ from build: /'):
        verify.verify_target(PAGES_URL, 'github-pages', marker, read=response_reader(output, marker, mutation=mutate))


def test_preflight_rejects_custom_domain_before_publication(site):
    root, output = site
    (output / 'CNAME').write_text('knowthegulf.com\n')
    marker = health.write_health(output, 'github-pages', root=root)
    with pytest.raises(ValueError, match='Staged CNAME'):
        verify.preflight_target(output, PAGES_URL, 'github-pages', marker)
    with pytest.raises(ValueError, match='origin is not isolated'):
        verify.preflight_target(output, 'https://knowthegulf.com', 'github-pages', marker)


def test_successful_preflight_does_not_claim_deployment(site):
    root, output = site
    marker = health.write_health(output, 'github-pages', root=root)
    result = verify.preflight_target(output, PAGES_URL, 'github-pages', marker)
    assert result['preflight'] == 'passed'
    assert result['deployment_status'] == 'not_verified'
    assert 'status' not in result


def test_target_preflight_is_before_upload_and_all_deploy_attempts():
    workflow = (ROOT / '.github/workflows/deploy-pages.yml').read_text()
    preflight = workflow.index('--preflight')
    assert workflow.index('steps.pages_config.outputs.base_url') < preflight
    assert preflight < workflow.index('uses: actions/upload-pages-artifact@')
    assert all(preflight < match.start() for match in __import__('re').finditer('uses: actions/deploy-pages@', workflow))
    assert 'enablement: false' in workflow


def test_staged_html_uses_content_bound_javascript_and_ignores_old_browser_cache(tmp_path):
    output = tmp_path / 'site'
    (output / 'assets').mkdir(parents=True)
    (output / 'nested').mkdir()
    (output / 'assets/legacy.js').write_text('globalThis.legacy = "fixed";')
    (output / 'assets/safety.js').write_text('globalThis.safe = globalThis.legacy === "fixed";')
    (output / 'index.html').write_text('<script src="/assets/legacy.js"></script><script defer src="assets/safety.js?v=old"></script><script src="https://cdn.example.invalid/library.js"></script>')
    (output / 'nested/index.html').write_text("<script src='../assets/legacy.js'></script>")
    paths = ['index.html', 'nested/index.html', 'assets/legacy.js', 'assets/safety.js']
    generated = staging.bind_javascript_generation(output, paths)
    assert len(generated) == len(paths) + 2
    text = (output / 'index.html').read_text()
    local_urls = [url for url in staging.script_sources(text) if not url.startswith('https:')]
    assert all(__import__('re').search(r'\.[0-9a-f]{64}\.js$', url) for url in local_urls)
    assert 'https://cdn.example.invalid/library.js' in text
    assert '../assets/legacy.' in (output / 'nested/index.html').read_text()
    # Deterministic browser-cache model: the old stable URL holds an unsafe
    # legacy writer, but the new document can request only the fixed generation.
    cache = {'/assets/legacy.js': 'globalThis.legacy = "unsafe";'}
    resources = {}
    for url in local_urls:
        resources[url] = cache.get(url, (output / url.lstrip('/')).read_text())
    script = "const vm=require('node:vm'); const context={}; for(const code of JSON.parse(process.argv[1]))vm.runInNewContext(code,context); if(context.legacy!=='fixed'||context.safe!==true)process.exit(1);"
    subprocess.run(['node', '-e', script, json.dumps(list(resources.values()))], check=True)


def test_javascript_change_gets_a_different_immutable_url(tmp_path):
    outputs = []
    for number, code in enumerate(['old generation', 'fixed generation']):
        output = tmp_path / str(number)
        (output / 'assets').mkdir(parents=True)
        (output / 'assets/app.js').write_text(code)
        (output / 'index.html').write_text('<script src="/assets/app.js"></script>')
        staging.bind_javascript_generation(output, ['index.html', 'assets/app.js'])
        outputs.append((output / 'index.html').read_text())
    assert outputs[0] != outputs[1]


def test_unreviewed_local_script_blocks_staging(tmp_path):
    (tmp_path / 'index.html').write_text('<script src="/private/unreviewed.js"></script>')
    with pytest.raises(ValueError, match='reviewed JavaScript allowlist'):
        staging.bind_javascript_generation(tmp_path, ['index.html'])


def test_dynamic_local_loader_is_bound_before_parent_is_hashed(tmp_path):
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets/nav.js').write_text('globalThis.nav = "new";')
    (tmp_path / 'assets/app.js').write_text("let s=document.createElement('script');s.src='/assets/nav.js';document.head.appendChild(s);")
    (tmp_path / 'index.html').write_text('<script src="/assets/app.js"></script>')
    paths = staging.bind_javascript_generation(tmp_path, ['index.html', 'assets/nav.js', 'assets/app.js'])
    nav = next(path for path in paths if path.startswith('assets/nav.') and path != 'assets/nav.js')
    app = next(path for path in paths if path.startswith('assets/app.') and path != 'assets/app.js')
    assert '/' + nav in (tmp_path / app).read_text()
    assert "'/assets/nav.js'" not in (tmp_path / app).read_text()
    digest = __import__('hashlib').sha256((tmp_path / app).read_bytes()).hexdigest()
    assert f'.{digest}.js' in app


def test_cyclic_local_javascript_dependencies_fail_closed(tmp_path):
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets/one.js').write_text("import './two.js';")
    (tmp_path / 'assets/two.js').write_text("import './one.js';")
    with pytest.raises(ValueError, match='Cyclic'):
        staging.bind_javascript_generation(tmp_path, ['assets/one.js', 'assets/two.js'])


@pytest.mark.parametrize('tag', [
    '<script src=/assets/app.js></script>',
    '<script data-src="/assets/app.js" src="/assets/app.js"></script>',
    "<SCRIPT data-src='/assets/app.js' SRC=/assets/app.js defer></SCRIPT>",
])
def test_exact_script_src_is_bound_in_all_valid_attribute_forms(tmp_path, tag):
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets/app.js').write_text('globalThis.version = "new";')
    (tmp_path / 'index.html').write_text(tag)
    staging.bind_javascript_generation(tmp_path, ['index.html', 'assets/app.js'])
    text = (tmp_path / 'index.html').read_text()
    sources = staging.script_sources(text)
    assert len(sources) == 1
    assert __import__('re').fullmatch(r'/assets/app\.[0-9a-f]{64}\.js', sources[0])
    if 'data-src' in tag:
        assert 'data-src="/assets/app.js"' in text


@pytest.mark.parametrize('tag', [
    '<script src="/assets/app.js" src="/assets/other.js"></script>',
    '<script src></script>', '<script src=""></script>',
    '<script src="/assets/app.js"/>',
])
def test_ambiguous_or_invalid_script_tags_fail_closed(tmp_path, tag):
    (tmp_path / 'index.html').write_text(tag)
    with pytest.raises(ValueError):
        staging.bind_javascript_generation(tmp_path, ['index.html'])


@pytest.mark.parametrize('module_kind', ['esm', 'commonjs'])
def test_fingerprinted_relative_modules_still_execute(tmp_path, module_kind):
    (tmp_path / 'assets').mkdir()
    if module_kind == 'esm':
        (tmp_path / 'package.json').write_text('{"type":"module"}')
        dependency = 'export const value = 42;'
        app = "import {value} from './dependency.js'; if(value!==42)process.exit(1);"
    else:
        dependency = 'module.exports = 42;'
        app = "const value = require('./dependency.js'); if(value!==42)process.exit(1);"
    (tmp_path / 'assets/dependency.js').write_text(dependency)
    (tmp_path / 'assets/app.js').write_text(app)
    paths = staging.bind_javascript_generation(tmp_path, ['assets/dependency.js', 'assets/app.js'])
    versioned = next(path for path in paths if path.startswith('assets/app.') and path != 'assets/app.js')
    text = (tmp_path / versioned).read_text()
    assert "'./dependency." in text
    subprocess.run(['node', str(tmp_path / versioned)], check=True)
