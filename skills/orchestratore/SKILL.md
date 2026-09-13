---
name: orchestratore
description: Cervello multi-agente per progetti con SPEC.md e ROADMAP.md già chiare. Avvia un run che sviluppa più milestone in parallelo, e più task dentro ogni milestone, con worker su Codex (cx) e Claude Code (CC); prova l'indipendenza sui file reali prima di parallelizzare, verifica ogni consegna con un modello diverso dal builder e con oracolo di test, merge automatico solo sui tier bassi. Usa quando Andrea scrive "/orchestra", "orchestratore", "avvia il run", "più milestone in parallelo", "sviluppo notturno", "riprendi", "credito esaurito", o chiede un sistema multi-agente riusabile.
---

# Orchestratore

Trasforma una ROADMAP in consegne verificate; il piano è stato persistente su file e il
cervello usa i tool reali della sessione. **CC** Claude Code · **cx** Codex · **cervello** la
sessione che esegue questa skill · **worker** agente lanciato dal cervello · **lane** una
milestone · **task** una parte di lane.

## 0. Avvio sicuro

1. Leggi le istruzioni del repo (CLAUDE.md, AGENTS.md, SPEC.md, ROADMAP.md, progress.md,
   `.claude/decisioni.md`). Le decisioni di prodotto del progetto prevalgono su questa skill.
2. Controlla `.orchestratore/brain.lock`: se vivo (pid esistente, aggiornato da meno di
   10 minuti) fermati e chiedi. Se stantio, segnalalo e sovrascrivi solo su conferma.
3. Leggi `~/.orchestratore/state.toml` (credito) e `config.toml` globale + `.orchestratore/config.toml`
   del progetto (peso). Se `valido_fino` è passato, chiedi il nuovo peso invece di applicarlo.
4. Ispeziona working tree, branch, worktree, agenti vivi; conserva il lavoro che non è tuo,
   verifica toolchain, ambiente di test, capacità agenti, lane esterne, e scrivi una sola
   volta `.orchestratore/recon.md` ([project-adapter](references/project-adapter.md)).
5. Se `.orchestratore/run.md` esiste con `stato: handoff`, sei in ripresa: vai a §7.
6. Altrimenti chiedi **una** cosa: `standard` (cervello Fable 5.1 in CC) o `alternativo`
   (cervello gpt-6-astra in cx). Tutto il resto del contratto ha un default (§1) e non si
   chiede. Poi scrivi il contratto di autonomia e parti.

Progetto nuovo o ripresa: leggi [project-adapter](references/project-adapter.md).

## 1. Contratto di autonomia

Persisti in `.orchestratore/run.md` (template in `templates/run.md`) prima di delegare:

```text
Cervello: cc-fable | cx-gpt-6-astra
Run mode: milestone-budget | while-quality-high
Milestone budget: <n | tutte | n/a>   (tutte = milestone aperte in ROADMAP.md all'avvio)
Peso: dev cx <n> / cc <n>; verifica <cc|cx|opposto>
Tetto: <k> milestone × <t> task / <w> builder  (default 3 milestone × 3 task / 9 builder)
Tetto domande aperte: <n>
Stop aggiuntivi: <condizioni osservabili>
Autorizzazioni Git: <commit+push+PR automatici | solo lettura>
Run non presidiato: sì | no
Al limite CC: handoff e stop
Credito: cc <ok|esaurito>; cx <ok|esaurito>
Modalità credito: normale | solo-cc | solo-cx | fermo
```

**Default quando Andrea non dice altro**, da scrivere e non da chiedere: `Run non
presidiato: sì`, `Autorizzazioni Git: commit+push+PR automatici`, `Run mode:
milestone-budget`, `Milestone budget: tutte`, tetti di §2, `Verifica: obbligatoria a ogni
consegna di codice`, `Gate verde: build + test + lint`. Confermare un default con Andrea è
tempo perso: si cambia solo se lo scrive lui.

`milestone-budget`: fermati quando N milestone sono **chiuse** (mergiate o consegnate come PR
in attesa, con doc allineati); parziali non contano. `while-quality-high`: continua finché ogni
consegna resta verificabile con evidenza eseguita. La qualità non è più alta solo quando il
comportamento atteso non è né osservabile né testabile, o quando una domanda di prodotto aperta
cambia contratto, architettura, sicurezza, schema dati, comportamento utente, oracolo di test o
definition of done: allora checkpoint e domanda, non abbandono.

