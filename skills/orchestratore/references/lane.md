# Lane: dalla milestone all'integrazione automatica

Una lane è una milestone di ROADMAP.md in lavorazione. Segue la skill `milestone`
(`~/Dev/skills/milestone/SKILL.md`) con queste differenze.

## Fase 1 la produce il cervello

Il cervello scrive il `PERIMETRO` nel formato della skill `milestone` (obiettivo, definition
of done verificabile senza Andrea, aree ammesse, fuori perimetro, vincoli dalla SPEC, STOP)
e lo passa al worker come contratto. **Nessuna approvazione di Andrea per milestone**: il
contratto di autonomia copre il run. Un perimetro passato è congelato: il worker non lo
ridiscute, al massimo si ferma per una delle tre condizioni STOP.

## Fase 0 e Fase 2 nel worker

- Fase 0 rossa (albero sporco, main non allineato, build/test/lint rossi): il worker si
  ferma e riporta al cervello, non ad Andrea. Il cervello **sana**: un rosso preesistente è
  lavoro da fare, non un motivo per sospendere. Sospende solo se sanare esce dal perimetro
  del run o richiede una decisione di prodotto.
- Branch `m/<slug>` da `main` come branch di integrazione della milestone; i task figli su
  `m/<slug>/t<NN>` con worktree proprio. Struttura, owner dei file e integratore in
  [parallelismo](parallelismo.md).
- Esecuzione con `superpowers:writing-plans` poi TDD. Domande: nel registro quesiti di
  `.claude/decisioni.md`, mai ad Andrea. Il cervello valuta se sono bloccanti.
- Nessun file fuori dalle aree ammesse, nessuna dipendenza nuova senza motivo nel ledger.

## Gate verde: definito una volta, scritto in `run.md`

All'avvio il cervello individua i comandi reali di build, test e lint del progetto e li
scrive in `run.md` come `Gate verde: build=<cmd> test=<cmd> lint=<cmd>`. **Verde** significa
i tre comandi a exit 0 con output raw nel report; niente di meno vale come verde. Se un
comando non esiste nel progetto scrivilo (`lint=nessuno`) invece di inventarlo. Ogni worker
riceve questi comandi nel contratto del task.

## Verifica a ogni consegna, non solo a fine milestone

Ogni task che consegna codice passa dal verificatore prima che il suo stato avanzi da
`in review`. Il cervello scrive in `run.md` la riga di verifica con modello del verificatore,
hash, comando eseguito ed esito raw (formato in SKILL.md §4). Senza quella riga il task
non è verificato, qualunque cosa dica il builder.

## Fase 3: verificatore assegnato dal cervello

Il worker consegna: diff, hash, comandi eseguiti con output, limiti residui. Il cervello
congela le scritture del builder e lancia il verificatore (agent `verificatore` in CC, o
thread cx col modello determinato da `routing.md`) passando **solo** perimetro, branch, hash, comandi del gate verde
e aree ammesse. Mai il piano, il ledger o l'opinione del builder. I quattro passi obbligatori
— hash, gate verde, **oracolo**, perimetro — e il formato del verdetto sono in
[verifica](verifica.md): un verdetto senza i loro output raw vale come verifica non eseguita.

- OK → Fase 4.
- OK CON RISERVE → correzioni dentro perimetro, un secondo giro, poi Fase 4 con riserve nel report.
- `KO: oracolo assente` e `KO: fuori perimetro` sono KO pieni, mai riserve.
- KO → calcola la firma `gate + errore normalizzato + hash del diff` e confrontala con il
  registro. Una firma invariata già consegnata è deduplicata: non genera un altro giro.
- Massimo **due tentativi per approccio**. Dopo il secondo KO cambia ipotesi, strategia e
  modello; usa il runtime opposto quando disponibile e registra un nuovo `approccio_id`.
