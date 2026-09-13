# Orchestratore 0.4.0 — parallelismo a due livelli, verifica con oracolo, plugin eseguibile

Data: 13/09/2026. Sostituisce il disegno 0.1.0 dove diverge; il resto resta valido.

## Obiettivo

Un run notturno che la mattina lascia **main avanzato sulle milestone sicure e PR pronte su
quelle rischiose**, senza aver svegliato Andrea e senza aver barattato qualità per velocità.
Metrica principale: **quante volte il run ha interrotto Andrea**. Un run veloce che consegna
lavoro non verificato è un run fallito.

## Colli di bottiglia da cui nasce questa versione

1. Il run aspettava Andrea per cose che poteva decidere.
2. Le lane non erano indipendenti davvero: l'indipendenza era un'opinione del cervello.
3. Contesto e riprese: ogni worker riesplorava il repo, il cervello saturava integrando.

## Decisioni

| Tema | Decisione | Dove vive |
|---|---|---|
| Default del contratto | Scritti, non chiesti: non presidiato, git automatico, budget `tutte`, verifica obbligatoria | `SKILL.md` §1 |
| Gate rosso | Non è mai una condizione di stop; dopo due KO consecutivi si cambia **strategia e modello** | `SKILL.md` §1, `lane.md`, `routing.md` 7-bis |
| Indipendenza delle lane | Calcolata sui file reali (`comm -12` sui glob), scritta prima di occupare uno slot | `parallelismo.md` §2 |
| Lane che si toccano | Lane **contract-first** che congela e merga l'interfaccia, poi parallelo; se non isolabile, seriale | `parallelismo.md` §3 |
| Granularità | 3 milestone × 3 task = 9 builder; verifica e integrazione in un pool separato (max 3) | `parallelismo.md`, `config.toml` |
| Integrazione | Task con contratto dato a un `integratore`. Il cervello non scrive codice | `parallelismo.md` §5 |
| Verifica | Quattro passi con evidenza raw: hash, gate verde, **oracolo**, perimetro | `verifica.md` |
| Oracolo | Revert dei soli file non-test: la suite mirata deve diventare rossa, altrimenti `KO: oracolo assente` | `verifica.md`, `agents/verificatore.md` |
| Merge | Regola fissa sul diff reale: tier 1-2 auto-merge, tier 3 o area sensibile PR in attesa | `verifica.md`, `lane.md` |
| Gate CI assente | Fallback suite locale eseguita dal verificatore sull'hash della PR, output raw | `lane.md` |
| Domande | Solo prodotto, SPEC, autorizzazioni. Le scelte reversibili e locali diventano `## Assunzioni` | `SKILL.md` §5 |
| Risposte di Andrea | Propagate nello stesso turno in registro, SPEC, ROADMAP e perimetri congelati | `SKILL.md` §5 |
| Contesto | `.orchestratore/recon.md` scritto una volta e passato per path, scade con la revisione base | `project-adapter.md` |

## Cosa è diventato eseguibile

- `agents/`: `worker-impl`, `worker-mech`, `verificatore`, `pre-merge`, `integratore`.
  Il `model` del frontmatter è il default; il cervello può passarne uno diverso per chiamata.
- `bin/spawn-cx.sh` e `bin/spawn-cc.sh`: bridge con `--dry-run`, validazione del modello
  contro `routing.md` e rifiuto prima di spendere credito (65 modello, 65 effort, 66 cwd o
  prompt, 64 argomenti).
- `commands/orchestra.md` e `commands/orchestra-status.md`: porta d'ingresso, non logica
  duplicata.
- `hooks/`: `guard-run.sh` blocca in `PreToolUse` i comandi che la skill vieta in modo
  assoluto, ma **solo** quando esiste `.orchestratore/brain.lock`; `session-run-state.sh`
  mette in contesto un run presente. L'analisi non sta nello shell ma in `guard_run.py`:
  cinque giri di verifica hanno mostrato che un confronto a pattern non distingue un
  comando da una stringa che parla di quel comando, quindi o lasciava passare le varianti
  o bloccava i messaggi di commit. L'analizzatore tokenizza rispettando le virgolette,
  tratta il corpo di un heredoc come dato, toglie i commenti riga per riga senza
  mangiarsi l'a capo che separa due comandi, legge le opzioni con valore per programma
  (`-n` porta un valore per `nice` e non per `sudo`), salta gli operandi fissi dei
  wrapper (la durata di `timeout`, il file di `flock`, la directory di `chroot`), trova
  il comando di una shell come primo operando dopo le opzioni e guarda dentro le
  sostituzioni anche quando sono chiuse fra virgolette. Senza `python3` non c'e'
  analisi: la guardia lo dichiara su stderr e lascia passare, invece di fingere una
  protezione che non c'e'. Il modello di minaccia e i limiti accettati stanno nel
  docstring di `guard_run.py`; `tests/copertura-tabelle.py` impedisce che una voce delle
  tabelle resti senza un comando che la esercita.

## Gate

| Gate | Cosa prova |
|---|---|
| `tests/check-structure.sh` | struttura, manifest, presenza e forma di agent, bridge, comandi, hook |
| `tests/check-regressions.sh` | invarianti di testo: ogni regola di metodo è ancora scritta |
| `tests/check-regressions-mutations.sh` | ogni invariante è stato visto rosso almeno una volta; le mutazioni sul comportamento della guardia girano contro il gate eseguibile degli hook |
| `tests/check-bridge.sh` | i bridge compongono la riga giusta e rifiutano gli input invalidi, senza spendere credito |
| `tests/check-hooks.sh` | la guardia blocca il distruttivo con un run attivo, non interferisce fuori |

## Aperto

- Nessun run reale eseguito end-to-end: i gate provano il testo e il cablaggio, non il
  comportamento su un progetto vero. Serve un run pilota su due milestone con una
  contract-first, e la lettura delle metriche prodotte.
- Questo repo non ha `SPEC.md` né `ROADMAP.md`: l'orchestratore non può ancora orchestrare se
  stesso.
