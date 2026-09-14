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
  local copy prima dopo
  copy="$(mutate_copy "$mutation")"
  shift
  prima="$(impronta "$copy")"
  "$@" "$copy"
  dopo="$(impronta "$copy")"

  if [ "$prima" = "$dopo" ]; then
    printf 'MUTATION VOID: %s (il pattern non ha trovato niente da cambiare)\n' "$mutation"
    failures=$((failures + 1))
    return
  fi

  # I gate eseguibili girano una volta sola nella suite normale: qui basta il testo,
  # e ogni mutazione di bridge o hook e comunque coperta da un invariante di testo.
  if ORCHESTRATORE_SKIP_EXEC=1 bash "$copy/tests/check-regressions.sh" >/dev/null 2>&1; then
    printf 'MUTATION SURVIVED: %s\n' "$mutation"
    failures=$((failures + 1))
  else
    printf 'MUTATION KILLED: %s\n' "$mutation"
  fi
}

# Le mutazioni sul comportamento della guardia non si vedono nel testo: vanno provate
# facendo girare il gate eseguibile degli hook sulla copia mutata. Un meccanismo che
# sopravvive qui e' un meccanismo che nessun test difende, cioe' un meccanismo finto.
# Impronta dei file del plugin, per accorgersi di una mutazione che non muta niente.
impronta() {
  find "$1" -type f -not -path '*/.git/*' -exec shasum {} + | shasum | cut -d' ' -f1
}

expect_rejected_exec() {
  local mutation="$1"
  local copy prima dopo
  copy="$(mutate_copy "$mutation")"
  shift
  prima="$(impronta "$copy")"
  "$@" "$copy"
  dopo="$(impronta "$copy")"
  if [ "$prima" = "$dopo" ]; then
    printf 'MUTATION VOID: %s (il pattern non ha trovato niente da cambiare)\n' "$mutation"
    failures=$((failures + 1))
    return
  fi

  if bash "$copy/tests/check-hooks.sh" >/dev/null 2>&1; then
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
  perl -0pi -e 's/1\. Se la modalità era `normale`, salva il peso corrente in `credito\.peso_precedente`; non\n   sovrascriverlo durante ulteriori cambi di credito\./1. Aggiorna la modalità credito./' "$copy/skills/orchestratore/references/credito.md"
}

remove_credit_transitions() {
  local copy="$1"
  perl -0pi -e 's/Marca runtime, timestamp, motivo e\n   modalità: `solo-cx` se è esaurito CC, `solo-cc` se è esaurito cx, `fermo` se lo sono entrambi\./Marca runtime, timestamp e motivo./' "$copy/skills/orchestratore/references/credito.md"
}

negate_handoff() {
  local copy="$1"
  perl -0pi -e 's/Se è esaurito il runtime del cervello e l\x27altro è disponibile, scrivi l\x27handoff esplicito\n   all\x27altro runtime dopo aver completato solo il proprio checkpoint atomico, aggiornato\n   `run\.md` e lo stato credito e rilasciato `brain\.lock`; quindi fermati\./Se il cervello è esaurito, non scrivere handoff né rilasciare brain.lock, e non fermarti./' "$copy/skills/orchestratore/references/credito.md"
}

remove_restore_guard() {
  local copy="$1"
  perl -0pi -e 's/quando entrambi sono `ok`, ripristina\n+il peso salvato, torna a `normale` e conserva quel peso come traccia dell\x27ultimo failover\./ripristina il peso salvato e torna a normale./' "$copy/skills/orchestratore/references/credito.md"
}

