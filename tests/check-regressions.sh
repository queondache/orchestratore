#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)"
CATALOG="$ROOT/skills/orchestratore/references/codex-skills-catalog.jsonl"
SKILL="$ROOT/skills/orchestratore/SKILL.md"
ROUTING="$ROOT/skills/orchestratore/references/routing.md"
STATE="$ROOT/templates/state.toml"
CONFIG="$ROOT/templates/config.toml"
CREDITO="$ROOT/skills/orchestratore/references/credito.md"
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
  [[ "$(jq -r '.version' "$file")" == "0.4.1" ]]
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

# Il catalogo e' una cache locale di Codex: punta al checkout dove e' stato generato.
# Il gate deve restare forte sul checkout canonico e non mentire su worktree, clone o copie:
# per questo pretende sempre un path assoluto con il suffisso giusto, e in piu' che il file
# indicato esista davvero — o, se siamo altrove, che esista il suo equivalente qui.
catalog_path_ben_formato() {
  [[ "$catalog_skill" = /* ]] || return 1
  [[ "$catalog_skill" == */skills/orchestratore/SKILL.md ]]
}
catalog_path_risolvibile() {
  [[ -f "$catalog_skill" ]] || [[ -f "$expected_skill" ]]
}
check "catalogo usa un path assoluto a skills/orchestratore/SKILL.md" catalog_path_ben_formato
check "catalogo punta a un SKILL.md risolvibile" catalog_path_risolvibile
if [[ "$catalog_skill" == "$expected_skill" ]]; then
  ok "path orchestratore allineato a questo checkout"
elif [[ -f "$catalog_skill" ]]; then
  ok "path orchestratore allineato al checkout canonico (qui siamo in una copia)"
else
  ko "path orchestratore non risolvibile ne qui ne nel checkout canonico"
fi

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
if [[ "$cc_version" == "0.4.1" && "$cx_version" == "0.4.1" && "$cc_version" == "$cx_version" ]]; then
  ok "manifest CC e cx allineati alla versione 0.4.1"
else
  ko "manifest CC e cx allineati alla versione 0.4.1"
fi

check "manifest CC versione 0.4.1" json_version_is "$CC_MANIFEST"
check "manifest cx versione 0.4.1" json_version_is "$CX_MANIFEST"
check "marketplace CC versione 0.4.1" json_version_is "$CC_MARKETPLACE"
check "marketplace agenti versione 0.4.1" json_version_is "$AGENT_MARKETPLACE"

check "README documenta snapshot/cache" contains_fixed "snapshot/cache" "$README"
check "README richiede bump di versione" contains_fixed "bump di versione" "$README"
check "README richiede update/upgrade marketplace" contains_fixed "update/upgrade" "$README"
check "README richiede update o reinstallazione plugin" contains_fixed "update o la reinstallazione del plugin" "$README"

check "state definisce credito CC e CX" matches_in_file '\[credito\][\s\S]*?^cc = "ok"\s+# ok \| esaurito[\s\S]*?^cx = "ok"\s+# ok \| esaurito' "$STATE"
check "state limita le modalità credito" contains_in_file 'modalita = "normale"   # normale | solo-cc | solo-cx | fermo' "$STATE"
check "state conserva aggiornamento e motivo" matches_in_file '^aggiornato = "1970-01-01T00:00:00Z"[\s\S]*?^motivo = "stato iniziale"' "$STATE"
check "state conserva schema peso precedente" matches_in_file '\[credito\.peso_precedente\][\s\S]*?^dev = \{ cx = 100, cc = 0 \}[\s\S]*?^verifica = "cc"' "$STATE"

