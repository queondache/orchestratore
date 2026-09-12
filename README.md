# orchestratore

Plugin dual-runtime (Claude Code + Codex) che orchestra worker su più milestone in parallelo.
Cervello Fable 5.1 in CC (alternativa gpt-6-astra in cx), sviluppo su cx, verifica su CC con
modello diverso dal builder, gate pre-merge, auto-merge condizionato, registro quesiti,
celebrazione milestone e uso libero delle skill già installate nel perimetro del run.

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
tests/check-regressions.sh
tests/check-regressions-mutations.sh
```
