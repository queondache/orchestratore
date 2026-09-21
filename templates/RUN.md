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
Motivo del modello/effort ed eventuale trigger premium: <motivo | n/a>
Controller: SQLite locale per stato macchina, lease, fasi, retry, checkpoint ed event-id; run_id: <id>
Ruoli: stratega Claude; massimo 2 builder Codex; reviewer Claude separato
Tetto: max 2 builder; pool verifica separato, max 1 in volo
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
SPEC.md è la fonte dei requisiti; ROADMAP.md è la fonte delle milestone e del loro stato.
Fonte operativa unica: questo documento `.orchestratore/RUN.md`.
Il RUN contiene solo le milestone attive (massimo 2), i task e gli handoff necessari.
È aggiornato e ricompattato, non è append-only; limite: massimo 300 righe e 15 KB.
Non esistono `recon.md`, context pack o prompt-file permanenti: i worker ricevono riferimenti
a SPEC, ROADMAP e alla sezione task pertinente. SQLite non sostituisce questo documento.

## Piano di parallelizzazione

Solo le milestone attive selezionate da `ROADMAP.md` sono riportate qui; le altre restano
nella ROADMAP. Una riga per milestone, glob e dipendenze reali.

```text
<ID> | tier <1|2|3> | scrivibili: <glob, glob> | interfacce: <schema/tipi/firme> | dipende da: <ID | nessuna>
```

Prova di indipendenza (file reali, `comm -12` sui glob):
- parallelizzabili: <coppie>
- in conflitto: <coppia → file sovrapposti> → contract-first <ID>

## Milestone attive (massimo 2)

| ID | Milestone | Stato | Dipendenze | Owner |
|---|---|---|---|---|
| M<n> | <nome da ROADMAP> | in coda | <ID | nessuna> | Claude |

Se una milestone si chiude: aggiorna prima `ROADMAP.md`, poi compatta questa sezione e apri
la prossima milestone aperta eleggibile. Non copiare l'intera ROADMAP nel RUN.

## Registro task

### T-<id> — <milestone> — <stato>

Risultato osservabile per l'utente:
Dipendenze completate e contratto congelato:
File scrivibili (un owner per file):
File condivisi che integra il cervello:
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