downgrade_y2_version() {
  local copy="$1"
  sed -i.bak 's/"0\.4\.1"/"0.4.0"/g' "$copy/.claude-plugin/plugin.json"
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
  perl -0pi -e 's/auto-merge consentito solo se:/Attendi la parola `merge` di Andrea; poi:/i' "$copy/skills/orchestratore/references/lane.md"
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

restore_default_question() {
  local copy="$1"
  perl -0pi -e 's/\*\*Default quando Andrea non dice altro\*\*/Chiedi ad Andrea autorizzazioni git e run non presidiato/' "$copy/skills/orchestratore/SKILL.md"
}

restore_skill_permission_question() {
  local copy="$1"
  perl -0pi -e 's/Mai di\nskill, tool, modelli, permessi, approccio tecnico o conferma di un default del contratto:/Chiedi anche di skill, tool e permessi:/' "$copy/skills/orchestratore/SKILL.md"
}

weaken_cost_floor() {
  local copy="$1"
  perl -0pi -e 's/`gpt-5\.6-luna`: solo task meccaniche e delimitate; `medium` o `high`, mai `low`/`gpt-5.6-luna`: task meccaniche; parte da `low`/' "$copy/skills/orchestratore/references/routing.md"
}

weaken_bridge_cost_floor() {
  local copy="$1"
  perl -0pi -e 's/gpt-5\.6-luna:medium\|gpt-5\.6-luna:high/gpt-5.6-luna:low|gpt-5.6-luna:medium|gpt-5.6-luna:high/' "$copy/bin/spawn-cx.sh"
}

allow_stop_on_red() {
  local copy="$1"
  perl -0pi -e 's/\*\*Il rosso non è mai una condizione di stop del run\.\*\*/Un gate rosso ferma il run./' "$copy/skills/orchestratore/SKILL.md"
}

remove_retry_budget() {
  local copy="$1"
  perl -0pi -e 's/Massimo \*\*due tentativi per approccio\*\*/Tentativi senza limite per approccio/' "$copy/skills/orchestratore/references/lane.md"
}

remove_per_delivery_verification() {
  local copy="$1"
  perl -0pi -e 's/\*\*Verifica obbligatoria a ogni consegna, non solo a fine milestone\.\*\*/La verifica avviene solo a fine milestone./' "$copy/skills/orchestratore/SKILL.md"
}

remove_local_suite_fallback() {
  local copy="$1"
  perl -0pi -e 's/\*\*fallback suite locale\*\*/nessun merge/' "$copy/skills/orchestratore/references/lane.md"
}

remove_green_gate_definition() {
  local copy="$1"
  perl -0pi -e 's/## Gate verde: definito una volta, scritto in `run\.md`/## Note/' "$copy/skills/orchestratore/references/lane.md"
}

remove_doc_alignment_on_close() {
  local copy="$1"
  perl -0pi -e 's/Merge fatto e doc non allineati = milestone \*\*non\*\* chiusa\./Il merge chiude la milestone./' "$copy/skills/orchestratore/references/lane.md"
}

stop_after_one_milestone() {
  local copy="$1"
  perl -0pi -e 's/apri subito la lane successiva/fermati e riporta ad Andrea/g' "$copy/skills/orchestratore/references/lane.md"
}

remove_answer_propagation() {
  local copy="$1"
  perl -0pi -e 's/\*\*Propagazione della risposta, automatica e nello stesso turno\.\*\*/Le risposte restano nel registro quesiti./' "$copy/skills/orchestratore/SKILL.md"
}

remove_parallel_plan() {
  local copy="$1"
  perl -0pi -e 's/## 1\. Piano di parallelizzazione, prima di qualsiasi delega/## 1. Note/' "$copy/skills/orchestratore/references/parallelismo.md"
}

remove_independence_proof() {
  local copy="$1"
  perl -0pi -e 's/comm -12/valuta a occhio/' "$copy/skills/orchestratore/references/parallelismo.md"
}

remove_contract_first() {
  local copy="$1"
  perl -0pi -e 's/lane \*\*contract-first\*\*, non parallelo/parallelo comunque/' "$copy/skills/orchestratore/SKILL.md"
}

allow_brain_to_code() {
  local copy="$1"
  perl -0pi -e 's/\*\*Il cervello non scrive codice\.\*\*/Il cervello integra i branch dei task./' "$copy/skills/orchestratore/references/parallelismo.md"
}

remove_verifier_steps() {
  local copy="$1"
  perl -0pi -e 's/## I quattro passi obbligatori/## Note/' "$copy/skills/orchestratore/references/verifica.md"
}

remove_oracle() {
  local copy="$1"
  perl -0pi -e 's/KO: oracolo assente/nota informativa/' "$copy/skills/orchestratore/references/verifica.md"
}

allow_tier3_automerge() {
  local copy="$1"
  perl -0pi -e 's/\*\*PR in attesa di Andrea\*\*/auto-merge/' "$copy/skills/orchestratore/references/verifica.md"
}

remove_sensitive_areas() {
  local copy="$1"
  perl -0pi -e 's/aree_sensibili/note/g' "$copy/skills/orchestratore/references/verifica.md"
}

remove_recon() {
  local copy="$1"
  perl -0pi -e 's/\.orchestratore\/recon\.md/appunti temporanei/g' "$copy/skills/orchestratore/references/project-adapter.md"
}

remove_metrics() {
  local copy="$1"
  perl -0pi -e 's/## Metriche/## Note finali/' "$copy/templates/run.md"
}

remove_ko_observer() {
  local copy="$1"
  perl -0pi -e 's/Nessun terzo approccio automatico\./Continua con altri approcci finche diventa verde./' "$copy/skills/orchestratore/references/lane.md"
}

remove_config_risk_areas() {
  local copy="$1"
  perl -0pi -e 's/\[rischio\]/[note]/' "$copy/templates/config.toml"
}

weaken_verifier_agent() {
  local copy="$1"
  perl -0pi -e 's/## I quattro passi, tutti obbligatori/## Suggerimenti/' "$copy/agents/verificatore.md"
}

allow_verifier_writes() {
  local copy="$1"
  perl -0pi -e 's/Non modifichi nessun file/Puoi correggere quello che trovi/' "$copy/agents/verificatore.md"
}

allow_premerge_promotion() {
  local copy="$1"
  perl -0pi -e 's/non promuovi mai una PR da `in attesa` ad `auto`/puoi promuovere una PR da in attesa ad auto/' "$copy/agents/pre-merge.md"
}

allow_integrator_to_implement() {
  local copy="$1"
  perl -0pi -e 's/\*\*Nessuna implementazione nuova\.\*\*/Puoi completare il codice mancante./' "$copy/agents/integratore.md"
}

allow_worker_delegation() {
  local copy="$1"
  perl -0pi -e 's/\*\*Non deleghi\.\*\*/Puoi lanciare altri agenti./' "$copy/agents/worker-impl.md"
}

weaken_bridge_sandbox() {
  local copy="$1"
  perl -0pi -e 's/codex exec --yolo/codex exec -s read-only/' "$copy/bin/spawn-cx.sh"
}

remove_bridge_model_validation() {
  local copy="$1"
  perl -0pi -e 's/gpt-6-astra\|gpt-5\.6-sol\|gpt-5\.6-terra\|gpt-5\.6-luna/*/' "$copy/bin/spawn-cx.sh"
}

remove_bridge_dry_run() {
  local copy="$1"
  perl -0pi -e 's/--dry-run/--prova/g' "$copy/bin/spawn-cx.sh"
}

disable_run_guard() {
  local copy="$1"
  perl -0pi -e 's/\[ -f "\$CWD\/\.orchestratore\/brain\.lock" \] \|\| exit 0/true/' "$copy/hooks/guard-run.sh"
}

remove_guard_hook_registration() {
  local copy="$1"
  perl -0pi -e 's/"PreToolUse"/"PreToolUseDisabilitato"/' "$copy/hooks/hooks.json"
}

make_status_command_writable() {
  local copy="$1"
  perl -0pi -e 's/Non aprire task, non delegare, non modificare file\./Puoi aggiornare run.md mentre leggi./' "$copy/commands/orchestra-status.md"
}

make_start_ask_defaults() {
  local copy="$1"
  perl -0pi -e 's/L\x27unica domanda ammessa all\x27avvio/Chiedi ad Andrea ogni default prima di partire; la domanda ammessa all\x27avvio/' "$copy/commands/orchestra.md"
}

guard_a_capo_non_separa() {
  local copy="$1"
  perl -0pi -e 's/  lex.whitespace = " .t.r"/  lex.whitespace = " \\t\\r\\n"/' "$copy/hooks/guard_run.py"
}

guard_continuazione_non_unita() {
  local copy="$1"
  perl -0pi -e 's/    return cmd\.replace/    return cmd\n    return cmd.replace/' "$copy/hooks/guard_run.py"
}

guard_commenti_non_tolti() {
  local copy="$1"
  perl -0pi -e 's/    return "[^"]*"\.join\(taglia_commento[^\n]*/    return cmd/' "$copy/hooks/guard_run.py"
}

guard_opzioni_non_per_programma() {
  local copy="$1"
  perl -0pi -e 's/OPZIONI_CON_VALORE\.get\(corrente, \(\)\)/OPZIONI_CON_VALORE.get("nice", ())/' "$copy/hooks/guard_run.py"
}

guard_posizionali_non_saltati() {
  local copy="$1"
  perl -0pi -e 's/        if posizionali > 0:/        if False:/' "$copy/hooks/guard_run.py"
}

guard_clean_solo_con_d() {
  local copy="$1"
  perl -0pi -e 's/        if any\(a\.startswith\("--for"\) or flag_corto_con\(a, "f"\) for a in args\):/        if any(a == "--directories" for a in args):/' "$copy/hooks/guard_run.py"
}

guard_sostituzione_quotata_ignorata() {
  local copy="$1"
  perl -0pi -e 's/            analizza_comando\(interno, profondita \+ 1\)/            pass/' "$copy/hooks/guard_run.py"
}

guard_redirezioni_non_tolte() {
  local copy="$1"
  perl -0pi -e 's/    puliti = \[\]/    return token\n    puliti = []/' "$copy/hooks/guard_run.py"
}

guard_bundle_shell_ignorato() {
  local copy="$1"
  perl -0pi -e 's/        ultima = t\[-1\] if len\(t\) > 1 and not t\.startswith\("--"\) else ""/        ultima = ""/' "$copy/hooks/guard_run.py"
}

guard_abbreviazioni_push_esatte() {
  local copy="$1"
  perl -0pi -e 's/            if a\.startswith\("--for"\) or a\.startswith\("--mi"\):/            if a == "--force" or a == "--mirror":/' "$copy/hooks/guard_run.py"
}

guard_abbreviazione_clean_esatta() {
  local copy="$1"
  perl -0pi -e 's/        if any\(a\.startswith\("--for"\) or flag_corto_con\(a, "f"\) for a in args\):/        if any(a == "--force" for a in args):/' "$copy/hooks/guard_run.py"
}

guard_admin_senza_valore() {
  local copy="$1"
  perl -0pi -e 's/        if a\.split\("=", 1\)\[0\] == "--admin":/        if a == "--admin":/' "$copy/hooks/guard_run.py"
}

guard_apici_singoli_non_rispettati() {
  local copy="$1"
  perl -0pi -e 's/if apice == "\x27":/if False:/' "$copy/hooks/guard_run.py"
}

guard_continuazione_con_spazio() {
  local copy="$1"
  perl -0pi -e 's/    return cmd\.replace\("[^"]*n", ""\)/    return cmd.replace("\\\\\\n", " ")/' "$copy/hooks/guard_run.py"
}

guard_herestring_come_heredoc() {
  local copy="$1"
  perl -0pi -e 's/\(\?<!<\)<<-\?\(\?!<\)/<<-?/' "$copy/hooks/guard_run.py"
}

guard_commenters_di_shlex() {
  local copy="$1"
  perl -0pi -e 's/        lex\.commenters = ""/        pass/' "$copy/hooks/guard_run.py"
}

guard_heredoc_non_piu_dato() {
  local copy="$1"
  perl -0pi -e 's/    righe = cmd\.split/    return cmd\n    righe = cmd.split/' "$copy/hooks/guard_run.py"
}

guard_wrapper_non_saltati() {
  local copy="$1"
  perl -0pi -e 's/"xargs", "exec", "builtin", "stdbuf", "setsid",/"builtin",/' "$copy/hooks/guard_run.py"
}

guard_flag_lungo_esatto() {
  local copy="$1"
  perl -0pi -e 's/a\.startswith\("--for"\)/a == "--force"/' "$copy/hooks/guard_run.py"
}

guard_flag_corto_esatto() {
  local copy="$1"
  perl -0pi -e 's/return tok\.startswith\("-"\) and not tok\.startswith\("--"\) and lettera in tok\[1:\]/return tok == "-" + lettera/' "$copy/hooks/guard_run.py"
}

guard_quote_non_rispettate() {
  local copy="$1"
  perl -0pi -e 's/        lex = shlex\.shlex\([^\n]*\)/        return cmd.split()/' "$copy/hooks/guard_run.py"
}

guard_comando_annidato_ignorato() {
  local copy="$1"
  perl -0pi -e 's/            analizza_comando\(valore, profondita \+ 1\)/            pass/' "$copy/hooks/guard_run.py"
}

guard_reset_esatto() {
  local copy="$1"
  perl -0pi -e 's/a\.startswith\("--h"\) and a != "--help"/a == "--hard"/' "$copy/hooks/guard_run.py"
}

guard_rm_non_analizzato() {
  local copy="$1"
  perl -0pi -e 's/            analizza_rm\(segmento\[i \+ 1:\]\)/            pass/' "$copy/hooks/guard_run.py"
}

guard_find_non_analizzato() {
  local copy="$1"
  perl -0pi -e 's/            analizza_find\(segmento\[i \+ 1:\]\)/            pass/' "$copy/hooks/guard_run.py"
}

guard_gh_non_analizzato() {
  local copy="$1"
  perl -0pi -e 's/            analizza_gh\(segmento\[i \+ 1:\]\)/            pass/' "$copy/hooks/guard_run.py"
}

guard_avviso_senza_python_muto() {
  local copy="$1"
  perl -0pi -e 's/NON e attiva/attiva/' "$copy/hooks/guard-run.sh"
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
expect_rejected "A1 default contract question restored" restore_default_question
expect_rejected "A1 skill and permission questions restored" restore_skill_permission_question
expect_rejected "A2 stop on red allowed" allow_stop_on_red
expect_rejected "A2 retry budget removed" remove_retry_budget
expect_rejected "A3 per-delivery verification removed" remove_per_delivery_verification
expect_rejected "A4 local suite fallback removed" remove_local_suite_fallback
expect_rejected "A4 green gate definition removed" remove_green_gate_definition
expect_rejected "A5 doc alignment on close removed" remove_doc_alignment_on_close
expect_rejected "A5 stop after one milestone" stop_after_one_milestone
expect_rejected "A6 answer propagation removed" remove_answer_propagation
expect_rejected "E1 Luna low allowed" weaken_cost_floor
expect_rejected "B1 parallel plan removed" remove_parallel_plan
expect_rejected "B1 independence proof removed" remove_independence_proof
expect_rejected "B2 contract-first removed" remove_contract_first
expect_rejected "B3 brain allowed to integrate code" allow_brain_to_code
expect_rejected "B4 verifier steps removed" remove_verifier_steps
expect_rejected "B4 oracle KO removed" remove_oracle
expect_rejected "B5 tier3 auto-merge allowed" allow_tier3_automerge
expect_rejected "B5 sensitive areas removed" remove_sensitive_areas
expect_rejected "B6 recon removed" remove_recon
expect_rejected "B6 metrics removed" remove_metrics
expect_rejected "B6 KO observer turned into a stop" remove_ko_observer
expect_rejected "B7 config risk areas removed" remove_config_risk_areas
expect_rejected "C1 verifier agent steps removed" weaken_verifier_agent
expect_rejected "C1 verifier allowed to write" allow_verifier_writes
expect_rejected "C1 pre-merge promotion allowed" allow_premerge_promotion
expect_rejected "C1 integrator allowed to implement" allow_integrator_to_implement
expect_rejected "C1 worker delegation allowed" allow_worker_delegation
expect_rejected "C2 bridge sandbox weakened" weaken_bridge_sandbox
expect_rejected "C2 bridge model validation removed" remove_bridge_model_validation
expect_rejected "C2 bridge allows Luna low" weaken_bridge_cost_floor
expect_rejected "C2 bridge dry-run removed" remove_bridge_dry_run
expect_rejected "D1 status command made writable" make_status_command_writable
expect_rejected "D1 start command asks defaults" make_start_ask_defaults
expect_rejected "D2 run guard disabled" disable_run_guard
expect_rejected "D2 guard hook unregistered" remove_guard_hook_registration
expect_rejected_exec "D2 heredoc trattato come codice" guard_heredoc_non_piu_dato
expect_rejected_exec "D2 a capo non separa i comandi" guard_a_capo_non_separa
expect_rejected_exec "D2 wrapper non piu saltati" guard_wrapper_non_saltati
expect_rejected_exec "D2 prefisso del flag lungo ignorato" guard_flag_lungo_esatto
expect_rejected_exec "D2 flag corti combinati ignorati" guard_flag_corto_esatto
expect_rejected_exec "D2 tokenizzazione senza virgolette" guard_quote_non_rispettate
expect_rejected_exec "D2 comando annidato non analizzato" guard_comando_annidato_ignorato
expect_rejected_exec "D2 abbreviazione di --hard ignorata" guard_reset_esatto
expect_rejected_exec "D2 rm non analizzato" guard_rm_non_analizzato
expect_rejected_exec "D2 find non analizzato" guard_find_non_analizzato
expect_rejected_exec "D2 gh non analizzato" guard_gh_non_analizzato
expect_rejected_exec "D2 guardia muta quando non protegge" guard_avviso_senza_python_muto
expect_rejected_exec "D2 continuazione di riga non unita" guard_continuazione_non_unita
expect_rejected_exec "D2 commenti non tolti riga per riga" guard_commenti_non_tolti
expect_rejected_exec "D2 opzioni con valore non lette per programma" guard_opzioni_non_per_programma
expect_rejected_exec "D2 operandi del wrapper non saltati" guard_posizionali_non_saltati
expect_rejected_exec "D2 clean forzato bloccato solo con -d" guard_clean_solo_con_d
expect_rejected_exec "D2 sostituzione dentro le virgolette non analizzata" guard_sostituzione_quotata_ignorata
expect_rejected_exec "D2 redirezioni non tolte dai token" guard_redirezioni_non_tolte
expect_rejected_exec "D2 bundle di opzioni corte di shell ignorato" guard_bundle_shell_ignorato
expect_rejected_exec "D2 abbreviazioni dei flag di push non riconosciute" guard_abbreviazioni_push_esatte
expect_rejected_exec "D2 abbreviazione di --force per clean non riconosciuta" guard_abbreviazione_clean_esatta
expect_rejected_exec "D2 --admin con valore attaccato non riconosciuto" guard_admin_senza_valore
expect_rejected_exec "D2 apici singoli non rispettati nelle sostituzioni" guard_apici_singoli_non_rispettati
expect_rejected_exec "D2 continuazione di riga unita con uno spazio" guard_continuazione_con_spazio
expect_rejected_exec "D2 here-string scambiata per documento inline" guard_herestring_come_heredoc
expect_rejected_exec "D2 commenti lasciati alla regola grossolana di shlex" guard_commenters_di_shlex

if (( failures > 0 )); then
  printf 'RED: %d mutazioni sono sopravvissute\n' "$failures"
  exit 1
fi

printf 'GREEN: tutte le mutazioni sono respinte\n'
