#!/usr/bin/env bash
# PreToolUse dell'orchestratore: durante un run attivo blocca i comandi che la skill
# vieta in modo assoluto. Fuori da un run non interferisce mai.
# stdin: JSON con tool_input.command e cwd. Exit 2 = blocco, motivo su stderr.
set -uo pipefail

PAYLOAD="$(cat)"

read_field() { # read_field <command|cwd>
  printf '%s' "$PAYLOAD" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
k = sys.argv[1]
v = d.get("tool_input", {}).get("command") if k == "command" else d.get(k)
sys.stdout.write(v if isinstance(v, str) else "")
' "$1" 2>/dev/null
}

CMD="$(read_field command)"
CWD="$(read_field cwd)"
[ -n "$CMD" ] || exit 0
[ -n "$CWD" ] || CWD="$PWD"

# Nessun run attivo in questo progetto: l'orchestratore non ha voce in capitolo.
[ -f "$CWD/.orchestratore/brain.lock" ] || exit 0

blocca() {
  printf 'orchestratore: comando vietato durante un run attivo (%s).\n' "$1" >&2
  printf 'La skill lo esclude sempre: chiudi il checkpoint e chiedi ad Andrea.\n' >&2
  exit 2
}

case "$CMD" in
  *"push --force"*|*"push -f "*|*"push --force-with-lease"*) blocca "force-push" ;;
  *"reset --hard"*)                                          blocca "reset --hard" ;;
  *"clean -fd"*|*"clean -df"*|*"clean -fdx"*)                blocca "git clean distruttivo" ;;
  *"branch -D"*)                                             blocca "cancellazione di branch" ;;
  *"push"*"--delete"*|*"push origin :"*)                     blocca "cancellazione di branch remoto" ;;
  *"gh pr merge"*"--admin"*)                                 blocca "merge che scavalca i check" ;;
  *"rm -rf"*|*"rm -fr"*)                                     blocca "cancellazione ricorsiva forzata" ;;
esac

exit 0
