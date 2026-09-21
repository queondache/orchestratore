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

`bin/spawn-cc.sh [--dry-run] <modello> <cwd> <task-id>`, che esegue
`claude -p --model <modello> --permission-mode bypassPermissions --output-format json
--add-dir <cwd>` con il prompt su stdin, log in `<cwd>/.orchestratore/logs/<task-id>.log`.
Stessi codici di rifiuto del bridge cx (`65` modello/task-id, `66` cwd o RUN). Con `verifica cc`
il verificatore segue il tier di `routing.md`: Haiku per meccanico/basic, Sonnet per
importante, Opus solo su trigger o in solo-CC importante. La sezione task del verificatore
nel RUN rimanda a `agents/verificatore.md` e contiene solo perimetro, branch, hash, gate
verde e aree ammesse.
Il bridge genera lo stdin minimo dal `task-id`: indica di leggere `SPEC.md`, `ROADMAP.md` e
`.orchestratore/RUN.md`, eseguire solo la sezione task corrispondente e aggiornare soltanto
quella sezione con esito e checkpoint. Non accetta né crea prompt-file permanenti.

## Domande interattive

Con debito tossico ferma il turno e scrivi la domanda in chiaro, una sola, con 2-4 opzioni
e la raccomandata per prima. Riprendi solo dopo la risposta; registrala nel registro quesiti.

## Git, PR, lock, contesto

Come adapter-cc: `gh` per PR e checks, commit/push/PR automatici nel run non presidiato e
auto-merge solo al gate di lane.md; `brain.lock` con `runtime=cx`, `heavy.lock` prima dei processi pesanti. cx espone la percentuale di contesto
nella sessione: rispetta target 50% e tetto 70%; al 50% non aprire task nuovi, persisti e
compatta al primo checkpoint sicuro.

## Path locali usati da questa reference

- Catalogo cx: `/Users/andreapesce/Dev/skills/orchestratore/skills/orchestratore/references/codex-skills-catalog.jsonl`
- Skill di metodo leggibili per path: `/Users/andreapesce/Dev/skills/<nome>/SKILL.md`
