#!/usr/bin/env bash
# Bridge Claude Code: controller root separato dal worktree isolato del task.
# Uso: spawn-cc.sh [--dry-run] <modello> <effort> <project-root> <task-id> <stage> <task-cwd> <allowlist-json>
set -uo pipefail
QUI="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=bridge-common.sh
. "$QUI/bridge-common.sh"

DRY_RUN=0
if [ "${1:-}" = --dry-run ]; then DRY_RUN=1; shift; fi
[ "$#" -eq 7 ] || bridge_fail "uso: $(basename "$0") [--dry-run] <modello> <effort> <project-root> <task-id> <stage> <task-cwd> <allowlist-json>" 64
MODEL="$1"; EFFORT="$2"; PROJECT_ROOT="$3"; TASK_ID="$4"; STAGE="$5"; TASK_CWD="$6"; ALLOWLIST_JSON="$7"
case "$MODEL" in opus|sonnet|haiku) ;; *) bridge_fail "modello CC non ammesso: $MODEL (opus|sonnet|haiku)" 65 ;; esac
case "$EFFORT" in medium) ;; *) bridge_fail "effort CC non ammesso: $EFFORT (solo medium nel routing corrente)" 65 ;; esac

bridge_prepare
bridge_prompt
set -- claude -p --model "$MODEL" --effort "$EFFORT" --permission-mode bypassPermissions --output-format json --add-dir "$PROJECT_ROOT"
if [ "$STAGE" != build ]; then set -- "$@" --disallowed-tools Edit Write; fi
if [ "$DRY_RUN" -eq 1 ]; then
  printf 'comando:'; printf ' %q' "$@"; printf '\n'
  printf 'task: %s\nstage: %s\nstdin: %s\nlog: %s\n' "$TASK_ID" "$STAGE" "$PROMPT_TEXT" "$LOG"
  exit 0
fi

command -v claude >/dev/null 2>&1 || bridge_fail 'claude non installato' 69
command -v python3 >/dev/null 2>&1 || bridge_fail 'python3 necessario per verificare il guard Claude' 69
bridge_require_claude_guard
mkdir -p "$LOG_DIR" || exit 73
bridge_snapshot
export ORCHESTRATORE_PROJECT_ROOT="$PROJECT_ROOT"
export ORCHESTRATORE_TASK_CWD="$TASK_CWD" ORCHESTRATORE_STAGE="$STAGE" ORCHESTRATORE_ALLOWLIST_JSON="$ALLOWLIST_JSON"
printf '=== %s | modello %s | effort %s | stage %s | cwd %s\n' "$(date -u +%FT%TZ)" "$MODEL" "$EFFORT" "$STAGE" "$TASK_CWD" >> "$LOG"
(cd "$TASK_CWD" && printf '%s\n' "$PROMPT_TEXT" | "$@") 2>&1 | tee -a "$LOG"
STATUS="${PIPESTATUS[0]}"
bridge_validate_post
printf '=== exit %s\n' "$STATUS" >> "$LOG"
exit "$STATUS"