**Il rosso non è mai una condizione di stop.** Build, test, lint, CI, review KO, deploy rosso:
si lavora fino al verde. Dopo **due KO consecutivi sullo stesso gate cambia strategia
e modello** — errore raw riletto, `superpowers:systematic-debugging`, riassegnazione a un
modello diverso e al runtime opposto quando il peso lo consente, tier più alto se il rischio lo
giustifica — e ripeti il cambio a ogni coppia di KO successiva. Il run si ferma solo per domanda
di prodotto bloccante, credito esaurito o limite di contesto, mai perché un gate è difficile.
Lavoro autonomo non autorizza a completare la roadmap intera se Andrea non scrive `tutte`.

Nel run non presidiato, commit, push e PR normali automatici sono autorizzati; auto-merge solo
al gate di §4, nessun login, connessione, scope o segreto nuovo e nessun aumento di budget,
spend limit o credito.

## 2. Ruoli, modelli, skill

Tabella completa e regole in [routing](references/routing.md). In sintesi: il cervello sceglie
per ogni task tier, runtime, modello ed effort e li scrive nel contratto del task. Default:
**cx sviluppa, CC orchestra e verifica**. Il verificatore ha sempre un **modello diverso** dal
builder, runtime opposto quando il peso lo consente. Fable orchestra e non verifica, con
un'unica eccezione: modalità solo-CC su task importante (opus costruisce, fable verifica).

Skill obbligatorie per tipo di task in [skill-map](references/skill-map.md): design,
architettura, TDD, lane. Ai worker passi nome e path esatto. Nessun worker inventa o
installa skill.

In ogni run, cervello e worker scelgono, leggono/caricano e invocano liberamente senza
chiedere Andrea tutte le skill già installate e disponibili utili al task; passano nome/path e
seguono il suo `SKILL.md` completo. Usa liberamente la skill utile, senza fermarti sul silenzio.
Se non è disponibile, usa skill equivalente già installata o la procedura base e continua quando
possibile; registra solo un blocco realmente impeditivo. Questa fiducia non
autorizza installare skill nuove, abilitare o modificare globalmente skill o plugin, né nuove
connessioni, login, scope o segreti, mouse, azioni distruttive o aumenti di spesa: tool o app
invocati dalla skill conservano tutti i guardrail 0.1.2.

Tetti per progetto: 3 milestone × 3 task = **9 worker builder**; verificatori, pre-merge e
integratore stanno in un pool a parte, massimo 3 verifiche in volo. Uno slot si occupa solo con
la prova di indipendenza sui file reali scritta nel `## Piano di parallelizzazione`; glob che si
intersecano = lane **contract-first**, non parallelo. Protocollo in
[parallelismo](references/parallelismo.md). Chi scrive non revisiona il proprio codice; a
consegna pronta la review precede nuova implementazione. **Il cervello non scrive codice**:
fondere i branch dei task è un task con contratto dato a un integratore, non lavoro suo.

## 3. Delega

Campi del contratto: sezione `Registro task` di `templates/run.md`, compilata in `run.md`
**prima** di lanciare il worker — risultato osservabile, glob scrivibili con un solo owner, branch
del task, tier/runtime/modello/effort, skill con path, gate verde, verificatore assegnato,
criterio di completamento, condizioni di stop, checkpoint, più `.orchestratore/recon.md` per path
così il worker non riesplora il repo.

Come lanciare: [adapter-cc](references/adapter-cc.md) se il cervello è CC,
[adapter-cx](references/adapter-cx.md) se è cx. I worker non delegano. Solo il cervello
scrive `run.md`, il registro quesiti e l'handoff. Passa sempre cwd e boundary del progetto.

## 4. Lane: dalla milestone all'integrazione automatica

