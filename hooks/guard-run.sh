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

# I confronti per sottostringa sono aggirabili: `git  reset  --hard` con due spazi non
# assomiglia a `git reset --hard`. Si normalizzano gli spazi riga per riga, senza fondere
# righe diverse fra loro.
normalizza() {
  local linea out="" parole
  while IFS= read -r linea; do
    read -r -a parole <<< "$linea"
    out="$out${parole[*]}"$'\n'
  done <<< "$1"
  printf '%s' "$out"
}

# Il force-push non ha una sola forma: `git -c a=b push -f`, `git push -uf`,
# `/usr/bin/git push ----force` e soprattutto `git push origin +main`, che forza tramite
# refspec senza nessun flag. Si guarda il segmento che contiene davvero un git push e si
# esaminano i token uno per uno, non la riga come stringa.
forza_su_push() {
  local riga="$1" seg parole i visto_git visto_push
  riga="${riga//&&/$'\n'}"
  riga="${riga//||/$'\n'}"
  riga="${riga//;/$'\n'}"
  riga="${riga//|/$'\n'}"
  while IFS= read -r seg; do
    read -r -a parole <<< "$seg"
    [ "${#parole[@]}" -gt 0 ] || continue
    visto_git=0
    visto_push=0
    for (( i = 0; i < ${#parole[@]}; i++ )); do
      case "${parole[i]}" in
        git|*/git) visto_git=1 ;;
        push) [ "$visto_git" = 1 ] && visto_push=1 ;;
      esac
    done
    [ "${parole[0]}" = "push" ] && visto_push=1
    [ "$visto_push" = 1 ] || continue
    for (( i = 0; i < ${#parole[@]}; i++ )); do
      case "${parole[i]}" in
        --force|--force-with-lease|--force-with-lease=*) return 0 ;;
        +*)                                  return 0 ;;   # refspec forzata
        --*)                                 ;;            # altre opzioni lunghe
        -*f*)                                return 0 ;;   # -f, -uf, -fu
      esac
    done
  done <<< "$riga"
  return 1
}

CMD_N="$(normalizza "$CMD")"

forza_su_push "$CMD_N" && blocca "force-push"

case "$CMD_N" in
  *"reset --hard"*)                             blocca "reset --hard" ;;
  *"clean -fd"*|*"clean -df"*|*"clean -fdx"*)   blocca "git clean distruttivo" ;;
  *"branch -D"*)                                blocca "cancellazione di branch" ;;
  *"push"*"--delete"*|*"push origin :"*)        blocca "cancellazione di branch remoto" ;;
  *"gh pr merge"*"--admin"*)                    blocca "merge che scavalca i check" ;;
  *"rm -rf"*|*"rm -fr"*|*"rm -r -f"*|*"rm -f -r"*|*"rm --recursive --force"*)
                                                blocca "cancellazione ricorsiva forzata" ;;
esac

exit 0
