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

downgrade_y2_version() {
  local copy="$1"
  sed -i.bak 's/"0\.1\.3"/"0.1.1"/g' "$copy/.claude-plugin/plugin.json"
  rm -f "$copy/.claude-plugin/plugin.json.bak"
}

remove_yolo_permission() {
  local copy="$1"
  perl -0pi -e 's/codex exec --yolo/codex exec -s workspace-write/' "$copy/skills/orchestratore/references/adapter-cc.md"
}

remove_required_ci_gate() {
  local copy="$1"
  perl -0pi -e 's/required CI check/CI check/g' "$copy/skills/orchestratore/references/lane.md"
}

restore_manual_merge_wait() {
  local copy="$1"
  perl -0pi -e 's/Auto-merge consentito solo se:/Attendi la parola `merge` di Andrea; poi:/' "$copy/skills/orchestratore/references/lane.md"
}

remove_native_yolo_profile() {
  local copy="$1"
  perl -0pi -e 's/effective approval_policy=never \+ sandbox_mode=danger-full-access/profilo standard/' "$copy/skills/orchestratore/references/adapter-cx.md"
}

weaken_spending_ban() {
  local copy="$1"
  perl -0pi -e 's/acquisti, upgrade e aumenti di budget, spend limit o credito restano vietati/acquisti, upgrade e aumenti di spesa vanno valutati/' "$copy/skills/orchestratore/references/project-adapter.md"
}

allow_cancelled_ci() {
  local copy="$1"
  perl -0pi -e 's/assenti, pending, falliti o cancellati/assenti, pending, falliti o success/' "$copy/skills/orchestratore/references/lane.md"
}

remove_mouse_ban() {
  local copy="$1"
  perl -0pi -e 's/ Il mouse è sempre vietato\.//' "$copy/skills/orchestratore/SKILL.md"
}

remove_production_data_bans() {
  local copy="$1"
  perl -0pi -e 's/, modifiche distruttive o\n  massive ai dati di produzione//' "$copy/skills/orchestratore/SKILL.md"
  perl -0pi -e 's/modifiche distruttive o massive ai dati di\nproduzione, //' "$copy/skills/orchestratore/references/project-adapter.md"
}

restore_skill_consent_request() {
  local copy="$1"
  perl -0pi -e 's/Usa liberamente/Chiedi ad Andrea prima della skill; usa liberamente/' "$copy/skills/orchestratore/SKILL.md"
}

weaken_skill_freedom() {
  local copy="$1"
  perl -0pi -e 's/liberamente senza\s+chiedere Andrea tutte le skill già installate e disponibili utili al task/solo dopo consenso di Andrea/' "$copy/skills/orchestratore/SKILL.md"
}

allow_skill_installation() {
  local copy="$1"
  perl -0pi -e 's/non\s+autorizza installare skill nuove, abilitare o modificare globalmente skill o plugin/autorizza installare e abilitare nuove skill e plugin/' "$copy/skills/orchestratore/SKILL.md"
}

expand_skill_tool_permissions() {
  local copy="$1"
  perl -0pi -e 's/tool o app\s+invocati dalla skill conservano tutti i guardrail 0\.1\.2/le skill ampliano i permessi di tool e app/' "$copy/skills/orchestratore/SKILL.md"
}

restore_cc_skill_consent_request() {
  local copy="$1"
  perl -0pi -e 's/Usa skill/Chiedi Andrea prima della skill; usa skill/' "$copy/skills/orchestratore/references/adapter-cc.md"
}

remove_skill_map_fallback() {
  local copy="$1"
  perl -0pi -e 's/skill equivalente già installata o procedura base/ferma la lane/' "$copy/skills/orchestratore/references/skill-map.md"
}

allow_cc_global_skill_changes() {
  local copy="$1"
  perl -0pi -e 's/Mai installare, abilitare\s+o modificare globalmente skill o plugin/Puoi installare e abilitare globalmente skill o plugin/' "$copy/skills/orchestratore/references/adapter-cc.md"
}

add_cc_always_ask_skill_consent() {
  local copy="$1"
  perl -0pi -e 's/(## Worker CC nativi)/$1\n\nfermati e chiedi sempre il consenso di Andrea/' "$copy/skills/orchestratore/references/adapter-cc.md"
}

add_cc_allow_global_skill_changes() {
  local copy="$1"
  perl -0pi -e 's/(## Worker CC nativi)/$1\n\npuoi installare e abilitare globalmente skill\/plugin/' "$copy/skills/orchestratore/references/adapter-cc.md"
}

expect_rejected "missing peso_precedente schema" remove_peso_precedente
expect_rejected "missing one-time peso save" remove_one_time_save
expect_rejected "missing explicit credit transitions" remove_credit_transitions
expect_rejected "negated handoff and lock release" negate_handoff
expect_rejected "restore weight without both runtimes ok" remove_restore_guard
expect_rejected "Y2 manifest version downgraded" downgrade_y2_version
expect_rejected "Y2 Codex yolo permission removed" remove_yolo_permission
expect_rejected "Y2 required CI gate weakened" remove_required_ci_gate
expect_rejected "Y2 manual merge wait restored" restore_manual_merge_wait
expect_rejected "Y2 native Codex YOLO profile removed" remove_native_yolo_profile
expect_rejected "Y2 spending ban weakened" weaken_spending_ban
expect_rejected "Y4 cancelled CI check allowed" allow_cancelled_ci
expect_rejected "Y4 mouse ban removed" remove_mouse_ban
expect_rejected "Y4 production data bans removed" remove_production_data_bans
expect_rejected "S2 skill consent request restored" restore_skill_consent_request
expect_rejected "S2 skill freedom weakened" weaken_skill_freedom
expect_rejected "S2 skill installation allowed" allow_skill_installation
expect_rejected "S2 skill tool permissions expanded" expand_skill_tool_permissions
expect_rejected "S4 CC skill consent restored" restore_cc_skill_consent_request
expect_rejected "S4 skill-map fallback removed" remove_skill_map_fallback
expect_rejected "S4 CC global skill changes allowed" allow_cc_global_skill_changes
expect_rejected "S4 CC additive always asks skill consent" add_cc_always_ask_skill_consent
expect_rejected "S4 CC additive global skill changes allowed" add_cc_allow_global_skill_changes

if (( failures > 0 )); then
  printf 'RED: %d mutazioni sono sopravvissute\n' "$failures"
  exit 1
fi

printf 'GREEN: tutte le mutazioni sono respinte\n'
