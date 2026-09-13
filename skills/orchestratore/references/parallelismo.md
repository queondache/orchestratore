# Parallelismo a due livelli: milestone e task

Due livelli: **lane** = una milestone, **task** = una parte di una lane. Tetti per progetto:
3 milestone attive × 3 task per milestone, **massimo 9 worker builder**. Verificatori,
integratore e pre-merge non occupano slot builder: pool di verifica separato, massimo 3
verifiche in volo. Uno slot builder si occupa solo con la prova di indipendenza qui sotto.

## 1. Piano di parallelizzazione, prima di qualsiasi delega

Il cervello scrive in `run.md` la sezione `## Piano di parallelizzazione`, una riga per
milestone aperta:

```text
<ID> | tier <1|2|3> | scrivibili: <glob, glob> | interfacce: <schema/tipi/firme toccati> | dipende da: <ID | nessuna>
```

Le aree scrivibili sono **glob**, non descrizioni. Ricavale da ROADMAP, SPEC e struttura del
repo. Una milestone non riconducibile a un insieme di glob non è pronta per il parallelo: va
prima ridotta a perimetro.

## 2. Prova di indipendenza, sui file reali

Due milestone vanno in parallelo solo se valgono **entrambe** le condizioni:

- intersezione dei glob scrivibili vuota, dimostrata sui file del repo:
  `comm -12 <(git ls-files <glob A> | sort) <(git ls-files <glob B> | sort)` senza output;
- nessuna interfaccia condivisa dichiarata scrivibile da più di una lane.

Esito in `run.md`: coppie parallelizzabili e coppie in conflitto con i file che si
sovrappongono. Intersezione non vuota = il parallelo **non** si apre. Nessuna prova scritta =
nessuno slot occupato.

## 3. Contract-first quando due lane si toccano

Con intersezione non vuota, prima una **lane contract-first**: corta, un solo worker, tocca
solo l'interfaccia condivisa (schema, migrazione, tipi, firme API, contratto di evento), la
fa verificare e **mergiare su main**. Solo dopo partono in parallelo le lane che la consumano,
su base aggiornata.

Regole della lane contract-first:

- non implementa comportamento, definisce e congela la forma;
- l'interfaccia prodotta è **file congelato** per le lane consumatrici: nessuna la modifica,
  chi ha bisogno di cambiarla si ferma al checkpoint e riporta al cervello;
- se l'interfaccia non è isolabile in una lane corta, le milestone vanno **seriali**: il
  parallelo forzato costa più della rilavorazione che evita.

Dopo ogni merge su main il piano si ricalcola: i glob cambiano.

## 4. Task dentro la lane

- `m/<slug>` è il **branch di integrazione** della milestone, creato dal cervello da `main`.
- Ogni task figlio ha branch `m/<slug>/t<NN>` e worktree proprio, con glob scrivibili
  disgiunti dagli altri task della stessa lane. Un file, un task.
- I task che toccano l'interfaccia interna condivisa della milestone vanno **prima**, da
  soli: è la §3 a scala ridotta.
- Non spezzare per principio: un task sotto la mezz'ora di lavoro o con un solo file non si
  divide, il coordinamento costa più dell'esecuzione.
- Ogni task consegna con verifica propria (SKILL.md §4) prima di entrare nell'integrazione.

## 5. Integratore: mai il cervello

La fusione dei branch task in `m/<slug>` è un **task con contratto**, assegnato a un worker
integratore. Fa solo: merge dei task nell'ordine dichiarato, risoluzione dei conflitti
meccanici, gate verde sull'integrazione, consegna con hash e output raw. Nessuna
implementazione nuova: un conflitto che richiede una decisione torna al cervello, che riapre
il task giusto invece di farlo risolvere all'integratore.

**Il cervello non scrive codice.** Scrive `run.md`, il registro quesiti, i contratti e
l'handoff. Se integra, satura il contesto proprio quando le lane sono più aperte.

## 6. Precedenza e code

Una consegna pronta ha sempre precedenza su una nuova assegnazione. Oltre le 3 verifiche in
volo la consegna resta in coda e il report la segnala come `in coda di verifica`. Uno slot
builder libero senza lavoro indipendente dimostrato resta libero: i tetti non sono obiettivi.
