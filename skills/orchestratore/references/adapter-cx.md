# Adapter Codex: il cervello è gpt-6-astra in cx

## Avvio minimo in cx

Set di skill all'avvio: `i-have-adhd`, `orchestratore`, `openai-docs`. Le altre restano
installate ma non caricate. Carica una skill opzionale solo quando serve a un task concreto:
cercala nel catalogo locale con `rg -i <parola> references/codex-skills-catalog.jsonl`
(non caricare il catalogo intero), chiedi ad Andrea con una frase in italiano che nomina la
skill e il lavoro, e dopo il sì leggi quel `SKILL.md` e le sole reference pertinenti.
Un'istruzione esplicita di Andrea di usare una skill vale già come approvazione. Il silenzio
non è consenso. Leggere un file di skill non abilita tool MCP né cambia la config globale.

Il catalogo è stato ispezionato il 11/09/2026; la cache non prova disponibilità corrente.
Il catalogo CC (`~/Dev/skills/cc-installed-plugins.md`) non dice cosa ha cx, e viceversa.

## Worker cx nativi

Un thread per incarico, con modello ed effort dichiarati nel contratto del task
(`gpt-5.6-sol` importante, `gpt-5.6-terra` basic, `gpt-5.6-luna` meccanico; verifica
`gpt-5.6-sol`). Prompt del worker come in adapter-cc: contratto + perimetro + skill con
path + boundary + «non delegare, domande nel registro quesiti, checkpoint con diff, hash,
comandi e output». Se il runtime non permette di scegliere il modello per thread, usa
`codex exec` con `-m` dal cervello stesso e dichiaralo nel contratto.

## Worker CC via bridge

`bin/spawn-cc.sh <modello> <cwd> <prompt-file>` (M2), che esegue
`claude -p --model <modello> --permission-mode bypassPermissions --output-format json`
con il prompt letto da file, log in `.orchestratore/logs/<task-id>.log`. Con `verifica cc`
il verificatore è sempre `opus` via questo bridge; il prompt include il testo dell'agent
`verificatore` del plugin (`agents/verificatore.md`, M2) e solo perimetro e branch.

## Domande interattive

Con debito tossico ferma il turno e scrivi la domanda in chiaro, una sola, con 2-4 opzioni
e la raccomandata per prima. Riprendi solo dopo la risposta; registrala nel registro quesiti.

## Git, PR, lock, contesto

Come adapter-cc: `gh` per PR e checks, merge solo alla parola `merge`, `brain.lock` con
`runtime=cx`, `heavy.lock` prima dei processi pesanti. cx espone la percentuale di contesto
nella sessione: rispetta target 50% e tetto 70%; al 50% non aprire task nuovi, persisti e
compatta al primo checkpoint sicuro.

## Path locali usati da questa reference

- Catalogo cx: `/Users/andreapesce/Dev/skills/orchestratore/skills/orchestratore/references/codex-skills-catalog.jsonl`
- Skill di metodo leggibili per path: `/Users/andreapesce/Dev/skills/<nome>/SKILL.md`
