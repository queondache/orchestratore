# Lane: dalla milestone alla parola "merge"

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
  ferma e riporta al cervello, non ad Andrea. Il cervello decide se sanare o sospendere.
- Branch `m/<slug>` da `main`, o il worktree assegnato.
- Esecuzione con `superpowers:writing-plans` poi TDD. Domande: nel registro quesiti di
  `.claude/decisioni.md`, mai ad Andrea. Il cervello valuta se sono bloccanti.
- Nessun file fuori dalle aree ammesse, nessuna dipendenza nuova senza motivo nel ledger.

## Fase 3: verificatore assegnato dal cervello

Il worker consegna: diff, hash, comandi eseguiti con output, limiti residui. Il cervello
congela le scritture del builder e lancia il verificatore (agent `verificatore` in CC, o
thread cx con `gpt-5.6-sol`) passando **solo** perimetro e branch. Mai il piano, il ledger o
l'opinione del builder.

- OK → Fase 4.
- OK CON RISERVE → correzioni dentro perimetro, un secondo giro, poi Fase 4 con riserve nel report.
- KO → correzioni, nuovo giro. Massimo 2 KO consecutivi; al terzo la lane si sospende e la
  milestone entra tra le domande per Andrea.
- **Regola dell'hash**: l'OK vale solo sul codice esatto che va in PR. Ogni correzione dopo
  un verdetto, anche una riga, obbliga a un giro di conferma che non conta nel tetto.
  Nessuna PR senza OK sull'hash che contiene.

## Fase 4: PR

Secondo le autorizzazioni del contratto: commit, push, PR verso `main` con il perimetro nel
corpo, ROADMAP.md aggiornata con link PR. Mai merge. Se il contratto è solo lettura, il
cervello presenta il branch pronto e chiede l'autorizzazione.

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

`no` → il cervello riapre la lane sul builder con i motivi. `sì` → il cervello presenta ad
Andrea:

```text
MILESTONE: <nome>   PR: #<n>   CI: <stato da gh>
VERIFICATORE: <OK | OK CON RISERVE + elenco>   giri: <n>
PRE-MERGE (<modello>): suggerisco merge: sì
Scrivi 'merge' per chiudere.
```

## Merge e chiusura

Solo alla parola `merge` di Andrea: `gh pr merge <n> --squash --delete-branch`, verifica
con `gh pr view <n> --json state,mergedAt`, output raw nel report, `main` locale aggiornato.
Poi la milestone è **chiusa**: aggiorna i contatori in `run.md` e celebra (SKILL.md §7).

Stati distinti in `run.md`: `implementata`, `verificata`, `pronta` (pre-merge sì),
`integrata` (merge fatto), `chiusa` (ROADMAP e contatori aggiornati).
