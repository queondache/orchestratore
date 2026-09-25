"""Canonical repository-relative glob policy shared by controller gates."""
from __future__ import annotations

import fnmatch


def canonical_path_glob(pattern: str) -> str:
    value = pattern.strip()
    if not value:
        raise ValueError("path glob must not be empty")
    if "\\" in value:
        raise ValueError("path glob must use unambiguous forward slashes")
    if value.startswith("/") or (len(value) >= 2 and value[0].isalpha() and value[1] == ":"):
        raise ValueError("path glob must be relative")
    if "//" in value:
        raise ValueError("path glob must not contain empty path segments")
    parts = value.split("/")
    if any(part == "" for part in parts):
        raise ValueError("path glob must not contain empty path segments")
    if any(part == ".." for part in parts):
        raise ValueError("path glob must not contain parent path segments")
    canonical = "/".join(part for part in parts if part != ".")
    if not canonical:
        raise ValueError("path glob must identify a relative path")
    return canonical


def _match_segments(pattern: tuple[str, ...], path: tuple[str, ...]) -> bool:
    if not pattern:
        return not path
    if pattern[0] == "**":
        return _match_segments(pattern[1:], path) or (
            bool(path) and _match_segments(pattern, path[1:]))
    return bool(path) and fnmatch.fnmatchcase(path[0], pattern[0]) and _match_segments(
        pattern[1:], path[1:])


def path_matches_glob(path: str, pattern: str) -> bool:
    """Match path segments; ``**`` consumes zero or more complete segments."""
    return _match_segments(tuple(pattern.split("/")), tuple(path.split("/")))
