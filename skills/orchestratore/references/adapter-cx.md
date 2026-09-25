# Adapter Codex: il cervello è gpt-6-astra in cx

## Avvio minimo in cx

Il cervello e ogni worker cercano e caricano liberamente le skill già installate e disponibili
utili al task; per cx usa il catalogo locale con `rg -i <parola>
references/codex-skills-catalog.jsonl`, passa nome/path e legge il `SKILL.md` completo.
Non chiedere consenso per una skill né fermarti sul silenzio. Se manca, usa una skill
equivalente già installata o la procedura base. Non installare o abilitare skill/plugin e non
modificare configurazioni globali; una skill non amplia i permessi di tool o app.

Il catalogo è stato ispezionato il 11/09/2026; la cache non prova disponibilità corrente.
Il catalogo CC (`~/Dev/skills/cc-installed-plugins.md`) non dice cosa ha cx, e viceversa.

## Worker cx nativi

Un thread per incarico, con modello ed effort dichiarati nel contratto del task. Il cervello
usa `gpt-6-astra` medium; i dev usano `gpt-5.6-luna` da medium per il meccanico,
`gpt-5.6-terra` da medium per il basic e `gpt-5.6-sol` da low per l'importante. Astra parte
da low solo su escalation e non è un dev di primo tentativo. Prompt del worker come in adapter-cc: contratto + perimetro + skill con
path + boundary + «non delegare, domande nel registro quesiti, checkpoint con diff, hash,
comandi e output». Se il runtime non permette di scegliere il modello per thread, usa
`codex exec` con `-m` dal cervello stesso e dichiaralo nel contratto.

Prima di delegare verifica nel profilo effettivo `approval_policy=never` e
`sandbox_mode=danger-full-access` (effective approval_policy=never + sandbox_mode=danger-full-access).
Se non puoi ottenerlo senza input, non delegare quella lane e usa un path già `--yolo` con
`codex exec --yolo`; non chiedere permessi di routine.

## Worker CC via bridge

`bin/spawn-cc.sh [--dry-run] <modello> <effort> <project-root> <task-id> <stage> <task-cwd> <allowlist-json>`, che esegue
`claude -p --model <modello> --effort <effort> --permission-mode bypassPermissions --output-format json
--add-dir <project-root>` dal worktree isolato, con prompt su stdin e log nel control plane
`<project-root>/.orchestratore/logs/<task-id>.<stage>.log`. Il bridge rifiuta checkout non
isolati, worktree di un altro repository e plugin/hook guard non attivo; verifica inoltre a
fine processo che RUN e checkout di controllo siano immutati. Stessi codici di rifiuto del
bridge cx (`65` modello/effort/task-id/stage/allowlist, `66` path, worktree o RUN, `69` runtime/guard).
Il build è accettato solo se ogni path cambiato dal base SHA appartiene ai glob congelati;
strategy/review/finalize richiedono worktree pulito e immutato. Con `verifica cc`
il verificatore segue il tier di `routing.md`: Haiku per meccanico/basic, Sonnet per
importante, Opus solo su trigger o in solo-CC importante. La sezione task del verificatore
nel RUN rimanda a `agents/verificatore.md` e contiene solo perimetro, branch, hash, gate
verde e aree ammesse.
Il bridge genera lo stdin minimo e specifico per `strategy`, `build`, `review` o `finalize`.
Il worker legge RUN dal project root in sola lettura e restituisce esito e checkpoint al
controller: non scrive mai RUN e non accetta né crea prompt-file permanenti.

## Domande interattive

Con debito tossico ferma il turno e scrivi la domanda in chiaro, una sola, con 2-4 opzioni
e la raccomandata per prima. Riprendi solo dopo la risposta; registrala nel registro quesiti.

## Git, PR, lock, contesto

Come adapter-cc: gli hook rifiutano `gh`, `curl` e push nei worker; il controller è l'unica
autorità del protocollo per PR, check e merge e integra solo al gate di lane.md. È un
guardrail anti-errore, non una sandbox o una barriera egress/filesystem contro codice ostile:
vale il modello di fiducia di SKILL.md §8. `brain.lock` con `runtime=cx`, `heavy.lock` prima dei processi pesanti. cx espone la percentuale di contesto
nella sessione: rispetta target 50% e tetto 70%; al 50% non aprire task nuovi, persisti e
compatta al primo checkpoint sicuro.

## Path locali usati da questa reference

- Catalogo cx: `/Users/andreapesce/Dev/skills/orchestratore/skills/orchestratore/references/codex-skills-catalog.jsonl`
- Skill di metodo leggibili per path: `/Users/andreapesce/Dev/skills/<nome>/SKILL.md`
