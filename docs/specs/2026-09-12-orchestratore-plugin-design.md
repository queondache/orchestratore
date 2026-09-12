# Orchestratore — design del plugin dual-runtime (CC + cx)

Data: 12/09/2026. Stato: approvato in brainstorming con Andrea, da tradurre in piano.
Sostituisce l'attuale `skills/orchestratore/SKILL.md` (creata con cx il 10/09/2026).

## 1. Obiettivo

Su progetti grandi con `SPEC.md` e `ROADMAP.md` già chiare, Andrea avvia un run e un
orchestratore forte governa worker che sviluppano più milestone in parallelo con modelli
più economici. Le domande si accumulano in un registro; quando una risposta è bloccante
per la qualità, l'orchestratore chiude il checkpoint e la pone ad Andrea in modo
interattivo. Ogni milestone verificata viene celebrata con GIF e recap.

Glossario: **CC** = Claude Code. **cx** = Codex CLI. **Cervello** = sessione che esegue
la skill orchestratore. **Worker** = agente lanciato dal cervello. **Lane** = una milestone
in lavorazione, eseguita con il protocollo della skill `milestone`.

## 2. Decisioni prese con Andrea

| # | Tema | Decisione |
|---|---|---|
| D1 | Topologia | Un solo cervello vivo per volta. Default in CC con Fable 5.1. Alternativa in cx con `gpt-6-astra`. All'avvio l'orchestratore chiede: `standard` o `alternativo`. |
| D2 | Switch cervello | Manuale con handoff. Al limite CC il cervello scrive l'handoff in `.orchestratore/run.md` e si ferma. Andrea apre cx e scrive `riprendi`. |
| D3 | Distribuzione del lavoro | Default: **cx sviluppa, CC orchestra e verifica**. Motivo: quota cx abbondante per un mese (settembre-ottobre 2026), quota CC scarsa. Il default è configurabile, non cablato. |
| D4 | Peso CC/cx | Riga nel contratto di autonomia (`peso: dev cx 100 / cc 0`) più comando `/orchestra peso …` in corsa. Il peso guida solo le assegnazioni nuove. |
| D5 | Builder ≠ verificatore | Sempre modello diverso. Runtime opposto quando il peso lo consente. |
| D6 | Modello di verifica in CC | **Sempre opus**. Fable non verifica: orchestra soltanto. |
| D7 | Tier implementazione | Importante → opus (CC) / `gpt-5.6-sol` (cx). Basic → sonnet (CC) / `gpt-5.6-terra` (cx). Meccanico → haiku / `gpt-5.6-luna`. |
| D8 | Concorrenza | Tetto 3 milestone / 6 worker. L'orchestratore decide la concorrenza reale. `AGENTS.md` si aggiorna a questi numeri. |
| D9 | Perimetro plugin | Skill + agent + comandi + hook. `milestone` resta skill separata, usata come lane. |
| D10 | Distribuzione | Repo GitHub privato `queondache/orchestratore`, clonato in `~/Dev/skills/orchestratore` (repo annidato, gitignorato nell'ombrello). Install via git in CC e cx. |
| D11 | Skill obbligatorie | Orchestratore e worker usano le skill installate (design, metodo, superpowers). Ai worker cx si passano nome e path esatto. |
| D12 | Celebrazione | Dopo ogni milestone verificata: GIF delfino o balena alternate, frase `una milestone meno`, recap 🟢🟡🔴. |
| D13 | Multi-sessione | Il plugin gira in più sessioni VS Code su progetti diversi nello stesso momento. Stato e lock sono per progetto; la config peso è globale con override per progetto. |
| D14 | Credito esaurito | Comando `/orchestra credito cc esaurito` (o `cx`): tutto si sposta sul runtime con credito, cervello compreso. Il cervello sul runtime esaurito scrive l'handoff e chiede di riprendere dall'altro. `/orchestra credito cc ok` ripristina il peso precedente. |
| D15 | Gate pre-merge | Prima dell'auto-merge passa un agente con modello diverso dal builder (e dal verificatore, quando possibile) che rilegge PR, CI e verdetto e dice `suggerisco merge: sì | no + motivi`. Auto-merge solo con hash revisionato, verifier finale OK e required CI tutti success. |
| D16 | Solo-CC su task importante | Con cx esaurito: opus costruisce, **fable verifica**. Eccezione dichiarata a D6, valida solo in modalità solo-CC e solo su task importanti. |

"Importante" (D7) segue i criteri tier di `senior-architect` §5: tocca schema, migrazioni,
auth, pagamenti, multi-tenancy, PII, sicurezza, concorrenza. Tutto il resto è basic.

## 3. Architettura

### 3.1 Cervello e bridge

```
Andrea ──/orchestra start──▶ Cervello (CC: fable | cx: gpt-6-astra)
                                 │
                 ┌───────────────┼────────────────────┐
                 ▼               ▼                    ▼
           worker nativo    worker bridge        verificatore
        (Agent tool in CC | (bin/spawn-cx.sh     (nativo o bridge,
         thread in cx)      bin/spawn-cc.sh)      modello ≠ builder)
                 │               │                    │
                 └──────── .orchestratore/run.md ◀────┘
                           .claude/decisioni.md
```

- **Cervello in CC**: worker CC via tool `Agent` con `model` esplicito e
  `isolation: "worktree"` per le lane parallele. Worker cx via
  `bin/spawn-cx.sh <modello> <effort> <cwd> <prompt-file>`, che incapsula
  `codex exec --yolo -m <modello> -c model_reasoning_effort=<effort>` (`--yolo` è l'alias
  ufficiale di `--dangerously-bypass-approvals-and-sandbox`).
- **Cervello in cx**: worker cx nativi. Worker CC via
  `bin/spawn-cc.sh <modello> <cwd> <prompt-file>`, che incapsula
  `claude -p --model <modello> --permission-mode bypassPermissions --output-format json`.
- I bridge sono deterministici: costruiscono la riga di comando, loggano stdout e stderr in
  `.orchestratore/logs/<task-id>.log`, restituiscono exit code. Nessuna logica di
  orchestrazione dentro gli script.
- Un solo cervello vivo. Il file `run.md` porta `cervello: cc|cx` e `stato: attivo|handoff`.
  Un cervello che trova `stato: attivo` con runtime diverso dal proprio si ferma e chiede.

### 3.2 Routing modelli ed effort

| Tier | Quando | CC | cx | Effort default |
|---|---|---|---|---|
| Cervello | sempre | fable | gpt-6-astra | alto |
| Verifica | ogni consegna | opus | gpt-5.6-sol | alto |
| Impl. importante | criteri §2 | opus | gpt-5.6-sol | alto |
| Impl. basic | resto | sonnet | gpt-5.6-terra | medio |
| Meccanico | inventari, lint, rinomine, test deterministici | haiku | gpt-5.6-luna | basso |

Regole:
1. Il cervello sceglie tier, runtime ed effort per ogni task e li scrive nel contratto del task.
2. Verificatore mai dello stesso modello del builder. Con `peso dev cx 100`, builder cx e
   verificatore opus in CC soddisfano la regola automaticamente. Con peso misto, il
   cervello sceglie il runtime opposto quando disponibile, altrimenti modello diverso.
3. Escalation di un tier solo su trigger concreto: contratto ambiguo, due tentativi falliti,
   disaccordo tra builder e verificatore, rischio alto scoperto in corso.
4. De-escalation sul lavoro di follow-up meccanico.
5. Mai dichiarare che un modello ha girato se il runtime non lo riporta.
6. Modalità solo-CC (cx esaurito): basic → sonnet costruisce, opus verifica; importante →
   opus costruisce, fable verifica (D16). Modalità solo-cx (CC esaurito): basic → terra
   costruisce, sol verifica; importante → sol costruisce, gpt-6-astra verifica.

### 3.3 Peso CC/cx

- Default utente in `~/.orchestratore/config.toml`:
  ```toml
  [peso]
  dev = { cx = 100, cc = 0 }
  verifica = "cc"        # cc | cx | opposto
  valido_fino = "2026-10-12"
  ```
  Alla scadenza il cervello lo segnala all'avvio e chiede il nuovo peso invece di applicarlo
  in silenzio.
- Override per run nel contratto di autonomia. Override in corsa con `/orchestra peso dev cx 60`.
- Il peso vale per le assegnazioni nuove. I task in volo finiscono dove sono.
- `verifica = "cc"` con cervello cx significa che il cervello cx lancia opus via bridge.
- Override per progetto in `.orchestratore/config.toml`, stesse chiavi; vince sul globale.
- **Credito esaurito** (D14): `/orchestra credito cx esaurito` porta il peso a `dev cc 100,
  verifica cc` e applica la regola 6 del routing; le assegnazioni nuove vanno tutte su CC,
  i task cx in volo vengono lasciati finire il checkpoint corrente e poi riassegnati se non
  consegnano. `/orchestra credito cc esaurito` con cervello CC: il cervello scrive l'handoff,
  marca `credito: cc esaurito` in `run.md` e chiede ad Andrea di aprire cx e scrivere
  `riprendi`; il cervello cx legge il flag e parte già con `dev cx 100, verifica cx`.
  `/orchestra credito <runtime> ok` ripristina il peso salvato prima dell'esaurimento.
  Lo stato del credito è globale (`~/.orchestratore/state.toml`) perché vale per tutte le
  sessioni aperte: ogni cervello lo rilegge a ogni assegnazione.

### 3.4 Contratto di autonomia

Scritto in `.orchestratore/run.md` all'avvio, dopo la domanda `standard | alternativo`:

```text
Cervello: cc-fable | cx-gpt-6-astra
Run mode: milestone-budget | while-quality-high
Milestone budget: <n | tutte | n/a>   (tutte = tutte le milestone aperte di ROADMAP.md al momento dell'avvio)
Peso: dev cx <n> / cc <n>; verifica <cc|cx|opposto>
Tetto: <k> milestone / <w> worker  (default 3 / 6)
Tetto domande aperte: <n>
Stop aggiuntivi: <condizioni osservabili>
Run non presidiato: sì | no
Autorizzazioni Git: <commit+push+PR automatici | solo lettura>
Al limite CC: handoff e stop
Credito: cc ok | cc esaurito; cx ok | cx esaurito  (letto da ~/.orchestratore/state.toml)
```

Le milestone parziali o bloccate non contano nel budget. Una richiesta di lavoro autonomo
non autorizza a completare l'intera roadmap se Andrea non lo dice.

### 3.5 Unità di delega (contratto del task)

Registrato in `run.md` prima di lanciare il worker:

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

I worker non delegano. Solo il cervello scrive `run.md`, il registro quesiti e l'handoff.

### 3.6 Lane = skill `milestone` senza Fase 1

Ogni worker di implementazione riceve un `PERIMETRO` nel formato della skill `milestone`
(obiettivo, definition of done, aree ammesse, fuori perimetro, vincoli, STOP). Lo produce
il cervello: nessuna approvazione di Andrea per milestone. Il worker esegue Fasi 0, 2, 3, 4.
Differenze rispetto alla skill usata a mano:

- Fase 0 rossa: il worker si ferma e riporta al cervello, non ad Andrea.
- Domande: nel registro quesiti, mai ad Andrea. Il cervello decide se sono bloccanti.
- Fase 3: il verificatore lo assegna il cervello, non il worker, per garantire modello diverso.
- Regola del verdetto invariata: OK vale solo sull'hash che va in PR. Ogni correzione
  successiva obbliga a un giro di conferma.
- Fase 4: commit, push e PR verso `main` sono automatici nel run non presidiato.
- **Gate pre-merge** (D15): con PR aperta e CI riportata da `gh`, il cervello lancia
  l'agent `pre-merge` con modello diverso dal builder e, se i modelli disponibili lo
  consentono, diverso anche dal verificatore. Riceve: perimetro, diff della PR, stato CI,
  verdetto del verificatore con hash. Produce: `suggerisco merge: sì | no`, tre motivi al
  massimo, rischi residui. Con `no` il cervello riapre la lane sul builder; con `sì` esegue
  auto-merge solo con hash revisionato, verifier indipendente finale OK, almeno un required
  CI check e tutti i required check success. Esempio con peso default: builder terra (cx), verificatore opus (CC), pre-merge
  sol (cx). Solo-CC: builder sonnet, verificatore opus, pre-merge fable in lettura.

### 3.7 Registro quesiti e gate del debito

- Le domande vanno in `.claude/decisioni.md` del progetto, sezione registro quesiti,
  con ID, testo, impatto, task bloccati, stato.
- Prima di aprire ogni milestone il cervello esegue il gate del debito. Il debito è tossico
  quando una domanda aperta cambia contratto, architettura, sicurezza, schema dati,
  comportamento utente, oracolo di test o definition of done della milestone successiva;
  quando una milestone precedente andrebbe dichiarata verificata per assunzione; o quando
  il tetto domande è raggiunto.
- Con debito tossico: chiude solo il checkpoint sicuro in volo, poi **pone la domanda ad
  Andrea in modo interattivo**: in CC con il tool di domanda strutturata (opzioni con
  raccomandazione prima), in cx fermando il turno con la domanda in chiaro. Una domanda per
  volta, la più piccola che sblocca.
- Domande non bloccanti si accumulano e compaiono nel report di stato come conteggio.
  Non si ripete una domanda invariata.

### 3.8 Visibilità, celebrazione, handoff

Report di stato (`/orchestra status` e a ogni cambio di stato, comunque ogni 10 minuti):

```text
In corso: <milestone, owner, fase, modello/runtime>
Verificato dall'ultimo report: <evidenza | niente di nuovo>
Domande: <aperte/tetto; bloccanti con ID e task | nessuna>
Peso in uso: dev cx n / cc n; verifica <…>; credito cc <ok|esaurito>, cx <ok|esaurito>
Contesto: <percentuale se il runtime la espone | non disponibile>
Prossimo checkpoint: <gate osservabile>
```

Celebrazione dopo ogni milestone verificata e chiusa (D12): GIF cliccabile alternando
delfino e balena (URL GIPHY già presenti nella skill attuale), riga `una milestone meno`,
poi:

```markdown
🟢 <completate> milestone completate
🟡 <bloccate da Andrea> milestone bloccate da Andrea
🔴 <mancanti> milestone mancanti per finire
```

Conteggi ricalcolati da `run.md`, mai dalla conversazione.

Handoff (al limite CC, a fine run o a `/orchestra stop`): obiettivo, contratto e budget
residuo, task attivi con owner e stato, revisione base più impronta delle modifiche non
committate, domande aperte con impatto, evidenze verificate, prossima azione singola.
`riprendi` da qualsiasi cervello: verifica agenti vivi con i tool della sessione, impronta
del filesystem e stato Git prima di riassegnare.

### 3.9 Governo del contesto

Target 50%, tetto 70% per ogni thread. In CC il root non legge la propria percentuale in
modo affidabile: la regola vale in modo forte per i worker (contesto proprio, turno che
finisce a un checkpoint) e in modo best effort per il cervello, che si affida ai checkpoint
frequenti e all'handoff. Nessuna promessa di rollover automatico.

### 3.10 Multi-sessione e lock per progetto

Più sessioni VS Code, ognuna su un progetto diverso, possono avere un cervello attivo
ciascuna (D13). Regole:

- Stato per progetto: `.orchestratore/run.md`, `.orchestratore/logs/`, override peso.
  Nessuno stato di run in `~/.orchestratore/`, che tiene solo config globale e stato credito.
- Lock per progetto: `.orchestratore/brain.lock` con runtime, pid, sessione, timestamp.
  Un cervello che trova un lock vivo (pid esistente, aggiornato da meno di 10 minuti) si
  ferma e chiede; un lock stantio viene segnalato e sovrascritto solo su conferma.
- Tetto 3 milestone / 6 worker vale per progetto. Il carico macchina si governa con la regola
  «un solo processo pesante locale per volta» dichiarata in `run.md` di ciascun progetto:
  build, suite DB e browser non si sovrappongono nemmeno tra progetti diversi. Il cervello
  controlla `~/.orchestratore/heavy.lock` prima di lanciare un processo pesante.
- I worker ricevono sempre `cwd` e boundary del filesystem del proprio progetto.
- Lo stato credito (D14) è l'unico stato condiviso tra sessioni oltre alla config.

### 3.11 Skill obbligatorie per tipo di task

Mappa nella skill, con path per i worker cx:

| Tipo di task | Skill | Disponibile in cx |
|---|---|---|
| Architettura, DB, tier, sicurezza | `senior-architect` + skill di progetto (`mesa-`/`pau-senior-architect`) | per path `~/Dev/skills/…` |
| Implementazione con test | `superpowers:test-driven-development`, `systematic-debugging` | per path nella cache plugin CC |
| UI nuova | `frontend-design` o `impeccable` (CC); `design-taste-frontend`, `high-end-visual-design`, `ui-ux-pro-max` (cx native) | sì |
| Redesign | `redesign-existing-projects` | sì |
| Lane milestone | `milestone` | per path |
| Verifica | agent `verificatore` del plugin | opus via bridge |
| Deploy Vercel | plugin `vercel` | sì |

Il cervello scrive nel contratto del task nome e path esatto. Un worker non inventa né
installa skill. Se una skill richiesta manca sul runtime scelto, il cervello sposta il task
sull'altro runtime o passa il file per path.

## 4. Struttura del repo `queondache/orchestratore`

```
orchestratore/
├── .claude-plugin/plugin.json          # name, version, description
├── .claude-plugin/marketplace.json     # marketplace con un plugin, source ./
├── .codex-plugin/plugin.json           # skills ./skills/, interface
├── skills/orchestratore/
│   ├── SKILL.md                        # italiano, ≤ 250 righe, il metodo
│   └── references/
│       ├── adapter-cc.md               # Agent tool, worktree, AskUserQuestion, gh
│       ├── adapter-cx.md               # thread, codex exec, catalogo skill cx
│       ├── routing.md                  # tabella tier/modelli/effort, regola builder≠verificatore
│       ├── lane.md                     # milestone senza Fase 1, verdetto su hash
│       ├── skill-map.md                # §3.10 con path
│       └── project-adapter.md          # onboarding progetto nuovo / ripresa
├── agents/                             # solo CC
│   ├── worker-impl.md                  # model: opus|sonnet scelto dal cervello
│   ├── worker-mech.md                  # model: haiku
│   ├── verificatore.md                 # model: opus; portato da ~/Dev/agents
│   └── pre-merge.md                    # modello scelto dal cervello, sola lettura + gh
├── commands/                           # solo CC
│   ├── orchestra-start.md
│   ├── orchestra-status.md
│   ├── orchestra-peso.md
│   ├── orchestra-stop.md
│   ├── orchestra-riprendi.md
│   └── orchestra-credito.md            # cc|cx esaurito|ok
├── hooks/
│   ├── hooks.json                      # SessionStart: startup|resume
│   └── roadmap-check.sh                # ≥2 milestone aperte senza dipendenze → hint
├── bin/
│   ├── spawn-cx.sh
│   └── spawn-cc.sh
├── templates/
│   ├── run.md                          # contratto + registro task + handoff
│   ├── config.toml                     # default peso globale e per progetto
│   └── state.toml                      # stato credito globale
├── docs/specs/                         # questa spec
├── tests/                              # smoke del §6
└── README.md
```

Il `verificatore` attuale (`~/Dev/agents/verificatore.md`, symlink da `~/.claude/agents/`, già `model: opus`) viene spostato nel plugin;
in `~/Dev/agents` e `~/.claude/agents` restano symlink finché le skill `milestone` e `allineamento` lo
richiamano per nome.

## 5. Incastri con il metodo esistente

- `~/Dev/CLAUDE.md`, tabella routing: nuova riga
  «ROADMAP con ≥2 milestone indipendenti, run autonomo → `orchestratore`».
- `~/Dev/AGENTS.md`: tetto 3 milestone / 6 worker; regola builder ≠ verificatore;
  rimando alla skill per il resto. Il file resta il mandato, non duplica la procedura.
- `skills/milestone/SKILL.md`: nota «dentro un run dell'orchestratore la Fase 1 la produce
  il cervello, le domande vanno nel registro quesiti».
- `~/Dev/skills/README.md` e `cc-installed-plugins.md`: voce orchestratore aggiornata a
  plugin con repo.
- `~/Dev/.gitignore`: `skills/orchestratore/` come repo annidato.
- `~/.codex/AGENTS.md`: path della skill aggiornati al plugin installato.

## 6. Verifica del plugin

Repo sandbox `~/Dev/dev-cc/orchestratore-sandbox` con `SPEC.md`, `ROADMAP.md` a 3
milestone (2 indipendenti, 1 dipendente), progetto Node minimo con test.

| Caso | Atteso |
|---|---|
| Install da git in CC e cx | plugin elencato in `installed_plugins.json` e in `~/.codex/config.toml` |
| Hook SessionStart in sandbox | hint `/orchestra start` visibile |
| `/orchestra start` standard, `peso dev cx 100` | 2 worker cx in parallelo, 1 milestone in attesa di dipendenza |
| Verifica | ogni consegna verificata da opus in CC; log mostra modelli diversi |
| Domanda bloccante iniettata in ROADMAP | run si ferma al gate, domanda interattiva, ripartenza dopo risposta |
| `/orchestra stop` poi `riprendi` da cx | cervello cx legge `run.md`, non riassegna task già chiusi |
| Celebrazione | GIF alternata, frase esatta, contatori coerenti con `run.md` |
| Prova di rosso | un test rotto di proposito nel sandbox produce KO del verificatore, nessuna PR |
| `/orchestra credito cx esaurito` a run avviato | assegnazioni nuove solo CC; task importante → opus costruisce, fable verifica; `credito cx ok` ripristina il peso |
| `/orchestra credito cc esaurito` con cervello CC | handoff scritto, richiesta di `riprendi` da cx; cervello cx parte con `dev cx 100, verifica cx` |
| Gate pre-merge | per ogni PR un agente con modello diverso da builder e verificatore; output `suggerisco merge: sì/no`; auto-merge solo con tutti i gate richiesti |
| Due sandbox in due sessioni | due cervelli attivi su progetti diversi senza conflitto; secondo cervello sullo stesso progetto si ferma sul lock |

Output raw dei comandi nel log della milestone di implementazione.

## 7. Milestone di implementazione (per il piano)

1. **Scheletro plugin** — repo, manifest CC e cx, skill riscritta, references, install verificata in entrambi.
2. **Bridge e agent** — `spawn-cx.sh`, `spawn-cc.sh`, agent CC, verificatore portato dentro, routing.
3. **Comandi, hook, stato** — `/orchestra *` incluso `credito`, hook ROADMAP, `run.md`, lock per progetto, config peso e stato credito, handoff e `riprendi`, agent `pre-merge`.
4. **Sandbox e incastri** — test §6, aggiornamento CLAUDE.md, AGENTS.md, milestone, README, inventario.

## 8. Fuori perimetro

- Switch automatico del cervello senza comando di Andrea (`credito esaurito` è un comando
  esplicito, non un rilevamento).
- Lettura automatica delle quote CC e cx.
- Policy GPU e runner remoti dell'attuale skill: rimossa. Resta solo «build, test e DB
  pesanti serializzati; non sovrapporre processi pesanti in locale».
- Portare `milestone`, `allineamento`, `spec-builder` dentro il plugin.
- Repo pubblico.

## 9. Assunzioni dichiarate

- Le autorizzazioni Git dei worker seguono il mandato del progetto (Mesa e Pau: delega già
  attiva). Per altri progetti il contratto di autonomia le chiede all'avvio.
- Prefisso comandi `/orchestra`. In cx gli stessi verbi in linguaggio naturale.
- La skill viene riscritta in italiano; i manifest e i nomi tecnici restano in inglese.
