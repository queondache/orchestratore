# Parallelismo a due profili: milestone e bugfix

Il run congela prima della prima assegnazione un profilo concreto:

- `milestone`: unità di consegna = milestone di ROADMAP, massimo **5 builder** simultanei;
- `bugfix`: unità = bug riproducibile e delimitato, massimo **15 builder** simultanei.

Il limite conta tutti i builder, qualunque sia il runtime. Stratega, reviewer, pre-merge e
integratore non consumano slot builder. Il pool review è separato: capacità istantanea
`ceil(builder della wave/3)`, con massimo 2 nel profilo `milestone` e 5 in `bugfix`; la wave
conta builder in corso e consegne in attesa di review, così la capacità non scende mai a zero
con review pendenti. Una consegna
in attesa di review ha precedenza su un nuovo builder: non saturare l'implementazione mentre
la coda cresce. I tetti sono capacità, non obiettivi.

## 0. Rilevamento non ambiguo del profilo

La precedenza è: richiesta esplicita nel prompt → valore progetto diverso da `auto` →
rilevamento. Il rilevamento sceglie `bugfix` solo se il perimetro richiesto è un elenco di bug
con riproduzione/oracolo individuali e nessuna milestone è l'unità di consegna; sceglie
`milestone` se il lavoro deriva da ROADMAP o contiene feature, refactor o milestone. Un run
misto congela `milestone`; per usare 15 builder va chiusa la fase milestone e aperta una nuova
fase `bugfix`. `auto` non può essere scritto nel RUN né passato al controller. Prima del primo
dispatch scrivi profilo, motivo e fonte della decisione.

Il profilo determina anche la policy di arresto predefinita: `milestone-budget: tutte` oppure
`bug-budget: tutti` dalla fonte congelata. La formula review 1 ogni 3 builder, cap 2/5, è
un'assunzione operativa reversibile del run: può essere configurata prima del dispatch senza
mescolare review e quota builder né alzare modello/effort.

## 1. Piano di parallelizzazione, prima di qualsiasi delega

Il cervello scrive in `RUN.md` la sezione `## Piano di parallelizzazione`, una riga per
unità aperta (`M-*` o `B-*`):

```text
<ID> | tipo <milestone|bug> | tier <1|2|3> | riproduzione/oracolo <ref|n/a> | scrivibili: <glob, glob> | interfacce: <schema/tipi/firme toccati> | dipende da: <ID | nessuna>
```

Le aree scrivibili sono **glob**, non descrizioni. Ricavale da ROADMAP, SPEC, bug tracker e
struttura del repo. Un'unità non riconducibile a un insieme di glob non è pronta per il parallelo: va
prima ridotta a perimetro.

## 2. Prova di indipendenza, sui file reali

Due unità vanno in parallelo solo se valgono **entrambe** le condizioni:

- intersezione dei glob scrivibili vuota, dimostrata sui file del repo:
  `comm -12 <(git ls-files <glob A> | sort) <(git ls-files <glob B> | sort)` senza output;
- nessuna interfaccia condivisa dichiarata scrivibile da più di una lane.

Esito in `RUN.md`: gruppi parallelizzabili e coppie in conflitto con i file che si
sovrappongono. Intersezione non vuota = il parallelo **non** si apre. Nessuna prova scritta =
nessuno slot occupato.

Nel profilo `bugfix`, bug con stack trace, causa probabile, modulo o file condiviso formano
prima un cluster. Un solo owner riproduce e isola la causa comune; poi il cluster diventa
contract-first o si serializza. Quindici ticket non equivalgono automaticamente a quindici
unità indipendenti.

## 3. Contract-first quando due lane si toccano

Con intersezione non vuota, prima una **lane/cluster contract-first**: corta, un solo worker, tocca
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
  disgiunti dagli altri task della stessa lane. Il controller registra il path canonico
  del worktree nel task e lo passa al bridge come `task-cwd`; il checkout del progetto è
  solo control plane. Il bridge verifica che sia un root distinto con lo stesso Git common
  dir del progetto, anche quando il worktree è fratello del checkout; il controller ne
  garantisce l'unicità fra task attivi. Un file, un task.
- I task che toccano l'interfaccia interna condivisa della milestone vanno **prima**, da
  soli: è la §3 a scala ridotta.
- Non spezzare per principio: un task sotto la mezz'ora di lavoro o con un solo file non si
  divide, il coordinamento costa più dell'esecuzione.
- Ogni task consegna con verifica propria (SKILL.md §4) prima di entrare nell'integrazione.
- Nessun worker scrive `RUN.md`: lo legge dal project root e restituisce un report
  strutturato. Il controller applica gli aggiornamenti al RUN in serie dopo aver validato
  assignment, generation ed esito, evitando scritture concorrenti e report tardivi.

## 5. Integratore: mai il cervello

La fusione dei branch task in `m/<slug>` è un **task con contratto**, assegnato a un worker
integratore. Fa solo: merge dei task nell'ordine dichiarato, risoluzione dei conflitti
meccanici, gate verde sull'integrazione, consegna con hash e output raw. Nessuna
implementazione nuova: un conflitto che richiede una decisione torna al cervello, che riapre
il task giusto invece di farlo risolvere all'integratore.

**Il cervello non scrive codice.** Scrive `RUN.md`, il registro quesiti, i contratti e
l'handoff. Se integra, satura il contesto proprio quando le lane sono più aperte.

## 6. Precedenza e code

Una consegna pronta ha sempre precedenza su una nuova assegnazione. La capacità review si
ricalcola sulla wave (`ceil(n/3)`) senza superare 2/5; se la coda raggiunge la capacità,
non si aprono nuovi builder finché almeno una review termina. Il report distingue review
attive e in coda. Uno slot builder libero senza lavoro indipendente dimostrato resta libero.

Un solo processo pesante locale gira per volta tramite `~/.orchestratore/heavy.lock`, anche
se più builder sono pronti: build complete, suite DB, browser e container entrano in coda;
ricognizioni, modifiche isolate e test leggeri possono restare paralleli.
