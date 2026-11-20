import hashlib
import json
from pathlib import Path

import pytest

from scripts import export_vps_builder_source as export


@pytest.fixture
def builder(tmp_path):
    root = tmp_path / 'persistent'
    root.mkdir()
    controller = tmp_path / 'control.py'
    controller.write_text('raise RuntimeError("must never execute")\n')
    for name in export.MODULES:
        (root / name).write_text('# source only\n')
    (root / 'public_release.py').write_text('''
def allowed():
    return json.loads((HERE / 'public.json').read_text())
def build():
    for helper in (HERE / 'overrides').glob('*.py'):
        raise RuntimeError("must never execute")
''')
    (root / 'public.json').write_text('["index.html", "data/current_flag.json"]')
    (root / 'overrides').mkdir()
    (root / 'overrides' / 'render.py').write_text('print("never execute")\n')
    (root / '.env').write_text('SECRET=never read this\n')
    (root / 'runtime.json').write_text('{"private":"never read this"}')
    return root, controller


def inventory(root):
    return {str(p): (p.read_bytes(), p.stat().st_mtime_ns, p.stat().st_mode)
            for p in root.rglob('*') if p.is_file()}


def test_complete_exact_source_no_execution_no_mutation(builder, capsys):
    root, controller = builder
    before = inventory(root.parent)
    result = export.collect(root, controller)
    assert result['complete']
    assert inventory(root.parent) == before
    assert not capsys.readouterr().out
    names = {f['name'] for f in result['files']}
    assert names == set(export.MODULES) | {'control.py', 'public.json', 'overrides/render.py'}
    for entry in result['files']:
        assert entry['sha256'] == hashlib.sha256(entry['source'].encode()).hexdigest()
    assert 'never read this' not in json.dumps(result)


@pytest.mark.parametrize('secret', [
    'password = "not-a-real-password"',
    'client_secret: "not-a-real-secret"',
    '-----BEGIN PRIVATE KEY-----',
    'https://example-user:example-password@example.invalid/',
    'Authorization: Bearer example-token',
    'ghp_' + 'a' * 20,
    '{"password": "example-secret"}',
    'TOKEN = "example-secret"',
    'password = 123456',
])
def test_possible_credentials_withhold_entire_file(builder, secret):
    root, controller = builder
    (root / 'deploy.py').write_text(secret)
    result = export.collect(root, controller)
    assert not result['complete']
    assert secret not in json.dumps(result)
    assert next(f for f in result['files'] if f['name'] == 'deploy.py')['status'].startswith('WITHHELD')


def test_symlink_and_parent_symlink_rejected(builder):
    root, controller = builder
    link = root.parent / 'alias'
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(OSError):
        export.read_regular(link / 'deploy.py')
    (root / 'deploy.py').unlink()
    (root / 'deploy.py').symlink_to(controller)
    assert not export.collect(root, controller)['complete']


def test_oversize_file_rejected(builder, monkeypatch):
    root, controller = builder
    monkeypatch.setattr(export, 'MAX_FILE', 5)
    assert not export.collect(root, controller)['complete']


def test_total_bound_is_fail_closed(builder, monkeypatch):
    root, controller = builder
    monkeypatch.setattr(export, 'MAX_TOTAL', 10)
    result = export.collect(root, controller)
    assert not result['complete']
    assert sum(len(f.get('source', '').encode()) for f in result['files']) <= 10


@pytest.mark.parametrize('body', ['{"secret": "do not export"}', '["/etc/shadow"]', '["../secret"]'])
def test_arbitrary_json_not_exported(builder, body):
    root, controller = builder
    (root / 'public.json').write_text(body)
    result = export.collect(root, controller)
    assert not result['complete']
    assert not any(f['name'] == 'public.json' for f in result['files'])


def test_dynamic_or_escaping_dependency_not_evaluated():
    for source in ["def allowed(): return __import__('os').system('false')",
                   "def allowed(): return (HERE / '../secret.json').read_text()"]:
        with pytest.raises(ValueError):
            export.local_dependencies(source)


def test_missing_module_reported_without_unbounded_paths(builder):
    root, controller = builder
    (root / 'runtime_input.py').unlink()
    result = export.collect(root, controller)
    assert not result['complete']
    assert {'name': 'runtime_input.py', 'error': 'FileNotFoundError'} in result['errors']


def test_json_source_control_characters_are_escaped(builder):
    root, controller = builder
    (root / 'deploy.py').write_text('# \x1b[31m terminal control\n')
    result = json.dumps(export.collect(root, controller), ensure_ascii=True)
    assert '\x1b' not in result
    assert '\\u001b' in result


def test_fifo_rejected_without_blocking(builder):
    import os
    root, controller = builder
    (root / 'deploy.py').unlink()
    os.mkfifo(root / 'deploy.py')
    assert not export.collect(root, controller)['complete']


def test_helper_enumeration_bounded(builder):
    root, controller = builder
    for i in range(257):
        (root / 'overrides' / f'{i}.txt').touch()
    assert not export.collect(root, controller)['complete']


def test_helper_directory_symlink_rejected(builder):
    root, controller = builder
    folder = root / 'overrides'
    folder.rename(root / 'actual')
    folder.symlink_to(root / 'actual', target_is_directory=True)
    assert not export.collect(root, controller)['complete']


def test_pinned_directory_read_ignores_path_replacement(builder):
    import os
    root, controller = builder
    folder = root / 'overrides'
    fd = export.open_directory(folder)
    try:
        folder.rename(root / 'actual')
        folder.mkdir()
        (folder / 'render.py').write_text('replacement')
        assert export.read_regular(Path('render.py'), fd) == b'print("never execute")\n'
    finally:
        os.close(fd)


def test_serialized_output_bound(builder, monkeypatch, capsys):
    root, controller = builder
    monkeypatch.setattr(export, 'MAX_OUTPUT', 5)
    monkeypatch.setattr('sys.argv', ['export', '--root', str(root), '--controller', str(controller)])
    assert export.main() == 1
    assert 'source' not in capsys.readouterr().out
