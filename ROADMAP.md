# ROADMAP — orchestratore

Delta fra `SPEC.md` e il codice reale. Stato con evidenza eseguita, mai per assunzione.
Ultimo allineamento: 21/09/2026, versione 0.5.0; PR #3 mergiata con merge SHA
`482ca674d05114d41e83db0ee18984c176c13495`.

## Stato per milestone

| ID | Milestone | Stato | Evidenza |
|---|---|---|---|
| M1 | Scheletro del plugin: skill, reference, template, gate strutturale | **FATTO** | `tests/check-structure.sh` verde; `docs/plans/2026-09-12-m1-scheletro-plugin.md` |
| M2 | Agent del plugin e bridge verso l'altro runtime | **FATTO** | `agents/` (5 file), `bin/spawn-*.sh`, `tests/check-bridge.sh` verde; PR #1 |
| M3 | Comandi slash e hook | **FATTO** | `commands/` (2 file), `hooks/hooks.json` + 2 script, `tests/check-hooks.sh` verde; PR #1 |
| M4 | Autonomia: default scritti, rosso mai stop, chiusura con doc allineati | **FATTO** | invarianti A1-A7 in `check-regressions.sh`; mutazioni A uccise |
| M5 | Parallelismo a due livelli con prova di indipendenza e contract-first | **FATTO** | `references/parallelismo.md`; invarianti B1-B3; `## Piano di parallelizzazione` in `templates/RUN.md` |
| M6 | Verifica con oracolo e merge per classe di rischio | **FATTO** | `references/verifica.md`, `agents/verificatore.md`, `agents/pre-merge.md`; invarianti B4-B5 |
| M7 | Contesto e memoria del run: RUN unico compatto, assunzioni, metriche, osservatore KO | **FATTO** | `project-adapter.md` §3-bis; sezioni `## Assunzioni` e `## Metriche` in `templates/RUN.md`; invarianti B6-B9 |
| M8 | Run pilota end-to-end su un progetto reale | **MANCANTE** | fuori perimetro 0.5.0 e non bloccante; nessun run mai eseguito; `SPEC.md [APERTO-01]` |
| M9 | Evidenza del modello che ha davvero girato | **MANCANTE** | fuori perimetro 0.5.0 e non bloccante; `routing.md` regola 9 lo esige, nessun meccanismo lo produce; `SPEC.md [APERTO-02]` |
| M10 | Routing economico per modello, effort e task | **FATTO** | `references/routing.md`; invariante I11; gate e mutazioni verdi; review indipendente sul commit di release |
| M11 | Controller persistente SQLite e CLI congelata | **FATTO** | `controller/**`, `bin/orchestratore-controller`, `tests/check-controller.sh`; 14 test OK; review Claude Sonnet su fingerprint `bd8f3b22` |
| M12 | Contratto plugin, ingressi e contesto persistente | **FATTO** | skill/reference/template/test aggiornati; struttura e regressioni verdi; mutation suite verde; review Terra su `e42dba2d` |
| M13 | Integrazione e release 0.5.0 | **FATTO** | PR #3 mergiata con merge SHA `482ca674d05114d41e83db0ee18984c176c13495`; gate finali locali verdi e review indipendente OK |
| M14 | Profili di parallelismo 5 milestone / 15 bugfix e pool review proporzionato | **FATTO** | Dispatch concorrente 5/15, review 2/5, ownership fail-closed e admission atomica; 33 test controller, regressioni e mutation suite verdi; review indipendente finale OK |

M4-M7 sono state consegnate nella stessa PR #1, verificata in modo indipendente da Fable
sull'hash che va in `main`.

## Prossima milestone

**M8 — Run pilota end-to-end.** Bloccata da una decisione di Andrea: su quale progetto girare
e con che budget di credito. Il pilota deve includere almeno due milestone di cui una coppia
con glob che si intersecano, così da esercitare la lane contract-first, e deve chiudersi
producendo la sezione `## Metriche` di `RUN.md`. M8 non è parte della release 0.5.0 e non ne
blocca la consegna.

M9 resta fuori perimetro 0.5.0 e non bloccante: l'evidenza runtime del modello sarà affrontata
in una milestone successiva.

M14 rende esplicito il profilo prima del dispatch: `milestone` fino a 5 builder, `bugfix` fino
a 15; owner esclusivo per file, conflitti contract-first o seriali, processi pesanti seriali.
Reviewer e pre-merge restano fuori quota builder; il pool review è `ceil(builder della wave/3)`,
con cap 2/5 e precedenza delle consegne sulle nuove assegnazioni.

Definition of done di M8:

- `RUN.md` reale con piano di parallelizzazione e prova di indipendenza sui file veri;
- almeno una lane contract-first mergiata prima delle consumatrici;
- almeno un task verificato con i quattro passi, oracolo incluso, output raw nel log;
- almeno una milestone chiusa con merge automatico e una lasciata come PR in attesa;
- `## Metriche` compilata, con il numero di interruzioni chieste ad Andrea.

## Non in roadmap

CI del repository: scelta di Andrea del 13/09/2026, vale il fallback suite locale del gate di
merge (`references/lane.md`). Se un giorno il repo avrà required checks, il gate cambia forma
da solo senza modifiche alla skill.
