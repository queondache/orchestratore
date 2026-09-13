#!/usr/bin/env bash
# PreToolUse dell'orchestratore: durante un run attivo blocca i comandi che la skill
# vieta in modo assoluto. Fuori da un run non interferisce mai.
# stdin: JSON con tool_input.command e cwd. Exit 2 = blocco, motivo su stderr.
set -uo pipefail

PAYLOAD="$(cat)"

read_field() { # read_field <command|cwd>
  command -v python3 >/dev/null 2>&1 || return 1
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
[ -n "$CWD" ] || CWD="$PWD"

# Nessun run attivo in questo progetto: l'orchestratore non ha voce in capitolo.
[ -f "$CWD/.orchestratore/brain.lock" ] || exit 0

# Senza interprete non si fallisce aperti: il comando si estrae dal JSON grezzo. Si legge
# solo il campo `command`, mai description o cwd, che altrimenti bloccherebbero per una
# parola in un commento. Se anche questo fallisce, ultima spiaggia: tutto il payload, che
# chiude invece di aprire.
raw_command() {
  printf '%s' "$PAYLOAD" \
    | grep -m 1 -oE '"command"[[:space:]]*:[[:space:]]*"([^"\\]|\\.)*"' \
    | sed -e 's/^"command"[[:space:]]*:[[:space:]]*"//' -e 's/"$//' \
          -e 's/\\"/"/g' -e 's/\\n/ /g' -e 's/\\t/ /g' -e 's/\\\\/\\/g'
}

if [ -z "$CMD" ]; then
  CMD="$(raw_command)"
  [ -n "$CMD" ] || CMD="$PAYLOAD"
fi

blocca() {
  printf 'orchestratore: comando vietato durante un run attivo (%s).\n' "$1" >&2
  printf 'La skill lo esclude sempre: chiudi il checkpoint e chiedi ad Andrea.\n' >&2
  exit 2
}

# Il force-push si scrive in molti modi, anche corto e in fondo alla riga (`git push -f`).
# Il flag va cercato nel segmento che contiene il push, non nella riga intera: altrimenti
# `git push origin feat/a && rm -f /tmp/x` verrebbe scambiato per un force-push e il worker
# si fermerebbe per niente.
forza_su_push() {
  local riga="$1" seg
  riga="${riga//&&/$'\n'}"
  riga="${riga//||/$'\n'}"
  riga="${riga//;/$'\n'}"
  riga="${riga//|/$'\n'}"
  while IFS= read -r seg; do
    # via gli spazi in coda, cosi` un flag come ultimo token resta riconoscibile
    seg="${seg%"${seg##*[![:space:]]}"}"
    case "$seg" in
      *"git push"*|*"git -C"*"push"*|"push "*|"push")
        case "$seg" in
          *" --force"*|*" --force-with-lease"*|*" -f "*|*" -f") return 0 ;;
        esac
        ;;
    esac
  done <<< "$riga"
  return 1
}

forza_su_push "$CMD" && blocca "force-push"

case "$CMD" in
  *"reset --hard"*)                                          blocca "reset --hard" ;;
  *"clean -fd"*|*"clean -df"*|*"clean -fdx"*)                blocca "git clean distruttivo" ;;
  *"branch -D"*)                                             blocca "cancellazione di branch" ;;
  *"push"*"--delete"*|*"push origin :"*)                     blocca "cancellazione di branch remoto" ;;
  *"gh pr merge"*"--admin"*)                                 blocca "merge che scavalca i check" ;;
  *"rm -rf"*|*"rm -fr"*)                                     blocca "cancellazione ricorsiva forzata" ;;
esac

exit 0
