#!/usr/bin/env bash
# PreToolUse dell'orchestratore: guardrail accidentale sui comandi esclusi dal contratto.
# Non e' una sandbox contro codice worker ostile. Fuori da un run non interferisce mai.
# stdin: JSON con tool_input.command e cwd. Exit 2 = blocco, motivo su stderr.
#
# Questo file fa solo tre cose: capire se c'e' un run attivo, e in quel caso passare il
# payload all'analizzatore, che sta in guard_run.py. L'analisi non e' in shell perche' un
# confronto a pattern non distingue un comando da una stringa che parla di quel comando:
# cinque giri di verifica lo hanno dimostrato, con bypass da una parte e messaggi di commit
# bloccati dall'altra. Il modello di minaccia e i limiti reali sono documentati in
# guard_run.py: leggi quelli prima di cambiare qualcosa.
set -uo pipefail

PAYLOAD="$(cat)"
QUI="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

# Il cwd della sessione: se il payload non lo dice, e' la directory del processo.
CWD=""
if command -v python3 >/dev/null 2>&1; then
  CWD="$(printf '%s' "$PAYLOAD" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
v = d.get("cwd")
sys.stdout.write(v if isinstance(v, str) else "")
' 2>/dev/null)"
fi
[ -n "$CWD" ] || CWD="$PWD"

# Risolvi sempre dal git root: il tool puo partire da qualunque sottodirectory.
# I bridge impostano ORCHESTRATORE_PROJECT_ROOT, cosi' la guardia resta attiva anche
# quando il worker esegue nel worktree isolato e brain.lock vive nel control plane.
ROOT="${ORCHESTRATORE_PROJECT_ROOT:-}"
if [ -n "$ROOT" ]; then
  ROOT="$(CDPATH= cd -- "$ROOT" 2>/dev/null && pwd -P)" || exit 0
  [ -s "$ROOT/.orchestratore/RUN.md" ] || exit 0
else
  ROOT="$(git -C "$CWD" rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -z "$ROOT" ]; then
    ROOT="$(CDPATH= cd -- "$CWD" 2>/dev/null && pwd -P)" || exit 0
    while [ "$ROOT" != / ] && [ ! -f "$ROOT/.orchestratore/brain.lock" ]; do ROOT="${ROOT%/*}"; [ -n "$ROOT" ] || ROOT=/; done
  fi
  [ -f "$ROOT/.orchestratore/brain.lock" ] || exit 0
fi

# Senza python3 non c'e' feedback anticipato. Si passa oltre, ma lo si dichiara: il gate di
# integrazione resta separato da questo guardrail accidentale.
if ! command -v python3 >/dev/null 2>&1; then
  printf 'orchestratore: python3 assente, il guardrail accidentale NON e attivo.\n' >&2
  exit 0
fi

printf '%s' "$PAYLOAD" | python3 "$QUI/guard_run.py"
exit "${PIPESTATUS[1]}"
