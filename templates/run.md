# Run orchestratore — <progetto>

stato: attivo | handoff
cervello: cc-fable | cx-gpt-6-astra
avviato: <ISO 8601>
ultimo aggiornamento: <ISO 8601>

## Contratto di autonomia

Run mode: milestone-budget | while-quality-high
Milestone budget: <n | tutte | n/a>
Peso: dev cx <n> / cc <n>; verifica <cc|cx|opposto>
Politica costo: cheapest-capable; Astra cervello=medium; Luna>=medium; Terra>=medium; Sol>=low; Astra worker>=low
Tetto: 3 milestone × 3 task = max 9 worker builder; pool verifica separato, max 3 in volo
Tetto domande aperte: <n>
Gate verde: build=<cmd> test=<cmd> lint=<cmd>
Required checks sul branch base: sì | no (se no vale il fallback suite locale)
Verifica: obbligatoria a ogni consegna di codice, verificatore ≠ builder
Rosso: mai uno stop; dopo 2 KO consecutivi cambia strategia e modello
Stop aggiuntivi: <condizioni osservabili>
Run non presidiato: sì | no
Skill: usa liberamente skill installate disponibili; nome/path + SKILL.md completo; fallback equivalente/base se manca
Autorizzazioni Git: <commit+push+PR automatici | solo lettura>
Classe di rischio: tier 1-2 auto-merge; tier 3 o area sensibile PR in attesa di Andrea
Recon riusabile: .orchestratore/recon.md su revisione base <sha>
Auto-merge: solo hash revisionato + verifier indipendente finale OK + pre-merge sì + (≥1 required CI check con tutti i required check success | fallback suite locale verde eseguita dal verificatore)
Chiusura milestone: merge + ROADMAP + progress + decisioni allineati, poi lane successiva
Al limite CC: handoff e stop
Credito: cc <ok|esaurito>; cx <ok|esaurito>

## Piano di parallelizzazione

Una riga per milestone aperta; glob, non descrizioni.

```text
<ID> | tier <1|2|3> | scrivibili: <glob, glob> | interfacce: <schema/tipi/firme> | dipende da: <ID | nessuna>
```

Prova di indipendenza (file reali, `comm -12` sui glob):
- parallelizzabili: <coppie>
- in conflitto: <coppia → file sovrapposti> → lane contract-first <ID> prima del parallelo

## Milestone (totale fissato all'avvio: <n>)

| ID | Milestone | Tier | Classe merge | Stato | PR | Verificatore | Pre-merge |
|---|---|---|---|---|---|---|---|
| M1 | <nome> | <1|2|3> | auto \| in attesa | in coda | | | |

Contatori: 🟢 <completate> · 🟡 <bloccate da Andrea> · 🔴 <mancanti>
Ultima GIF usata: delfino | balena | nessuna

## Registro task

### T-001 — <milestone> — <stato>
Branch: m/<slug>/t01 (integrazione su m/<slug>)
Risultato osservabile per l'utente:
Dipendenze completate e contratto congelato:
File scrivibili (un owner per file):
File condivisi che integra il cervello:
Tier / runtime / modello / effort:
Motivo del modello/effort ed eventuale trigger premium:
Skill obbligatorie: <nome → path esatto>
Recon: .orchestratore/recon.md (revisione base <sha>)
Gate verde (comandi esatti di build, test, lint):
Verificatore assegnato (modello diverso dal builder):
Verifica ammessa e ambiente:
Criterio di completamento:
Decisioni aperte e condizioni di stop:
Prossimo checkpoint:
Consegna: <hash, comandi eseguiti, output, limiti residui>
verifica T-001: <modello/runtime del verificatore> su <hash> → OK | OK CON RISERVE | KO
comando: <comando eseguito dal verificatore> → <esito raw>
KO consecutivi: <n> — cambio strategia/modello: <cosa è cambiato | n/a>

## Domande (dettaglio in .claude/decisioni.md)

Aperte: <n> / tetto <n>. Bloccanti: <ID e task | nessuna>.

## Assunzioni

Ammesse solo se reversibili e locali; altrimenti diventano domanda.

| ID | Assunzione | Reversibile | Dove è applicata | Stato |
|---|---|---|---|---|
| A-001 | <testo> | sì | <file o task> | da confermare |

## Metriche (aggiornate a ogni chiusura di milestone)

Milestone chiuse: <n> · PR in attesa di Andrea: <n>
Interruzioni chieste ad Andrea: <n>   ← metrica principale
Giri di KO totali: <n> (per milestone: <ID n, ID n>)
Rilavorazioni dopo verifica: <n> · Verifiche riassegnate per verdetto senza evidenza: <n>
Escalation premium (Astra/Opus/high): <n; task e trigger>
Durata per milestone: <ID hh:mm> · Token: <input/output | non disponibile>

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
