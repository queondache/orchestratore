# orchestratore

Plugin dual-runtime (Claude Code + Codex) che orchestra worker su più milestone in parallelo e
su più task dentro ogni milestone (3 × 3, max 9 builder), con prova di indipendenza sui file reali,
lane contract-first quando le milestone si toccano e integratore dedicato.
Cervello Fable 5.1 in CC (alternativa gpt-6-astra in cx), sviluppo su cx, verifica su CC con
modello diverso dal builder, gate pre-merge, auto-merge condizionato, registro quesiti,
celebrazione milestone e uso libero delle skill già installate nel perimetro del run.
Il routing è `cheapest-capable`: cervello cx Astra medium; dev Luna da medium, Terra da
medium e Sol da low; Astra worker da low solo quando un trigger osservabile richiede escalation.
Verifica indipendente a ogni consegna, non solo a fine milestone; un gate rosso non ferma il
run: feedback invariato deduplicato, due tentativi per approccio e massimo due approcci
automatici prima di parcheggiare la lane e liberare lo slot. A milestone chiusa: merge, allineamento di
ROADMAP/progress/decisioni e apertura immediata della lane successiva. Il verificatore esegue
quattro passi con evidenza raw — hash, gate verde, oracolo (il test nuovo deve diventare rosso
senza la modifica), perimetro — e il merge automatico vale solo per tier 1-2: tier 3 e aree
sensibili restano PR in attesa.

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

## Aggiornamento

Le installazioni del plugin sono snapshot/cache: le modifiche al repository non vengono
propagate automaticamente. Ogni release richiede un bump di versione, l'update/upgrade del
marketplace e l'update o la reinstallazione del plugin in ciascun runtime.

## Uso

In un progetto con `SPEC.md` e `ROADMAP.md`: `/orchestratore:orchestra start` (CC) oppure
«avvia il run» (cx). Sottocomandi: `start`, `status`, `peso`, `credito`, `stop`, `riprendi`;
`/orchestratore:orchestra-status` è il report di sola lettura.

## Struttura

- `skills/orchestratore/` la skill e le reference (routing, lane, parallelismo, verifica,
  credito, skill-map, adapter-cc, adapter-cx, project-adapter)
- `templates/` run.md, config.toml, state.toml
- `agents/` i cinque agent del plugin (worker-impl, worker-mech, verificatore, pre-merge,
  integratore)
- `bin/` i bridge `spawn-cx.sh` e `spawn-cc.sh`, entrambi con `--dry-run`
- `commands/` `/orchestratore:orchestra` e `/orchestratore:orchestra-status`
- `hooks/` guardia PreToolUse sui comandi vietati durante un run, stato del run a SessionStart
- `tests/` gate strutturale, regressioni, mutazioni, bridge, hook

## Test

```bash
tests/check-structure.sh
tests/check-regressions.sh
tests/check-regressions-mutations.sh
tests/check-bridge.sh
tests/check-hooks.sh
```