check "credito salva peso una sola volta lasciando normale" matches_in_file 'Se la modalità era `normale`, salva il peso corrente in `credito\.peso_precedente`; non\s+sovrascriverlo durante ulteriori cambi di credito\.' "$CREDITO"
check "credito associa esaurimento CC a solo-cx" contains_in_file 'modalità: `solo-cx` se è esaurito CC' "$CREDITO"
check "credito associa esaurimento cx a solo-cc" contains_in_file '`solo-cc` se è esaurito cx' "$CREDITO"
check "credito associa doppio esaurimento a fermo" contains_in_file '`fermo` se lo sono entrambi' "$CREDITO"
check "routing applica solo-CC al cx esaurito" contains_in_file '**Solo-CC** (cx esaurito)' "$ROUTING"
check "routing applica solo-cx al CC esaurito" contains_in_file '**Solo-cx** (CC esaurito)' "$ROUTING"
check "routing vieta assegnazioni in fermo" matches_in_file 'Con entrambi\s+esauriti, modalità\s+`fermo`: nessuna assegnazione e nessuna capacità simulata\.' "$ROUTING"

check "credito impone handoff positivo, rilascio lock e stop" matches_in_file 'Se è esaurito il runtime del cervello e l\x27altro è disponibile, scrivi l\x27handoff esplicito\s+all\x27altro runtime dopo aver completato solo il proprio checkpoint atomico, aggiornato\s+`run\.md` e lo stato credito e rilasciato `brain\.lock`; quindi fermati\.' "$CREDITO"
check "credito ripristina il peso solo con entrambi ok" matches_in_file 'quando entrambi sono `ok`, ripristina\s+il peso salvato, torna a `normale`' "$CREDITO"

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

LANE="$ROOT/skills/orchestratore/references/lane.md"
RUN_TPL="$ROOT/templates/run.md"
PROJECT_ADAPTER="$ROOT/skills/orchestratore/references/project-adapter.md"
ADAPTER_CC="$ROOT/skills/orchestratore/references/adapter-cc.md"

# A1 — autonomia: default scritti, non chiesti
check "A1 fissa i default del contratto" contains_in_file '**Default quando Andrea non dice altro**' "$SKILL"
check "A1 default git commit+push+PR automatici" contains_in_file 'Autorizzazioni Git: commit+push+PR automatici' "$SKILL"
check "A1 default run non presidiato" matches_in_file 'Run non\s+presidiato: sì' "$SKILL"
check "A1 vieta di chiedere conferma dei default" contains_in_file 'si cambia solo se lo scrive lui' "$SKILL"
check "A1 vieta domande su skill tool permessi" matches_in_file 'Mai di\s+skill, tool, modelli, permessi, approccio tecnico o conferma di un default' "$SKILL"

# A2 — il rosso non ferma il run
check "A2 dichiara il rosso non stop" contains_in_file 'Il rosso non è mai una condizione di stop' "$SKILL"
check "A2 firma stabile del problema" contains_in_file 'gate + errore normalizzato + hash del diff' "$LANE"
check "A2 deduplica feedback invariato" contains_in_file 'firma invariata già consegnata è deduplicata' "$LANE"
check "A2 limita a due tentativi per approccio" contains_in_file 'due tentativi per approccio' "$LANE"
check "A2 limita a due approcci automatici" contains_in_file 'dopo due approcci distinti' "$LANE"
check "A2 parcheggia la lane e continua il run" matches_in_file 'bloccata-tecnica[\s\S]*?libera lo slot[\s\S]*?continua il lavoro indipendente' "$LANE"
check "A2 template persiste firma e approccio" matches_in_file 'Firma KO:[\s\S]*?approccio_id:[\s\S]*?Tentativi approccio' "$ROOT/templates/run.md"

# A3 — verifica a ogni consegna
check "A3 verifica obbligatoria per consegna" contains_in_file 'Verifica obbligatoria a ogni consegna, non solo a fine milestone' "$SKILL"
check "A3 formato riga di verifica con hash" contains_in_file 'verifica T-<id>' "$SKILL"
check "A3 senza riga il task resta in review" contains_in_file 'il task resta `in review`' "$SKILL"
check "A3 lane ripete la verifica per consegna" contains_in_file '## Verifica a ogni consegna, non solo a fine milestone' "$LANE"
check "A3 template registra la verifica" contains_in_file 'verifica T-001:' "$RUN_TPL"
check "A3 agent mancante non salta la verifica" matches_in_file 'Mancanza di un agent non è mai un motivo\s+per saltare la verifica' "$ADAPTER_CC"

