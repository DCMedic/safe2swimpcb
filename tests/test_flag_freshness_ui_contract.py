from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_safety_behavior():
    subprocess.run(['node', '--test', 'tests/safety_state.test.cjs'], cwd=ROOT, check=True)


def test_only_safety_ui_writes_primary_panel():
    for name in ['app.js', 'menu.js', 'western-location.js', 'eastern-location.js', 'southwest-location.js', 'site-ui.js', 'quality-ui.js']:
        text = (ROOT / 'assets' / name).read_text()
        for identifier in ['currentFlag', 'currentStatus', 'flagPole', 'flagFreshness', 'statusFreshness']:
            assert f"$('{identifier}')" not in text
            assert f"getElementById('{identifier}')" not in text
    for path in [ROOT / 'index.html', *ROOT.glob('*/index.html')]:
        text = path.read_text()
        if 'id="currentFlag"' in text or 'id="currentStatus"' in text:
            assert '/assets/safety-state.js' in text and '/assets/safety-ui.js' in text
            assert text.index('/assets/safety-state.js') < text.index('/assets/safety-ui.js')
