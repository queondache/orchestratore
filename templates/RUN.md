# Run orchestratore — <progetto>

stato: attivo | handoff
cervello: cc-fable | cx-gpt-6-astra
avviato: <ISO 8601>
ultimo aggiornamento: <ISO 8601>

## Contratto di autonomia

Run mode: milestone-budget | bug-budget | while-quality-high
Profilo parallelismo: milestone | bugfix
Fonte profilo: <richiesta esplicita | config progetto | rilevamento> — <evidenza>
Milestone budget: <n | tutte | n/a>
Bug budget: <n | tutti | n/a>
Peso: dev cx <n> / cc <n>; verifica <cc|cx|opposto>
Politica costo: cheapest-capable; Astra cervello=medium; Luna>=medium; Terra>=medium; Sol>=low; Astra worker>=low
Motivo del modello/effort ed eventuale trigger premium: <motivo | n/a>
Controller: SQLite locale per stato macchina, lease, fasi, retry, checkpoint ed event-id; run_id: <id>
Ruoli: stratega Claude; builder Codex di default; reviewer Claude separato
Tetto: milestone max 5 builder / 2 review; bugfix max 15 builder / 5 review
Capacità review corrente: ceil(builder della wave/3), entro il cap del profilo; coda review: <n>
Tetto domande aperte: <n>
Gate verde: build=<cmd> test=<cmd> lint=<cmd>
Required checks sul branch base: sì | no
Verifica: obbligatoria a ogni consegna di codice, verificatore ≠ builder
Rosso: firma persistita e deduplicata; max 2 tentativi/approccio, max 2 approcci automatici
Run non presidiato: sì | no
Autorizzazioni Git: <commit+push+PR automatici | solo lettura>
Classe di rischio: tier 1-2 auto-merge; tier 3 o area sensibile PR in attesa

Fonte requisiti: `SPEC.md`.
Fonte milestone e del loro stato: `ROADMAP.md`.
Fonte bug e del loro stato: <path/query congelata | n/a>.
SPEC.md è la fonte dei requisiti; ROADMAP.md è la fonte delle milestone e del loro stato.
Fonte operativa unica: questo documento `.orchestratore/RUN.md`.
Il RUN contiene solo le unità attive (massimo 5 milestone o 15 bug), i task e gli handoff necessari.
È aggiornato e ricompattato, non è append-only; limite: massimo 300 righe e 15 KB.
Non esistono `recon.md`, context pack o prompt-file permanenti: i worker ricevono riferimenti
a SPEC, ROADMAP e alla sezione task pertinente. SQLite non sostituisce questo documento.

## Piano di parallelizzazione

Solo le unità attive selezionate dalla fonte sono riportate qui; le altre restano nella
ROADMAP o nel bug tracker. Una riga per unità, glob e dipendenze reali.

```text
<ID> | tipo <milestone|bug> | tier <1|2|3> | riproduzione/oracolo <ref|n/a> | scrivibili: <glob, glob> | interfacce: <schema/tipi/firme> | dipende da: <ID | nessuna>
```

Prova di indipendenza (file reali, `comm -12` sui glob):
- parallelizzabili: <coppie>
- in conflitto: <coppia → file sovrapposti> → contract-first <ID>

## Unità attive (massimo 5 milestone o 15 bug)

| ID | Tipo | Unità | Stato | Dipendenze | Owner |
|---|---|---|---|---|---|
| M<n>/B<n> | milestone/bug | <nome dalla fonte> | in coda | <ID | nessuna> | <owner> |

Se un'unità si chiude: aggiorna prima la fonte, poi compatta questa sezione e apri la
successiva unità eleggibile. Non copiare l'intera ROADMAP o bug tracker nel RUN.

## Registro task

### T-<id> — <milestone> — <stato>

Risultato osservabile per l'utente:
Dipendenze completate e contratto congelato:
File scrivibili (un owner per file):
File condivisi riservati all'integratore:
Tier / runtime / modello / effort:
Strategia Claude:
Prossimo passo builder Codex:
Gate verde (comandi esatti):
Verificatore assegnato (modello diverso dal builder):
Criterio di completamento:
Decisioni aperte e condizioni di stop:
Consegna: <hash, comandi eseguiti, output, limiti residui>
verifica T-<id>: <modello/runtime> su <hash> → OK | OK CON RISERVE | KO
comando: <comando eseguito> → <esito raw>
Firma KO: <gate|errore normalizzato|hash diff> — approccio_id: <A1|A2>
Tentativi approccio: <0|1|2> — cambio ipotesi/strategia/modello: <cosa è cambiato | n/a>
Blocco tecnico: <no | evidenza, owner, condizione di ripresa>

## Domande

Aperte: <n> / tetto <n>. Bloccanti: <ID e task | nessuna>.

## Assunzioni

Le assunzioni ammesse sono reversibili e locali.

| ID | Assunzione | Reversibile | Punto di applicazione | Stato |
|---|---|---|---|---|
| A-POOL-REVIEW | Pool review separato = ceil(builder della wave/3), cap 2 milestone / 5 bugfix; review prima di nuovi builder | sì | scheduler del run | attiva |
| A-<id> | <testo> | sì | <file o task> | attiva |

## Stato durevole del controller

Fase: <strategia|implementata|verificata|pronta|integrata|documentata|finalizzata>
Finalizzata: <sì|no>
Ripresa parziale: <A|B|C|D|E|nessuna>

## Metriche

Milestone chiuse: <n> · PR in attesa: <n> · Interruzioni chieste ad Andrea: <n>
Giri di KO: <n> · Rilavorazioni: <n> · Token: <input/output | non disponibile>

## Handoff

Obiettivo e budget residuo:
Task attivi (owner, stato):
Impronta modifiche non committate:
Evidenze verificate:
Prossima azione (una sola):
