---
name: orchestratore
description: Cervello multi-agente per progetti con SPEC.md e ROADMAP.md già chiare. Avvia un run che sviluppa più milestone in parallelo con worker su Codex (cx) e Claude Code (CC), verifica ogni consegna con un modello diverso dal builder, accumula le domande e si ferma solo quando una risposta è bloccante. Usa quando Andrea scrive "/orchestra", "orchestratore", "avvia il run", "più milestone in parallelo", "sviluppo notturno", "riprendi", "credito esaurito", o chiede un sistema multi-agente riusabile.
---

# Orchestratore

Trasforma una ROADMAP in consegne verificate. Il piano è stato persistente su file, non un
servizio: il cervello usa i tool reali della sessione per lanciare e governare i worker.

Glossario: **CC** Claude Code · **cx** Codex · **cervello** la sessione che esegue questa
skill · **worker** agente lanciato dal cervello · **lane** una milestone in lavorazione.

## 0. Avvio sicuro

1. Leggi le istruzioni del repo (CLAUDE.md, AGENTS.md, SPEC.md, ROADMAP.md, progress.md,
   `.claude/decisioni.md`). Le decisioni di prodotto del progetto prevalgono su questa skill.
2. Controlla `.orchestratore/brain.lock`: se vivo (pid esistente, aggiornato da meno di
   10 minuti) fermati e chiedi. Se stantio, segnalalo e sovrascrivi solo su conferma.
3. Leggi `~/.orchestratore/state.toml` (credito) e `config.toml` globale + `.orchestratore/config.toml`
   del progetto (peso). Se `valido_fino` è passato, chiedi il nuovo peso invece di applicarlo.
4. Ispeziona working tree, branch, worktree, agenti vivi. Conserva il lavoro che non è tuo.
5. Verifica toolchain, ambiente di test, capacità agenti, lane esterne.
6. Se `.orchestratore/run.md` esiste con `stato: handoff`, sei in ripresa: vai a §7.
7. Altrimenti chiedi **una** cosa: `standard` (cervello Fable 5.1 in CC) o `alternativo`
   (cervello gpt-6-astra in cx). Poi scrivi il contratto di autonomia (§1).

Progetto nuovo o ripresa: leggi [project-adapter](references/project-adapter.md).

## 1. Contratto di autonomia

Persisti in `.orchestratore/run.md` (template in `templates/run.md`) prima di delegare:

```text
Cervello: cc-fable | cx-gpt-6-astra
Run mode: milestone-budget | while-quality-high
Milestone budget: <n | tutte | n/a>   (tutte = milestone aperte in ROADMAP.md all'avvio)
Peso: dev cx <n> / cc <n>; verifica <cc|cx|opposto>
Tetto: <k> milestone / <w> worker  (default 3 milestone / 6 worker)
Tetto domande aperte: <n>
Stop aggiuntivi: <condizioni osservabili>
Autorizzazioni Git: <dal mandato del progetto: commit+push+PR | solo lettura>
Al limite CC: handoff e stop
Credito: cc <ok|esaurito>; cx <ok|esaurito>
```

`milestone-budget`: fermati quando N milestone sono verificate e pronte all'integrazione.
Parziali e bloccate non contano. `while-quality-high`: continua solo finché ogni gate passa:
contratto non ambiguo, dipendenze e ambiente pronti, verifica focalizzata, review senza
finding grave aperto, nessuna domanda che cambi contratto o definition of done. Due
tentativi falliti sullo stesso gate, review ripetutamente inconcludente o comportamento non
verificabile = qualità non più alta: checkpoint e stop. Una richiesta di lavoro autonomo non
autorizza a completare la roadmap intera se Andrea non scrive `tutte`.

## 2. Ruoli, modelli, skill

