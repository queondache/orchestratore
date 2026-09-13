#!/usr/bin/env bash
# Bridge dell'orchestratore: lancia un worker Claude Code non interattivo.
# Uso: bin/spawn-cc.sh [--dry-run] <modello> <cwd> <prompt-file>
# Il bridge non decide niente: modello e prompt li sceglie il cervello.

set -uo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; shift; fi

if [ "$#" -ne 3 ]; then
  printf 'uso: %s [--dry-run] <modello> <cwd> <prompt-file>\n' "$(basename "$0")" >&2
  exit 64
fi

MODEL="$1"; CWD="$2"; PROMPT="$3"

case "$MODEL" in
  opus|sonnet|haiku) ;;
  *) printf 'modello CC non ammesso: %s (opus|sonnet|haiku)\n' "$MODEL" >&2; exit 65 ;;
esac

[ -d "$CWD" ] || { printf 'cwd inesistente: %s\n' "$CWD" >&2; exit 66; }
[ -s "$PROMPT" ] || { printf 'prompt assente o vuoto: %s\n' "$PROMPT" >&2; exit 66; }

TASK_ID="$(basename "$PROMPT")"; TASK_ID="${TASK_ID%.*}"
LOG_DIR="$CWD/.orchestratore/logs"
LOG="$LOG_DIR/$TASK_ID.log"

set -- claude -p --model "$MODEL" --permission-mode bypassPermissions \
  --output-format json --add-dir "$CWD"

if [ "$DRY_RUN" -eq 1 ]; then
  printf 'comando: %s\n' "$*"
  printf 'stdin: %s\n' "$PROMPT"
  printf 'log: %s\n' "$LOG"
  exit 0
fi

command -v claude >/dev/null 2>&1 || { printf 'claude non installato\n' >&2; exit 69; }
mkdir -p "$LOG_DIR" || exit 73

{
  printf '=== %s | modello %s | cwd %s\n' "$(date -u +%FT%TZ)" "$MODEL" "$CWD"
} >> "$LOG"

( cd "$CWD" && "$@" < "$PROMPT" ) 2>&1 | tee -a "$LOG"
STATUS="${PIPESTATUS[0]}"
printf '=== exit %s\n' "$STATUS" >> "$LOG"
exit "$STATUS"
