#!/usr/bin/env python3
"""Guardrail accidentale stage-aware per i tool di scrittura dei worker.

Il gate di integrazione post-worker resta l'autorita sul risultato consegnato;
questo hook fornisce feedback anticipato, non isola codice worker ostile.
"""
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from controller.path_policy import canonical_path_glob, path_matches_glob  # noqa: E402

def reject(reason: str) -> None:
    print(f"orchestratore: scrittura vietata ({reason}).", file=sys.stderr)
    raise SystemExit(2)


def paths_from(payload: dict) -> list[str]:
    tool = str(payload.get("tool_name", "")).lower()
    data = payload.get("tool_input") or {}
    direct = data.get("file_path") or data.get("path")
    if isinstance(direct, str):
        return [direct]
    if "apply_patch" in tool:
        patch = data.get("patch") or data.get("input")
        if isinstance(patch, str):
            return re.findall(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", patch, re.MULTILINE)
    return []


def main() -> None:
    stage = os.environ.get("ORCHESTRATORE_STAGE", "")
    if not stage:
        return
    try:
        payload = json.load(sys.stdin)
    except Exception:
        reject("payload hook non valido")
    if stage != "build":
        reject(f"stage {stage} in sola lettura")
    try:
        raw_patterns = json.loads(os.environ["ORCHESTRATORE_ALLOWLIST_JSON"])
        if (not isinstance(raw_patterns, list) or not raw_patterns or
                not all(isinstance(item, str) for item in raw_patterns)):
            raise ValueError("allowlist non valida")
        patterns = tuple(dict.fromkeys(canonical_path_glob(item)
                                       for item in raw_patterns))
        root = Path(os.environ["ORCHESTRATORE_TASK_CWD"]).resolve()
    except Exception:
        reject("ownership non disponibile")
    paths = paths_from(payload)
    if not paths:
        reject("path del tool non determinabile")
    for raw in paths:
        target = Path(raw)
        target = target.resolve() if target.is_absolute() else (root / target).resolve()
        try:
            relative = target.relative_to(root).as_posix()
        except ValueError:
            reject(f"path fuori task worktree: {target}")
        if not any(path_matches_glob(relative, pattern) for pattern in patterns):
            reject(f"path fuori ownership: {relative}")


if __name__ == "__main__":
    main()
