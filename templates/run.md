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
Run non presidiato: sì | no
Autorizzazioni Git: <commit+push+PR automatici | solo lettura>
Auto-merge: solo hash revisionato + verifier indipendente finale OK + pre-merge sì + ≥1 required CI check + tutti i required check success
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
