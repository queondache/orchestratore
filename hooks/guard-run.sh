#!/usr/bin/env bash
# PreToolUse dell'orchestratore: durante un run attivo blocca i comandi che la skill vieta
# in modo assoluto. Fuori da un run non interferisce mai.
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

# Nessun run attivo in questo progetto: l'orchestratore non ha voce in capitolo.
[ -f "$CWD/.orchestratore/brain.lock" ] || exit 0

# Senza python3 non c'e' analisi. Si passa oltre, ma lo si dice: una guardia che tace e non
# protegge e' peggio di una che non c'e', perche' fa credere di esserci.
if ! command -v python3 >/dev/null 2>&1; then
  printf 'orchestratore: python3 assente, la guardia sui comandi vietati NON e attiva.\n' >&2
  exit 0
fi

printf '%s' "$PAYLOAD" | python3 "$QUI/guard_run.py"
exit "${PIPESTATUS[1]}"
