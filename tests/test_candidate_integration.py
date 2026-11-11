"""Cross-work-package checks for the reviewed, fail-closed release candidate."""
import hashlib
import re
import shutil
import subprocess
from pathlib import Path

from scripts import stage_public_artifact as staging
from scripts.inject_social_meta import inject_or_replace


ROOT = Path(__file__).resolve().parents[1]


def test_built_safety_panels_load_only_allowlisted_content_bound_scripts(tmp_path):
    source = tmp_path / 'source'
    manifest = ROOT / 'infra/public-artifact.json'
    for name in staging.public_paths(manifest):
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
        if destination.suffix == '.html':
            destination.write_text(inject_or_replace(destination.read_text(encoding='utf-8')), encoding='utf-8')

    output = tmp_path / 'public'
    paths = staging.stage(source, output, manifest)
    versioned = {}
    for stem in ('safety-state', 'safety-ui'):
        digest = hashlib.sha256((output / 'assets' / f'{stem}.js').read_bytes()).hexdigest()
        versioned[stem] = f'assets/{stem}.{digest}.js'
        assert versioned[stem] in paths
        assert (output / versioned[stem]).read_bytes() == (output / 'assets' / f'{stem}.js').read_bytes()

    for route in ('index.html', 'destin/index.html', 'cape-san-blas/index.html', 'siesta-key/index.html'):
        html = (output / route).read_text(encoding='utf-8')
        scripts = re.findall(r'<script\b[^>]*\bsrc="([^"]+)"', html)
        assert scripts.count('/' + versioned['safety-state']) == 1
        assert scripts.count('/' + versioned['safety-ui']) == 1
        assert scripts.index('/' + versioned['safety-state']) < scripts.index('/' + versioned['safety-ui'])
        assert '/assets/safety-state.js' not in scripts
        assert '/assets/safety-ui.js' not in scripts

    # The safety renderer's CommonJS entry must retain an explicit relative
    # dependency, not accidentally turn into a bare Node/browser module name.
    ui = (output / versioned['safety-ui']).read_text(encoding='utf-8')
    assert f"require('./{Path(versioned['safety-state']).name}')" in ui
    subprocess.run(['node', '-e', 'require(process.argv[1])', str(output / versioned['safety-ui'])], check=True)
