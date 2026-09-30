#!/usr/bin/env bash
# SessionStart: if this repository has an active orchestratore run, surface it.
# Silent otherwise. Reads only; never changes anything.
set -uo pipefail

ROOT="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null)" || exit 0
RUN="$ROOT/.orchestratore/RUN.md"
[ -f "$RUN" ] || exit 0

field() { sed -n "s/^$1: //p" "$RUN" | head -n 1; }
STATUS="$(field status)"
[ "$STATUS" = done ] && exit 0

printf 'orchestratore run in this repository: status %s, updated %s\n' \
  "${STATUS:-unknown}" "$(field updated)"
GOAL="$(field goal)"
[ -n "$GOAL" ] && printf 'goal: %s\n' "$GOAL"
NEXT="$(field next)"
[ -n "$NEXT" ] && printf 'next: %s\n' "$NEXT"
CHECK="$(cd "$(dirname "$0")/.." && pwd)/bin/run-check.py"
if command -v python3 >/dev/null 2>&1 && [ -f "$CHECK" ]; then
  PROBLEMS="$(python3 "$CHECK" --run "$RUN" 2>/dev/null | python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for p in d.get("problems", [])[:3]:
    print("RUN.md check: " + p)' 2>/dev/null)"
  [ -n "$PROBLEMS" ] && printf '%s\n' "$PROBLEMS"
fi
if [ -f "$ROOT/.orchestratore/coordinator.lock/owner" ]; then
  printf 'coordinator lock: %s (another coordinator may be running; check before starting)\n' \
    "$(tr '\n' ' ' < "$ROOT/.orchestratore/coordinator.lock/owner")"
fi
printf 'To continue: /orchestratore:orchestra resume\n'
exit 0
