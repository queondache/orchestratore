# Controller esterno locale: contratto runtime

Il controller locale è l'unico proprietario dello stato del run. La skill descrive il
protocollo; non simula scheduler, persistenza o processi che il controller non espone.
L'interfaccia congelata è JSON CLI:

```text
bin/orchestratore-controller --db <path> init|start|add-task|schedule|complete|fail|checkpoint|status|acquire|release
```

`dispatch` e `run-once` possono aggiungersi, ma il contratto non ne presume la presenza.

## Ingressi equivalenti

App Codex locale, Codex CLI e Claude CLI sono tre ingressi equivalenti allo stesso run:
ricevono lo stesso `project_root` e `run_id`, invocano il controller locale e leggono la
stessa fonte persistente SQLite. L'ingresso non sceglie ruoli, tetti o stato iniziale e non crea
un secondo cervello. Se il controller non è disponibile, registra il blocco e non finge
un run in memoria. L'utente non deve mantenere due terminali aperti.

## Ruoli e setting per-run

Ogni run congela questi setting prima della prima assegnazione:

- stratega: Claude;
- builder: Codex, massimo 2 in volo complessivi;
- reviewer: Claude separato dal builder e dalla strategia operativa della consegna;
- modelli/effort e fallback espliciti, nel rispetto di `routing.md`;
- gate, budget, autorizzazioni e policy Git del run.

Un ingresso può chiedere un cambio solo per le assegnazioni future; il controller lo
persiste come evento del run. Un fallback non può trasformare builder e reviewer nella
stessa identità di verifica.

## Stato durevole e finalizzazione

Ogni transizione è persistita prima di schedulare il passo seguente. `implementata`,
`verificata`, `pronta`, `integrata`, `documentata` e `finalizzata` sono fasi distinte.
Solo `finalizzata` è terminale/completata: codice finito senza PR, merge o documenti
richiesti è il caso E e resta riprendibile, mai `completato`.

Il controller conserva run, task, tentativi, firme KO, hash revisionato, PR/CI/merge,
documenti, domande, credito e checkpoint fino a `finalize`. Un riavvio riconcilia gli
effetti esterni prima di ripeterli e riparte dalla prima fase non provata.

SQLite e la lease del controller sono autoritativi. `.orchestratore/brain.lock` è solo una
proiezione di compatibilità: se diverge da lease/SQLite, riconcilia oppure ferma il run e
non avvia mai un secondo cervello.

## Ripresa dei fallimenti parziali A-E

- A: strategia incompleta → riprende la prima fase senza evidenza durevole.
- B: build interrotta o worker stantio → riprende la prima fase senza evidenza durevole.
- C: implementazione fatta ma review indipendente assente o invalida → riprende la review.
- D: review/PR pronta ma gate di integrazione incompleto → riprende il gate non provato.
- E: codice/PR/merge parziali ma non sono tutti provati esito PR, merge o attesa approvata,
  e documenti ROADMAP/progress/decisioni richiesti → riprende la prima fase non provata.

Nessuna ripresa retrocede una fase provata né duplica un side effect già riconciliato.

## Contesto e retry

Il controller registra uso contesto quando il runtime lo espone. Da 50% persiste un
checkpoint trasferibile con summary, fase, hash esatto, fingerprint del filesystem e session
id, e non apre nuovo lavoro. Da 70% avvia una sessione fresca da quel checkpoint. Se la misura
non è disponibile lo dichiara; non promette né presume auto-compact.

Per ogni firma KO sono ammessi due tentativi per approccio e due approcci distinti. Poi
cambia prospettiva (stratega/modello/ipotesi) oppure parcheggia con evidenza, owner e
condizione di ripresa. Non esiste un quinto tentativo automatico mascherato da review.
