#!/usr/bin/env python3
"""Produce a deterministic content snapshot of a Git worktree.

Unlike ``git status``, this notices content changes when a path was already dirty,
is ignored, or carries an index optimization such as assume-unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


def git_z(cwd: Path, *args: str) -> list[str]:
    proc = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip() or "git snapshot failed")
    return [part.decode(errors="surrogateescape") for part in proc.stdout.split(b"\0") if part]


def fingerprint(path: Path) -> str:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return "missing"
    mode = stat.S_IFMT(info.st_mode) | stat.S_IMODE(info.st_mode)
    digest = hashlib.sha256()
    digest.update(str(mode).encode("ascii"))
    digest.update(b"\0")
    if stat.S_ISLNK(info.st_mode):
        digest.update(os.readlink(path).encode(errors="surrogateescape"))
    elif stat.S_ISREG(info.st_mode):
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    elif stat.S_ISDIR(info.st_mode):
        digest.update(b"directory")
    else:
        digest.update(repr((info.st_size, info.st_mtime_ns)).encode("ascii"))
    return digest.hexdigest()


def ignored(cwd: Path) -> dict[str, str]:
    paths = git_z(cwd, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    return {path: fingerprint(cwd / path) for path in sorted(set(paths))}


def tracked(cwd: Path) -> dict[str, str]:
    """Fingerprint every index path without trusting status/index optimization bits."""
    paths = git_z(cwd, "ls-files", "--cached", "-z")
    return {path: fingerprint(cwd / path) for path in sorted(set(paths))}


def untracked(cwd: Path) -> dict[str, str]:
    paths = git_z(cwd, "ls-files", "--others", "--exclude-standard", "-z")
    return {path: fingerprint(cwd / path) for path in sorted(set(paths))}


def all_paths(cwd: Path) -> set[str]:
    paths = set(git_z(cwd, "ls-files", "--cached", "-z"))
    paths.update(git_z(cwd, "ls-files", "--others", "--exclude-standard", "-z"))
    paths.update(git_z(cwd, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cwd")
    parser.add_argument("--ignored-json", action="store_true")
    parser.add_argument("--tracked-json", action="store_true")
    parser.add_argument("--untracked-json", action="store_true")
    parser.add_argument("--exclude-prefix", action="append", default=[])
    args = parser.parse_args()
    cwd = Path(args.cwd).resolve()
    try:
        if args.ignored_json:
            print(json.dumps(ignored(cwd), sort_keys=True, separators=(",", ":")))
            return 0
        if args.tracked_json:
            print(json.dumps(tracked(cwd), sort_keys=True, separators=(",", ":")))
            return 0
        if args.untracked_json:
            print(json.dumps(untracked(cwd), sort_keys=True, separators=(",", ":")))
            return 0
        prefixes = tuple(value.strip("/") + "/" for value in args.exclude_prefix)
        digest = hashlib.sha256()
        for relative in sorted(all_paths(cwd)):
            if any(relative == prefix[:-1] or relative.startswith(prefix) for prefix in prefixes):
                continue
            digest.update(relative.encode(errors="surrogateescape"))
            digest.update(b"\0")
            digest.update(fingerprint(cwd / relative).encode("ascii"))
            digest.update(b"\0")
        print(digest.hexdigest())
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"orchestratore: snapshot worktree fallita: {exc}", file=sys.stderr)
        return 74


if __name__ == "__main__":
    raise SystemExit(main())
