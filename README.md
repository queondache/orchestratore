# orchestratore 0.5.0

Plugin dual-runtime (Claude Code + Codex) che orchestra worker su più milestone in parallelo e
su più task dentro ogni milestone, con prova di indipendenza sui file reali, lane contract-first
quando le milestone si toccano e integratore dedicato. Il controller locale usa SQLite WAL e
lease autorevole; app Codex locale, Codex CLI e Claude CLI entrano nello stesso `run_id`.
Il flusso standard è strategia Claude, massimo due builder Codex e review Claude separata.
Il routing è `cheapest-capable`: cervello cx Astra medium; dev Luna da medium, Terra da
medium e Sol da low; Astra worker da low solo quando un trigger osservabile richiede escalation.
Verifica indipendente a ogni consegna, non solo a fine milestone; un gate rosso non ferma il
run: feedback invariato deduplicato, due tentativi per approccio e massimo due approcci
automatici prima di parcheggiare la lane e liberare lo slot. A milestone chiusa: merge, allineamento di
ROADMAP/progress/decisioni e apertura immediata della lane successiva. Il verificatore esegue
quattro passi con evidenza raw — hash, gate verde, oracolo (il test nuovo deve diventare rosso
senza la modifica), perimetro — e il merge automatico vale solo per tier 1-2: tier 3 e aree
sensibili restano PR in attesa.

La ripresa A-E richiede evidenza della fase precedente; E è completa solo con outcome PR,
merge o attesa approvata e documenti allineati. Checkpoint e session rollover sono espliciti:
si persiste da 50 e si apre una nuova sessione da 70 senza affidarsi all'auto-compact. Il retry
è finito a 2×2.

Spec: `docs/specs/2026-09-12-orchestratore-plugin-design.md`. Piani: `docs/plans/`.

## Stato release 0.5.0

La release è stata integrata con PR #3, merge SHA
`482ca674d05114d41e83db0ee18984c176c13495`. Claude Code è aggiornato da 0.4.0 a 0.5.0 e
Codex è installato alla 0.5.0. È necessaria una nuova sessione per applicare la versione
aggiornata.

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
«avvia il run» (cx). Sottocomandi: `start`, `status`, `peso`, `credito`, `stop`, `riprendi`;
`/orchestratore:orchestra-status` è il report di sola lettura.

`SPEC.md` è la fonte dei requisiti, `ROADMAP.md` la fonte delle milestone e del loro stato,
`.orchestratore/RUN.md` l'unica fonte operativa. All'avvio il RUN contiene al massimo due
milestone aperte; viene aggiornato e ricompattato entro 300 righe/15 KB. Non vengono creati
`recon.md`, context pack o prompt-file permanenti; SQLite conserva soltanto stato macchina,
lease, fasi, retry, checkpoint ed event-id.

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
