#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/orchestratore-regression.XXXXXX")"

cleanup() {
  rm -rf -- "$TMP"
}
trap cleanup EXIT

failures=0

mutate_copy() {
  local mutation="$1"
  local copy="$TMP/$mutation"
  cp -R "$ROOT" "$copy"
  copy="$(CDPATH= cd -- "$copy" && pwd -P)"
  sed -i.bak "s|$ROOT|$copy|g" "$copy/skills/orchestratore/references/codex-skills-catalog.jsonl"
  rm -f "$copy/skills/orchestratore/references/codex-skills-catalog.jsonl.bak"
  printf '%s\n' "$copy"
}

expect_rejected() {
  local mutation="$1"
  local copy
  copy="$(mutate_copy "$mutation")"
  shift
  "$@" "$copy"

  if bash "$copy/tests/check-regressions.sh" >/dev/null 2>&1; then
    printf 'MUTATION SURVIVED: %s\n' "$mutation"
    failures=$((failures + 1))
  else
    printf 'MUTATION KILLED: %s\n' "$mutation"
  fi
}

remove_peso_precedente() {
  local copy="$1"
  sed -i.bak '/^# Peso salvato/,$d' "$copy/templates/state.toml"
  rm -f "$copy/templates/state.toml.bak"
}

remove_one_time_save() {
  local copy="$1"
  perl -0pi -e 's/1\. Se la modalità era `normale`, salva il peso corrente in `credito\.peso_precedente`; non\n   sovrascriverlo durante ulteriori cambi di credito\./1. Aggiorna la modalità credito./' "$copy/skills/orchestratore/SKILL.md"
}

remove_credit_transitions() {
  local copy="$1"
  perl -0pi -e 's/Marca runtime, timestamp, motivo e\n   modalità: `solo-cx` se è esaurito CC, `solo-cc` se è esaurito cx, `fermo` se lo sono entrambi\./Marca runtime, timestamp e motivo./' "$copy/skills/orchestratore/SKILL.md"
}

negate_handoff() {
  local copy="$1"
  perl -0pi -e 's/Se è esaurito il runtime del cervello e l\x27altro è disponibile, scrivi l\x27handoff esplicito\n   all\x27altro runtime dopo aver completato solo il proprio checkpoint atomico, aggiornato\n   `run\.md` e lo stato credito e rilasciato `brain\.lock`; quindi fermati\./Se il cervello è esaurito, non scrivere handoff né rilasciare brain.lock, e non fermarti./' "$copy/skills/orchestratore/SKILL.md"
}

remove_restore_guard() {
  local copy="$1"
  perl -0pi -e 's/quando entrambi sono `ok`, ripristina\n+il peso salvato, torna a `normale` e conserva quel peso come traccia dell\x27ultimo failover\./ripristina il peso salvato e torna a normale./' "$copy/skills/orchestratore/SKILL.md"
}

expect_rejected "missing peso_precedente schema" remove_peso_precedente
expect_rejected "missing one-time peso save" remove_one_time_save
expect_rejected "missing explicit credit transitions" remove_credit_transitions
expect_rejected "negated handoff and lock release" negate_handoff
expect_rejected "restore weight without both runtimes ok" remove_restore_guard

if (( failures > 0 )); then
  printf 'RED: %d mutazioni sono sopravvissute\n' "$failures"
  exit 1
fi

printf 'GREEN: tutte le mutazioni sono respinte\n'
