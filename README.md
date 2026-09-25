# orchestratore — candidato v0.6.0

Plugin dual-runtime (Claude Code + Codex) che orchestra worker su più milestone in parallelo e
su più task dentro ogni milestone, con prova di indipendenza sui file reali, lane contract-first
quando le milestone si toccano e integratore dedicato. Il controller locale usa SQLite WAL e
lease autorevole; app Codex locale, Codex CLI e Claude CLI entrano nello stesso `run_id`.
Il flusso standard è strategia Claude, builder Codex e review Claude separata. Il profilo
`milestone` ammette fino a 5 builder simultanei; `bugfix` fino a 15, ma solo per bug
riproducibili con ownership di file disgiunta. Reviewer e pre-merge sono fuori quota builder.
La capacità review è `ceil(builder della wave/3)`, con cap 2/5, e le consegne hanno precedenza
sulle nuove assegnazioni. I processi pesanti locali restano serializzati.
Il routing è `cheapest-capable`: cervello cx Astra medium; dev Luna da medium, Terra da
medium e Sol da low; Astra worker da low solo quando un trigger osservabile richiede escalation.
Verifica indipendente a ogni consegna, non solo a fine milestone; un gate rosso non ferma il
run: feedback invariato deduplicato, due tentativi per approccio e massimo due approcci
automatici prima di parcheggiare la lane e liberare lo slot. A milestone chiusa: merge, allineamento di
ROADMAP/progress/decisioni e apertura immediata della lane successiva. Il verificatore esegue
quattro passi con evidenza raw — hash, gate verde, oracolo (il test nuovo deve diventare rosso
senza la modifica), perimetro. Il merge automatico è fail-closed: vale solo per tier 1-2,
richiede una allowlist esplicita che copra ogni file del diff e almeno un check CI richiesto
verde; tier 3, aree sensibili e path non classificati restano PR in attesa.

I worker Codex e Claude operano in worktree distinti con ownership verificata. Durante un run
non possono usare `gh`, `curl` o `git push`: il controller è l'unica autorità del protocollo
per leggere PR/check e richiedere il merge. Questi controlli sono guardrail contro errori e
gate d'integrazione, non una sandbox contro un worker locale ostile.

La ripresa A-E richiede evidenza della fase precedente; E è completa solo con outcome PR,
merge o attesa approvata e documenti allineati. Checkpoint e session rollover sono espliciti:
si persiste da 50 e si apre una nuova sessione da 70 senza affidarsi all'auto-compact. Il retry
è finito a 2×2.

Spec: `docs/specs/2026-09-12-orchestratore-plugin-design.md`. Piani: `docs/plans/`.

## Stato release

**Candidato v0.6.0**: metadati e gate locali sono in preparazione per la release di
produzione. Non esistono ancora PR o SHA finali della v0.6.0; finché il candidato non viene
pubblicato e installato, le sessioni correnti continuano a usare la propria versione in cache.

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

## Aggiornamento

Le installazioni del plugin sono snapshot/cache: le modifiche al repository non vengono
propagate automaticamente. Ogni release richiede un bump di versione, l'update/upgrade del
marketplace e l'update o la reinstallazione del plugin in ciascun runtime.

## Uso

In un progetto con `SPEC.md` e `ROADMAP.md`: `/orchestratore:orchestra start` (CC) oppure
«avvia il run» (cx). In `bugfix`, ROADMAP è opzionale: indica una fonte congelata con ID,
riproduzione e oracolo per ogni bug. Sottocomandi: `start`, `status`, `peso`, `credito`, `stop`, `riprendi`;
`/orchestratore:orchestra-status` è il report di sola lettura.

`SPEC.md` è la fonte dei requisiti, `ROADMAP.md` la fonte delle milestone e del loro stato,
`.orchestratore/RUN.md` l'unica fonte operativa. All'avvio il RUN congela un profilo concreto:
`milestone` per ROADMAP, feature, refactor o run misti; `bugfix` solo per un insieme di bug
indipendenti con riproduzione/oracolo. La precedenza è prompt, config progetto, rilevamento;
`auto` non entra mai nel RUN. Il RUN contiene massimo 5 milestone o 15 bug aperti e viene
aggiornato e ricompattato entro 300 righe/15 KB. Non vengono creati
`recon.md`, context pack o prompt-file permanenti; SQLite conserva soltanto stato macchina,
lease, fasi, retry, checkpoint ed event-id.
La policy di arresto predefinita segue il profilo: `milestone-budget: tutte` oppure
`bug-budget: tutti` dalla fonte bug congelata.

## Struttura

- `skills/orchestratore/` la skill e le reference (routing, lane, parallelismo, verifica,
  credito, skill-map, adapter-cc, adapter-cx, project-adapter)
- `templates/` RUN.md, config.toml, state.toml
- `agents/` i cinque agent del plugin (worker-impl, worker-mech, verificatore, pre-merge,
  integratore)
- `bin/` i bridge `spawn-cx.sh` e `spawn-cc.sh`, entrambi con `--dry-run`
- `commands/` `/orchestratore:orchestra` e `/orchestratore:orchestra-status`
- `hooks/` guardia PreToolUse sui comandi vietati durante un run, stato del run a SessionStart
- `controller/` riduttore di transizioni, schema SQLite e prove di recovery/idempotenza
- `tests/` gate strutturale, regressioni, mutazioni, bridge, hook e controller

## Test

```bash
tests/check-structure.sh
tests/check-regressions.sh
tests/check-regressions-mutations.sh
tests/check-bridge.sh
tests/check-hooks.sh
tests/check-controller.sh
```
