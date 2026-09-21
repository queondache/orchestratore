# Project adapter: progetto nuovo o ripresa

## Progetto nuovo per l'orchestratore

1. Leggi CLAUDE.md, AGENTS.md, SPEC.md, ROADMAP.md, progress.md, `.claude/decisioni.md`,
   `lessons.md`. Se ROADMAP.md manca o è più vecchia di SPEC.md: fermati, «serve
   `/allineamento` prima». Se SPEC.md manca: «serve `spec-builder` prima».
2. Individua i comandi reali di build, test e lint e l'ambiente disponibile (locale, CI, DB
   di test) e **scrivili in `RUN.md`** come `Gate verde: build=<cmd> test=<cmd> lint=<cmd>`;
   un comando inesistente si scrive `nessuno`, non si inventa. Controlla anche se il branch
   base ha required checks (`gh api repos/<owner>/<repo>/branches/<base>/protection`) e
   registralo: decide quale forma del gate di merge vale (lane.md).
3. Crea `.orchestratore/` (aggiungila a `.gitignore` del progetto se manca) e copia
   `templates/RUN.md` in `.orchestratore/RUN.md`. Opzionale: `.orchestratore/config.toml`
   dal template per peso, costo o `aree_sensibili` diversi dal globale. Registra sempre
   `cheapest-capable` e i minimi per modello nel contratto del run.
3-bis. Aggiorna `.orchestratore/RUN.md` come unica memoria operativa: conserva solo gate,
   mappa minima dei moduli, task attivi, evidenze e prossimo passo. Seleziona da `ROADMAP.md`
   massimo 2 milestone aperte eleggibili e riportale nella sezione `Milestone attive`; non
   copiare l'intera roadmap. Dopo ogni consegna aggiorna la sezione task e compatta ciò che è
   superato, mantenendo il documento entro 300 righe e 15 KB. Non creare `recon.md`, context
   pack o prompt-file permanenti: il worker riceve path e sezione task del RUN. Dopo ogni
   consegna il RUN compatta ciò che è superato.
4. Cattura stato Git in sola lettura: branch, hash, worktree, PR aperte (`gh pr list`).
5. Leggi `ROADMAP.md` per stato e dipendenze; il RUN contiene solo le prime 2 milestone aperte
   eleggibili. Il totale per i contatori resta nella ROADMAP, non viene duplicato nel RUN.
6. Registra in `RUN.md` se il run è non presidiato: commit, push e PR normali sono automatici;
   auto-merge resta vincolato al gate di lane.md.
7. Scrivi il `## Piano di parallelizzazione` e la prova di indipendenza sui file reali
   ([parallelismo](parallelismo.md)) prima di occupare qualsiasi slot: un owner per file,
   nessun ciclo di dipendenze e builder in volo ≤ 2 nel run.
   Intersezione di glob non vuota → lane contract-first, non parallelo.

Non copiare regole di dominio da un altro progetto. Le istruzioni e le decisioni di prodotto
del repo corrente prevalgono sempre su questa skill.

## Handoff, ripresa, contesto

**Handoff** (limite contesto, credito esaurito, `/orchestra stop`, fine run): in `RUN.md`
scrivi obiettivo, contratto e budget residuo, task attivi con owner e stato, revisione base
più impronta delle modifiche non committate, domande aperte con impatto, evidenze verificate,
una sola prossima azione. Poi `stato: handoff` e rilascia il lock.

**Contesto**: target 50%, tetto 70% per ogni thread. Al 50% non aprire task nuovi: finisci
solo lo step atomico e persisti un checkpoint trasferibile. Al 70% esegui un rollover
esplicito con handoff persistito; se la misura non è disponibile dichiaralo. Nessuna promessa
o assunzione di auto-compact. Il protocollo completo è in [controller](controller.md).

**Ripresa** (`riprendi` o `/orchestra riprendi`):

1. Leggi `RUN.md` (ultimo handoff) e `~/.orchestratore/state.toml` (credito).
2. Elenca gli agenti vivi con i tool della sessione e riconciliali con `RUN.md`: uno stato
   `running` senza agente vivo diventa `da riassegnare`.
3. Confronta revisione base e impronta delle modifiche non committate con il filesystem
   reale prima di qualsiasi scrittura.
4. Chiudi consegne e review verificabili prima di aprire fronti nuovi.
5. Riparti dalla prossima azione registrata; non ripetere ricognizioni già fatte.

## Stati dei task in `RUN.md`

`in coda` (dipendenze incomplete) · `pronto` · `in corso` · `in review` · `verificato` ·
`pronto al merge` (pre-merge sì) · `integrato` · `chiuso` · `bloccato` (condizione esterna
nominata, con owner dello sblocco) · `esterno` (di un'altra lane o sessione: non duplicare).
Se il progetto ha già un vocabolario di stati, adotta quello.

## Scelte di provider e servizi

Hosting, database, storage, email, pagamenti sono decisioni di architettura: confronto in
sola lettura (vincoli di prodotto, regione dati, DPA, backup, costo di uscita) e domanda nel
registro quesiti. Le app già collegate come plugin Codex sono automatiche nel perimetro
congelato del task, inclusi side effect esterni non distruttivi direttamente richiesti.
Nessun login, connessione, scope o segreto nuovo; modifiche distruttive o massive ai dati di
produzione, acquisti, upgrade e aumenti di budget, spend limit o credito restano vietati.