- Se la stessa firma resta rossa dopo due approcci distinti, stato `bloccata-tecnica`: scrivi
  evidenza raw, tentativi, modelli, owner e condizione osservabile di ripresa; libera lo slot e
  continua il lavoro indipendente. Nessun terzo approccio automatico. Riapri solo quando cambia
  input, diff o evidenza; il rosso della lane non ferma l'intero run.
- **Regola dell'hash**: l'OK vale solo sul codice esatto che va in PR. Ogni correzione dopo
  un verdetto, anche una riga, obbliga a un giro di conferma che non conta nel tetto.
  Nessuna PR senza OK sull'hash che contiene.

## Fase 4: PR

Nel run non presidiato: commit, push e PR normali automatici verso `main`, con il perimetro
nel corpo e ROADMAP.md aggiornata con link PR. Il contratto solo lettura resta un blocco.

## Gate pre-merge

Con PR aperta e CI riportata da `gh pr checks`, il cervello lancia l'agent `pre-merge`
(modello diverso dal builder e, se possibile, dal verificatore; vedi routing regola 1) con:
perimetro, diff della PR, stato CI, verdetto del verificatore con hash. Output obbligatorio:

```text
PRE-MERGE PR #<n> hash <sha>
suggerisco merge: sì | no
motivi (max 3):
- …
rischi residui: <elenco | nessuno>
```

`no` → il cervello riapre la lane sul builder con i motivi.

## Merge e chiusura

Prima del gate, la **classe di rischio** calcolata sul diff reale ([verifica](verifica.md)):
tier 1-2 → auto-merge; tier 3 o area sensibile → PR in attesa di Andrea, stato `pronta`,
milestone contata come 🟡 bloccata da Andrea. La regola è fissa: nessuna promozione e nessun
declassamento discrezionale.

Per le sole milestone tier 1-2, auto-merge consentito solo se: hash esatto revisionato;
verificatore indipendente finale OK su quell'hash; `suggerisco merge: sì`; e il gate di
qualità eseguita, in una delle due forme.

- Repo **con** required checks (`gh pr checks`, o
  `gh api repos/<owner>/<repo>/branches/<base>/protection` che espone
  `required_status_checks`): almeno un required CI check, tutti i required check
  success. Checks assenti, pending, falliti o cancellati bloccano sempre il merge.
- Repo **senza** required checks configurati: vale il **fallback suite locale**. Il
  verificatore — mai il builder — esegue sull'hash esatto della PR i comandi del
  `Gate verde` di `run.md`: build, test e lint tutti a exit 0, comandi e output raw nel
  report e in `run.md`. Suite assente, non eseguibile o parziale = merge bloccato e domanda
  ad Andrea. Un fallback dichiarato senza output raw non vale.

Con il gate passato esegui
`gh pr merge <n> --squash`, verifica con
`gh pr view <n> --json state,mergedAt`, conserva output raw nel report e aggiorna `main`
locale. Non usare force-push, reset o cancellazioni distruttive.
Poi, nello stesso turno e senza chiedere, la milestone diventa **chiusa**:

1. `ROADMAP.md`: milestone a FATTO con link PR e hash di merge;
2. `progress.md`: `Dove siamo` e `Prossimo passo` riscritti sullo stato reale;
3. `.claude/decisioni.md`: decisioni prese nella lane e risposte propagate (SKILL.md §5);
4. `SPEC.md` solo se la lane ha cambiato una regola di prodotto già decisa da Andrea;
5. contatori in `run.md` e celebrazione (SKILL.md §7).

Merge fatto e doc non allineati = milestone **non** chiusa. Chiusa la milestone,
apri subito la lane successiva se restano milestone aperte e budget: il run non finisce
con una milestone, finisce col budget.

Stati distinti in `run.md`: `implementata`, `verificata`, `pronta` (pre-merge sì),
`integrata` (merge fatto), `chiusa` (ROADMAP e contatori aggiornati).