# A4 — gate verde definito e fallback di merge senza CI
check "A4 definisce il gate verde" contains_in_file '## Gate verde: definito una volta, scritto in `run.md`' "$LANE"
check "A4 gate verde nel template" contains_in_file 'Gate verde: build=' "$RUN_TPL"
check "A4 gate verde nel project adapter" contains_in_file 'Gate verde: build=' "$PROJECT_ADAPTER"
check "A4 fallback suite locale senza required checks" contains_in_file 'fallback suite locale' "$LANE"
check "A4 fallback eseguito dal verificatore" matches_in_file 'Il\s+verificatore — mai il builder — esegue' "$LANE"
check "A4 fallback senza output raw non vale" contains_in_file 'Un fallback dichiarato senza output raw non vale' "$LANE"

# A5 — chiusura milestone, doc allineati, lane successiva
check "A5 chiusura aggiorna i doc" contains_in_file 'la milestone diventa **chiusa**' "$LANE"
check "A5 merge senza doc non chiude" contains_in_file 'Merge fatto e doc non allineati = milestone **non** chiusa' "$LANE"
check "A5 apre subito la lane successiva" contains_in_file 'apri subito la lane successiva' "$LANE"
check "A5 il run finisce col budget" contains_in_file 'finisce col budget' "$LANE"
check "A5 skill impone chiusura in un colpo solo" contains_in_file 'Chiusura di milestone, in un colpo solo e senza chiedere' "$SKILL"

# A6 — propagazione delle risposte di Andrea
check "A6 propaga la risposta nello stesso turno" contains_in_file 'Propagazione della risposta, automatica e nello stesso turno' "$SKILL"
check "A6 propaga in SPEC" contains_in_file 'aggiorna `SPEC.md` nel punto che tocca' "$SKILL"
check "A6 propaga in ROADMAP e perimetri" matches_in_file '`ROADMAP\.md` e i perimetri delle milestone coinvolte' "$SKILL"
check "A6 riemette i contratti congelati incoerenti" matches_in_file 'riemetti il\s+perimetro e passalo al worker' "$SKILL"
check "A6 allinea prima di aprire una lane" contains_in_file 'se divergono, allinea prima' "$SKILL"

# A7 — cadenza report onesta
check "A7 rimuove la cadenza a tempo non rispettabile" does_not_contain 'comunque ogni 10 minuti' "$SKILL"

# E1 — costo: modello ed effort minimi adatti alla task, escalation motivata
check "E1 politica cheapest-capable predefinita" contains_in_file 'politica predefinita è `cheapest-capable`' "$ROUTING"
check "E1 cervello cx Astra medium" contains_in_file '| gpt-6-astra | **medium fisso** |' "$ROUTING"
check "E1 Luna non usa low" contains_in_file '`gpt-5.6-luna`: solo task meccaniche e delimitate; `medium` o `high`, mai `low`' "$ROUTING"
check "E1 Terra non usa low" contains_in_file '`gpt-5.6-terra`: task basic; `medium` o `high`, mai `low`' "$ROUTING"
check "E1 Sol può partire da low" contains_in_file '`gpt-5.6-sol`: task importanti; parte da `low`' "$ROUTING"
check "E1 Astra worker parte da low solo in escalation" matches_in_file '`gpt-6-astra`: cervello a `medium`; nei worker parte da `low` ed entra solo per\s+escalation' "$ROUTING"
check "E1 premium richiede trigger registrato" matches_in_file 'Ogni uso di `high`,\s+`Astra` o `Opus` registra il trigger' "$ROUTING"
check "E1 default CC non sono premium" bash -c "grep -q '^model: sonnet$' '$ROOT/agents/worker-impl.md' && grep -q '^model: haiku$' '$ROOT/agents/verificatore.md'"
check "E1 contratto registra politica e trigger" matches_in_file 'Politica costo: cheapest-capable[\s\S]*?Motivo del modello/effort ed eventuale trigger premium' "$RUN_TPL"
check "E1 config vieta premium senza trigger" matches_in_file '\[costo\][\s\S]*?strategia = "cheapest-capable"[\s\S]*?premium_solo_con_trigger = true' "$CONFIG"

