#!/usr/bin/env bash
# PreToolUse dell'orchestratore: durante un run attivo blocca i comandi che la skill vieta
# in modo assoluto. Fuori da un run non interferisce mai.
# stdin: JSON con tool_input.command e cwd. Exit 2 = blocco, motivo su stderr.
#
# MODELLO DI MINACCIA — leggilo prima di aggiungere pattern.
# Questa guardia e' una rete contro l'ERRORE, non una barriera contro un avversario. Un
# worker che voglia aggirarla ci riesce sempre: `eval`, `$(...)`, i backtick, una variabile,
# un alias, `git -c alias.p="push -f"` non sono risolvibili senza eseguire il comando. La
# barriera vera restano il permission mode del runtime e i guardrail globali di Andrea.
# Qui si coprono le forme che un worker scrive per sbaglio o per fretta, e si paga caro ogni
# falso positivo: in un run non presidiato un blocco ferma il worker e chiama Andrea.
#
# Limiti noti e accettati, verificati uno per uno: non passano la guardia
#   `echo -f | xargs git push`     (il flag arriva dallo stdin, non e' nel comando)
#   `$G push -f` con G=git, e ogni forma che nasconde il comando in una variabile
# Sono gesti deliberati, non errori: chi li scrive sta aggirando la guardia di proposito, e
# nessun pattern lo ferma. Se serve una barriera vera, va messa nel permission mode, non qui.
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

# Senza interprete si estrae il solo campo `command` dal JSON grezzo: mai description o cwd,
# che altrimenti bloccherebbero per una parola in un commento.
raw_command() {
  printf '%s' "$PAYLOAD" \
    | grep -m 1 -oE '"command"[[:space:]]*:[[:space:]]*"([^"\\]|\\.)*"' \
    | sed -e 's/^"command"[[:space:]]*:[[:space:]]*"//' -e 's/"$//' \
          -e 's/\\"/"/g' -e 's/\\n/ /g' -e 's/\\t/ /g' -e 's/\\\\/\\/g'
}

CMD="$(read_field command)"
CWD="$(read_field cwd)"
[ -n "$CWD" ] || CWD="$PWD"

# Nessun run attivo in questo progetto: l'orchestratore non ha voce in capitolo.
[ -f "$CWD/.orchestratore/brain.lock" ] || exit 0

if [ -z "$CMD" ]; then
  CMD="$(raw_command)"
  # Ultima spiaggia: senza nemmeno grep si guarda il payload intero. Copre poco, e va detto.
  [ -n "$CMD" ] || CMD="$PAYLOAD"
fi

blocca() {
  printf 'orchestratore: comando vietato durante un run attivo (%s).\n' "$1" >&2
  printf 'La skill lo esclude sempre: chiudi il checkpoint e chiedi ad Andrea.\n' >&2
  exit 2
}

# Toglie da un token la punteggiatura di shell che non ne cambia il senso per noi.
pulisci() {
  local t="$1"
  t="${t//\"/}"
  t="${t//\'/}"
  t="${t//\\/}"
  t="${t#\$}"
  printf '%s' "$t"
}

TOK=()

# `-rf` porta sia r sia f: ritorna 0 se il token e' un flag corto con quella lettera.
flag_corto_con() { # flag_corto_con <token> <lettera>
  case "$1" in
    --*) return 1 ;;
    -*"$2"*) return 0 ;;
    *) return 1 ;;
  esac
}

analizza_push() { # analizza_push <indice del primo argomento dopo push>
  local i
  for (( i = $1; i < ${#TOK[@]}; i++ )); do
    case "${TOK[i]}" in
      --force*|--mirror) blocca "force-push" ;;
      +*)                blocca "force-push" ;;
      --del*|--prune)    blocca "cancellazione di branch remoto" ;;
      :*)                blocca "cancellazione di branch remoto" ;;
      --*)               ;;
      -*)
        flag_corto_con "${TOK[i]}" f && blocca "force-push"
        flag_corto_con "${TOK[i]}" d && blocca "cancellazione di branch remoto"
        ;;
    esac
  done
}

