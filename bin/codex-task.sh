#!/usr/bin/env bash
# Run one Orchestratore brief through Codex inside an isolated git worktree.
#
# Usage:
#   bash codex-task.sh [--dry-run] [--model M] [--effort E] [--sandbox S] <build|verify> <worktree> <brief.md>
#
#   build   Codex edits the worktree; the script then commits every change on the
#           worktree's branch and prints `hash=<sha>`. The coordinator verifies that hash.
#   verify  Codex reviews and runs checks; it must not change tracked files or HEAD.
#           A change is reported as a violation (exit 3).
#
# Defaults: sandbox workspace-write, Codex's own configured model and effort.
# Output: `<id> hash=`, `<id> log=` and `<id> last=` lines on stdout (safe to run many in
# parallel with xargs -P); the full transcript is in the log
# next to the brief (<brief-dir>/<id>.<mode>.log), the final message in <id>.<mode>.last.md.
# Exit: Codex's exit code, 3 on a verify violation, 64 on bad usage.
set -uo pipefail

usage() { echo "usage: codex-task.sh [--dry-run] [--model M] [--effort E] [--sandbox S] <build|verify> <worktree> <brief.md>" >&2; exit 64; }

DRY_RUN=0 MODEL="" EFFORT="" SANDBOX="workspace-write"
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --model) MODEL="${2:-}"; shift ;;
    --effort) EFFORT="${2:-}"; shift ;;
    --sandbox) SANDBOX="${2:-}"; shift ;;
    --) shift; break ;;
    -*) usage ;;
    *) break ;;
  esac
  shift
done
[ $# -eq 3 ] || usage
MODE="$1" WORKTREE="$2" BRIEF="$3"
case "$MODE" in build|verify) ;; *) usage ;; esac
case "$SANDBOX" in read-only|workspace-write|danger-full-access) ;; *) usage ;; esac
[ -f "$BRIEF" ] || { echo "brief not found: $BRIEF" >&2; exit 64; }
git -C "$WORKTREE" rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "not a git worktree: $WORKTREE" >&2; exit 64; }
WORKTREE="$(git -C "$WORKTREE" rev-parse --show-toplevel)"

ID="$(basename "$BRIEF" .md)"
LOG="$(dirname "$BRIEF")/$ID.$MODE.log"
LAST="$(dirname "$BRIEF")/$ID.$MODE.last.md"

set -- codex exec -C "$WORKTREE" -o "$LAST"
if [ "$SANDBOX" = danger-full-access ]; then
  set -- "$@" --dangerously-bypass-approvals-and-sandbox
else
  set -- "$@" --sandbox "$SANDBOX"
fi
[ -n "$MODEL" ] && set -- "$@" -m "$MODEL"
[ -n "$EFFORT" ] && set -- "$@" -c "model_reasoning_effort=$EFFORT"
set -- "$@" -

if [ "$DRY_RUN" -eq 1 ]; then
  printf '%q ' "$@"; printf '< %q\n' "$BRIEF"
  exit 0
fi
command -v codex >/dev/null 2>&1 || { echo "codex is not installed" >&2; exit 69; }

HEAD_BEFORE="$(git -C "$WORKTREE" rev-parse HEAD)"
printf '=== %s %s %s\n' "$(date -u +%FT%TZ)" "$MODE" "$*" >> "$LOG"
"$@" < "$BRIEF" >> "$LOG" 2>&1
STATUS=$?
printf '=== exit %s\n' "$STATUS" >> "$LOG"
echo "$ID log=$LOG"
echo "$ID last=$LAST"
[ "$STATUS" -eq 0 ] || { echo "codex exited $STATUS; nothing committed" >&2; exit "$STATUS"; }

if [ "$MODE" = verify ]; then
  if [ "$(git -C "$WORKTREE" rev-parse HEAD)" != "$HEAD_BEFORE" ] || ! git -C "$WORKTREE" diff --quiet HEAD; then
    echo "$ID violation: verify changed HEAD or tracked files in $WORKTREE"
    exit 3
  fi
  echo "$ID hash=$HEAD_BEFORE"
  exit 0
fi

if [ -z "$(git -C "$WORKTREE" status --porcelain)" ]; then
  echo "$ID no changes to commit"
else
  git -C "$WORKTREE" add -A && git -C "$WORKTREE" commit -q -m "orchestratore: $ID" || { echo "commit failed in $WORKTREE" >&2; exit 1; }
fi
echo "$ID hash=$(git -C "$WORKTREE" rev-parse HEAD)"
