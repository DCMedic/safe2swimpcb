#!/usr/bin/env python3
"""Read-only, bounded source handoff. Never imports or runs inspected code."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat

MAX_FILE = 262144
MAX_TOTAL = 1048576
MAX_OUTPUT = 2097152
MODULES = ("deploy.py", "public_release.py", "runtime_build.py", "runtime_input.py",
           "snapshot_input.py", "test_release.py", "ktg-status-guard.js")
NAME = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,100}\Z")
SENSITIVE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"(?:gh[pousr]_|github_pat_|sk-proj-)[A-Za-z0-9_-]{16,}|"
    r"(?i:authorization\s*[:=]\s*['\"]?(?:bearer|basic)\s+\S+)|"
    r"(?i:\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret|token)['\"]?\s*[:=]\s*(?:['\"][^'\"]+|[0-9]+))|"
    r"https?://[^\s/'\"]+:[^\s/'\"]+@"
)


def open_directory(path):
    """Return a pinned descriptor without following any directory symlinks."""
    path = Path(path)
    if not path.is_absolute() or any(p in (".", "..") for p in path.parts):
        raise ValueError("absolute normalized path required")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:]:
            nxt = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_regular(path, directory_fd=None):
    """Reject symlinks, unstable reads, nonregular files and oversized input."""
    path = Path(path)
    fd = open_directory(path.parent) if directory_fd is None else os.dup(directory_fd)
    try:
        data_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(data_fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE:
                raise ValueError("not a bounded regular file")
            data = stream.read(MAX_FILE + 1)
            after = os.fstat(stream.fileno())
        if len(data) > MAX_FILE or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("file changed or exceeded bound")
        return data
    finally:
        os.close(fd)


def local_dependencies(source):
    """Only the known builder's literal public list and helper directory."""
    tree = ast.parse(source)
    lists, directories = set(), set()
    for fn in tree.body:
        if not isinstance(fn, ast.FunctionDef) or fn.name not in ("allowed", "build"):
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            base = node.func.value
            if not (isinstance(base, ast.BinOp) and isinstance(base.op, ast.Div)
                    and isinstance(base.left, ast.Name) and base.left.id == "HERE"
                    and isinstance(base.right, ast.Constant) and isinstance(base.right.value, str)):
                continue
            name = base.right.value
            if not NAME.fullmatch(name) or name in (".", ".."):
                raise ValueError("unsupported dependency path")
            if fn.name == "allowed" and node.func.attr == "read_text" and name.endswith(".json"):
                lists.add(name)
            if (fn.name == "build" and node.func.attr == "glob" and len(node.args) == 1
                    and isinstance(node.args[0], ast.Constant) and node.args[0].value == "*.py"):
                directories.add(name)
    if len(lists) != 1 or len(directories) != 1:
        raise ValueError("expected one literal public list and helper directory")
    return lists, directories


def collect(root, controller):
    root = Path(root)
    output = {"format": "kt003-source-handoff-v1", "files": [], "errors": []}
    data_by_name = {}
    total = 0

    def add(path, label, data=None):
        nonlocal total
        try:
            if data is None:
                data = read_regular(path)
            total += len(data)
            if total > MAX_TOTAL:
                raise ValueError("total export limit exceeded")
            source = data.decode("utf-8")
            item = {"name": label, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            if SENSITIVE.search(source):
                item["status"] = "WITHHELD: possible credential; owner review required"
            else:
                item.update(status="source", source=source)
                data_by_name[label] = source
            output["files"].append(item)
        except (OSError, ValueError, UnicodeError) as exc:
            output["errors"].append({"name": label, "error": type(exc).__name__})

    add(controller, "control.py")
    for name in MODULES:
        add(root / name, name)
    if "public_release.py" in data_by_name:
        try:
            lists, directories = local_dependencies(data_by_name["public_release.py"])
            for name in sorted(lists):
                # Export only a list of relative public filenames, never arbitrary JSON.
                raw_list = read_regular(root / name)
                values = json.loads(raw_list)
                if (not isinstance(values, list) or len(values) > 1000
                        or not all(isinstance(v, str) and len(v) <= 200 and not v.startswith("/")
                                   and ".." not in v.split("/") and ":" not in v
                                   and not any(c in v for c in "\n\r\\") for v in values)):
                    raise ValueError("unexpected public-list shape")
                add(root / name, name, raw_list)
            for directory in sorted(directories):
                folder = root / directory
                fd = open_directory(folder)
                try:
                    helpers = []
                    with os.scandir(fd) as entries:
                        for count, entry in enumerate(entries, 1):
                            if count > 256:
                                raise ValueError("helper directory entry limit")
                            if entry.name.endswith(".py"):
                                helpers.append(entry.name)
                                if not NAME.fullmatch(entry.name) or len(helpers) > 32:
                                    raise ValueError("unexpected helper name/count")
                    if not helpers:
                        raise ValueError("no helpers")
                    for name in sorted(helpers):
                        add(folder / name, directory + "/" + name, read_regular(Path(name), fd))
                finally:
                    os.close(fd)
        except (OSError, ValueError, SyntaxError, UnicodeError, RecursionError) as exc:
            output["errors"].append({"name": "builder dependencies", "error": type(exc).__name__})
    output["complete"] = not output["errors"] and all(f["status"] == "source" for f in output["files"])
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--controller", type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.root, args.controller)
    output = json.dumps(result, indent=2, ensure_ascii=True)
    if len(output.encode("utf-8")) > MAX_OUTPUT:
        print('{"complete": false, "errors": ["serialized output limit exceeded"]}')
        return 1
    print(output)
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