analizza_git() { # analizza_git <indice del token git>
  local i j sub canc forz forza ricorsiva
  # un push forzato puo' nascondersi in una configurazione passata a git stesso, e il valore
  # di `-c` viene saltato dal ciclo qui sotto: va guardato a parte, su tutti i token.
  for (( i = $1 + 1; i < ${#TOK[@]}; i++ )); do
    case "${TOK[i]}" in
      alias.*=*push*|remote.*.push=+*) blocca "force-push nascosto in una configurazione" ;;
    esac
  done
  j=$(( $1 + 1 ))
  while [ "$j" -lt "${#TOK[@]}" ]; do
    case "${TOK[j]}" in
      -c|-C|--git-dir|--work-tree|--namespace|--exec-path) j=$(( j + 2 )) ;;
      -*) j=$(( j + 1 )) ;;
      *) break ;;
    esac
  done
  [ "$j" -lt "${#TOK[@]}" ] || return 0
  sub="${TOK[j]}"

  case "$sub" in
    push) analizza_push $(( j + 1 )) ;;
    reset)
      for (( i = j + 1; i < ${#TOK[@]}; i++ )); do
        case "${TOK[i]}" in --har*) blocca "reset --hard" ;; esac
      done
      ;;
    clean)
      forza=0; ricorsiva=0
      for (( i = j + 1; i < ${#TOK[@]}; i++ )); do
        case "${TOK[i]}" in
          --force) forza=1 ;;
          --*) ;;
          -*)
            flag_corto_con "${TOK[i]}" f && forza=1
            flag_corto_con "${TOK[i]}" d && ricorsiva=1
            ;;
        esac
      done
      [ "$forza" = 1 ] && [ "$ricorsiva" = 1 ] && blocca "git clean distruttivo"
      ;;
    branch)
      canc=0; forz=0
      for (( i = j + 1; i < ${#TOK[@]}; i++ )); do
        case "${TOK[i]}" in
          --del*) canc=1 ;;
          --force) forz=1 ;;
          --*) ;;
          -*)
            case "${TOK[i]}" in *D*) canc=1; forz=1 ;; esac
            flag_corto_con "${TOK[i]}" d && canc=1
            flag_corto_con "${TOK[i]}" f && forz=1
            ;;
        esac
      done
      [ "$canc" = 1 ] && [ "$forz" = 1 ] && blocca "cancellazione forzata di branch"
      ;;
  esac
}

analizza_rm() { # analizza_rm <indice del token rm>
  local i forza=0 ricorsiva=0
  for (( i = $1 + 1; i < ${#TOK[@]}; i++ )); do
    case "${TOK[i]}" in
      --force) forza=1 ;;
      --recursive) ricorsiva=1 ;;
      --) break ;;
      --*) ;;
      -*)
        flag_corto_con "${TOK[i]}" f && forza=1
        flag_corto_con "${TOK[i]}" r && ricorsiva=1
        flag_corto_con "${TOK[i]}" R && ricorsiva=1
        ;;
    esac
  done
  [ "$forza" = 1 ] && [ "$ricorsiva" = 1 ] && blocca "cancellazione ricorsiva forzata"
}

analizza_find() { # analizza_find <indice del token find>
  local i
  for (( i = $1 + 1; i < ${#TOK[@]}; i++ )); do
    case "${TOK[i]}" in
      -delete) blocca "cancellazione ricorsiva forzata" ;;
      -exec|-execdir)
        case "${TOK[i + 1]:-}" in rm|*/rm) blocca "cancellazione ricorsiva forzata" ;; esac
        ;;
    esac
  done
}

analizza_gh() { # analizza_gh <indice del token gh>
  local i api=0 elimina=0
  for (( i = $1 + 1; i < ${#TOK[@]}; i++ )); do
    case "${TOK[i]}" in
      --admin) blocca "merge che scavalca i check" ;;
      api) api=1 ;;
      DELETE) elimina=1 ;;
    esac
  done
  [ "$api" = 1 ] && [ "$elimina" = 1 ] && blocca "cancellazione via API GitHub"
}

analizza_segmento() {
  local grezzi t i prog
  read -r -a grezzi <<< "$1"
  [ "${#grezzi[@]}" -gt 0 ] || return 0

  TOK=()
  for t in "${grezzi[@]}"; do
    t="$(pulisci "$t")"
    [ "$t" = "#" ] && break
    [ -n "$t" ] && TOK+=("$t")
  done
  [ "${#TOK[@]}" -gt 0 ] || return 0

  # Prefissi che non cambiano il comando vero: wrapper, assegnazioni, durate.
  i=0
  while [ "$i" -lt "${#TOK[@]}" ]; do
    case "${TOK[i]}" in
      env|sudo|command|nice|nohup|time|timeout|ionice|xargs|eval) i=$(( i + 1 )) ;;
      bash|sh|zsh|/bin/sh|/bin/bash|-c) i=$(( i + 1 )) ;;
      *=*) i=$(( i + 1 )) ;;
      [0-9]*) i=$(( i + 1 )) ;;
      *) break ;;
    esac
  done
  [ "$i" -lt "${#TOK[@]}" ] || return 0

  prog="${TOK[i]}"
  case "$prog" in
    git|*/git)   analizza_git "$i" ;;
    rm|*/rm)     analizza_rm "$i" ;;
    find|*/find) analizza_find "$i" ;;
    gh|*/gh)     analizza_gh "$i" ;;
    push)        [ "$i" = 0 ] && analizza_push $(( i + 1 )) ;;
  esac
}

esamina() { # esamina <testo del comando>
  local testo="$1" riga
  testo="${testo//&&/$'\n'}"
  testo="${testo//||/$'\n'}"
  testo="${testo//;/$'\n'}"
  testo="${testo//|/$'\n'}"
  testo="${testo//(/$'\n'}"
  testo="${testo//)/$'\n'}"
  testo="${testo//\{/$'\n'}"
  testo="${testo//\}/$'\n'}"
  testo="${testo//\`/$'\n'}"
  while IFS= read -r riga; do
    analizza_segmento "$riga"
  done <<< "$testo"
}

# Un comando composto si spezza sui separatori di shell, parentesi e graffe comprese,
# cosi' una subshell, una sostituzione di comando e un wrapper come eval arrivano tutti
# all'analisi come il comando che contengono.
esamina "$CMD"

exit 0
