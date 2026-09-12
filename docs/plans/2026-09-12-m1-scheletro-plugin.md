# Orchestratore plugin — Piano M1: scheletro plugin

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trasformare `~/Dev/skills/orchestratore` in un repo plugin dual-runtime installabile in Claude Code (CC) e Codex (cx), con la skill riscritta secondo la spec, reference, template e test strutturale verde.

**Architecture:** Repo git annidato sotto `~/Dev/skills/orchestratore` (gitignorato dall'ombrello), manifest `.claude-plugin/` per CC e `.codex-plugin/` + `.agents/plugins/marketplace.json` per cx. La skill è markdown puro: un `SKILL.md` snello in italiano più `references/` tematiche. Un solo script di test bash (`tests/check-structure.sh`) fa da gate: prima rosso, poi verde a ogni task.

**Tech Stack:** bash, jq, git, gh, `claude plugin`, `codex plugin`. Nessuna dipendenza nuova.

**Spec:** `docs/specs/2026-09-12-orchestratore-plugin-design.md` (nello stesso repo). Il piano argomenta dalla spec: leggila prima.

## Stato di esecuzione Codex — 2026-09-12

**Contratto di autonomia:** run mode `milestone-budget`; budget `1` milestone (M1);
unattended `no`; tetto domande aperte `8`; tetto effettivo `1` implementer + `1`
reviewer attivi (capacità runtime: 3 worker oltre al coordinatore); stop prima di installazioni
fuori workspace, rimozione dei symlink, `gh repo create` e `git push`. Le conferme specifiche
sono state ricevute prima di ciascun gruppo di azioni T8, poi le azioni sono state completate.
Contesto root: percentuale non disponibile, checkpoint per task; token/costi: non disponibili.

**Base:** umbrella `4e3c08fea9c96668bfb2fbfc7a61cae9bdba27d6`, branch `main`,
impronta stato iniziale `323ac7704a36e4252963d5b27f0b36781b33ec0d51f64fd46b4a9d12af1dfdc8`.
Modifiche preesistenti da preservare: `.gitignore`, `CLAUDE.md`, `AGENTS.md` e
`dev-cc/audit-fulgaro/`. I documenti M1 sono nuovi e appartengono a questa milestone.

**Ambiente:** macOS arm64, 12 CPU, 24 GiB; `bash`, `jq`, `git`, `gh`, `claude`, `codex`
presenti. Workload `cpu-ram` leggero, target locale; nessun build, browser, container o DB.
Profilo compute `local-lightweight-2026-09-12`, fallback: bloccare i processi pesanti.

| Task | Stato | Owner / file | Dipendenze | Risultato e criterio di pronto | Verifica |
|---|---|---|---|---|---|
| T1 | completato | implementer T1: `~/Dev/.gitignore`, repo plugin, `tests/check-structure.sh` | ricognizione completa | repo annidato e gate rosso registrato; commit previsti dal piano | reviewer sol: `OK` su `ee5f390`; 21 KO, exit 1 |
| T2 | completato | implementer T2: quattro manifest | T1 | manifest CC/cx `0.1.0` validi | reviewer sol: `OK` su `d02a4f6`; 4 controlli OK |
| T3 | completato | implementer T3: `skills/orchestratore/SKILL.md` | T2 | contratto italiano conforme, massimo 250 righe | reviewer sol: `OK` su `5ecf6b7`; contenuto identico, 10/10 controlli `OK` |
| T4 | completato | implementer T4: `routing.md`, `lane.md`, `skill-map.md`, rimozione `runtime-bridges.md` | T3 | reference di metodo coerenti | reviewer sol: `OK` su `eb06a1c`; 6 controlli T4 `OK` |
| T5 | completato | implementer T5: adapter runtime, `project-adapter.md`, rimozione `skill-activation.md`; coordinatore integra `~/.codex/AGENTS.md` dopo conferma esterna | T4 | reference runtime complete e path coerenti | reviewer sol: `OK` su `007012a`; gate reference tutti `OK`; path globali aggiornati in T8 |
| T6 | completato | implementer T6: `templates/*` | T5 locale | tre template conformi allo schema | reviewer sol: `OK` su `0612601`; 3 controlli `OK`, TOML valido |
| T7 | completato | implementer T7: `README.md`, log raw verde | T6 | README presente e gate interamente verde | reviewer sol: `OK` su `8083b63`; 31/31 `OK`, log raw identico |
| T8 | completato | coordinatore: install, symlink, inventari, GitHub | T7 + conferme | plugin installato una volta per runtime e repo remoto privato | CC e cx `0.1.0` enabled; symlink rimossi; repo PRIVATE; umbrella `fcea471` |

Decisioni aperte: nessuna. Autorizzazioni T8 richieste, ricevute ed eseguite:
installazioni/modifiche fuori workspace; rimozione symlink; creazione repo e push.

## Global Constraints

- `SKILL.md` in italiano, massimo 250 righe, frontmatter `name: orchestratore` e `description` con i trigger.
- Manifest e chiavi tecniche in inglese. Commenti in italiano, nomi di file e variabili in inglese.
- Nessun placeholder (`TODO`, `TBD`) nei file consegnati.
- Nessun path `/Users/andreapesce` cablato dentro `skills/`, salvo in `references/adapter-cx.md` dove serve il path del catalogo.
- Modelli e tier esattamente come spec §3.2: cervello fable / gpt-6-astra; verifica opus / gpt-5.6-sol; importante opus / gpt-5.6-sol; basic sonnet / gpt-5.6-terra; meccanico haiku / gpt-5.6-luna.
- GIF celebrazione: URL esatti già presenti nella skill attuale (delfino `AhV2lfKBfEvcEqj6h3`, balena `Q6rD2TLgqMiHf4a0Pt`); frase esatta `una milestone meno`.
- Tetto default 3 milestone / 6 worker. Peso default `dev cx 100 / cc 0`, `verifica cc`, `valido_fino 2026-10-12`.
- Git: commit nel repo plugin liberi (Andrea ha approvato la milestone). `git push` e `gh repo create` solo dopo conferma esplicita di Andrea nel turno in cui avviene (regola bypass mode del CLAUDE.md).
- Commit message senza attribuzioni automatiche salvo la riga `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## File Structure (fine M1)

```
~/Dev/skills/orchestratore/                 # repo git proprio
├── .gitignore
├── .claude-plugin/plugin.json              # manifest CC
├── .claude-plugin/marketplace.json         # marketplace CC (un plugin, source ./)
├── .codex-plugin/plugin.json               # manifest cx
├── .agents/plugins/marketplace.json        # marketplace cx
├── skills/orchestratore/
│   ├── SKILL.md
│   └── references/
│       ├── routing.md                      # tier, modelli, effort, regole builder≠verificatore
│       ├── lane.md                         # milestone senza Fase 1, verificatore, pre-merge
│       ├── skill-map.md                    # skill obbligatorie per tipo di task + path
│       ├── adapter-cc.md                   # come il cervello CC lancia e governa
│       ├── adapter-cx.md                   # come il cervello cx lancia e governa; catalogo
│       ├── project-adapter.md              # avvio in progetto nuovo / ripresa
│       └── codex-skills-catalog.jsonl      # invariato
├── templates/
│   ├── run.md                              # contratto + registro task + handoff
│   ├── config.toml                         # peso default globale / per progetto
│   └── state.toml                          # stato credito globale
├── tests/check-structure.sh                # gate strutturale
├── docs/specs/…                            # già presente
├── docs/plans/…                            # questo piano
└── README.md
```

Rimossi rispetto a oggi: `references/runtime-bridges.md` (assorbito in `routing.md`), `references/skill-activation.md` (assorbito in `adapter-cx.md`). `agents/`, `commands/`, `hooks/`, `bin/` arrivano in M2 e M3.

---

### Task 1: Repo annidato e gate strutturale rosso

**Files:**
- Modify: `~/Dev/.gitignore` (dopo la riga `Marketing/`)
- Create: `~/Dev/skills/orchestratore/.gitignore`
- Create: `~/Dev/skills/orchestratore/tests/check-structure.sh`

**Interfaces:**
- Produces: `tests/check-structure.sh` con exit 0 solo se tutti i controlli passano; ogni task successivo lo porta più vicino al verde. Funzione `check <descrizione> <comando>` che stampa `OK`/`KO` e accumula i fallimenti.

- [x] **Step 1: Stacca la cartella dall'ombrello**

```bash
cd ~/Dev
git rm -r --cached skills/orchestratore
python3 - <<'EOF'
import pathlib
p = pathlib.Path(".gitignore"); s = p.read_text()
anchor = "markitdown/\nMarketing/\n"
assert anchor in s
s = s.replace(anchor, anchor + "/skills/orchestratore/\n", 1)
p.write_text(s)
EOF
git status --short | head
```

Atteso: righe `D  skills/orchestratore/...` per i 5 file tracciati e ` M .gitignore`. Nessun altro file di sotto-progetti.

- [x] **Step 2: Commit nell'ombrello**

```bash
cd ~/Dev
git add .gitignore skills/orchestratore
git commit -m "skills: orchestratore diventa repo annidato (plugin)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git status --short skills/orchestratore
```

Atteso: nessuna riga per `skills/orchestratore` (ignorato).

- [x] **Step 3: Inizializza il repo plugin**

```bash
cd ~/Dev/skills/orchestratore
git init -b main
cat > .gitignore <<'EOF'
.DS_Store
node_modules/
*.log
tests/tmp/
EOF
mkdir -p tests skills/orchestratore
# La skill oggi sta nella radice: portala nella struttura plugin
mv SKILL.md references skills/orchestratore/
ls skills/orchestratore
```
Atteso: `SKILL.md  references`.

- [x] **Step 4: Scrivi il gate strutturale (rosso)**

Crea `tests/check-structure.sh`:

```bash
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
check "SKILL.md tetto 3 milestone / 6 worker" grep -q '3 milestone / 6 worker' "$SKILL"
check "SKILL.md regola builder != verificatore" grep -qi 'modello diverso' "$SKILL"

# References
for f in routing.md lane.md skill-map.md adapter-cc.md adapter-cx.md project-adapter.md codex-skills-catalog.jsonl; do
  check "references/$f esiste" test -s "$REFS/$f"
done
check "references vecchie rimosse" bash -c "! test -e '$REFS/runtime-bridges.md' && ! test -e '$REFS/skill-activation.md'"
check "routing.md contiene i 10 modelli" bash -c "for m in fable gpt-6-astra opus gpt-5.6-sol sonnet gpt-5.6-terra haiku gpt-5.6-luna; do grep -q \"\$m\" '$REFS/routing.md' || exit 1; done"
check "lane.md contiene regola verdetto su hash" grep -qi 'hash' "$REFS/lane.md"
check "lane.md contiene pre-merge" grep -q 'suggerisco merge' "$REFS/lane.md"

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
```

```bash
chmod +x tests/check-structure.sh
```

- [x] **Step 5: Esegui il gate, deve essere rosso**

Run: `tests/check-structure.sh; echo "exit=$?"`
Atteso: molte righe `KO`, ultima riga `ROSSO: N controlli falliti`, `exit=1`. Salva l'output raw nel log della milestone (prova di rosso).

- [x] **Step 6: Primo commit del repo plugin**

```bash
cd ~/Dev/skills/orchestratore
git add -A
git commit -m "chore: repo plugin orchestratore, gate strutturale rosso

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Manifest CC e cx

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.claude-plugin/marketplace.json`
- Create: `.codex-plugin/plugin.json`
- Create: `.agents/plugins/marketplace.json`

**Interfaces:**
- Produces: nome plugin `orchestratore`, marketplace `orchestratore`, versione `0.1.0`. In CC la skill sarà `orchestratore:orchestratore`; in cx idem.

- [x] **Step 1: Manifest CC**

`.claude-plugin/plugin.json`:
```json
{
  "name": "orchestratore",
  "version": "0.1.0",
  "description": "Orchestratore multi-agente dual-runtime (Claude Code + Codex): cervello Fable, worker a tier, verifica con modello diverso, gate pre-merge, peso CC/cx, celebrazione milestone.",
  "author": {
    "name": "Andrea Pesce",
    "url": "https://github.com/queondache"
  },
  "homepage": "https://github.com/queondache/orchestratore",
  "repository": "https://github.com/queondache/orchestratore",
  "license": "UNLICENSED",
  "keywords": ["orchestrator", "multi-agent", "milestone", "codex", "claude-code"]
}
```

`.claude-plugin/marketplace.json`:
```json
{
  "$schema": "https://www.schemastore.org/claude-code-marketplace.json",
  "name": "orchestratore",
  "description": "Marketplace privato di Andrea per il plugin orchestratore.",
  "owner": { "name": "Andrea Pesce" },
  "plugins": [
    {
      "name": "orchestratore",
      "description": "Orchestratore multi-agente dual-runtime (CC + cx).",
      "source": "./",
      "category": "development"
    }
  ]
}
```

- [x] **Step 2: Manifest cx**

`.codex-plugin/plugin.json`:
```json
{
  "name": "orchestratore",
  "version": "0.1.0",
  "description": "Orchestratore multi-agente dual-runtime per Codex e Claude Code.",
  "author": { "name": "Andrea Pesce", "url": "https://github.com/queondache" },
  "homepage": "https://github.com/queondache/orchestratore",
  "repository": "https://github.com/queondache/orchestratore",
  "license": "UNLICENSED",
  "keywords": ["orchestrator", "multi-agent", "milestone", "codex"],
  "skills": "./skills/",
  "interface": {
    "displayName": "Orchestratore",
    "shortDescription": "Cervello multi-agente per milestone parallele",
    "longDescription": "Coordina worker su Codex e Claude Code: contratto di autonomia, routing per tier, verifica con modello diverso dal builder, gate pre-merge, registro quesiti, celebrazione milestone.",
    "developerName": "Andrea Pesce",
    "category": "Development",
    "capabilities": ["Instructions"],
    "defaultPrompt": [
      "Usa orchestratore per avviare il run sulle milestone di ROADMAP.md.",
      "riprendi",
      "orchestra status"
    ]
  }
}
```

`.agents/plugins/marketplace.json`:
```json
{
  "name": "orchestratore",
  "interface": { "displayName": "Orchestratore" },
  "plugins": [
    {
      "name": "orchestratore",
      "source": {
        "source": "url",
        "url": "https://github.com/queondache/orchestratore.git",
        "ref": "main"
      },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Development"
    }
  ]
}
```

- [x] **Step 3: Verifica i 4 controlli manifest**

Run: `tests/check-structure.sh | grep -E 'plugin.json|marketplace.json'`
Atteso: 4 righe `OK`.

- [x] **Step 4: Commit**

```bash
git add .claude-plugin .codex-plugin .agents
git commit -m "feat: manifest plugin per Claude Code e Codex

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: SKILL.md riscritto

**Files:**
- Modify: `skills/orchestratore/SKILL.md` (sostituzione integrale)

**Interfaces:**
- Consumes: nomi file di `references/` e `templates/` definiti nel File Structure; verbi comando `/orchestra start|status|peso|stop|riprendi|credito` (implementati in M3); agent `worker-impl`, `worker-mech`, `verificatore`, `pre-merge` (M2).
- Produces: il contratto di comportamento del cervello. Tutti gli altri file lo dettagliano, non lo contraddicono.

- [x] **Step 1: Sostituisci il file con questo contenuto**

```markdown
---
name: orchestratore
description: Cervello multi-agente per progetti con SPEC.md e ROADMAP.md già chiare. Avvia un run che sviluppa più milestone in parallelo con worker su Codex (cx) e Claude Code (CC), verifica ogni consegna con un modello diverso dal builder, accumula le domande e si ferma solo quando una risposta è bloccante. Usa quando Andrea scrive "/orchestra", "orchestratore", "avvia il run", "più milestone in parallelo", "sviluppo notturno", "riprendi", "credito esaurito", o chiede un sistema multi-agente riusabile.
---

# Orchestratore

Trasforma una ROADMAP in consegne verificate. Il piano è stato persistente su file, non un
servizio: il cervello usa i tool reali della sessione per lanciare e governare i worker.

Glossario: **CC** Claude Code · **cx** Codex · **cervello** la sessione che esegue questa
skill · **worker** agente lanciato dal cervello · **lane** una milestone in lavorazione.

## 0. Avvio sicuro

1. Leggi le istruzioni del repo (CLAUDE.md, AGENTS.md, SPEC.md, ROADMAP.md, progress.md,
   `.claude/decisioni.md`). Le decisioni di prodotto del progetto prevalgono su questa skill.
2. Controlla `.orchestratore/brain.lock`: se vivo (pid esistente, aggiornato da meno di
   10 minuti) fermati e chiedi. Se stantio, segnalalo e sovrascrivi solo su conferma.
3. Leggi `~/.orchestratore/state.toml` (credito) e `config.toml` globale + `.orchestratore/config.toml`
   del progetto (peso). Se `valido_fino` è passato, chiedi il nuovo peso invece di applicarlo.
4. Ispeziona working tree, branch, worktree, agenti vivi. Conserva il lavoro che non è tuo.
5. Verifica toolchain, ambiente di test, capacità agenti, lane esterne.
6. Se `.orchestratore/run.md` esiste con `stato: handoff`, sei in ripresa: vai a §7.
7. Altrimenti chiedi **una** cosa: `standard` (cervello Fable 5.1 in CC) o `alternativo`
   (cervello gpt-6-astra in cx). Poi scrivi il contratto di autonomia (§1).

Progetto nuovo o ripresa: leggi [project-adapter](references/project-adapter.md).

## 1. Contratto di autonomia

Persisti in `.orchestratore/run.md` (template in `templates/run.md`) prima di delegare:

```text
Cervello: cc-fable | cx-gpt-6-astra
Run mode: milestone-budget | while-quality-high
Milestone budget: <n | tutte | n/a>   (tutte = milestone aperte in ROADMAP.md all'avvio)
Peso: dev cx <n> / cc <n>; verifica <cc|cx|opposto>
Tetto: <k> milestone / <w> worker  (default 3 milestone / 6 worker)
Tetto domande aperte: <n>
Stop aggiuntivi: <condizioni osservabili>
Autorizzazioni Git: <dal mandato del progetto: commit+push+PR | solo lettura>
Al limite CC: handoff e stop
Credito: cc <ok|esaurito>; cx <ok|esaurito>
```

`milestone-budget`: fermati quando N milestone sono verificate e pronte all'integrazione.
Parziali e bloccate non contano. `while-quality-high`: continua solo finché ogni gate passa:
contratto non ambiguo, dipendenze e ambiente pronti, verifica focalizzata, review senza
finding grave aperto, nessuna domanda che cambi contratto o definition of done. Due
tentativi falliti sullo stesso gate, review ripetutamente inconcludente o comportamento non
verificabile = qualità non più alta: checkpoint e stop. Una richiesta di lavoro autonomo non
autorizza a completare la roadmap intera se Andrea non scrive `tutte`.

## 2. Ruoli, modelli, skill

Tabella completa e regole in [routing](references/routing.md). In sintesi: il cervello sceglie
per ogni task tier, runtime, modello ed effort e li scrive nel contratto del task. Default:
**cx sviluppa, CC orchestra e verifica**. Il verificatore ha sempre un **modello diverso** dal
builder, runtime opposto quando il peso lo consente. Fable orchestra e non verifica, con
un'unica eccezione: modalità solo-CC su task importante (opus costruisce, fable verifica).

Skill obbligatorie per tipo di task in [skill-map](references/skill-map.md): design,
architettura, TDD, lane. Ai worker passi nome e path esatto. Nessun worker inventa o
installa skill.

Tetto 3 milestone / 6 worker per progetto, tetti non obiettivi: apri parallelo solo con
contratti congelati, dipendenze soddisfatte, file senza owner sovrapposti, verifica pronta.
Chi scrive non revisiona il proprio codice. Appena una consegna è pronta, la review ha
precedenza su nuova implementazione.

## 3. Delega

Registra in `run.md` prima di lanciare il worker:

```text
Task / milestone:
Risultato osservabile per l'utente:
Dipendenze completate e contratto congelato:
File scrivibili (un owner per file):
File condivisi che integra il cervello:
Tier / runtime / modello / effort:
Skill obbligatorie: <nome → path esatto>
Verifica ammessa e ambiente:
Criterio di completamento:
Decisioni aperte e condizioni di stop:
Prossimo checkpoint:
```

Come lanciare: [adapter-cc](references/adapter-cc.md) se il cervello è CC,
[adapter-cx](references/adapter-cx.md) se è cx. I worker non delegano. Solo il cervello
scrive `run.md`, il registro quesiti e l'handoff. Passa sempre cwd e boundary del progetto.

## 4. Lane: dalla milestone alla parola "merge"

Protocollo in [lane](references/lane.md). Ogni lane segue la skill `milestone` senza la
Fase 1: il perimetro lo produci tu, senza chiedere approvazione ad Andrea. Sequenza:
perimetro → worker implementa (Fasi 0, 2) → verificatore con modello diverso (Fase 3, OK
valido solo sull'hash che va in PR) → PR (Fase 4, mai merge) → **gate pre-merge** con un
terzo modello che risponde `suggerisco merge: sì | no` → presenti ad Andrea e attendi la
parola `merge`. Domande del worker: nel registro quesiti, mai ad Andrea.

## 5. Registro quesiti e gate del debito

Le domande vanno in `.claude/decisioni.md`, sezione registro quesiti: ID, testo, impatto,
task bloccati, stato. Prima di aprire ogni milestone esegui il gate del debito. Il debito è
**tossico** se una domanda aperta cambia contratto, architettura, sicurezza, schema dati,
comportamento utente, oracolo di test o definition of done della prossima milestone; se una
milestone precedente andrebbe dichiarata verificata per assunzione; o se il tetto domande è
raggiunto. Con debito tossico: chiudi solo il checkpoint sicuro in volo, poi poni ad Andrea
**una domanda per volta, la più piccola che sblocca**, in modo interattivo (CC: tool di
domanda strutturata con raccomandazione per prima; cx: fermi il turno con la domanda in
chiaro). Domande non bloccanti si accumulano e compaiono nel report come conteggio. Non
ripetere una domanda invariata. Il silenzio non è mai una decisione.

## 6. Peso e credito

Il peso guida solo le assegnazioni nuove; i task in volo finiscono dove sono. Override in
corsa: `/orchestra peso dev cx 60`. Credito (`~/.orchestratore/state.toml`, condiviso tra
tutte le sessioni aperte):
- `/orchestra credito cx esaurito` → peso `dev cc 100, verifica cc`, routing solo-CC.
  I task cx in volo finiscono il checkpoint corrente, poi vengono riassegnati se non consegnano.
- `/orchestra credito cc esaurito` con cervello CC → scrivi l'handoff, marca il flag in
  `run.md`, chiedi ad Andrea di aprire cx e scrivere `riprendi`. Il cervello cx parte con
  `dev cx 100, verifica cx`.
- `/orchestra credito <runtime> ok` → ripristina il peso salvato prima dell'esaurimento.

## 7. Visibilità, celebrazione, handoff, ripresa

Report (`/orchestra status`, a ogni cambio di stato, comunque ogni 10 minuti):

```text
In corso: <milestone, owner, fase, modello/runtime>
Verificato dall'ultimo report: <evidenza | niente di nuovo>
Domande: <aperte/tetto; bloccanti con ID e task | nessuna>
Peso in uso: dev cx n / cc n; verifica <…>; credito cc <ok|esaurito>, cx <ok|esaurito>
Contesto: <percentuale se il runtime la espone | non disponibile>
Prossimo checkpoint: <gate osservabile>
```

**Celebrazione**, a ogni milestone verificata e chiusa: una GIF cliccabile, alternando
delfino e balena tra celebrazioni consecutive, poi la frase esatta e il recap:

```markdown
[![Delfino che salta](https://media.giphy.com/media/AhV2lfKBfEvcEqj6h3/giphy.gif)](https://giphy.com/gifs/guitarjamz-dolphin-jump-surfing-drone-shot-AhV2lfKBfEvcEqj6h3)

una milestone meno

🟢 <completate> milestone completate
🟡 <bloccate da Andrea> milestone bloccate da Andrea
🔴 <mancanti> milestone mancanti per finire
```

Balena: `[![Balena che sbuffa](https://media.giphy.com/media/Q6rD2TLgqMiHf4a0Pt/giphy.gif)](https://giphy.com/gifs/whale-whales-savethewhales-Q6rD2TLgqMiHf4a0Pt)`.
Conteggi ricalcolati da `run.md`, mai dalla conversazione. `Bloccate da Andrea` = ferme per
una sua decisione o autorizzazione; blocchi tecnici non entrano nel giallo. `Mancanti` =
totale del piano meno completate. Se il totale non è ancora finito, fissalo prima di chiudere
la prima milestone.

**Handoff** (limite contesto, credito esaurito, `/orchestra stop`, fine run): in `run.md`
scrivi obiettivo, contratto e budget residuo, task attivi con owner e stato, revisione base
più impronta delle modifiche non committate, domande aperte con impatto, evidenze verificate,
una sola prossima azione. Poi `stato: handoff` e rilascia il lock.

**Ripresa** (`riprendi` o `/orchestra riprendi`): verifica agenti vivi con i tool della
sessione, impronta del filesystem e stato Git; chiudi consegne e review verificabili prima di
aprire fronti nuovi; riparti dalla prossima azione registrata. Lo stato serializzato non prova
che un worker sia vivo o che un lavoro sia finito.

**Contesto**: target 50%, tetto 70% per ogni thread. Vale in modo forte per i worker (turno
che finisce a un checkpoint) e best effort per il cervello. Al 50% non aprire task nuovi;
finisci solo lo step atomico e persisti. Nessuna promessa di rollover automatico.

## 8. Confini

- Sviluppare non autorizza commit, push, merge, deploy, reset di schema, messaggi esterni,
  dati di produzione, acquisti. Segui il mandato del progetto scritto nel contratto; per
  ciò che manca chiedi prima, mai dopo.
- Un solo processo pesante locale per volta, anche tra progetti diversi
  (`~/.orchestratore/heavy.lock`): build, suite DB, browser, container non si sovrappongono.
- Ottimizza criteri di accettazione verificati per token: passa contratti e path, non
  documenti interi; riusa ricognizioni con base dichiarata; misura token solo se il runtime
  li espone, altrimenti scrivi «non disponibile».
- Non costruire strumenti di coordinamento nuovi salvo richiesta esplicita.

## Anti-pattern

- Chiedere ad Andrea di approvare ogni perimetro dentro un run autorizzato.
- Verificatore o pre-merge con lo stesso modello del builder.
- Dichiarare una milestone completata senza verdetto sull'hash in PR.
- Riempire gli slot di concorrenza senza lavoro indipendente sul percorso critico.
- Ripetere una domanda invariata, o trasformare il silenzio in una decisione.
- Contare le milestone dalla conversazione invece che da `run.md`.
- Due cervelli vivi sullo stesso progetto.
```

- [x] **Step 2: Verifica i controlli SKILL.md**

Run: `tests/check-structure.sh | grep 'SKILL.md'`
Atteso: 10 righe `OK`. Se `<= 250 righe` è KO, accorcia §7 o §8 senza togliere regole.

- [x] **Step 3: Commit**

```bash
git add skills/orchestratore/SKILL.md
git commit -m "feat(skill): SKILL.md riscritto secondo la spec del 12/09

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: References di metodo: routing, lane, skill-map

**Files:**
- Create: `skills/orchestratore/references/routing.md`
- Create: `skills/orchestratore/references/lane.md`
- Create: `skills/orchestratore/references/skill-map.md`
- Delete: `skills/orchestratore/references/runtime-bridges.md`

**Interfaces:**
- Consumes: tier e regole di SKILL.md §2 e §4.
- Produces: nomi tier `cervello`, `verifica`, `importante`, `basic`, `meccanico`; nomi agent `worker-impl`, `worker-mech`, `verificatore`, `pre-merge` usati in M2.

- [x] **Step 1: routing.md**

```markdown
# Routing: tier, modelli, effort

Il cervello sceglie per ogni task tier, runtime, modello ed effort. Li scrive nel contratto
del task. I nomi modello sono quelli esposti oggi dai due runtime; se un runtime non li
espone, usa il più vicino e scrivi nel contratto quale hai usato.

| Tier | Quando | CC | cx | Effort default |
|---|---|---|---|---|
| cervello | sempre | fable | gpt-6-astra | alto |
| verifica | ogni consegna | opus | gpt-5.6-sol | alto |
| importante | tocca schema, migrazioni, auth, pagamenti, multi-tenancy, PII, sicurezza, concorrenza | opus | gpt-5.6-sol | alto |
| basic | tutto il resto | sonnet | gpt-5.6-terra | medio |
| meccanico | inventari, lint, rinomine, test deterministici | haiku | gpt-5.6-luna | basso |

Criterio "importante": tier 2 e 3 di `senior-architect` §5.

## Regole

1. **Builder ≠ verificatore**, sempre a livello di modello. Runtime opposto quando il peso
   lo consente. Il gate pre-merge usa un terzo modello, diverso dal builder e, se i modelli
   disponibili lo consentono, dal verificatore.
2. Default (peso `dev cx 100 / cc 0`, `verifica cc`): builder terra o sol su cx,
   verificatore opus su CC, pre-merge sol su cx (o astra se il builder era sol).
3. **Solo-CC** (cx esaurito): basic → sonnet costruisce, opus verifica, pre-merge haiku in
   lettura con checklist; importante → opus costruisce, **fable verifica** (unica eccezione a
   "Fable non verifica"), pre-merge sonnet.
4. **Solo-cx** (CC esaurito): basic → terra costruisce, sol verifica, pre-merge luna con
   checklist; importante → sol costruisce, gpt-6-astra verifica, pre-merge terra.
5. Escalation di un tier solo su trigger concreto: contratto ambiguo, due tentativi
   falliti, disaccordo builder/verificatore, rischio alto scoperto in corso.
   De-escalation sul follow-up meccanico.
6. Effort: il cervello può alzare o abbassare l'effort default di un livello; lo scrive nel
   contratto. In cx si passa con `-c model_reasoning_effort=<low|medium|high>`; in CC con la
   definizione dell'agent o l'istruzione nel prompt.
7. Mai dichiarare che un modello ha girato se il runtime non lo riporta. Il log del bridge
   e il campo `model` della risposta sono l'unica evidenza.

## Agent CC del plugin (M2)

| Agent | Modello | Uso |
|---|---|---|
| `worker-impl` | opus o sonnet, scelto dal cervello | implementazione importante o basic |
| `worker-mech` | haiku | lavoro meccanico |
| `verificatore` | opus | verifica indipendente, sola lettura |
| `pre-merge` | scelto dal cervello, diverso da builder e verificatore | gate pre-merge, sola lettura + `gh` |

In cx non esistono agent dichiarati: il cervello cx passa modello ed effort a ogni thread
o a ogni `codex exec`.
```

- [x] **Step 2: lane.md**

```markdown
# Lane: dalla milestone alla parola "merge"

Una lane è una milestone di ROADMAP.md in lavorazione. Segue la skill `milestone`
(`~/Dev/skills/milestone/SKILL.md`) con queste differenze.

## Fase 1 la produce il cervello

Il cervello scrive il `PERIMETRO` nel formato della skill `milestone` (obiettivo, definition
of done verificabile senza Andrea, aree ammesse, fuori perimetro, vincoli dalla SPEC, STOP)
e lo passa al worker come contratto. **Nessuna approvazione di Andrea per milestone**: il
contratto di autonomia copre il run. Un perimetro passato è congelato: il worker non lo
ridiscute, al massimo si ferma per una delle tre condizioni STOP.

## Fase 0 e Fase 2 nel worker

- Fase 0 rossa (albero sporco, main non allineato, build/test/lint rossi): il worker si
  ferma e riporta al cervello, non ad Andrea. Il cervello decide se sanare o sospendere.
- Branch `m/<slug>` da `main`, o il worktree assegnato.
- Esecuzione con `superpowers:writing-plans` poi TDD. Domande: nel registro quesiti di
  `.claude/decisioni.md`, mai ad Andrea. Il cervello valuta se sono bloccanti.
- Nessun file fuori dalle aree ammesse, nessuna dipendenza nuova senza motivo nel ledger.

## Fase 3: verificatore assegnato dal cervello

Il worker consegna: diff, hash, comandi eseguiti con output, limiti residui. Il cervello
congela le scritture del builder e lancia il verificatore (agent `verificatore` in CC, o
thread cx con `gpt-5.6-sol`) passando **solo** perimetro e branch. Mai il piano, il ledger o
l'opinione del builder.

- OK → Fase 4.
- OK CON RISERVE → correzioni dentro perimetro, un secondo giro, poi Fase 4 con riserve nel report.
- KO → correzioni, nuovo giro. Massimo 2 KO consecutivi; al terzo la lane si sospende e la
  milestone entra tra le domande per Andrea.
- **Regola dell'hash**: l'OK vale solo sul codice esatto che va in PR. Ogni correzione dopo
  un verdetto, anche una riga, obbliga a un giro di conferma che non conta nel tetto.
  Nessuna PR senza OK sull'hash che contiene.

## Fase 4: PR

Secondo le autorizzazioni del contratto: commit, push, PR verso `main` con il perimetro nel
corpo, ROADMAP.md aggiornata con link PR. Mai merge. Se il contratto è solo lettura, il
cervello presenta il branch pronto e chiede l'autorizzazione.

## Gate pre-merge

Con PR aperta e CI riportata da `gh pr checks`, il cervello lancia l'agent `pre-merge`
(modello diverso dal builder e, se possibile, dal verificatore; vedi routing regola 1) con:
perimetro, diff della PR, stato CI, verdetto del verificatore con hash. Output obbligatorio:

```text
PRE-MERGE PR #<n> hash <sha>
suggerisco merge: sì | no
motivi (max 3):
- …
rischi residui: <elenco | nessuno>
```

`no` → il cervello riapre la lane sul builder con i motivi. `sì` → il cervello presenta ad
Andrea:

```text
MILESTONE: <nome>   PR: #<n>   CI: <stato da gh>
VERIFICATORE: <OK | OK CON RISERVE + elenco>   giri: <n>
PRE-MERGE (<modello>): suggerisco merge: sì
Scrivi 'merge' per chiudere.
```

## Merge e chiusura

Solo alla parola `merge` di Andrea: `gh pr merge <n> --squash --delete-branch`, verifica
con `gh pr view <n> --json state,mergedAt`, output raw nel report, `main` locale aggiornato.
Poi la milestone è **chiusa**: aggiorna i contatori in `run.md` e celebra (SKILL.md §7).

Stati distinti in `run.md`: `implementata`, `verificata`, `pronta` (pre-merge sì),
`integrata` (merge fatto), `chiusa` (ROADMAP e contatori aggiornati).
```

- [x] **Step 3: skill-map.md**

```markdown
# Skill obbligatorie per tipo di task

Il cervello scrive nel contratto del task nome e path esatto di ogni skill richiesta. Un
worker non inventa né installa skill. Se una skill manca sul runtime scelto, il cervello
sposta il task sull'altro runtime oppure passa il file per path.

| Tipo di task | Skill | CC | cx |
|---|---|---|---|
| Architettura, DB, tier, sicurezza | `senior-architect` + skill di progetto (`mesa-senior-architect`, `pau-senior-architect`, `zerocampo-senior-architect`) | nativa | per path `~/Dev/skills/<nome>/SKILL.md` |
| Implementazione con test | `superpowers:test-driven-development`, `superpowers:systematic-debugging` | nativa | per path nella cache plugin CC (`~/.claude/plugins/cache/claude-plugins-official/superpowers/<versione>/skills/<nome>/SKILL.md`) |
| Piano di una lane | `superpowers:writing-plans` | nativa | per path come sopra |
| UI nuova | CC: `frontend-design` o `impeccable`; cx: `design-taste-frontend`, `high-end-visual-design`, `ui-ux-pro-max` | nativa | nativa |
| Redesign | `redesign-existing-projects` | nativa | nativa |
| Lane milestone | `milestone` | nativa | per path `~/Dev/skills/milestone/SKILL.md` |
| Verifica | agent `verificatore` del plugin | nativo | opus via bridge, o thread `gpt-5.6-sol` con il testo dell'agent per path |
| Deploy Vercel | plugin `vercel` | nativo | nativo |
| Output per Andrea | `i-have-adhd` sempre attiva; `caveman` se attiva | nativa | nativa |

Prima di ogni assegnazione UI il cervello controlla se il progetto impone una skill di design
(CLAUDE.md del progetto): quella vince sulla tabella.

Inventario completo lato CC: `~/Dev/skills/cc-installed-plugins.md`. Lato cx:
`references/codex-skills-catalog.jsonl` (cerca con `rg -i <parola>`; non caricarlo intero).
```

- [x] **Step 4: Rimuovi runtime-bridges.md e verifica**

```bash
git rm -q skills/orchestratore/references/runtime-bridges.md
tests/check-structure.sh | grep -E 'routing|lane|skill-map|references vecchie'
```
Atteso: `OK` per routing.md, lane.md (due controlli), skill-map.md; `references vecchie rimosse` ancora `KO` finché esiste skill-activation.md (Task 5).

- [x] **Step 5: Commit**

```bash
git add skills/orchestratore/references
git commit -m "feat(references): routing, lane, skill-map

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: References di runtime: adapter-cc, adapter-cx, project-adapter

**Files:**
- Create: `skills/orchestratore/references/adapter-cc.md`
- Create: `skills/orchestratore/references/adapter-cx.md`
- Modify: `skills/orchestratore/references/project-adapter.md` (sostituzione integrale)
- Delete: `skills/orchestratore/references/skill-activation.md`

**Interfaces:**
- Consumes: bridge `bin/spawn-cx.sh <modello> <effort> <cwd> <prompt-file>` e `bin/spawn-cc.sh <modello> <cwd> <prompt-file>` (implementati in M2; qui solo descritti con la firma esatta).
- Produces: procedura concreta per lanciare worker da ciascun runtime.

- [x] **Step 1: adapter-cc.md**

```markdown
# Adapter Claude Code: il cervello è Fable in CC

## Worker CC nativi

Tool `Agent`. Regole:
- `subagent_type`: `orchestratore:worker-impl`, `orchestratore:worker-mech`,
  `orchestratore:verificatore`, `orchestratore:pre-merge` (dal plugin, M2). Finché gli
  agent non esistono, usa `general-purpose` con `model` esplicito.
- `model`: sempre esplicito (`opus`, `sonnet`, `haiku`). Mai lasciare il default.
- `isolation: "worktree"` per ogni lane di implementazione parallela. Il verificatore
  lavora sul branch della PR, non sul worktree del builder.
- Prompt del worker = contratto del task (SKILL.md §3) + perimetro + skill obbligatorie con
  path + boundary del filesystem + «non delegare, non chiedere ad Andrea, domande nel registro
  quesiti, termina il turno a un checkpoint con diff, hash, comandi e output».
- Un worker per incarico. Chiudi i thread finiti; accetta consegne sintetiche, non transcript.

## Worker cx via bridge

`bin/spawn-cx.sh <modello> <effort> <cwd> <prompt-file>` (M2), che esegue
`codex exec -m <modello> -c model_reasoning_effort=<effort> -s workspace-write --approve-for-me`
con il prompt letto da file, log in `.orchestratore/logs/<task-id>.log`, exit code restituito.
Lancialo con `Bash` in background (`run_in_background: true`) e leggi il log al
checkpoint. Modelli cx: `gpt-6-astra`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`.
Il bridge non decide niente: modello, effort e prompt li scegli tu.

## Domande interattive

Con debito tossico usa il tool di domanda strutturata (`AskUserQuestion`): una domanda,
2-4 opzioni, la raccomandata per prima con «(Recommended)». Registra la risposta esatta nel
registro quesiti e sblocca solo i task che risolve davvero.

## Git e PR

`gh pr create`, `gh pr checks`, `gh pr view --json state,mergedAt`. Merge solo alla parola
`merge` di Andrea. Output raw nel report, mai riassunto.

## Contesto

Il root CC non legge la propria percentuale in modo affidabile: lavora per checkpoint
frequenti e scrivi l'handoff presto. I worker hanno contesto proprio: ogni turno finisce a
un checkpoint. Se il runtime segnala compattazione, ricarica solo `run.md` e ricontrolla
l'impronta del filesystem prima di continuare.

## Lock e stato

- `.orchestratore/brain.lock`: `runtime=cc pid=<pid> session=<id> updated=<iso>`;
  aggiornalo a ogni report di stato, rilascialo all'handoff.
- `~/.orchestratore/heavy.lock` prima di build, suite DB, browser, container: se occupato
  da un pid vivo, aspetta o riordina i task.
```

- [x] **Step 2: adapter-cx.md**

```markdown
# Adapter Codex: il cervello è gpt-6-astra in cx

## Avvio minimo in cx

Set di skill all'avvio: `i-have-adhd`, `orchestratore`, `openai-docs`. Le altre restano
installate ma non caricate. Carica una skill opzionale solo quando serve a un task concreto:
cercala nel catalogo locale con `rg -i <parola> references/codex-skills-catalog.jsonl`
(non caricare il catalogo intero), chiedi ad Andrea con una frase in italiano che nomina la
skill e il lavoro, e dopo il sì leggi quel `SKILL.md` e le sole reference pertinenti.
Un'istruzione esplicita di Andrea di usare una skill vale già come approvazione. Il silenzio
non è consenso. Leggere un file di skill non abilita tool MCP né cambia la config globale.

Il catalogo è stato ispezionato il 11/09/2026; la cache non prova disponibilità corrente.
Il catalogo CC (`~/Dev/skills/cc-installed-plugins.md`) non dice cosa ha cx, e viceversa.

## Worker cx nativi

Un thread per incarico, con modello ed effort dichiarati nel contratto del task
(`gpt-5.6-sol` importante, `gpt-5.6-terra` basic, `gpt-5.6-luna` meccanico; verifica
`gpt-5.6-sol`). Prompt del worker come in adapter-cc: contratto + perimetro + skill con
path + boundary + «non delegare, domande nel registro quesiti, checkpoint con diff, hash,
comandi e output». Se il runtime non permette di scegliere il modello per thread, usa
`codex exec` con `-m` dal cervello stesso e dichiaralo nel contratto.

## Worker CC via bridge

`bin/spawn-cc.sh <modello> <cwd> <prompt-file>` (M2), che esegue
`claude -p --model <modello> --permission-mode bypassPermissions --output-format json`
con il prompt letto da file, log in `.orchestratore/logs/<task-id>.log`. Con `verifica cc`
il verificatore è sempre `opus` via questo bridge; il prompt include il testo dell'agent
`verificatore` del plugin (`agents/verificatore.md`, M2) e solo perimetro e branch.

## Domande interattive

Con debito tossico ferma il turno e scrivi la domanda in chiaro, una sola, con 2-4 opzioni
e la raccomandata per prima. Riprendi solo dopo la risposta; registrala nel registro quesiti.

## Git, PR, lock, contesto

Come adapter-cc: `gh` per PR e checks, merge solo alla parola `merge`, `brain.lock` con
`runtime=cx`, `heavy.lock` prima dei processi pesanti. cx espone la percentuale di contesto
nella sessione: rispetta target 50% e tetto 70%; al 50% non aprire task nuovi, persisti e
compatta al primo checkpoint sicuro.

## Path locali usati da questa reference

- Catalogo cx: `/Users/andreapesce/Dev/skills/orchestratore/skills/orchestratore/references/codex-skills-catalog.jsonl`
- Skill di metodo leggibili per path: `/Users/andreapesce/Dev/skills/<nome>/SKILL.md`
```

- [x] **Step 3: project-adapter.md (sostituzione integrale)**

```markdown
# Project adapter: progetto nuovo o ripresa

## Progetto nuovo per l'orchestratore

1. Leggi CLAUDE.md, AGENTS.md, SPEC.md, ROADMAP.md, progress.md, `.claude/decisioni.md`,
   `lessons.md`. Se ROADMAP.md manca o è più vecchia di SPEC.md: fermati, «serve
   `/allineamento` prima». Se SPEC.md manca: «serve `spec-builder` prima».
2. Individua comandi di build, test, lint e l'ambiente disponibile (locale, CI, DB di test).
3. Crea `.orchestratore/` (aggiungila a `.gitignore` del progetto se manca) e copia
   `templates/run.md` in `.orchestratore/run.md`. Opzionale: `.orchestratore/config.toml`
   dal template per un peso diverso dal globale.
4. Cattura stato Git in sola lettura: branch, hash, worktree, PR aperte (`gh pr list`).
5. Conta le milestone aperte in ROADMAP.md e le loro dipendenze: è il totale per i contatori
   della celebrazione. Fissalo in `run.md`.
6. Registra in `run.md` il mandato Git del progetto (Mesa e Pau: commit+push+PR delegati;
   altri: chiedi all'avvio).
7. Valida prima di delegare: un owner per file, nessun ciclo di dipendenze, milestone attive
   ≤ tetto, worker ≤ tetto. Se non c'è un validatore, fallo a mano e scrivilo.

Non copiare regole di dominio da un altro progetto. Le istruzioni e le decisioni di prodotto
del repo corrente prevalgono sempre su questa skill.

## Ripresa

1. Leggi `run.md` (ultimo handoff) e `~/.orchestratore/state.toml` (credito).
2. Elenca gli agenti vivi con i tool della sessione e riconciliali con `run.md`: uno stato
   `running` senza agente vivo diventa `da riassegnare`.
3. Confronta revisione base e impronta delle modifiche non committate con il filesystem
   reale prima di qualsiasi scrittura.
4. Chiudi consegne e review verificabili prima di aprire fronti nuovi.
5. Riparti dalla prossima azione registrata; non ripetere ricognizioni già fatte.

## Stati dei task in `run.md`

`in coda` (dipendenze incomplete) · `pronto` · `in corso` · `in review` · `verificato` ·
`pronto al merge` (pre-merge sì) · `integrato` · `chiuso` · `bloccato` (condizione esterna
nominata, con owner dello sblocco) · `esterno` (di un'altra lane o sessione: non duplicare).
Se il progetto ha già un vocabolario di stati, adotta quello.

## Scelte di provider e servizi

Hosting, database, storage, email, pagamenti sono decisioni di architettura: confronto in
sola lettura (vincoli di prodotto, regione dati, DPA, backup, costo di uscita) e domanda nel
registro quesiti. Login, provisioning, DNS, deploy, acquisti e rotazione segreti richiedono
ciascuno l'autorizzazione del progetto.
```

- [x] **Step 4: Rimuovi skill-activation.md, aggiorna il riferimento in ~/.codex/AGENTS.md**

Stato: `skill-activation.md` rimosso nel commit `007012a`; aggiornamento di
`~/.codex/AGENTS.md` rinviato a T8 perché richiede conferma esterna specifica.

```bash
cd ~/Dev/skills/orchestratore
git rm -q skills/orchestratore/references/skill-activation.md
sed -i '' 's#/Users/andreapesce/Dev/skills/orchestratore/references/skill-activation.md#/Users/andreapesce/Dev/skills/orchestratore/skills/orchestratore/references/adapter-cx.md#; s#/Users/andreapesce/Dev/skills/orchestratore/references/codex-skills-catalog.jsonl#/Users/andreapesce/Dev/skills/orchestratore/skills/orchestratore/references/codex-skills-catalog.jsonl#' ~/.codex/AGENTS.md
grep -n "orchestratore/" ~/.codex/AGENTS.md
```
Atteso: due righe con i nuovi path sotto `skills/orchestratore/references/`.

- [x] **Step 5: Verifica references**

Run: `tests/check-structure.sh | grep -E 'references|adapter|project-adapter'`
Atteso: tutti `OK`, incluso `references vecchie rimosse`.

- [x] **Step 6: Commit**

```bash
git add -A skills/orchestratore
git commit -m "feat(references): adapter-cc, adapter-cx, project-adapter; rimosse le reference Codex-only

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Template run.md, config.toml, state.toml

**Files:**
- Create: `templates/run.md`
- Create: `templates/config.toml`
- Create: `templates/state.toml`

**Interfaces:**
- Produces: schema di `run.md` letto e scritto dai comandi di M3; chiavi TOML `peso.dev.cx`, `peso.dev.cc`, `peso.verifica`, `peso.valido_fino`, `credito.cc`, `credito.cx`, `credito.peso_precedente`.

- [x] **Step 1: templates/run.md**

```markdown
# Run orchestratore — <progetto>

stato: attivo | handoff
cervello: cc-fable | cx-gpt-6-astra
avviato: <ISO 8601>
ultimo aggiornamento: <ISO 8601>

## Contratto di autonomia

Run mode: milestone-budget | while-quality-high
Milestone budget: <n | tutte | n/a>
Peso: dev cx <n> / cc <n>; verifica <cc|cx|opposto>
Tetto: 3 milestone / 6 worker
Tetto domande aperte: <n>
Stop aggiuntivi: <condizioni osservabili>
Autorizzazioni Git: <commit+push+PR | solo lettura>
Al limite CC: handoff e stop
Credito: cc <ok|esaurito>; cx <ok|esaurito>

## Milestone (totale fissato all'avvio: <n>)

| ID | Milestone | Stato | PR | Verificatore | Pre-merge | Note |
|---|---|---|---|---|---|---|
| M1 | <nome> | in coda | | | | |

Contatori: 🟢 <completate> · 🟡 <bloccate da Andrea> · 🔴 <mancanti>
Ultima GIF usata: delfino | balena | nessuna

## Registro task

### T-001 — <milestone> — <stato>
Risultato osservabile per l'utente:
Dipendenze completate e contratto congelato:
File scrivibili (un owner per file):
File condivisi che integra il cervello:
Tier / runtime / modello / effort:
Skill obbligatorie: <nome → path esatto>
Verifica ammessa e ambiente:
Criterio di completamento:
Decisioni aperte e condizioni di stop:
Prossimo checkpoint:
Consegna: <hash, comandi eseguiti, output, limiti residui>

## Domande (dettaglio in .claude/decisioni.md)

Aperte: <n> / tetto <n>. Bloccanti: <ID e task | nessuna>.

## Handoff

Obiettivo:
Contratto e budget residuo:
Task attivi (owner, stato):
Revisione base: <sha>   Impronta modifiche non committate: <hash>
Domande aperte con impatto:
Evidenze verificate:
Token riportati dal runtime: <input/output/totale | non disponibile>
Contesto: <percentuale | non disponibile>, compattazioni: <n>
Prossima azione (una sola):
```

- [x] **Step 2: templates/config.toml**

```toml
# Peso CC/cx dell'orchestratore.
# Globale: ~/.orchestratore/config.toml. Per progetto: .orchestratore/config.toml (vince).
# Valori interi, dev.cx + dev.cc = 100.

[peso]
dev = { cx = 100, cc = 0 }
verifica = "cc"            # cc | cx | opposto
valido_fino = "2026-10-12" # alla scadenza il cervello chiede il nuovo peso, non lo applica in silenzio

[tetti]
milestone = 3
worker = 6
domande_aperte = 8
```

- [x] **Step 3: templates/state.toml**

```toml
# Stato credito condiviso tra tutte le sessioni: ~/.orchestratore/state.toml.
# Lo scrivono solo i comandi `credito`; ogni cervello lo rilegge a ogni assegnazione.

[credito]
cc = "ok"   # ok | esaurito
cx = "ok"   # ok | esaurito
aggiornato = "1970-01-01T00:00:00Z"

# Peso salvato prima dell'ultimo `credito <runtime> esaurito`, ripristinato da `credito <runtime> ok`.
[credito.peso_precedente]
dev = { cx = 100, cc = 0 }
verifica = "cc"
```

- [x] **Step 4: Verifica template**

Run: `tests/check-structure.sh | grep templates`
Atteso: 3 righe `OK`.

- [x] **Step 5: Commit**

```bash
git add templates
git commit -m "feat(templates): run.md, config.toml, state.toml

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: README e gate verde

**Files:**
- Create: `README.md`

- [x] **Step 1: README.md**

```markdown
# orchestratore

Plugin dual-runtime (Claude Code + Codex) che orchestra worker su più milestone in parallelo.
Cervello Fable 5.1 in CC (alternativa gpt-6-astra in cx), sviluppo su cx, verifica su CC con
modello diverso dal builder, gate pre-merge, registro quesiti, celebrazione milestone.

Spec: `docs/specs/2026-09-12-orchestratore-plugin-design.md`. Piani: `docs/plans/`.

## Install

Claude Code:
```bash
claude plugin marketplace add queondache/orchestratore
claude plugin install orchestratore@orchestratore
```

Codex:
```bash
codex plugin marketplace add queondache/orchestratore
codex plugin add orchestratore@orchestratore
```

Sviluppo locale: al posto di `queondache/orchestratore` passa il path del clone
(`~/Dev/skills/orchestratore`).

## Uso

In un progetto con `SPEC.md` e `ROADMAP.md`: `/orchestra start` (CC) oppure «avvia il run»
(cx). Comandi: `start`, `status`, `peso`, `credito`, `stop`, `riprendi` (M3).

## Struttura

- `skills/orchestratore/` la skill e le reference (routing, lane, skill-map, adapter-cc,
  adapter-cx, project-adapter)
- `templates/` run.md, config.toml, state.toml
- `agents/`, `commands/`, `hooks/`, `bin/` in arrivo con M2 e M3
- `tests/check-structure.sh` gate strutturale

## Test

```bash
tests/check-structure.sh
```
```

- [x] **Step 2: Gate verde**

Run: `tests/check-structure.sh; echo "exit=$?"`
Atteso: tutte le righe `OK`, `VERDE: tutti i controlli passano`, `exit=0`. Output raw nel log della milestone.

- [x] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README del plugin

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Install in CC e cx, pulizia symlink, repo GitHub

**Files:**
- Delete: symlink `~/.claude/skills/orchestratore`, `~/.codex/skills/orchestratore`, `~/.agents/skills/orchestratore`
- Modify: `~/Dev/skills/README.md` (riga `orchestratore/`), `~/Dev/skills/cc-installed-plugins.md` (riga orchestratore e conteggio plugin)

**Interfaces:**
- Produces: plugin `orchestratore@orchestratore` installato in entrambi i runtime; skill visibile una sola volta per runtime.

- [x] **Step 1: Install in CC dal path locale**

```bash
claude plugin marketplace add ~/Dev/skills/orchestratore
claude plugin install orchestratore@orchestratore
claude plugin details orchestratore@orchestratore 2>&1 | head -30
```
Atteso: install senza errori; `details` elenca la skill `orchestratore` e nessun agent/command (arrivano dopo).

- [x] **Step 2: Rimuovi i symlink vecchi in CC e verifica unicità**

```bash
rm ~/.claude/skills/orchestratore
ls -la ~/.claude/skills | grep -c orchestratore   # atteso 0
```
Poi in una nuova sessione CC (o dopo `/reload-plugins` se disponibile): la lista skill mostra `orchestratore:orchestratore` una sola volta.

- [x] **Step 3: Install in cx dal path locale**

```bash
codex plugin marketplace add ~/Dev/skills/orchestratore
codex plugin add orchestratore@orchestratore
grep -n 'orchestratore' ~/.codex/config.toml
```
Atteso: sezione `[marketplaces.orchestratore]` e `[plugins."orchestratore@orchestratore"]`. Se il marketplace da path locale non è accettato, salta e ripeti dopo lo Step 6 con `queondache/orchestratore`.

- [x] **Step 4: Rimuovi i symlink vecchi in cx e .agents; disattiva la skill standalone in config.toml**

```bash
rm ~/.codex/skills/orchestratore ~/.agents/skills/orchestratore
python3 - <<'EOF'
import pathlib,re
p=pathlib.Path.home()/".codex/config.toml"; s=p.read_text()
# La skill standalone "orchestratore" non esiste più: resta solo quella del plugin
s=re.sub(r'\[\[skills\.config\]\]\nname = "orchestratore"\nenabled = true\n\n?', '', s)
p.write_text(s)
EOF
grep -n 'name = "orchestratore' ~/.codex/config.toml
```
Atteso: nessuna riga standalone; se il plugin ha aggiunto `name = "orchestratore:orchestratore"`, quella resta con `enabled = true`.

- [x] **Step 5: Aggiorna README e inventario dell'ombrello**

```bash
cd ~/Dev/skills
python3 - <<'EOF'
import pathlib
p=pathlib.Path("README.md"); s=p.read_text()
old=[l for l in s.splitlines() if l.startswith("| `orchestratore/` |")][0]
new="| `orchestratore/` | plugin (repo annidato) | coordinamento multi-agente CC + cx: cervello Fable, worker a tier, verifica con modello diverso, gate pre-merge | repo `queondache/orchestratore`; installato come plugin in CC e cx, non più symlink |"
p.write_text(s.replace(old,new,1))
p=pathlib.Path("cc-installed-plugins.md"); s=p.read_text()
old=[l for l in s.splitlines() if l.startswith("| orchestratore |")][0]
new="| orchestratore | architecture/method | Plugin dual-runtime: cervello Fable in CC (alt. gpt-6-astra in cx), cx sviluppa, CC verifica con opus, builder ≠ verificatore, gate pre-merge, celebrazione milestone. Comandi `/orchestra *` (M3) | plugin `orchestratore@orchestratore`, repo ~/Dev/skills/orchestratore |"
p.write_text(s.replace(old,new,1))
EOF
cd ~/Dev && git add skills/README.md skills/cc-installed-plugins.md && git commit -m "skills: orchestratore è un plugin installato

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [x] **Step 6: Repo GitHub privato e push (CHIEDI CONFERMA AD ANDREA PRIMA)**

Fermati e scrivi: «Creo `queondache/orchestratore` privato su GitHub e faccio push di `main`. Confermi?». Solo dopo il sì:

```bash
cd ~/Dev/skills/orchestratore
gh repo create queondache/orchestratore --private --source=. --remote=origin --push
gh repo view queondache/orchestratore --json name,visibility,defaultBranchRef
git log --oneline -1 origin/main
```
Atteso: `visibility: PRIVATE`, `defaultBranchRef: main`, ultimo hash uguale a `git log -1 --format=%h`.

- [x] **Step 7: Report finale M1**

```text
MILESTONE: M1 scheletro plugin   REPO: queondache/orchestratore (privato)   PUSH: <sì | in attesa di conferma>
DEFINITION OF DONE
- repo annidato e gitignorato nell'ombrello: OK. Evidenza: `cd ~/Dev && git status --short skills/orchestratore` vuoto
- manifest CC e cx validi: OK. Evidenza: 4 righe OK del gate
- SKILL.md riscritto ≤ 250 righe: OK. Evidenza: `wc -l` + gate
- references e template presenti, vecchie rimosse: OK. Evidenza: gate
- install CC: OK. Evidenza: output `claude plugin details orchestratore@orchestratore`
- install cx: <OK | rimandato al repo remoto>. Evidenza: `grep orchestratore ~/.codex/config.toml`
- symlink vecchi rimossi, skill visibile una volta sola: OK. Evidenza: `ls -la ~/.claude/skills ~/.codex/skills ~/.agents/skills | grep orchestratore`
GATE: tests/check-structure.sh VERDE (era ROSSO al Task 1, output nel log)
PROSSIMA MILESTONE: M2 bridge e agent (bin/spawn-cx.sh, bin/spawn-cc.sh, agents/*.md)
```

---

## Esito finale M1 — 2026-09-12

```text
MILESTONE: M1 scheletro plugin   REPO: queondache/orchestratore (privato)   PUSH: sì
DEFINITION OF DONE
- repo annidato e gitignorato nell'ombrello: OK. Evidenza: repo separato; durante la review
  resta solo il diff conclusivo del piano, destinato al commit finale
- manifest CC e cx validi: OK. Evidenza: quattro controlli manifest OK nel gate
- SKILL.md riscritto ≤ 250 righe: OK. Evidenza: 194 righe e dieci controlli SKILL OK
- references e template presenti, vecchie rimosse: OK. Evidenza: gate strutturale
- install CC: OK. Evidenza: orchestratore@orchestratore 0.1.0 enabled, Skills 1
- install cx: OK. Evidenza: orchestratore@orchestratore 0.1.0 installed, enabled
- symlink vecchi rimossi, skill visibile una volta sola: OK. Evidenza: tre path assenti
GATE: tests/check-structure.sh VERDE, 31/31 OK (era ROSSO con 21 KO al Task 1)
PROSSIMA MILESTONE: M2 bridge e agent (bin/spawn-cx.sh, bin/spawn-cc.sh, agents/*.md)
```

Review indipendenti: T1-T7 `OK`; T8 pre-push `OK`; review finale sul diff del piano e
sullo stato installato richiesta prima del commit conclusivo. Token/costi: non disponibili.

---

## Self-review (fatta)

- **Copertura spec §7 M1**: repo (T1, T8), manifest CC e cx (T2), skill riscritta (T3), references (T4, T5), install verificata in entrambi (T8). Template (T6) anticipati da M3 perché SKILL.md li cita.
- **Placeholder**: nessun TODO/TBD; ogni file ha il contenuto completo. Il gate lo controlla.
- **Coerenza nomi**: agent `worker-impl`, `worker-mech`, `verificatore`, `pre-merge` uguali in SKILL.md, routing.md, adapter-cc.md, skill-map.md. Bridge `spawn-cx.sh <modello> <effort> <cwd> <prompt-file>` e `spawn-cc.sh <modello> <cwd> <prompt-file>` uguali in adapter-cc e adapter-cx. Chiavi TOML uguali tra config.toml, state.toml e SKILL.md §0/§6. Stati task uguali tra lane.md, project-adapter.md e run.md.
- **Fuori da M1**: agent, comandi, hook, bridge, sandbox, modifiche a CLAUDE.md, AGENTS.md e milestone (M2-M4).