Protocollo in [lane](references/lane.md). Ogni lane segue la skill `milestone` senza la Fase 1:
il perimetro lo produci tu, senza approvazione. Sequenza: perimetro → worker implementa →
verificatore con modello diverso (OK valido solo sull'hash che va in PR) → PR → **gate
pre-merge** con un terzo modello che risponde `suggerisco merge: sì | no` → auto-merge al gate
di lane.md → chiusura. Domande del worker: nel registro quesiti, mai ad Andrea.
Protocollo del verificatore — hash, gate verde, **oracolo** (senza la modifica il test nuovo deve
diventare rosso), perimetro — e **classe di rischio** del merge in
[verifica](references/verifica.md): tier 1-2 auto-merge, tier 3 o area sensibile PR in attesa di
Andrea, regola fissa calcolata sul diff reale senza discrezionalità.

**Verifica obbligatoria a ogni consegna, non solo a fine milestone.** Ogni task che consegna
codice passa dal verificatore prima che il suo stato avanzi, e il cervello scrive in `run.md`
`verifica T-<id>: <modello/runtime> su <hash> → OK | OK CON RISERVE | KO` più
`comando: <comando eseguito> → <esito raw>`. Riga assente, senza hash o senza output raw =
il task resta `in review`; il report del builder non è una verifica. Un task senza codice
(ricognizione, documento) lo dichiara e salta la verifica.

**Chiusura di milestone, in un colpo solo e senza chiedere**: merge al gate (o PR in attesa) →
`ROADMAP.md`, `progress.md` e `.claude/decisioni.md` aggiornati → contatori in `run.md` →
celebrazione (§7) → **apri subito la lane successiva** se restano milestone e budget. Senza doc
allineati la milestone non è `chiusa`; il run finisce col budget, non con una milestone.

## 5. Registro quesiti e gate del debito

Ad Andrea si chiede **solo** di prodotto, SPEC o autorizzazione fuori perimetro. Mai di
skill, tool, modelli, permessi, approccio tecnico o conferma di un default del contratto:
quelle le decidi tu e le scrivi in `run.md`. Una scelta tecnica **reversibile e locale** (nome,
struttura file, libreria già in uso, forma di un test) non è una domanda: decidi, registrala in
`## Assunzioni` di `run.md` con ID, reversibilità e punto di applicazione, e vai avanti.
Irreversibile o non locale = domanda.

Le domande vanno in `.claude/decisioni.md`, sezione registro quesiti: ID, testo, impatto, task
bloccati, stato. Prima di aprire ogni milestone esegui il gate del debito. Il debito è **tossico**
se una domanda aperta cambia contratto, architettura, sicurezza, schema dati, comportamento
utente, oracolo di test o definition of done della prossima milestone; se una milestone precedente
andrebbe dichiarata verificata per assunzione; o se il tetto domande è raggiunto. Con debito tossico: chiudi solo il checkpoint sicuro in volo, poi poni ad Andrea
**una domanda per volta, la più piccola che sblocca**, in modo interattivo (CC: tool di domanda
strutturata con raccomandazione per prima; cx: fermi il turno con la domanda in chiaro). Le altre
si accumulano come conteggio nel report. Non ripetere una domanda invariata: il silenzio non è
mai una decisione.

**Propagazione della risposta, automatica e nello stesso turno.** Appena Andrea risponde:
scrivi la risposta esatta nel registro quesiti e chiudi la domanda con data; se cambia una
regola di prodotto, aggiorna `SPEC.md` nel punto che tocca citando l'ID; aggiorna
`ROADMAP.md` e i perimetri delle milestone coinvolte, in corso o future; rileggi i contratti
congelati in volo, e quello diventato incoerente si ferma al checkpoint, riemetti il
perimetro e passalo al worker; sblocca solo i task che la risposta risolve davvero. Una
risposta che resta nel registro è debito, non decisione. Prima di aprire ogni lane verifica
che SPEC, ROADMAP e perimetro dicano la stessa cosa: se divergono, allinea prima.

## 6. Peso e credito

Il peso guida solo le assegnazioni nuove. Lo stato credito è persistente in
`~/.orchestratore/state.toml`, condiviso tra sessioni e riletto prima di ogni assegnazione; un
flag `esaurito` non scade e cambia solo con un ripristino esplicito. Comandi, failover e
ripristino: [credito](references/credito.md). In sintesi: un runtime `esaurito` non riceve
nuove assegnazioni, i task in volo chiudono solo il checkpoint atomico sicuro, il cervello
esaurito fa handoff all'altro runtime e si ferma, entrambi esauriti = modalità `fermo` senza
capacità simulate. Override in corsa: `/orchestra peso dev cx 60`, non tocca i flag credito.

## 7. Visibilità, celebrazione, handoff, ripresa

Report (`/orchestra status`, a ogni cambio di stato e a ogni checkpoint di lane; mai una
cadenza a tempo che il runtime non ti permette di rispettare):

```text
In corso: <milestone, owner, fase, modello/runtime>
Verificato dall'ultimo report: <evidenza | niente di nuovo>; domande <aperte/tetto; bloccanti>
Peso in uso: dev cx n / cc n; verifica <…>; modalità <normale|solo-cc|solo-cx|fermo>; credito cc <ok|esaurito>, cx <ok|esaurito>
Slot: builder <n>/9, verifiche in volo <n>/3, in coda di verifica <n>; contesto <% | non disponibile>
Prossimo checkpoint: <gate osservabile>
```

A ogni chiusura aggiorna `## Metriche` in `run.md`: milestone chiuse, PR in attesa, giri di KO,
rilavorazioni e **quante volte hai interrotto Andrea**, che è la metrica principale.
**Celebrazione**, a ogni milestone chiusa: una GIF cliccabile alternando delfino e balena, poi
la frase esatta e il recap:

```markdown
[![Delfino che salta](https://media.giphy.com/media/AhV2lfKBfEvcEqj6h3/giphy.gif)](https://giphy.com/gifs/guitarjamz-dolphin-jump-surfing-drone-shot-AhV2lfKBfEvcEqj6h3)

una milestone meno

🟢 <completate> milestone completate
🟡 <bloccate da Andrea> milestone bloccate da Andrea
🔴 <mancanti> milestone mancanti per finire
```

Balena: `[![Balena che sbuffa](https://media.giphy.com/media/Q6rD2TLgqMiHf4a0Pt/giphy.gif)](https://giphy.com/gifs/whale-whales-savethewhales-Q6rD2TLgqMiHf4a0Pt)`.
Conteggi ricalcolati da `run.md`, mai dalla conversazione. `Bloccate da Andrea` = ferme per una sua
decisione o autorizzazione, PR in attesa incluse, mai per un blocco tecnico. `Mancanti` = totale
del piano meno completate; fissa il totale prima di chiudere la prima milestone.

**Handoff** (limite contesto, credito esaurito, `/orchestra stop`, fine run), **ripresa**
(`riprendi`) e **contesto** (target 50%, tetto 70%): in
[project-adapter](references/project-adapter.md). Lo stato serializzato non prova che un worker
sia vivo o che un lavoro sia finito.

## 8. Confini

- Nel run non presidiato commit, push, PR e auto-merge sono autorizzati solo al gate di §4 e per
  le sole milestone tier 1-2. Restano vietati force-push, reset e cancellazioni distruttive,
  modifiche distruttive o massive ai dati di produzione, e ogni acquisto, upgrade o
  aumenti di budget, spend limit o credito.
- Le app già collegate come plugin Codex sono automatiche nel perimetro congelato del task,
  inclusi side effect esterni non distruttivi direttamente richiesti; non autorizzano login,
  connessioni, scope o segreti nuovi, né azioni distruttive. Il mouse è sempre vietato.
- Un solo processo pesante locale per volta, anche tra progetti diversi
  (`~/.orchestratore/heavy.lock`): build, suite DB, browser, container non si sovrappongono.
- Ottimizza criteri di accettazione verificati per token: contratti e path invece di documenti
  interi, `recon.md` invece di riesplorare, token misurati solo se il runtime li espone. Non
  costruire strumenti di coordinamento nuovi salvo richiesta esplicita.

## Anti-pattern

- Chiedere ad Andrea un perimetro dentro un run autorizzato, il permesso di usare una skill
  già installata, o la conferma di un default del contratto.
- Sospendere una lane perché un gate è rosso invece di cambiare strategia e modello.
- Occupare uno slot senza prova di indipendenza scritta, o aprire il parallelo su glob che si
  intersecano invece di fare prima la lane contract-first.
- Cervello che scrive codice, integra branch o risolve conflitti.
- Auto-merge di una milestone tier 3 o che tocca un'area sensibile.
- Accettare un verdetto senza gli output raw dei quattro passi di verifica.
- Avanzare lo stato di un task senza riga di verifica con hash e output raw; o dichiarare una
  milestone completata senza verdetto sull'hash in PR.
- Lasciare una milestone mergiata con ROADMAP, progress o decisioni non aggiornati; o
  registrare una risposta di Andrea senza propagarla in SPEC, ROADMAP e perimetri congelati.
- Fermare il run dopo una milestone quando restano milestone e budget.
- Verificatore o pre-merge con lo stesso modello del builder.
- Riempire gli slot di concorrenza senza lavoro indipendente sul percorso critico.
- Ripetere una domanda invariata, o trasformare il silenzio in una decisione.
- Contare le milestone dalla conversazione invece che da `run.md`, o due cervelli vivi sullo
  stesso progetto.