Tabella completa e regole in [routing](references/routing.md). In sintesi: il cervello sceglie
per ogni task tier, runtime, modello ed effort e li scrive nel contratto del task. Default:
**cx sviluppa, CC orchestra e verifica**. Il verificatore ha sempre un **modello diverso** dal
builder, runtime opposto quando il peso lo consente. Fable orchestra e non verifica, con
un'unica eccezione: modalità solo-CC su task importante (opus costruisce, fable verifica).

Skill obbligatorie per tipo di task in [skill-map](references/skill-map.md): design,
architettura, TDD, lane. Ai worker passi nome e path esatto. Nessun worker inventa o
installa skill.

Tetto 3 milestone / 6 worker per progetto, tetti non obiettivi: apri parallelo solo con
contratti congelati, dipendenze soddisfatte, file senza owner sovrapposti, verifica pronta.
Chi scrive non revisiona il proprio codice. Appena una consegna è pronta, la review ha
precedenza su nuova implementazione.

## 3. Delega

Registra in `run.md` prima di lanciare il worker:

```text
Task / milestone:
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
```

Come lanciare: [adapter-cc](references/adapter-cc.md) se il cervello è CC,
[adapter-cx](references/adapter-cx.md) se è cx. I worker non delegano. Solo il cervello
scrive `run.md`, il registro quesiti e l'handoff. Passa sempre cwd e boundary del progetto.

## 4. Lane: dalla milestone alla parola "merge"

