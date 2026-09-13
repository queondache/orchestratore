# ROADMAP — orchestratore

Delta fra `SPEC.md` e il codice reale. Stato con evidenza eseguita, mai per assunzione.
Ultimo allineamento: 13/09/2026, versione 0.4.0, PR
[#1](https://github.com/queondache/orchestratore/pull/1).

## Stato per milestone

| ID | Milestone | Stato | Evidenza |
|---|---|---|---|
| M1 | Scheletro del plugin: skill, reference, template, gate strutturale | **FATTO** | `tests/check-structure.sh` verde; `docs/plans/2026-09-12-m1-scheletro-plugin.md` |
| M2 | Agent del plugin e bridge verso l'altro runtime | **FATTO** | `agents/` (5 file), `bin/spawn-*.sh`, `tests/check-bridge.sh` verde; PR #1 |
| M3 | Comandi slash e hook | **FATTO** | `commands/` (2 file), `hooks/hooks.json` + 2 script, `tests/check-hooks.sh` verde; PR #1 |
| M4 | Autonomia: default scritti, rosso mai stop, chiusura con doc allineati | **FATTO** | invarianti A1-A7 in `check-regressions.sh`; mutazioni A uccise |
| M5 | Parallelismo a due livelli con prova di indipendenza e contract-first | **FATTO** | `references/parallelismo.md`; invarianti B1-B3; `## Piano di parallelizzazione` in `templates/run.md` |
| M6 | Verifica con oracolo e merge per classe di rischio | **FATTO** | `references/verifica.md`, `agents/verificatore.md`, `agents/pre-merge.md`; invarianti B4-B5 |
| M7 | Contesto e memoria del run: recon, assunzioni, metriche, osservatore KO | **FATTO** | `project-adapter.md` §3-bis; sezioni `## Assunzioni` e `## Metriche` in `templates/run.md`; invarianti B6 |
| M8 | Run pilota end-to-end su un progetto reale | **MANCANTE** | nessun run mai eseguito; `SPEC.md [APERTO-01]` |
| M9 | Evidenza del modello che ha davvero girato | **MANCANTE** | `routing.md` regola 9 lo esige, nessun meccanismo lo produce; `SPEC.md [APERTO-02]` |

M4-M7 sono state consegnate nella stessa PR #1, verificata in modo indipendente da Fable
sull'hash che va in `main`.

## Prossima milestone

**M8 — Run pilota end-to-end.** Bloccata da una decisione di Andrea: su quale progetto girare
e con che budget di credito. Il pilota deve includere almeno due milestone di cui una coppia
con glob che si intersecano, così da esercitare la lane contract-first, e deve chiudersi
producendo la sezione `## Metriche` di `run.md`.

Definition of done di M8:

- `run.md` reale con piano di parallelizzazione e prova di indipendenza sui file veri;
- almeno una lane contract-first mergiata prima delle consumatrici;
- almeno un task verificato con i quattro passi, oracolo incluso, output raw nel log;
- almeno una milestone chiusa con merge automatico e una lasciata come PR in attesa;
- `## Metriche` compilata, con il numero di interruzioni chieste ad Andrea.

## Non in roadmap

CI del repository: scelta di Andrea del 13/09/2026, vale il fallback suite locale del gate di
merge (`references/lane.md`). Se un giorno il repo avrà required checks, il gate cambia forma
da solo senza modifiche alla skill.