PARALLELISMO="$ROOT/skills/orchestratore/references/parallelismo.md"
VERIFICA="$ROOT/skills/orchestratore/references/verifica.md"

# B1 — piano di parallelizzazione e prova di indipendenza
check "B1 tetti a due livelli nella skill" contains_in_file '3 milestone × 3 task = **9 worker builder**' "$SKILL"
check "B1 pool di verifica fuori dal tetto builder" matches_in_file 'verificatori, pre-merge e\s+integratore stanno in un pool a parte' "$SKILL"
check "B1 piano di parallelizzazione richiesto" contains_in_file '## 1. Piano di parallelizzazione, prima di qualsiasi delega' "$PARALLELISMO"
check "B1 glob non descrizioni" contains_in_file 'Le aree scrivibili sono **glob**, non descrizioni' "$PARALLELISMO"
check "B1 prova di indipendenza sui file reali" contains_in_file 'comm -12' "$PARALLELISMO"
check "B1 nessuno slot senza prova" contains_in_file 'Nessuna prova scritta =' "$PARALLELISMO"
check "B1 piano nel template run" contains_in_file '## Piano di parallelizzazione' "$RUN_TPL"
check "B1 project adapter impone il piano" contains_in_file 'Piano di parallelizzazione' "$PROJECT_ADAPTER"

# B2 — contract-first
check "B2 contract-first nella skill" contains_in_file 'lane **contract-first**, non parallelo' "$SKILL"
check "B2 contract-first merge su main prima del parallelo" contains_in_file 'mergiare su main**. Solo dopo partono in parallelo' "$PARALLELISMO"
check "B2 interfaccia congelata per le consumatrici" contains_in_file '**file congelato** per le lane consumatrici' "$PARALLELISMO"
check "B2 fallback seriale se non isolabile" contains_in_file 'le milestone vanno **seriali**' "$PARALLELISMO"

# B3 — task nella lane e integratore
check "B3 branch di integrazione della milestone" contains_in_file 'branch di integrazione' "$LANE"
check "B3 branch dei task figli" contains_in_file 'm/<slug>/t<NN>' "$PARALLELISMO"
check "B3 integratore e un task con contratto" contains_in_file 'è un **task con contratto**' "$PARALLELISMO"
check "B3 cervello non scrive codice nel parallelismo" contains_in_file '**Il cervello non scrive codice.**' "$PARALLELISMO"
check "B3 cervello non scrive codice nella skill" contains_in_file '**Il cervello non scrive codice**' "$SKILL"
check "B3 routing elenca integratore" contains_in_file '`integratore`' "$ROUTING"
check "B3 routing separa i tetti" contains_in_file '**Tetti separati**' "$ROUTING"

# B4 — protocollo di verifica e oracolo
check "B4 quattro passi obbligatori" contains_in_file '## I quattro passi obbligatori' "$VERIFICA"
check "B4 hash dimostrato" contains_in_file 'git rev-parse HEAD' "$VERIFICA"
check "B4 oracolo con rosso atteso" contains_in_file 'deve diventare **rossa**' "$VERIFICA"
check "B4 KO oracolo assente" contains_in_file 'KO: oracolo assente' "$VERIFICA"
check "B4 KO fuori perimetro" contains_in_file 'KO: fuori perimetro' "$VERIFICA"
check "B4 verdetto senza evidenza si riassegna" matches_in_file 'non è un verdetto: il cervello lo tratta\s+come verifica non eseguita' "$VERIFICA"
check "B4 lane rimanda al protocollo" contains_in_file 'I quattro passi obbligatori' "$LANE"
check "B4 skill nomina oracolo" contains_in_file '**oracolo**' "$SKILL"
check "B4 routing impone i quattro passi" contains_in_file 'oracolo incluso' "$ROUTING"

