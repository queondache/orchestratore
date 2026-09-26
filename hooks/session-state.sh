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
NEXT="$(field next)"
[ -n "$NEXT" ] && printf 'next: %s\n' "$NEXT"
if [ -f "$ROOT/.orchestratore/coordinator.lock/owner" ]; then
  printf 'coordinator lock: %s (another coordinator may be running; check before starting)\n' \
    "$(tr '\n' ' ' < "$ROOT/.orchestratore/coordinator.lock/owner")"
fi
printf 'To continue: /orchestratore:orchestra resume\n'
exit 0
