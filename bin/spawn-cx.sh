#!/usr/bin/env bash
# Bridge dell'orchestratore: lancia un worker Codex non interattivo.
# Uso: bin/spawn-cx.sh [--dry-run] <modello> <effort> <cwd> <task-id>
# Il bridge costruisce un prompt minimo dal task id; non legge i documenti.
# --yolo e' l'alias di --dangerously-bypass-approvals-and-sandbox.

set -uo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; shift; fi

if [ "$#" -ne 4 ]; then
  printf 'uso: %s [--dry-run] <modello> <effort> <cwd> <task-id>\n' "$(basename "$0")" >&2
  exit 64
fi

MODEL="$1"; EFFORT="$2"; CWD="$3"; TASK_ID="$4"

case "$MODEL" in
  gpt-6-astra|gpt-5.6-sol|gpt-5.6-terra|gpt-5.6-luna) ;;
  *) printf 'modello cx non ammesso: %s\n' "$MODEL" >&2; exit 65 ;;
esac

case "$MODEL:$EFFORT" in
  gpt-5.6-luna:medium|gpt-5.6-luna:high|gpt-5.6-terra:medium|gpt-5.6-terra:high) ;;
  gpt-5.6-sol:low|gpt-5.6-sol:medium|gpt-5.6-sol:high) ;;
  gpt-6-astra:low|gpt-6-astra:medium|gpt-6-astra:high) ;;
  *) printf 'combinazione modello/effort non ammessa: %s %s\n' "$MODEL" "$EFFORT" >&2; exit 65 ;;
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

set -- codex exec --yolo -m "$MODEL" -c "model_reasoning_effort=$EFFORT" -C "$CWD" -

if [ "$DRY_RUN" -eq 1 ]; then
  printf 'comando: %s\n' "$*"
  printf 'task: %s\n' "$TASK_ID"
  printf 'stdin: %s\n' "$PROMPT_TEXT"
  printf 'log: %s\n' "$LOG"
  exit 0
fi

command -v codex >/dev/null 2>&1 || { printf 'codex non installato\n' >&2; exit 69; }
mkdir -p "$LOG_DIR" || exit 73

{
  printf '=== %s | modello %s | effort %s | cwd %s\n' "$(date -u +%FT%TZ)" "$MODEL" "$EFFORT" "$CWD"
} >> "$LOG"

printf '%s\n' "$PROMPT_TEXT" | "$@" 2>&1 | tee -a "$LOG"
STATUS="${PIPESTATUS[1]}"
printf '=== exit %s\n' "$STATUS" >> "$LOG"
exit "$STATUS"
