#!/usr/bin/env bash
# SessionStart dell'orchestratore: se il progetto ha un run, mettilo in contesto.
# Silenzioso in ogni altro caso. Non modifica niente.
set -uo pipefail

RUN=".orchestratore/RUN.md"
[ -f "$RUN" ] || exit 0

STATO="$(sed -n 's/^stato: //p' "$RUN" | head -n 1)"
CERVELLO="$(sed -n 's/^cervello: //p' "$RUN" | head -n 1)"
AGG="$(sed -n 's/^ultimo aggiornamento: //p' "$RUN" | head -n 1)"
PROSSIMA="$(sed -n 's/^Prossima azione (una sola): //p' "$RUN" | head -n 1)"

printf 'Run orchestratore presente in questo progetto.\n'
printf 'stato: %s | cervello: %s | ultimo aggiornamento: %s\n' \
  "${STATO:-ignoto}" "${CERVELLO:-ignoto}" "${AGG:-ignoto}"
[ -n "$PROSSIMA" ] && printf 'prossima azione registrata: %s\n' "$PROSSIMA"

if [ -f ".orchestratore/brain.lock" ]; then
  printf 'brain.lock: %s\n' "$(cat .orchestratore/brain.lock)"
  printf 'Un altro cervello potrebbe essere vivo: verifica prima di avviare un run.\n'
fi
printf 'Per riprendere: /orchestratore:orchestra riprendi\n'
exit 0
