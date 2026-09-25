#!/usr/bin/env python3
"""Fail-closed attestation that the enabled runtime uses this exact hook bundle."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys


PLUGIN_ID = "orchestratore@orchestratore"
CORE_FILES = (
    "hooks/hooks.json",
    "hooks/guard_run.py",
    "controller/path_policy.py",
)


def fail(message: str) -> None:
    print(f"orchestratore: {message}", file=sys.stderr)
    raise SystemExit(69)


def bundle_digest(root: Path) -> str:
    manifest_path = root / "hooks/hooks.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"manifest hook non valido: {exc}")
    referenced: set[str] = set()
    for event in manifest.get("hooks", {}).values():
        if not isinstance(event, list):
            fail("manifest hook contiene un evento non valido")
        for registration in event:
            for hook in registration.get("hooks", []) if isinstance(registration, dict) else []:
                command = hook.get("command") if isinstance(hook, dict) else None
                prefix = "${CLAUDE_PLUGIN_ROOT}/"
                if not isinstance(command, str) or not command.startswith(prefix):
                    fail(f"comando hook non locale o non attestabile: {command!r}")
                relative = command[len(prefix):]
                if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
                    fail(f"path hook non sicuro: {relative!r}")
                referenced.add(relative)
    if not referenced:
        fail("manifest hook senza executable attestabili")
    files = sorted(set(CORE_FILES) | referenced)
    digest = hashlib.sha256()
    for relative in files:
        path = root / relative
        if not path.is_file():
            fail(f"bundle hook incompleto: {path}")
        if relative in referenced and not os.access(path, os.X_OK):
            fail(f"hook installato non eseguibile: {path}")
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def codex_candidate(plugin: dict) -> Path:
    direct = plugin.get("installPath")
    if isinstance(direct, str) and direct:
        return Path(direct)
    source = plugin.get("source")
    if isinstance(source, dict) and isinstance(source.get("path"), str):
        candidate = Path(source["path"])
        if (candidate / "hooks" / "hooks.json").is_file():
            return candidate
    name = plugin.get("name")
    marketplace = plugin.get("marketplaceName")
    version = plugin.get("version")
    if not all(isinstance(value, str) and value for value in (name, marketplace, version)):
        fail("metadati installazione Codex incompleti")
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    return codex_home / "plugins" / "cache" / marketplace / name / version


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in {"codex", "claude"}:
        fail("uso verify-hook-install.py <codex|claude> <expected-root>")
    runtime, expected_raw = sys.argv[1:]
    expected = Path(expected_raw).resolve()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        fail(f"{runtime} plugin list non ha restituito JSON valido")
    plugins = payload.get("installed") if runtime == "codex" and isinstance(payload, dict) else payload
    if not isinstance(plugins, list):
        fail(f"formato plugin list {runtime} non riconosciuto")
    plugin = next((item for item in plugins if isinstance(item, dict) and
                   (item.get("pluginId") or item.get("id")) == PLUGIN_ID), None)
    if not plugin or plugin.get("enabled") is not True or plugin.get("installed", True) is not True:
        fail(f"plugin {PLUGIN_ID} non installato e abilitato in {runtime}")
    if runtime == "codex":
        installed = codex_candidate(plugin).resolve()
    else:
        raw = plugin.get("installPath")
        if not isinstance(raw, str) or not raw:
            fail("Claude non dichiara installPath del plugin")
        installed = Path(raw).resolve()
    if bundle_digest(installed) != bundle_digest(expected):
        fail(f"bundle hook {runtime} installato non coincide con il bridge corrente")


if __name__ == "__main__":
    main()
