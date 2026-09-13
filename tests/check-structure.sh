#!/usr/bin/env bash
# Gate strutturale del plugin orchestratore. Exit 0 solo se tutto passa.
# Uso: tests/check-structure.sh   (da qualsiasi cwd)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0

check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf 'OK  %s\n' "$desc"
  else
    printf 'KO  %s\n' "$desc"; FAIL=$((FAIL+1))
  fi
}

json_key() { # json_key <file> <jq-path>
  jq -e "$2" "$1"
}

SKILL="$ROOT/skills/orchestratore/SKILL.md"
REFS="$ROOT/skills/orchestratore/references"

# Manifest
check "plugin.json CC valido con name/version/description" \
  json_key "$ROOT/.claude-plugin/plugin.json" '.name=="orchestratore" and (.version|test("^[0-9]+\\.[0-9]+\\.[0-9]+$")) and (.description|length>0)'
check "marketplace.json CC con un plugin source ./" \
  json_key "$ROOT/.claude-plugin/marketplace.json" '.name=="orchestratore" and (.plugins|length==1) and .plugins[0].source=="./"'
check "plugin.json cx valido con skills ./skills/" \
  json_key "$ROOT/.codex-plugin/plugin.json" '.name=="orchestratore" and .skills=="./skills/" and (.interface.displayName|length>0)'
check "marketplace.json cx presente" \
  json_key "$ROOT/.agents/plugins/marketplace.json" '.name=="orchestratore" and (.plugins|length==1)'

# SKILL.md
check "SKILL.md esiste" test -f "$SKILL"
check "SKILL.md frontmatter name: orchestratore" grep -q '^name: orchestratore$' "$SKILL"
check "SKILL.md frontmatter description" grep -q '^description: .\{40,\}' "$SKILL"
check "SKILL.md <= 250 righe" bash -c "[ \$(wc -l < '$SKILL') -le 250 ]"
check "SKILL.md nomina standard|alternativo" grep -q 'standard' "$SKILL"
check "SKILL.md frase celebrazione esatta" grep -q '^una milestone meno$' "$SKILL"
check "SKILL.md GIF delfino" grep -q 'AhV2lfKBfEvcEqj6h3' "$SKILL"
check "SKILL.md GIF balena" grep -q 'Q6rD2TLgqMiHf4a0Pt' "$SKILL"
check "SKILL.md tetto 3 milestone x 3 task / 9 builder" grep -q '3 milestone × 3 task' "$SKILL"
check "SKILL.md pool di verifica separato" grep -q '9 worker builder' "$SKILL"
check "SKILL.md regola builder != verificatore" grep -qi 'modello diverso' "$SKILL"

# References
for f in routing.md lane.md credito.md parallelismo.md verifica.md skill-map.md adapter-cc.md adapter-cx.md project-adapter.md codex-skills-catalog.jsonl; do
  check "references/$f esiste" test -s "$REFS/$f"
done
check "references vecchie rimosse" bash -c "! test -e '$REFS/runtime-bridges.md' && ! test -e '$REFS/skill-activation.md'"
check "routing.md contiene i 10 modelli" bash -c "for m in fable gpt-6-astra opus gpt-5.6-sol sonnet gpt-5.6-terra haiku gpt-5.6-luna; do grep -q \"\$m\" '$REFS/routing.md' || exit 1; done"
check "lane.md contiene regola verdetto su hash" grep -qi 'hash' "$REFS/lane.md"
check "lane.md contiene pre-merge" grep -q 'suggerisco merge' "$REFS/lane.md"

# Agent del plugin
for a in worker-impl worker-mech verificatore pre-merge integratore; do
  check "agents/$a.md esiste" test -s "$ROOT/agents/$a.md"
  check "agents/$a.md dichiara name" grep -q "^name: $a$" "$ROOT/agents/$a.md"
  check "agents/$a.md dichiara model" grep -q '^model: ' "$ROOT/agents/$a.md"
  check "agents/$a.md dichiara tools" grep -q '^tools: ' "$ROOT/agents/$a.md"
done
check "verificatore e in sola lettura" bash -c "! grep -qE '^tools:.*(Write|Edit)' '$ROOT/agents/verificatore.md'"
check "pre-merge e in sola lettura" bash -c "! grep -qE '^tools:.*(Write|Edit)' '$ROOT/agents/pre-merge.md'"
check "integratore non implementa" grep -qi 'Nessuna implementazione nuova' "$ROOT/agents/integratore.md"

# Bridge
check "bin/spawn-cx.sh eseguibile" test -x "$ROOT/bin/spawn-cx.sh"
check "bin/spawn-cc.sh eseguibile" test -x "$ROOT/bin/spawn-cc.sh"
check "bridge cx passa il gate eseguibile" bash "$ROOT/tests/check-bridge.sh"

# Comandi e hook
for c in orchestra orchestra-status; do
  check "commands/$c.md esiste" test -s "$ROOT/commands/$c.md"
  check "commands/$c.md ha description" grep -q '^description: ' "$ROOT/commands/$c.md"
done
check "commands/orchestra.md elenca i sottocomandi" bash -c "for s in start status peso credito stop riprendi; do grep -q \"\$s\" '$ROOT/commands/orchestra.md' || exit 1; done"
check "hooks/hooks.json esiste" test -s "$ROOT/hooks/hooks.json"
check "hooks/guard-run.sh eseguibile" test -x "$ROOT/hooks/guard-run.sh"
check "hooks/session-run-state.sh eseguibile" test -x "$ROOT/hooks/session-run-state.sh"
check "hook passano il gate eseguibile" bash "$ROOT/tests/check-hooks.sh"

# Template
check "templates/run.md" test -s "$ROOT/templates/run.md"
check "templates/config.toml con peso default" bash -c "grep -q 'cx = 100' '$ROOT/templates/config.toml' && grep -q 'valido_fino = \"2026-10-12\"' '$ROOT/templates/config.toml'"
check "templates/state.toml" test -s "$ROOT/templates/state.toml"

# Igiene
check "nessun TODO/TBD nei file consegnati" bash -c "! grep -rEn 'TODO|TBD' '$ROOT/skills' '$ROOT/templates' '$ROOT/.claude-plugin' '$ROOT/.codex-plugin'"
check "nessun path utente cablato fuori da adapter-cx.md" bash -c "! grep -rln '/Users/andreapesce' '$ROOT/skills' '$ROOT/templates' | grep -v 'adapter-cx.md' | grep -v 'codex-skills-catalog.jsonl'"
check "README.md presente" test -s "$ROOT/README.md"

echo
if [ "$FAIL" -eq 0 ]; then echo "VERDE: tutti i controlli passano"; exit 0; fi
echo "ROSSO: $FAIL controlli falliti"; exit 1
