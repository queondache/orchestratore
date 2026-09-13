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

# Ogni regola vale sul singolo segmento di comando, mai sulla riga intera: altrimenti
# `git push origin feat/a && gh pr merge 3 --squash --delete-branch` verrebbe letto come una
# cancellazione di branch remoto e fermerebbe il worker per niente.
#
# Il force-push non ha una sola forma: `git -c a=b push -f`, `git push -uf`,
# `/usr/bin/git push ----force` e soprattutto `git push origin +main`, che forza tramite
# refspec senza nessun flag. Per questo i token si guardano uno per uno.
analizza_segmento() {
  local seg="$1" parole piatto i visto_git=0 visto_push=0
  read -r -a parole <<< "$seg"
  [ "${#parole[@]}" -gt 0 ] || return 0
  piatto="${parole[*]}"

  for (( i = 0; i < ${#parole[@]}; i++ )); do
    case "${parole[i]}" in
      git|*/git) visto_git=1 ;;
      push)      [ "$visto_git" = 1 ] && visto_push=1 ;;
    esac
  done
  [ "${parole[0]}" = "push" ] && visto_push=1

  if [ "$visto_push" = 1 ]; then
    for (( i = 0; i < ${#parole[@]}; i++ )); do
      case "${parole[i]}" in
        --force|--force-with-lease|--force-with-lease=*) blocca "force-push" ;;
        +*)                                 blocca "force-push" ;;          # refspec forzata
        --delete)                           blocca "cancellazione di branch remoto" ;;
        :*)                                 blocca "cancellazione di branch remoto" ;;
        --*)                                ;;                             # altre opzioni lunghe
        -*f*)                               blocca "force-push" ;;          # -f, -uf, -fu
      esac
    done
  fi

  case "$piatto" in
    *"reset --hard"*)                           blocca "reset --hard" ;;
    *"clean -fd"*|*"clean -df"*|*"clean -fdx"*) blocca "git clean distruttivo" ;;
    *"branch -D"*)                              blocca "cancellazione di branch" ;;
    *"gh pr merge"*"--admin"*)                  blocca "merge che scavalca i check" ;;
    *"rm -rf"*|*"rm -fr"*|*"rm -r -f"*|*"rm -f -r"*|*"rm --recursive --force"*)
                                                blocca "cancellazione ricorsiva forzata" ;;
  esac
}

CMD_N="$(normalizza "$CMD")"
SEGMENTI="${CMD_N//&&/$'\n'}"
SEGMENTI="${SEGMENTI//||/$'\n'}"
SEGMENTI="${SEGMENTI//;/$'\n'}"
SEGMENTI="${SEGMENTI//|/$'\n'}"

while IFS= read -r SEG; do
  analizza_segmento "$SEG"
done <<< "$SEGMENTI"

exit 0