# B5 — classe di rischio del merge
check "B5 regola fissa senza discrezionalita" contains_in_file 'regola fissa, nessuna discrezionalità' "$VERIFICA"
check "B5 classe calcolata sul diff reale" contains_in_file 'sul diff reale' "$VERIFICA"
check "B5 tier 3 in attesa di Andrea" contains_in_file '**PR in attesa di Andrea**' "$VERIFICA"
check "B5 aree sensibili configurabili" contains_in_file 'aree_sensibili' "$VERIFICA"
check "B5 nessuna promozione ad auto-merge" contains_in_file 'non promuove mai' "$VERIFICA"
check "B5 lane applica la classe prima del gate" contains_in_file '**classe di rischio** calcolata sul diff reale' "$LANE"
check "B5 auto-merge solo tier 1-2" contains_in_file 'Per le sole milestone tier 1-2' "$LANE"
check "B5 template registra la classe" contains_in_file 'Classe di rischio:' "$RUN_TPL"
check "B5 confini limitano auto-merge ai tier bassi" matches_in_file 'auto-merge sono autorizzati solo al gate di §4 e per\s+le sole milestone tier 1-2' "$SKILL"

# B6 — recon, assunzioni, metriche, osservatore
check "B6 recon riusabile" contains_in_file '.orchestratore/recon.md' "$PROJECT_ADAPTER"
check "B6 recon scade con la revisione base" contains_in_file 'il recon è scaduto' "$PROJECT_ADAPTER"
check "B6 contratto passa il recon per path" contains_in_file '.orchestratore/recon.md` per path' "$SKILL"
check "B6 assunzioni reversibili non sono domande" contains_in_file 'non è una domanda: decidi, registrala in' "$SKILL"
check "B6 assunzioni nel template" contains_in_file '## Assunzioni' "$RUN_TPL"
check "B6 metriche nel template" contains_in_file '## Metriche' "$RUN_TPL"
check "B6 metrica principale interruzioni" contains_in_file 'Interruzioni chieste ad Andrea' "$RUN_TPL"
check "B6 skill aggiorna le metriche" contains_in_file 'quante volte hai interrotto Andrea' "$SKILL"
check "B6 loop KO finito" contains_in_file 'Nessun terzo approccio automatico' "$LANE"
check "B6 blocco di lane non ferma il run" contains_in_file 'il rosso della lane non ferma l'"'"'intero run' "$LANE"

CONFIG_TPL="$ROOT/templates/config.toml"
check "B7 config espone i tetti a due livelli" matches_in_file 'task_per_milestone = 3[\s\S]*?builder = 9' "$CONFIG_TPL"
check "B7 config separa il pool di verifica" contains_in_file 'verifiche_in_volo = 3' "$CONFIG_TPL"
check "B7 config elenca le aree sensibili" matches_in_file '\[rischio\][\s\S]*?aree_sensibili = \[' "$CONFIG_TPL"

AGENTS="$ROOT/agents"
BIN="$ROOT/bin"

