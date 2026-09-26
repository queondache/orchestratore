#!/usr/bin/env python3
"""Deterministic merge gate for an Orchestratore pull request.

Answers one question with evidence: may this exact commit be merged without a
human? The answer is "yes" only when every condition holds:

  * the PR is open, not a draft, and its head is the verified SHA;
  * the declared risk tier is 1 or 2;
  * every changed path is covered by the explicit auto-merge allowlist;
  * no changed path matches a built-in or configured sensitive glob;
  * the base branch has required status checks and all of them passed
    (or --no-required-checks-ok is given, after the full local gate ran on
    the exact SHA).

Any uncertainty is a "no". With --merge, a "yes" is executed through
`gh pr merge --squash --match-head-commit <sha>`, so GitHub itself rejects the
merge if the head moved after the check.

Exit codes: 0 merge allowed (and merged with --merge), 1 not allowed, 2 error.
Output: one JSON object on stdout.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

# Paths that always need a human: schema, auth, payments, tenancy, personal
# data, secrets, permissions, deletion. A project can add more, never remove.
BUILTIN_SENSITIVE = (
    "**/schema", "**/schema.*", "**/schema/**",
    "**/migration", "**/migrations", "**/migration/**", "**/migrations/**",
    "**/auth/**", "**/authentication/**", "**/session/**", "**/sessions/**",
    "**/payment/**", "**/payments/**", "**/billing/**",
    "**/tenant/**", "**/tenants/**", "**/tenancy/**", "**/multitenancy/**",
    "**/pii/**", "**/patient/**", "**/patients/**", "**/health/**",
    "**/secret/**", "**/secrets/**", "**/*secret*", "**/*credential*",
    "**/*.pem", "**/*.key", "**/.env", "**/.env.*",
    "**/permission/**", "**/permissions/**", "**/role/**", "**/roles/**",
    "**/user/**", "**/users/**", "**/delete/**", "**/deletion/**",
    "**/purge/**", "**/retention/**",
)
DEFAULT_CONFIG = ".orchestratore/config.toml"


class GateError(Exception):
    """A condition could not be evaluated; the gate answers no."""


def canonical_glob(pattern: str) -> str:
    value = pattern.strip()
    if not value or "\\" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise GateError("invalid glob (must be relative, forward slashes): %r" % pattern)
    parts = [p for p in value.split("/") if p != "."]
    if not parts or "" in parts or ".." in parts:
        raise GateError("invalid glob (empty or parent segment): %r" % pattern)
    return "/".join(parts)


def _match(pattern: Sequence[str], path: Sequence[str]) -> bool:
    if not pattern:
        return not path
    if pattern[0] == "**":
        return _match(pattern[1:], path) or (bool(path) and _match(pattern, path[1:]))
    return bool(path) and fnmatch.fnmatchcase(path[0], pattern[0]) and _match(pattern[1:], path[1:])


def matches(path: str, pattern: str) -> bool:
    """Segment-wise glob match; `**` spans zero or more whole segments."""
    return _match(tuple(pattern.split("/")), tuple(path.split("/")))


def read_config(path: Path) -> Dict[str, List[str]]:
    """Read [merge] auto_merge_globs / sensitive_globs; missing file = empty."""
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import tomllib  # Python >= 3.11
        section = tomllib.loads(text).get("merge", {})
    except ModuleNotFoundError:
        section = _read_merge_section(text)
    result: Dict[str, List[str]] = {}
    for key in ("auto_merge_globs", "sensitive_globs"):
        value = section.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise GateError("config [merge].%s must be a list of strings" % key)
        result[key] = value
    return result


def _read_merge_section(text: str) -> Dict[str, Any]:
    """Minimal fallback for Python < 3.11: string arrays inside [merge]."""
    match = re.search(r"^\[merge\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    if not match:
        return {}
    body = re.sub(r"#[^\n\"']*$", "", match.group(1), flags=re.M)
    section: Dict[str, Any] = {}
    for key, raw in re.findall(r"^(\w+)\s*=\s*\[(.*?)\]", body, re.M | re.S):
        section[key] = re.findall(r"\"([^\"]*)\"|'([^']*)'", raw)
        section[key] = [a or b for a, b in section[key]]
    return section


def gh(args: List[str], repo: str | None, allow_fail: bool = False) -> Tuple[int, str, str]:
    cmd = ["gh", *args] + (["--repo", repo] if repo and args[0] == "pr" else [])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GateError("cannot run gh: %s" % exc) from exc
    if proc.returncode != 0 and not allow_fail:
        raise GateError("gh %s failed: %s" % (" ".join(args[:2]), proc.stderr.strip()))
    return proc.returncode, proc.stdout, proc.stderr


def required_checks(slug: str, base: str) -> List[str] | None:
    """Names of required checks on the base branch; None when none configured."""
    code, out, err = gh(["api", "repos/%s/branches/%s/protection/required_status_checks"
                         % (slug, base)], None, allow_fail=True)
    if code != 0:
        if "404" in err or "not protected" in err.lower():
            return None
        raise GateError("cannot read branch protection: %s" % err.strip())
    data = json.loads(out)
    names = set(data.get("contexts") or [])
    names.update(c.get("context") for c in data.get("checks") or [] if c.get("context"))
    return sorted(names) or None


def evaluate(args: argparse.Namespace) -> Dict[str, Any]:
    config = read_config(Path(args.config))
    allow = [canonical_glob(g) for g in config.get("auto_merge_globs", []) + args.allow]
    sensitive = [canonical_glob(g) for g in config.get("sensitive_globs", []) + args.sensitive]
    reasons: List[str] = []

    _, out, _ = gh(["pr", "view", str(args.pr), "--json",
                    "headRefOid,baseRefName,state,isDraft,files"], args.repo)
    pr = json.loads(out)
    files = sorted(f["path"] for f in pr.get("files") or [])
    if pr.get("state") != "OPEN":
        reasons.append("PR is %s, not OPEN" % pr.get("state"))
    if pr.get("isDraft"):
        reasons.append("PR is a draft")
    if pr.get("headRefOid") != args.sha:
        reasons.append("PR head %s differs from verified sha %s" % (pr.get("headRefOid"), args.sha))
    if args.tier == 3:
        reasons.append("declared risk tier 3 needs a human")
    if not files:
        reasons.append("PR has no changed files to classify")

    sensitive_hits = [p for p in files
                      if any(matches(p, g) for g in BUILTIN_SENSITIVE + tuple(sensitive))]
    if sensitive_hits:
        reasons.append("sensitive paths touched: %s" % ", ".join(sensitive_hits))
    if not allow:
        reasons.append("no auto-merge allowlist configured")
        unclassified = files
    else:
        unclassified = [p for p in files if not any(matches(p, g) for g in allow)]
        if unclassified:
            reasons.append("paths outside the auto-merge allowlist: %s" % ", ".join(unclassified))

    slug = args.repo or gh(["repo", "view", "--json", "nameWithOwner", "-q",
                            ".nameWithOwner"], None)[1].strip()
    required = required_checks(slug, pr.get("baseRefName", ""))
    check_states: Dict[str, str] = {}
    if required is None:
        if not args.no_required_checks_ok:
            reasons.append("base branch has no required checks "
                           "(pass --no-required-checks-ok only after the full local gate ran on this sha)")
    else:
        _, out, _ = gh(["pr", "checks", str(args.pr), "--required", "--json", "name,bucket"],
                       args.repo, allow_fail=True)
        try:
            check_states = {c["name"]: c["bucket"] for c in json.loads(out or "[]")}
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise GateError("cannot parse required checks") from exc
        for name in required:
            state = check_states.get(name, "missing")
            if state != "pass":
                reasons.append("required check %s is %s" % (name, state))

    return {"merge": not reasons, "merged": False, "pr": args.pr, "sha": args.sha,
            "tier": args.tier, "reasons": reasons, "changed_paths": files,
            "sensitive_paths": sensitive_hits, "unclassified_paths": unclassified,
            "required_checks": required, "check_states": check_states}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--sha", required=True, help="verified commit that must be the PR head")
    parser.add_argument("--tier", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--allow", action="append", default=[], metavar="GLOB")
    parser.add_argument("--sensitive", action="append", default=[], metavar="GLOB")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--repo", help="OWNER/REPO (default: current repository)")
    parser.add_argument("--no-required-checks-ok", action="store_true")
    parser.add_argument("--merge", action="store_true", help="squash-merge when allowed")
    args = parser.parse_args(argv)
    try:
        result = evaluate(args)
        if result["merge"] and args.merge:
            gh(["pr", "merge", str(args.pr), "--squash", "--match-head-commit", args.sha],
               args.repo)
            result["merged"] = True
    except (GateError, json.JSONDecodeError) as exc:
        print(json.dumps({"merge": False, "merged": False, "error": str(exc),
                          "reasons": [str(exc)]}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["merge"] else 1


if __name__ == "__main__":
    sys.exit(main())
