#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)"
CATALOG="$ROOT/skills/orchestratore/references/codex-skills-catalog.jsonl"
SKILL="$ROOT/skills/orchestratore/SKILL.md"
ROUTING="$ROOT/skills/orchestratore/references/routing.md"
STATE="$ROOT/templates/state.toml"
README="$ROOT/README.md"
CC_MANIFEST="$ROOT/.claude-plugin/plugin.json"
CX_MANIFEST="$ROOT/.codex-plugin/plugin.json"

failures=0

ok() {
  printf 'OK: %s\n' "$1"
}

ko() {
  printf 'KO: %s\n' "$1"
  failures=$((failures + 1))
}

check() {
  local label="$1"
  shift
  if "$@"; then
    ok "$label"
  else
    ko "$label"
  fi
}

contains_fixed() {
  local needle="$1"
  shift
  grep -Fqi -- "$needle" "$@"
}

catalog_entry_count() {
  jq -r 'select(.name == "orchestratore") | .name' "$CATALOG" | wc -l | tr -d ' '
}

catalog_field() {
  local field="$1"
  jq -r "select(.name == \"orchestratore\") | .$field" "$CATALOG"
}

jsonl_valid() {
  jq -e . "$CATALOG" >/dev/null
}

check "catalogo JSONL valido" jsonl_valid
if [[ "$(catalog_entry_count)" == "1" ]]; then
  ok "catalogo contiene una sola entry orchestratore"
else
  ko "catalogo contiene una sola entry orchestratore"
fi

expected_skill="$ROOT/skills/orchestratore/SKILL.md"
catalog_skill="$(catalog_field path)"
if [[ "$catalog_skill" == "$expected_skill" ]]; then
  ok "path orchestratore esatto per questo checkout"
else
  ko "path orchestratore esatto per questo checkout"
fi
check "path orchestratore esistente" test -f "$catalog_skill"

if [[ "$(catalog_field pluginId)" == "orchestratore@orchestratore" ]]; then
  ok "pluginId orchestratore corretto"
else
  ko "pluginId orchestratore corretto"
fi

frontmatter_description="$(sed -n 's/^description: //p' "$SKILL" | head -n 1)"
if [[ "$(catalog_field description)" == "$frontmatter_description" ]]; then
  ok "description catalogo allineata al frontmatter"
else
  ko "description catalogo allineata al frontmatter"
fi

if [[ "$(catalog_field source)" == "installed-cache; runtime availability must be checked" ]]; then
  ok "source catalogo descrive cache e verifica runtime"
else
  ko "source catalogo descrive cache e verifica runtime"
fi

cc_version="$(jq -r '.version' "$CC_MANIFEST")"
cx_version="$(jq -r '.version' "$CX_MANIFEST")"
if [[ "$cc_version" == "0.1.1" && "$cx_version" == "0.1.1" && "$cc_version" == "$cx_version" ]]; then
  ok "manifest CC e cx allineati alla versione 0.1.1"
else
  ko "manifest CC e cx allineati alla versione 0.1.1"
fi

check "README documenta snapshot/cache" contains_fixed "snapshot/cache" "$README"
check "README richiede bump di versione" contains_fixed "bump di versione" "$README"
check "README richiede update/upgrade marketplace" contains_fixed "update/upgrade" "$README"
check "README richiede update o reinstallazione plugin" contains_fixed "update o la reinstallazione del plugin" "$README"

P2_FILES=("$SKILL" "$ROUTING" "$STATE")
check "P2 riconosce fino a nuovo avviso" contains_fixed "fino a nuovo avviso" "${P2_FILES[@]}"
check "P2 riconosce CC ha finito i crediti" contains_fixed "cc ha finito i crediti" "${P2_FILES[@]}"
check "P2 riconosce cx ha finito i crediti" contains_fixed "cx ha finito i crediti" "${P2_FILES[@]}"
check "P2 definisce modalità solo-CC" contains_fixed "solo-CC" "${P2_FILES[@]}"
check "P2 definisce modalità solo-cx" contains_fixed "solo-cx" "${P2_FILES[@]}"
check "P2 definisce modalità fermo" contains_fixed "modalità fermo" "${P2_FILES[@]}"

if awk 'BEGIN { IGNORECASE=1 } /cervello/ && /esaurit/ && /handoff/ { found=1 } END { exit !found }' "$SKILL" "$ROUTING"; then
  ok "P2 impone handoff al runtime quando il cervello è esausto"
else
  ko "P2 impone handoff al runtime quando il cervello è esausto"
fi

if ((failures > 0)); then
  printf 'ROSSO: %d controlli falliti\n' "$failures"
  exit 1
fi

printf 'VERDE: tutti i controlli regressione passano\n'