# C1 — agent del plugin reali, non promessi
check "C1 verificatore applica i quattro passi" contains_in_file '## I quattro passi, tutti obbligatori' "$AGENTS/verificatore.md"
check "C1 verificatore esige oracolo rosso" contains_in_file 'KO: oracolo assente' "$AGENTS/verificatore.md"
check "C1 verificatore non scrive file" contains_in_file 'Non modifichi nessun file' "$AGENTS/verificatore.md"
check "C1 pre-merge calcola la classe sul diff" contains_in_file '## Classe di rischio, calcolata sul diff reale' "$AGENTS/pre-merge.md"
check "C1 pre-merge non promuove mai" contains_in_file 'non promuovi mai una PR da `in attesa` ad `auto`' "$AGENTS/pre-merge.md"
check "C1 pre-merge risponde nel formato fisso" contains_in_file 'suggerisco merge: sì | no' "$AGENTS/pre-merge.md"
check "C1 worker non delega" contains_in_file '**Non deleghi.**' "$AGENTS/worker-impl.md"
check "C1 worker non parla con Andrea" contains_in_file '**Non parli con Andrea.**' "$AGENTS/worker-impl.md"
check "C1 worker resta nei glob" contains_in_file '**Scrivi solo dentro i glob dichiarati**' "$AGENTS/worker-impl.md"
check "C1 integratore non implementa" contains_in_file '**Nessuna implementazione nuova.**' "$AGENTS/integratore.md"
check "C1 integratore non usa git distruttivo" contains_in_file 'Nessun `--force`, nessun `reset --hard`' "$AGENTS/integratore.md"
check "C1 worker-mech si ferma se non e meccanico" contains_in_file 'non meccanico' "$AGENTS/worker-mech.md"

# C2 — bridge: validano prima di spendere credito
check "C2 cx usa yolo" contains_in_file 'codex exec --yolo' "$BIN/spawn-cx.sh"
check "C2 cx valida i modelli di routing" contains_in_file 'gpt-6-astra|gpt-5.6-sol|gpt-5.6-terra|gpt-5.6-luna' "$BIN/spawn-cx.sh"
check "C2 cx valida effort per modello" contains_in_file 'case "$MODEL:$EFFORT" in' "$BIN/spawn-cx.sh"
check "C2 cx impone Luna da medium" contains_in_file 'gpt-5.6-luna:medium|gpt-5.6-luna:high' "$BIN/spawn-cx.sh"
check "C2 cx impone Terra da medium" contains_in_file 'gpt-5.6-terra:medium|gpt-5.6-terra:high' "$BIN/spawn-cx.sh"
check "C2 cx consente Sol da low" contains_in_file 'gpt-5.6-sol:low|gpt-5.6-sol:medium|gpt-5.6-sol:high' "$BIN/spawn-cx.sh"
check "C2 cx vieta Luna low" does_not_contain 'gpt-5.6-luna:low' "$BIN/spawn-cx.sh"
check "C2 cx vieta Terra low" does_not_contain 'gpt-5.6-terra:low' "$BIN/spawn-cx.sh"
check "C2 cc usa bypassPermissions" contains_in_file '--permission-mode bypassPermissions' "$BIN/spawn-cc.sh"
check "C2 cc valida i modelli CC" contains_in_file 'opus|sonnet|haiku' "$BIN/spawn-cc.sh"
check "C2 bridge espongono dry-run" matches_in_file '\-\-dry-run' "$BIN/spawn-cx.sh"
check "C2 bridge scrivono il log per task" contains_in_file '.orchestratore/logs' "$BIN/spawn-cx.sh"
check "C2 bridge propagano l exit code" contains_in_file 'exit "$STATUS"' "$BIN/spawn-cc.sh"
check "C2 gate eseguibile del bridge presente" test -x "$ROOT/tests/check-bridge.sh"
if [ "${ORCHESTRATORE_SKIP_EXEC:-0}" = "1" ]; then
  ok "C2 gate eseguibile del bridge verde (saltato: gia coperto dagli invarianti di testo)"
else
  check "C2 gate eseguibile del bridge verde" bash "$ROOT/tests/check-bridge.sh"
fi
check "C2 adapter documenta i codici di rifiuto" contains_in_file 'modello fuori routing `65`' "$ADAPTER_CC"

COMMANDS="$ROOT/commands"
HOOKS="$ROOT/hooks"

