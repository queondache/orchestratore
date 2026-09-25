#!/usr/bin/env bash
# Bridge Codex: controller root separato dal worktree isolato del task.
# Uso: spawn-cx.sh [--dry-run] <modello> <effort> <project-root> <task-id> <stage> <task-cwd> <allowlist-json>
set -uo pipefail
QUI="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=bridge-common.sh
. "$QUI/bridge-common.sh"

DRY_RUN=0
if [ "${1:-}" = --dry-run ]; then DRY_RUN=1; shift; fi
[ "$#" -eq 7 ] || bridge_fail "uso: $(basename "$0") [--dry-run] <modello> <effort> <project-root> <task-id> <stage> <task-cwd> <allowlist-json>" 64
MODEL="$1"; EFFORT="$2"; PROJECT_ROOT="$3"; TASK_ID="$4"; STAGE="$5"; TASK_CWD="$6"; ALLOWLIST_JSON="$7"
case "$MODEL" in gpt-6-astra|gpt-5.6-sol|gpt-5.6-terra|gpt-5.6-luna) ;; *) bridge_fail "modello cx non ammesso: $MODEL" 65 ;; esac
case "$MODEL:$EFFORT" in
  gpt-5.6-luna:medium|gpt-5.6-luna:high|gpt-5.6-terra:medium|gpt-5.6-terra:high|gpt-5.6-sol:low|gpt-5.6-sol:medium|gpt-5.6-sol:high|gpt-6-astra:low|gpt-6-astra:medium|gpt-6-astra:high) ;;
  *) bridge_fail "combinazione modello/effort non ammessa: $MODEL $EFFORT" 65 ;;
esac

bridge_prepare
bridge_prompt
set -- codex exec --yolo --dangerously-bypass-hook-trust -m "$MODEL" -c "model_reasoning_effort=$EFFORT" -C "$TASK_CWD" -
if [ "$DRY_RUN" -eq 1 ]; then
  printf 'comando:'; printf ' %q' "$@"; printf '\n'
  printf 'task: %s\nstage: %s\nstdin: %s\nlog: %s\n' "$TASK_ID" "$STAGE" "$PROMPT_TEXT" "$LOG"
  exit 0
fi

command -v codex >/dev/null 2>&1 || bridge_fail 'codex non installato' 69
bridge_require_codex_guard
mkdir -p "$LOG_DIR" || exit 73
bridge_snapshot
export ORCHESTRATORE_PROJECT_ROOT="$PROJECT_ROOT"
export ORCHESTRATORE_TASK_CWD="$TASK_CWD" ORCHESTRATORE_STAGE="$STAGE" ORCHESTRATORE_ALLOWLIST_JSON="$ALLOWLIST_JSON"
printf '=== %s | modello %s | effort %s | stage %s | cwd %s\n' "$(date -u +%FT%TZ)" "$MODEL" "$EFFORT" "$STAGE" "$TASK_CWD" >> "$LOG"
printf '%s\n' "$PROMPT_TEXT" | "$@" 2>&1 | tee -a "$LOG"
STATUS="${PIPESTATUS[1]}"
bridge_validate_post
printf '=== exit %s\n' "$STATUS" >> "$LOG"
exit "$STATUS"
