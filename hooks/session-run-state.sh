#!/usr/bin/env bash
# SessionStart dell'orchestratore: se il progetto ha un run, mettilo in contesto.
# Silenzioso in ogni altro caso. Non modifica niente.
set -uo pipefail

ROOT="${ORCHESTRATORE_PROJECT_ROOT:-}"
if [ -n "$ROOT" ]; then
  ROOT="$(CDPATH= cd -- "$ROOT" 2>/dev/null && pwd -P)" || exit 0
else
  ROOT="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -z "$ROOT" ]; then
    ROOT="$(pwd -P)"
    while [ "$ROOT" != / ] && [ ! -f "$ROOT/.orchestratore/RUN.md" ]; do ROOT="${ROOT%/*}"; [ -n "$ROOT" ] || ROOT=/; done
  fi
fi
RUN="$ROOT/.orchestratore/RUN.md"
[ -f "$RUN" ] || exit 0

STATO="$(sed -n 's/^stato: //p' "$RUN" | head -n 1)"
CERVELLO="$(sed -n 's/^cervello: //p' "$RUN" | head -n 1)"
AGG="$(sed -n 's/^ultimo aggiornamento: //p' "$RUN" | head -n 1)"
PROSSIMA="$(sed -n 's/^Prossima azione (una sola): //p' "$RUN" | head -n 1)"

printf 'Run orchestratore presente in questo progetto.\n'
printf 'stato: %s | cervello: %s | ultimo aggiornamento: %s\n' \
  "${STATO:-ignoto}" "${CERVELLO:-ignoto}" "${AGG:-ignoto}"
[ -n "$PROSSIMA" ] && printf 'prossima azione registrata: %s\n' "$PROSSIMA"

if [ -f "$ROOT/.orchestratore/brain.lock" ]; then
  printf 'brain.lock: %s\n' "$(cat "$ROOT/.orchestratore/brain.lock")"
  printf 'Un altro cervello potrebbe essere vivo: verifica prima di avviare un run.\n'
fi
printf 'Per riprendere: /orchestratore:orchestra riprendi\n'
exit 0
