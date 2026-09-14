#!/usr/bin/env bash
# Bridge dell'orchestratore: lancia un worker Codex non interattivo.
# Uso: bin/spawn-cx.sh [--dry-run] <modello> <effort> <cwd> <prompt-file>
# Il bridge non decide niente: modello, effort e prompt li sceglie il cervello.
# --yolo e' l'alias di --dangerously-bypass-approvals-and-sandbox.

set -uo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; shift; fi

if [ "$#" -ne 4 ]; then
  printf 'uso: %s [--dry-run] <modello> <effort> <cwd> <prompt-file>\n' "$(basename "$0")" >&2
  exit 64
fi

MODEL="$1"; EFFORT="$2"; CWD="$3"; PROMPT="$4"

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
[ -s "$PROMPT" ] || { printf 'prompt assente o vuoto: %s\n' "$PROMPT" >&2; exit 66; }

TASK_ID="$(basename "$PROMPT")"; TASK_ID="${TASK_ID%.*}"
LOG_DIR="$CWD/.orchestratore/logs"
LOG="$LOG_DIR/$TASK_ID.log"

set -- codex exec --yolo -m "$MODEL" -c "model_reasoning_effort=$EFFORT" -C "$CWD" -

if [ "$DRY_RUN" -eq 1 ]; then
  printf 'comando: %s\n' "$*"
  printf 'stdin: %s\n' "$PROMPT"
  printf 'log: %s\n' "$LOG"
  exit 0
fi

command -v codex >/dev/null 2>&1 || { printf 'codex non installato\n' >&2; exit 69; }
mkdir -p "$LOG_DIR" || exit 73

{
  printf '=== %s | modello %s | effort %s | cwd %s\n' "$(date -u +%FT%TZ)" "$MODEL" "$EFFORT" "$CWD"
} >> "$LOG"

"$@" < "$PROMPT" 2>&1 | tee -a "$LOG"
STATUS="${PIPESTATUS[0]}"
printf '=== exit %s\n' "$STATUS" >> "$LOG"
exit "$STATUS"