# D1 — comandi: porta d'ingresso, non logica duplicata
check "D1 orchestra carica la skill come fonte di verita" contains_in_file 'è lei la fonte di verità' "$COMMANDS/orchestra.md"
check "D1 orchestra non chiede i default" contains_in_file "L'unica domanda ammessa all'avvio" "$COMMANDS/orchestra.md"
check "D1 orchestra impone il piano di parallelizzazione" contains_in_file '## Piano di parallelizzazione' "$COMMANDS/orchestra.md"
check "D1 status e sola lettura" contains_in_file 'Non aprire task, non delegare, non modificare file' "$COMMANDS/orchestra-status.md"
check "D1 status legge lo stato reale" contains_in_file 'mai dalla conversazione' "$COMMANDS/orchestra-status.md"
check "D1 status non stima" contains_in_file 'non stimare' "$COMMANDS/orchestra-status.md"

# D2 — hook: il divieto assoluto diventa eseguibile
check "D2 hooks.json registra PreToolUse su Bash" matches_in_file '"PreToolUse"[\s\S]*?"matcher": "Bash"' "$HOOKS/hooks.json"
check "D2 hooks.json registra SessionStart" contains_in_file '"SessionStart"' "$HOOKS/hooks.json"
check "D2 hooks.json usa CLAUDE_PLUGIN_ROOT" contains_in_file 'CLAUDE_PLUGIN_ROOT' "$HOOKS/hooks.json"
check "D2 guard attivo solo con un run vivo" contains_in_file '.orchestratore/brain.lock" ] || exit 0' "$HOOKS/guard-run.sh"
check "D2 guard blocca con exit 2" contains_in_file 'exit 2' "$HOOKS/guard-run.sh"
check "D2 analizzatore della guardia presente" test -s "$HOOKS/guard_run.py"
check "D2 guard delega l analisi all analizzatore" contains_in_file 'guard_run.py' "$HOOKS/guard-run.sh"
check "D2 guard senza python3 dichiara di non proteggere" contains_in_file 'NON e attiva' "$HOOKS/guard-run.sh"
check "D2 analizzatore copre il reset distruttivo" matches_in_file 'reset --hard' "$HOOKS/guard_run.py"
check "D2 analizzatore copre il merge amministrativo" contains_in_file '--admin' "$HOOKS/guard_run.py"
check "D2 analizzatore dichiara il modello di minaccia" contains_in_file 'MODELLO DI MINACCIA' "$HOOKS/guard_run.py"
check "D2 analizzatore elenca i limiti accettati" contains_in_file 'Limiti noti e accettati' "$HOOKS/guard_run.py"
check "D2 analizzatore tokenizza rispettando le virgolette" contains_in_file 'shlex.shlex' "$HOOKS/guard_run.py"
check "D2 analizzatore tratta i documenti inline come dato" contains_in_file 'togli_documenti_inline' "$HOOKS/guard_run.py"
check "D2 analizzatore guarda il sottocomando di git" contains_in_file 'analizza_git' "$HOOKS/guard_run.py"
check "D2 analizzatore salta i wrapper prima del programma" contains_in_file 'salta_prefissi' "$HOOKS/guard_run.py"
check "D2 session hook non modifica niente" contains_in_file 'Non modifica niente' "$HOOKS/session-run-state.sh"
check "D2 gate eseguibile degli hook presente" test -x "$ROOT/tests/check-hooks.sh"
if [ "${ORCHESTRATORE_SKIP_EXEC:-0}" = "1" ]; then
  ok "D2 gate eseguibile degli hook verde (saltato: gia coperto dagli invarianti di testo)"
else
  check "D2 gate eseguibile degli hook verde" bash "$ROOT/tests/check-hooks.sh"
fi

if ((failures > 0)); then
  printf 'ROSSO: %d controlli falliti\n' "$failures"
  exit 1
fi

printf 'VERDE: tutti i controlli regressione passano\n'
