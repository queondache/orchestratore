#!/usr/bin/env python3
"""Integration gate for accidental ownership violations in one clean task worktree.

This validates the delivered repository state.  It is not a sandbox against a
hostile worker running with the same local account.
"""
from __future__ import annotations

import json
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from controller.path_policy import canonical_path_glob, path_matches_glob  # noqa: E402


def die(message: str) -> None:
    print(f"orchestratore: {message}", file=sys.stderr)
    raise SystemExit(74)


def git(cwd: Path, *args: str, text: bool = False) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True,
                          text=text)
    if proc.returncode:
        detail = proc.stderr.strip() if text else proc.stderr.decode(errors="replace").strip()
        die(detail or "git ownership check fallito")
    return proc


def git_z(cwd: Path, *args: str) -> list[str]:
    return [item.decode(errors="surrogateescape") for item in
            git(cwd, *args).stdout.split(b"\0") if item]


def parse_patterns(raw: str) -> tuple[str, ...]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        die("allowlist non e JSON valido")
    if not isinstance(value, list) or not value or not all(isinstance(x, str) for x in value):
        die("allowlist deve essere una lista JSON non vuota di glob")
    try:
        return tuple(dict.fromkeys(canonical_path_glob(item) for item in value))
    except ValueError as exc:
        die(str(exc))


def index_entries(cwd: Path) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for record in git(cwd, "ls-files", "--stage", "-z").stdout.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, oid, stage = metadata.decode("ascii").split()
            path = raw_path.decode(errors="surrogateescape")
        except (ValueError, UnicodeDecodeError):
            die("index Git non interpretabile")
        if stage != "0":
            die(f"index con conflitto non ammesso: {path}")
        if mode == "160000":
            die(f"submodule/gitlink non ammesso nel task worktree: {path}")
        if mode == "120000":
            die(f"symlink non ammesso nel task worktree: {path}")
        if mode not in {"100644", "100755"}:
            die(f"modo index non supportato per {path}: {mode}")
        entries[path] = (mode, oid)
    return entries


def reject_hidden_flags(cwd: Path) -> None:
    for record in git(cwd, "ls-files", "-v", "-z").stdout.split(b"\0"):
        if not record:
            continue
        tag = chr(record[0])
        path = record[2:].decode(errors="surrogateescape") if len(record) > 2 else "?"
        if tag.islower() or tag == "S":
            die(f"assume-unchanged/skip-worktree/sparse non ammesso: {path}")
    sparse = subprocess.run(
        ["git", "-C", str(cwd), "config", "--bool", "core.sparseCheckout"],
        capture_output=True, text=True)
    if sparse.returncode not in {0, 1}:
        die("impossibile verificare sparse checkout")
    if sparse.stdout.strip().lower() == "true":
        die("sparse checkout non ammesso nel task worktree")


def worktree_changes(cwd: Path, entries: dict[str, tuple[str, str]]) -> set[str]:
    changed: set[str] = set()
    for path, (mode, oid) in entries.items():
        target = cwd / path
        try:
            info = target.lstat()
        except FileNotFoundError:
            changed.add(path)
            continue
        if stat.S_ISLNK(info.st_mode):
            die(f"symlink non ammesso nel task worktree: {path}")
        if stat.S_ISREG(info.st_mode):
            actual_mode = "100755" if info.st_mode & 0o111 else "100644"
        else:
            actual_mode = "invalid"
        hashed = subprocess.run(
            ["git", "-C", str(cwd), "hash-object", f"--path={path}", "--", path],
            capture_output=True, text=True)
        if (actual_mode != mode or hashed.returncode != 0 or
                hashed.stdout.strip() != oid):
            changed.add(path)
    return changed


def exact_head(cwd: Path) -> str:
    return git(cwd, "rev-parse", "--verify", "HEAD^{commit}", text=True).stdout.strip()


def assert_supported_index(cwd: Path) -> dict[str, tuple[str, str]]:
    reject_hidden_flags(cwd)
    return index_entries(cwd)


def untracked_and_ignored(cwd: Path) -> set[str]:
    paths = set(git_z(cwd, "ls-files", "--others", "--exclude-standard", "-z"))
    paths.update(git_z(cwd, "ls-files", "--others", "--ignored",
                       "--exclude-standard", "-z"))
    for path in paths:
        if (cwd / path).is_symlink():
            die(f"symlink non ammesso nel task worktree: {path}")
    return paths


def preflight(cwd: Path) -> None:
    exact_head(cwd)
    entries = assert_supported_index(cwd)
    staged = set(git_z(cwd, "diff-index", "--cached", "--name-only", "-z", "HEAD", "--"))
    dirty = staged | worktree_changes(cwd, entries) | untracked_and_ignored(cwd)
    if dirty:
        die("task worktree non completamente pulito: " + ", ".join(sorted(dirty)))


def postflight(cwd: Path, base: str, allowlist: tuple[str, ...], read_only: bool) -> None:
    resolved_base = git(cwd, "rev-parse", "--verify", f"{base}^{{commit}}",
                        text=True).stdout.strip()
    if resolved_base != base:
        die("base HEAD non e uno SHA completo e immutabile")
    head = exact_head(cwd)
    ancestor = subprocess.run(
        ["git", "-C", str(cwd), "merge-base", "--is-ancestor", base, head],
        capture_output=True)
    if ancestor.returncode != 0:
        die("HEAD finale non discende dal base HEAD")
    entries = assert_supported_index(cwd)
    changed = set(git_z(cwd, "diff-tree", "--no-commit-id", "--name-only",
                        "--no-renames", "-r", "-z", base, head, "--"))
    changed.update(git_z(cwd, "diff-index", "--cached", "--name-only", "-z",
                         head, "--"))
    changed.update(worktree_changes(cwd, entries))
    changed.update(untracked_and_ignored(cwd))
    if read_only and (head != base or changed):
        die("stage in sola lettura ha modificato il task worktree")
    outside = sorted(path for path in changed
                     if not any(path_matches_glob(path, pattern) for pattern in allowlist))
    if outside:
        die("path modificati fuori ownership: " + ", ".join(outside))


def main() -> None:
    if len(sys.argv) < 4 or sys.argv[1] not in {"preflight", "postflight"}:
        die("uso: validate-ownership.py preflight <cwd> <allowlist-json> | "
            "postflight <cwd> <base-head> <allowlist-json> [--read-only]")
    operation = sys.argv[1]
    cwd = Path(sys.argv[2]).resolve()
    if not cwd.is_dir():
        die("task worktree inesistente")
    if operation == "preflight":
        if len(sys.argv) != 4:
            die("argomenti preflight non validi")
        parse_patterns(sys.argv[3])
        preflight(cwd)
        return
    if len(sys.argv) not in {5, 6} or (len(sys.argv) == 6 and sys.argv[5] != "--read-only"):
        die("argomenti postflight non validi")
    postflight(cwd, sys.argv[3], parse_patterns(sys.argv[4]), len(sys.argv) == 6)


if __name__ == "__main__":
    main()