Protocollo in [lane](references/lane.md). Ogni lane segue la skill `milestone` senza la
Fase 1: il perimetro lo produci tu, senza chiedere approvazione ad Andrea. Sequenza:
perimetro → worker implementa (Fasi 0, 2) → verificatore con modello diverso (Fase 3, OK
valido solo sull'hash che va in PR) → PR (Fase 4, mai merge) → **gate pre-merge** con un
terzo modello che risponde `suggerisco merge: sì | no` → presenti ad Andrea e attendi la
parola `merge`. Domande del worker: nel registro quesiti, mai ad Andrea.

## 5. Registro quesiti e gate del debito

Le domande vanno in `.claude/decisioni.md`, sezione registro quesiti: ID, testo, impatto,
task bloccati, stato. Prima di aprire ogni milestone esegui il gate del debito. Il debito è
**tossico** se una domanda aperta cambia contratto, architettura, sicurezza, schema dati,
comportamento utente, oracolo di test o definition of done della prossima milestone; se una
milestone precedente andrebbe dichiarata verificata per assunzione; o se il tetto domande è
raggiunto. Con debito tossico: chiudi solo il checkpoint sicuro in volo, poi poni ad Andrea
**una domanda per volta, la più piccola che sblocca**, in modo interattivo (CC: tool di
domanda strutturata con raccomandazione per prima; cx: fermi il turno con la domanda in
chiaro). Domande non bloccanti si accumulano e compaiono nel report come conteggio. Non
ripetere una domanda invariata. Il silenzio non è mai una decisione.

## 6. Peso e credito

Il peso guida solo le assegnazioni nuove; i task in volo finiscono dove sono. Override in
corsa: `/orchestra peso dev cx 60`. Credito (`~/.orchestratore/state.toml`, condiviso tra
tutte le sessioni aperte):
- `/orchestra credito cx esaurito` → peso `dev cc 100, verifica cc`, routing solo-CC.
  I task cx in volo finiscono il checkpoint corrente, poi vengono riassegnati se non consegnano.
- `/orchestra credito cc esaurito` con cervello CC → scrivi l'handoff, marca il flag in
  `run.md`, chiedi ad Andrea di aprire cx e scrivere `riprendi`. Il cervello cx parte con
  `dev cx 100, verifica cx`.
- `/orchestra credito <runtime> ok` → ripristina il peso salvato prima dell'esaurimento.

## 7. Visibilità, celebrazione, handoff, ripresa

Report (`/orchestra status`, a ogni cambio di stato, comunque ogni 10 minuti):

```text
In corso: <milestone, owner, fase, modello/runtime>
Verificato dall'ultimo report: <evidenza | niente di nuovo>
Domande: <aperte/tetto; bloccanti con ID e task | nessuna>
Peso in uso: dev cx n / cc n; verifica <…>; credito cc <ok|esaurito>, cx <ok|esaurito>
Contesto: <percentuale se il runtime la espone | non disponibile>
Prossimo checkpoint: <gate osservabile>
```

**Celebrazione**, a ogni milestone verificata e chiusa: una GIF cliccabile, alternando
delfino e balena tra celebrazioni consecutive, poi la frase esatta e il recap:

```markdown
[![Delfino che salta](https://media.giphy.com/media/AhV2lfKBfEvcEqj6h3/giphy.gif)](https://giphy.com/gifs/guitarjamz-dolphin-jump-surfing-drone-shot-AhV2lfKBfEvcEqj6h3)

una milestone meno

🟢 <completate> milestone completate
🟡 <bloccate da Andrea> milestone bloccate da Andrea
🔴 <mancanti> milestone mancanti per finire
```

Balena: `[![Balena che sbuffa](https://media.giphy.com/media/Q6rD2TLgqMiHf4a0Pt/giphy.gif)](https://giphy.com/gifs/whale-whales-savethewhales-Q6rD2TLgqMiHf4a0Pt)`.
Conteggi ricalcolati da `run.md`, mai dalla conversazione. `Bloccate da Andrea` = ferme per
una sua decisione o autorizzazione; blocchi tecnici non entrano nel giallo. `Mancanti` =
totale del piano meno completate. Se il totale non è ancora finito, fissalo prima di chiudere
la prima milestone.

**Handoff** (limite contesto, credito esaurito, `/orchestra stop`, fine run): in `run.md`
scrivi obiettivo, contratto e budget residuo, task attivi con owner e stato, revisione base
più impronta delle modifiche non committate, domande aperte con impatto, evidenze verificate,
una sola prossima azione. Poi `stato: handoff` e rilascia il lock.

**Ripresa** (`riprendi` o `/orchestra riprendi`): verifica agenti vivi con i tool della
sessione, impronta del filesystem e stato Git; chiudi consegne e review verificabili prima di
aprire fronti nuovi; riparti dalla prossima azione registrata. Lo stato serializzato non prova
che un worker sia vivo o che un lavoro sia finito.

**Contesto**: target 50%, tetto 70% per ogni thread. Vale in modo forte per i worker (turno
che finisce a un checkpoint) e best effort per il cervello. Al 50% non aprire task nuovi;
finisci solo lo step atomico e persisti. Nessuna promessa di rollover automatico.

## 8. Confini

- Sviluppare non autorizza commit, push, merge, deploy, reset di schema, messaggi esterni,
  dati di produzione, acquisti. Segui il mandato del progetto scritto nel contratto; per
  ciò che manca chiedi prima, mai dopo.
- Un solo processo pesante locale per volta, anche tra progetti diversi
  (`~/.orchestratore/heavy.lock`): build, suite DB, browser, container non si sovrappongono.
- Ottimizza criteri di accettazione verificati per token: passa contratti e path, non
  documenti interi; riusa ricognizioni con base dichiarata; misura token solo se il runtime
  li espone, altrimenti scrivi «non disponibile».
- Non costruire strumenti di coordinamento nuovi salvo richiesta esplicita.

## Anti-pattern

- Chiedere ad Andrea di approvare ogni perimetro dentro un run autorizzato.
- Verificatore o pre-merge con lo stesso modello del builder.
- Dichiarare una milestone completata senza verdetto sull'hash in PR.
- Riempire gli slot di concorrenza senza lavoro indipendente sul percorso critico.
- Ripetere una domanda invariata, o trasformare il silenzio in una decisione.
- Contare le milestone dalla conversazione invece che da `run.md`.
- Due cervelli vivi sullo stesso progetto.
