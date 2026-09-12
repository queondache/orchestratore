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
CC_MARKETPLACE="$ROOT/.claude-plugin/marketplace.json"
AGENT_MARKETPLACE="$ROOT/.agents/plugins/marketplace.json"

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

does_not_contain() {
  local needle="$1"
  shift
  ! grep -Fqi -- "$needle" "$@"
}

does_not_match_in_files() {
  local pattern="$1"
  shift
  local file
  for file in "$@"; do
    if perl -0777 -ne "exit(m{$pattern}ims ? 0 : 1)" "$file"; then
      return 1
    fi
  done
}

json_version_is() {
  local file="$1"
  [[ "$(jq -r '.version' "$file")" == "0.1.3" ]]
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
if [[ "$cc_version" == "0.1.3" && "$cx_version" == "0.1.3" && "$cc_version" == "$cx_version" ]]; then
  ok "manifest CC e cx allineati alla versione 0.1.3"
else
  ko "manifest CC e cx allineati alla versione 0.1.3"
fi

check "manifest CC versione 0.1.3" json_version_is "$CC_MANIFEST"
check "manifest cx versione 0.1.3" json_version_is "$CX_MANIFEST"
check "marketplace CC versione 0.1.3" json_version_is "$CC_MARKETPLACE"
check "marketplace agenti versione 0.1.3" json_version_is "$AGENT_MARKETPLACE"

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

Y2_FILES=("$SKILL" "$ROOT/skills/orchestratore/references/lane.md" "$ROOT/skills/orchestratore/references/adapter-cc.md" "$ROOT/skills/orchestratore/references/adapter-cx.md" "$ROOT/skills/orchestratore/references/project-adapter.md" "$ROOT/templates/run.md" "$README")
check "Y2 dichiara run non presidiato" contains_in_file 'Run non presidiato' "$SKILL"
check "Y2 limita Codex a --yolo" contains_in_file 'codex exec --yolo' "$ROOT/skills/orchestratore/references/adapter-cc.md"
check "Y2 limita Claude a bypassPermissions" contains_in_file '--permission-mode bypassPermissions' "$ROOT/skills/orchestratore/references/adapter-cx.md"
check "Y2 consente Git normale automatico" contains_in_file 'commit, push e PR normali automatici' "$SKILL"
check "Y2 auto-merge richiede hash verificato" contains_in_file 'hash esatto revisionato' "$ROOT/skills/orchestratore/references/lane.md"
check "Y2 auto-merge richiede verifier finale" contains_in_file 'verificatore indipendente finale OK' "$ROOT/skills/orchestratore/references/lane.md"
check "Y2 auto-merge richiede CI required" matches_in_file 'almeno un required CI check[\s\S]*?tutti i required check.*success' "$ROOT/skills/orchestratore/references/lane.md"
check "Y4 blocca check CI assenti pending falliti o cancellati" contains_in_file 'assenti, pending, falliti o cancellati' "$ROOT/skills/orchestratore/references/lane.md"
check "Y2 limita plugin Codex già connessi" contains_in_file 'app già collegate come plugin Codex' "$ROOT/skills/orchestratore/references/project-adapter.md"
check "Y2 consente side effect esterni richiesti non distruttivi" contains_in_file 'side effect esterni non distruttivi direttamente richiesti' "$SKILL"
check "Y2 limita side effect al perimetro congelato" matches_in_file 'perimetro\s+congelato del task' "$ROOT/skills/orchestratore/references/project-adapter.md"
check "Y2 vieta nuove connessioni e segreti" contains_in_file 'nessun login, connessione, scope o segreto nuovo' "$SKILL"
check "Y2 vieta aumenti di spesa" contains_in_file 'aumenti di budget, spend limit o credito' "$SKILL"
check "Y2 mantiene divieto assoluto di spesa" matches_in_file 'acquisti, upgrade e aumenti di budget, spend limit o credito.*vietati' "$ROOT/skills/orchestratore/references/project-adapter.md"
check "Y2 vieta Git distruttivo" contains_in_file 'force-push, reset e cancellazioni distruttive' "$SKILL"
check "Y2 Codex nativo verifica profilo YOLO" contains_in_file 'effective approval_policy=never + sandbox_mode=danger-full-access' "$ROOT/skills/orchestratore/references/adapter-cx.md"
check "Y2 Codex nativo usa fallback yolo senza delegare" contains_in_file 'non delegare quella lane e usa un path già `--yolo`' "$ROOT/skills/orchestratore/references/adapter-cx.md"
check "Y2 Claude nativo verifica bypassPermissions" contains_in_file 'verifica `bypassPermissions` effettivo' "$ROOT/skills/orchestratore/references/adapter-cc.md"
check "Y4 vieta mouse nel contratto runtime" contains_in_file 'il mouse è sempre vietato' "$SKILL"
check "Y4 vieta modifiche distruttive o massive ai dati produzione nella skill" matches_in_file 'modifiche distruttive o\s+massive ai dati di produzione' "$SKILL"
check "Y4 vieta modifiche distruttive o massive ai dati produzione nel project adapter" matches_in_file 'modifiche distruttive o massive ai dati di\s+produzione' "$ROOT/skills/orchestratore/references/project-adapter.md"
check "Y2 non elimina branch automaticamente" does_not_contain '--delete-branch' "$ROOT/skills/orchestratore/references/lane.md"
check "Y2 rimuove attesa della parola merge" does_not_contain 'parola `merge`' "${Y2_FILES[@]}"

S2_FILES=("$SKILL" "$ROOT/skills/orchestratore/references/adapter-cx.md" "$ROOT/skills/orchestratore/references/adapter-cc.md" "$ROOT/skills/orchestratore/references/skill-map.md" "$ROOT/skills/orchestratore/references/project-adapter.md")
check "S2 rende libere le skill installate utili" matches_in_file 'liberamente senza\s+chiedere Andrea tutte le skill già installate e disponibili utili al task' "$SKILL"
check "S2 richiede lettura completa della skill scelta" contains_in_file 'seguono il suo `SKILL.md` completo' "$SKILL"
check "S2 rimuove consenso skill da Codex" does_not_contain 'chiedi ad Andrea con una frase in italiano che nomina la skill' "$ROOT/skills/orchestratore/references/adapter-cx.md"
check "S2 non reintroduce richiesta Andrea per skill" does_not_contain 'Chiedi ad Andrea prima della skill' "$SKILL"
check "S2 continua con skill equivalente o procedura base" contains_in_file 'skill equivalente già installata o la procedura base' "$SKILL"
check "S2 vieta installare o abilitare skill" matches_in_file 'non\s+autorizza installare skill nuove, abilitare o modificare globalmente skill o plugin' "$SKILL"
check "S2 conserva guardrail tool e app" matches_in_file 'tool o app\s+invocati dalla skill conservano tutti i guardrail 0.1.2' "$SKILL"
check "S4 adapter CC invoca skill installate liberamente" contains_in_file 'skill già installate e disponibili utili al task liberamente' "$ROOT/skills/orchestratore/references/adapter-cc.md"
check "S4 skill-map usa fallback equivalente o base" contains_in_file 'skill equivalente già installata o procedura base' "$ROOT/skills/orchestratore/references/skill-map.md"
check "S4 adapter CC vieta installazione e permessi ampliati" matches_in_file 'mai installare, abilitare\s+o modificare globalmente skill o plugin' "$ROOT/skills/orchestratore/references/adapter-cc.md"
check "S4 nessun consenso skill negli adapter" does_not_contain 'chiedi Andrea prima della skill' "${S2_FILES[@]}"
check "S4 nessun consenso o autorizzazione Andrea per skill" does_not_match_in_files '(?:fermati\s+e\s+)?(?:chied(?:i|ere)|richied(?:i|ere)|ott(?:ieni|enere)|attend(?:i|ere))(?:\s+\p{L}+){0,8}\s+(?:consenso|autorizzazione)(?:\s+\p{L}+){0,8}\s+(?:di\s+)?Andrea' "${S2_FILES[@]}"
check "S4 nessun fermo per skill o consenso" does_not_match_in_files '(?<!non\s)(?:fermati|stop)(?:\s+\p{L}+){0,10}\s+(?:skill|consenso|autorizzazione)' "${S2_FILES[@]}"
check "S4 nessuna installazione o abilitazione globale consentita" does_not_match_in_files '(?<!non\s)(?:consenti|autorizza|puoi)(?:\s+\p{L}+){0,8}\s+(?:installare|abilitare)(?:\s+\p{L}+){0,8}\s+globalmente\s+skill(?:/plugin|\s+o\s+plugin)?' "${S2_FILES[@]}"

if ((failures > 0)); then
  printf 'ROSSO: %d controlli falliti\n' "$failures"
  exit 1
fi

printf 'VERDE: tutti i controlli regressione passano\n'
