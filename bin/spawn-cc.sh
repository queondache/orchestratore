#!/usr/bin/env bash
# Bridge dell'orchestratore: lancia un worker Claude Code non interattivo.
# Uso: bin/spawn-cc.sh [--dry-run] <modello> <cwd> <task-id>
# Il bridge costruisce un prompt minimo dal task id; non legge i documenti.

set -uo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; shift; fi

if [ "$#" -ne 3 ]; then
  printf 'uso: %s [--dry-run] <modello> <cwd> <task-id>\n' "$(basename "$0")" >&2
  exit 64
fi

MODEL="$1"; CWD="$2"; TASK_ID="$3"

case "$MODEL" in
  opus|sonnet|haiku) ;;
  *) printf 'modello CC non ammesso: %s (opus|sonnet|haiku)\n' "$MODEL" >&2; exit 65 ;;
esac

[ -d "$CWD" ] || { printf 'cwd inesistente: %s\n' "$CWD" >&2; exit 66; }
case "$TASK_ID" in
  ''|*[!A-Za-z0-9._-]*|.*|-*) printf 'task-id non valido: %s\n' "$TASK_ID" >&2; exit 65 ;;
esac
RUN="$CWD/.orchestratore/RUN.md"
if [ "$DRY_RUN" -eq 0 ] && [ ! -s "$RUN" ]; then
  printf 'RUN.md assente o vuoto: %s\n' "$RUN" >&2
  exit 66
fi

LOG_DIR="$CWD/.orchestratore/logs"
LOG="$LOG_DIR/$TASK_ID.log"
PROMPT_TEXT="Leggi SPEC.md, ROADMAP.md e .orchestratore/RUN.md. Esegui solo la sezione task $TASK_ID. Rispetta owner, perimetro e gate. Aggiorna la sezione task $TASK_ID con esito e checkpoint."

set -- claude -p --model "$MODEL" --permission-mode bypassPermissions \
  --output-format json --add-dir "$CWD"

if [ "$DRY_RUN" -eq 1 ]; then
  printf 'comando: %s\n' "$*"
  printf 'task: %s\n' "$TASK_ID"
  printf 'stdin: %s\n' "$PROMPT_TEXT"
  printf 'log: %s\n' "$LOG"
  exit 0
fi

command -v claude >/dev/null 2>&1 || { printf 'claude non installato\n' >&2; exit 69; }
mkdir -p "$LOG_DIR" || exit 73

{
  printf '=== %s | modello %s | cwd %s\n' "$(date -u +%FT%TZ)" "$MODEL" "$CWD"
} >> "$LOG"

( cd "$CWD" && printf '%s\n' "$PROMPT_TEXT" | "$@" ) 2>&1 | tee -a "$LOG"
STATUS="${PIPESTATUS[0]}"
printf '=== exit %s\n' "$STATUS" >> "$LOG"
exit "$STATUS"
