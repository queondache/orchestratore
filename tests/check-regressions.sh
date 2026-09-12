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

contains_in_file() {
  local needle="$1"
  local file="$2"
  grep -Fqi -- "$needle" "$file"
}

matches_in_file() {
  local pattern="$1"
  local file="$2"
  perl -0777 -ne "exit !(m{$pattern}ims)" "$file"
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

check "state definisce credito CC e CX" matches_in_file '\[credito\][\s\S]*?^cc = "ok"\s+# ok \| esaurito[\s\S]*?^cx = "ok"\s+# ok \| esaurito' "$STATE"
check "state limita le modalità credito" contains_in_file 'modalita = "normale"   # normale | solo-cc | solo-cx | fermo' "$STATE"
check "state conserva aggiornamento e motivo" matches_in_file '^aggiornato = "1970-01-01T00:00:00Z"[\s\S]*?^motivo = "stato iniziale"' "$STATE"
check "state conserva schema peso precedente" matches_in_file '\[credito\.peso_precedente\][\s\S]*?^dev = \{ cx = 100, cc = 0 \}[\s\S]*?^verifica = "cc"' "$STATE"

check "skill salva peso una sola volta lasciando normale" matches_in_file 'Se la modalità era `normale`, salva il peso corrente in `credito\.peso_precedente`; non\s+sovrascriverlo durante ulteriori cambi di credito\.' "$SKILL"
check "skill associa esaurimento CC a solo-cx" contains_in_file 'modalità: `solo-cx` se è esaurito CC' "$SKILL"
check "skill associa esaurimento cx a solo-cc" contains_in_file '`solo-cc` se è esaurito cx' "$SKILL"
check "skill associa doppio esaurimento a fermo" contains_in_file '`fermo` se lo sono entrambi' "$SKILL"
check "routing applica solo-CC al cx esaurito" contains_in_file '**Solo-CC** (cx esaurito)' "$ROUTING"
check "routing applica solo-cx al CC esaurito" contains_in_file '**Solo-cx** (CC esaurito)' "$ROUTING"
check "routing vieta assegnazioni in fermo" matches_in_file 'Con entrambi\s+esauriti, modalità\s+`fermo`: nessuna assegnazione e nessuna capacità simulata\.' "$ROUTING"

check "skill impone handoff positivo, rilascio lock e stop" matches_in_file 'Se è esaurito il runtime del cervello e l\x27altro è disponibile, scrivi l\x27handoff esplicito\s+all\x27altro runtime dopo aver completato solo il proprio checkpoint atomico, aggiornato\s+`run\.md` e lo stato credito e rilasciato `brain\.lock`; quindi fermati\.' "$SKILL"
check "skill ripristina il peso solo con entrambi ok" matches_in_file 'quando entrambi sono `ok`, ripristina\s+il peso salvato, torna a `normale`' "$SKILL"

if ((failures > 0)); then
  printf 'ROSSO: %d controlli falliti\n' "$failures"
  exit 1
fi

printf 'VERDE: tutti i controlli regressione passano\n'
