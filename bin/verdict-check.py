#!/usr/bin/env python3
"""Deterministic check that a verifier's verdict is well formed and its facts support it.

Answers one question with evidence: may the coordinator act on this verdict? The
verifier gathers the evidence; this script applies fixed rules, so no agent can
turn a failing command or a reused proof into an OK.

  * a `VERDICT <ID> <hash>` header, a full 40-hex `hash:` line that the header
    hash prefixes and, with --hash, equals the delivered hash;
  * `result:` is OK, KO or BLOCKED;
  * every `commands:` line has `→ exit <n>` (or `->`) and a provenance tag:
    `[ran]` (run by the verifier on this hash), `[ci <run url or id>]` (the
    project's checks on this exact hash) or `[reused <what>]`;
  * OK: at least one command, every exit 0, only `ran` / `ci` evidence,
    `scope: none`, `findings: none`, `blocked: none` or absent;
  * KO: `findings:` names what is wrong;
  * BLOCKED: `blocked:` says what is missing to run the proof. It is not a KO.

Input: the verdict on stdin, or --verdict <file>. The header may sit inside prose
or a fenced block. Exit codes: 0 verdict valid, 1 invalid (treat as malformed),
2 error. Output: one JSON object on stdout.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

RESULTS = {"OK", "KO", "BLOCKED"}
COMMAND_RE = re.compile(r"(?:→|->)\s*exit\s+(-?\d+)\b(.*)$")
TAG_RE = re.compile(r"\[(ran|ci|reused)(?:\s+([^\]]*))?\]\s*$")


def field(lines: List[str], name: str) -> Optional[str]:
    for line in lines:
        if line.startswith(f"{name}:"):
            return line[len(name) + 1:].strip()
    return None


def is_none(value: Optional[str]) -> bool:
    return value is None or value.strip().lower() in {"none", "-", ""}


def evaluate(text: str, delivered: Optional[str]) -> Dict[str, object]:
    raw = [line.strip() for line in text.splitlines()]
    start = next((i for i, line in enumerate(raw) if line.startswith("VERDICT ")), None)
    problems: List[str] = []
    if start is None:
        return {"valid": False, "result": None, "problems": ["no `VERDICT <ID> <hash>` header"]}
    lines = [line for line in raw[start:] if not line.startswith("```")]

    header = lines[0].split()
    header_hash = header[2] if len(header) >= 3 else ""
    unit = header[1] if len(header) >= 2 else ""
    if not unit or not re.fullmatch(r"[0-9a-f]{7,40}", header_hash):
        problems.append("header must be `VERDICT <ID> <hex hash>`")

    full = field(lines, "hash") or ""
    if not re.fullmatch(r"[0-9a-f]{40}", full):
        problems.append(f"`hash:` must be the full 40-hex output of git rev-parse HEAD, got {full!r}")
    elif header_hash and not full.startswith(header_hash):
        problems.append("header hash does not prefix the `hash:` line")
    if delivered and full and full != delivered:
        problems.append(f"hash {full} is not the delivered hash {delivered}")

    result = (field(lines, "result") or "").upper()
    if result not in RESULTS:
        problems.append(f"result {result!r} is not one of OK, KO, BLOCKED")

    commands = [line[len("commands:"):].strip() for line in lines if line.startswith("commands:")]
    evidence = []
    for cmd in commands:
        m = COMMAND_RE.search(cmd)
        if not m:
            problems.append(f"command without `→ exit <code>`: {cmd!r}")
            continue
        code, rest = int(m.group(1)), m.group(2).strip()
        tag = TAG_RE.search(rest)
        if not tag:
            problems.append(f"command without provenance [ran|ci <ref>|reused <what>]: {cmd!r}")
            continue
        kind, ref = tag.group(1), (tag.group(2) or "").strip()
        if kind in {"ci", "reused"} and not ref:
            problems.append(f"[{kind}] needs a reference (run url or id, or what was reused): {cmd!r}")
        evidence.append((cmd, code, kind))

    scope, findings, blocked = field(lines, "scope"), field(lines, "findings"), field(lines, "blocked")
    if result == "OK":
        if not commands:
            problems.append("OK needs at least one command with its exit code")
        for cmd, code, kind in evidence:
            if code != 0:
                problems.append(f"OK with a failing command (exit {code}): {cmd!r}")
            if kind == "reused":
                problems.append(f"OK cannot rest on reused proof: {cmd!r}")
        if not is_none(scope):
            problems.append(f"OK with paths outside scope: {scope}")
        if not is_none(findings):
            problems.append(f"OK with open findings: {findings}")
        if not is_none(blocked):
            problems.append(f"OK while blocked: {blocked}")
    elif result == "KO":
        if is_none(findings) and is_none(scope):
            problems.append("KO must name its findings (file:line and what is wrong)")
    elif result == "BLOCKED":
        if is_none(blocked):
            problems.append("BLOCKED must say in `blocked:` what is missing to run the proof")

    return {"valid": not problems, "unit": unit, "result": result or None, "hash": full,
            "problems": problems}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--verdict", help="file holding the verdict (default: stdin)")
    parser.add_argument("--hash", help="the delivered hash the verdict must be about")
    args = parser.parse_args(argv)
    if args.verdict:
        path = Path(args.verdict)
        if not path.is_file():
            print(json.dumps({"valid": False, "error": f"verdict file not found: {path}"}))
            return 2
        text = path.read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    result = evaluate(text, args.hash)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
