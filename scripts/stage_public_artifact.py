#!/usr/bin/env python3
"""Copy only reviewed public files, never a repository checkout, into an artifact."""
from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
import posixpath
import re
from pathlib import Path, PurePosixPath
import shutil
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {'.nojekyll', 'CNAME', 'robots.txt', 'sitemap.xml', 'site.webmanifest', 'index.html'}


def public_paths(manifest: Path) -> list[str]:
    payload = json.loads(manifest.read_text(encoding='utf-8'))
    paths = payload.get('files', [])
    if payload.get('schema_version') != 1 or not paths or len(paths) != len(set(paths)):
        raise ValueError('Invalid or duplicate public artifact allowlist')
    for name in paths:
        path = PurePosixPath(name)
        if (not isinstance(name, str) or str(path) != name or path.is_absolute()
                or '..' in path.parts or '\\' in name
                or any(part.startswith('.') for part in path.parts) and name != '.nojekyll'):
            raise ValueError(f'Unsafe artifact path: {name}')
        allowed = (name in ROOT_FILES
                   or path.parts[0] == 'assets' and path.suffix.lower() in {'.js', '.css', '.svg', '.png', '.jpg', '.webp', '.ico'}
                   or path.parts[0] == 'data' and path.suffix in {'.json', '.csv'}
                   or len(path.parts) == 2 and path.name == 'index.html'
                      and path.parts[0] not in {'scripts', 'tests', 'docs', 'infra'})
        if not allowed:
            raise ValueError(f'Non-public artifact path: {name}')
    if not ROOT_FILES.issubset(paths) or 'data/current_flag.json' not in paths:
        raise ValueError('Public artifact allowlist omits required entry points')
    return sorted(paths)


class ScriptTags(HTMLParser):
    """Parse exact executable src attributes while preserving unrelated markup."""
    def __init__(self, text: str):
        super().__init__(convert_charrefs=False)
        self.offsets = [0]
        for line in text.splitlines(keepends=True):
            self.offsets.append(self.offsets[-1] + len(line))
        self.scripts = []
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag != 'script':
            return
        sources = [value for key, value in attrs if key == 'src']
        if not sources:
            return
        if len(sources) != 1 or not sources[0] or not sources[0].strip():
            raise ValueError('Script must have exactly one nonempty src attribute')
        line, column = self.getpos()
        start = self.offsets[line - 1] + column
        raw = self.get_starttag_text()
        self.scripts.append((start, start + len(raw), attrs, sources[0]))

    def handle_startendtag(self, tag, attrs):
        if tag == 'script':
            raise ValueError('Self-closing script tags are not supported in HTML artifacts')


def script_sources(text: str) -> list[str]:
    return [source for _, _, _, source in ScriptTags(text).scripts]


def rewrite_script_sources(text: str, resolve) -> str:
    for start, end, attrs, source in reversed(ScriptTags(text).scripts):
        target = resolve(source)
        if target == source:
            continue
        serialized = []
        for key, value in attrs:
            if key == 'src':
                value = target
            serialized.append(key if value is None else f'{key}="{html.escape(value, quote=True)}"')
        text = text[:start] + '<script ' + ' '.join(serialized) + '>' + text[end:]
    return text


def bind_javascript_generation(output: Path, paths: list[str]) -> list[str]:
    """Make new HTML request only content-addressed copies of reviewed local JS."""
    versions = {}
    sources = {name: (output / name).read_text(encoding='utf-8') for name in paths
               if PurePosixPath(name).parts[0] == 'assets' and PurePosixPath(name).suffix == '.js'}
    visiting = set()
    local_js = re.compile(r"([\"'`])((?:/(?!/)|\./|\.\./|assets/)[^\"'`\s]+\.js(?:[?#][^\"'`\s]*)?)\1")

    def local_path(owner: str, value: str) -> str:
        parsed = urlsplit(value)
        source = (output / parsed.path.lstrip('/')) if parsed.path.startswith('/') else (output / owner).parent / parsed.path
        try:
            return source.resolve().relative_to(output.resolve()).as_posix()
        except ValueError:
            raise ValueError(f'Local script escapes the artifact: {value}') from None

    def referenced_path(owner: str, value: str, versioned: str) -> str:
        if value.startswith('/'):
            return '/' + versioned
        relative = posixpath.relpath(versioned, PurePosixPath(owner).parent.as_posix())
        # ES imports and CommonJS require() treat a bare filename as a package,
        # unlike HTML src. Preserve an explicit relative module specifier.
        if value.startswith(('./', '../')) and not relative.startswith(('./', '../')):
            relative = './' + relative
        return relative

    def fingerprint(name: str) -> str:
        if name in versions:
            return versions[name]
        if name not in sources:
            raise ValueError(f'Local script is not in the reviewed JavaScript allowlist: {name}')
        if name in visiting:
            raise ValueError(f'Cyclic JavaScript dependencies require an explicit bundling strategy: {name}')
        visiting.add(name)
        def replace_dependency(match):
            dependency = local_path(name, match.group(2))
            versioned = fingerprint(dependency)
            return match.group(1) + referenced_path(name, match.group(2), versioned) + match.group(1)
        text = local_js.sub(replace_dependency, sources[name])
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
        path = PurePosixPath(name)
        versioned = path.with_name(f'{path.stem}.{digest}.js').as_posix()
        if (output / versioned).exists():
            raise ValueError(f'Generated JavaScript path collides with an allowlisted file: {versioned}')
        (output / name).write_text(text, encoding='utf-8')
        (output / versioned).write_text(text, encoding='utf-8')
        versions[name] = versioned
        visiting.remove(name)
        return versioned

    for name in sources:
        fingerprint(name)
    for name in paths:
        page = output / name
        if page.suffix != '.html':
            continue
        def replace(value):
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc:
                return value
            relative = local_path(name, value)
            if relative not in versions:
                raise ValueError(f'Local script is not in the reviewed JavaScript allowlist: {value}')
            versioned = versions[relative]
            target = referenced_path(name, value, versioned)
            return target
        page.write_text(rewrite_script_sources(page.read_text(encoding='utf-8'), replace), encoding='utf-8')
    return sorted([*paths, *versions.values()])


def stage(root: Path, output: Path, manifest: Path) -> list[str]:
    root, output = root.resolve(), output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Artifact output must not already exist')
    if output == root or output in root.parents:
        raise ValueError('Artifact output must not contain the source checkout')
    paths = public_paths(manifest)
    for name in paths:
        source = root / name
        if (not source.is_file() or not source.resolve().is_relative_to(root)
                or any(part.is_symlink() for part in [source, *source.parents] if part != root)):
            raise ValueError(f'Missing file or symlink in artifact input: {name}')
    output.mkdir(parents=True)
    for name in paths:
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, dest)
    return bind_javascript_generation(output, paths)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = stage(ROOT, args.output, ROOT / 'infra/public-artifact.json')
    print(f'Staged {len(paths)} public files, including deterministic versioned JavaScript, in {args.output}')


if __name__ == '__main__':
    main()
