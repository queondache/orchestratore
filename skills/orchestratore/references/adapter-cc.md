# Adapter Claude Code: il cervello è Fable in CC

## Worker CC nativi

Tool `Agent`. Regole:
- `subagent_type`: `orchestratore:worker-impl`, `orchestratore:worker-mech`,
  `orchestratore:verificatore`, `orchestratore:pre-merge` (dal plugin, M2). Finché gli
  agent non esistono, usa `general-purpose` con `model` esplicito.
- `model`: sempre esplicito (`opus`, `sonnet`, `haiku`). Mai lasciare il default.
- Per cervello e worker nativo verifica `bypassPermissions` effettivo per sessione; se non
  è disponibile senza input, non delegare la lane e usa un path già bypassPermissions.
- `isolation: "worktree"` per ogni lane di implementazione parallela. Il verificatore
  lavora sul branch della PR, non sul worktree del builder.
- Prompt del worker = contratto del task (SKILL.md §3) + perimetro + skill obbligatorie con
  path + boundary del filesystem + «non delegare, non chiedere ad Andrea, domande nel registro
  quesiti, termina il turno a un checkpoint con diff, hash, comandi e output».
- Un worker per incarico. Chiudi i thread finiti; accetta consegne sintetiche, non transcript.

## Worker cx via bridge

`bin/spawn-cx.sh <modello> <effort> <cwd> <prompt-file>` (M2), che esegue
`codex exec --yolo -m <modello> -c model_reasoning_effort=<effort>` (`--yolo` è l'alias
ufficiale di `--dangerously-bypass-approvals-and-sandbox`)
con il prompt letto da file, log in `.orchestratore/logs/<task-id>.log`, exit code restituito.
Lancialo con `Bash` in background (`run_in_background: true`) e leggi il log al
checkpoint. Modelli cx: `gpt-6-astra`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`.
Il bridge non decide niente: modello, effort e prompt li scegli tu.

## Domande interattive

Con debito tossico usa il tool di domanda strutturata (`AskUserQuestion`): una domanda,
2-4 opzioni, la raccomandata per prima con «(Recommended)». Registra la risposta esatta nel
registro quesiti e sblocca solo i task che risolve davvero.

## Git e PR

`gh pr create`, `gh pr checks`, `gh pr view --json state,mergedAt`. Nel run non presidiato,
commit/push/PR normali sono automatici e il merge segue esclusivamente il gate di lane.md.
Output raw nel report, mai riassunto.

## Contesto

Il root CC non legge la propria percentuale in modo affidabile: lavora per checkpoint
frequenti e scrivi l'handoff presto. I worker hanno contesto proprio: ogni turno finisce a
un checkpoint. Se il runtime segnala compattazione, ricarica solo `run.md` e ricontrolla
l'impronta del filesystem prima di continuare.

## Lock e stato

- `.orchestratore/brain.lock`: `runtime=cc pid=<pid> session=<id> updated=<iso>`;
  aggiornalo a ogni report di stato, rilascialo all'handoff.
- `~/.orchestratore/heavy.lock` prima di build, suite DB, browser, container: se occupato
  da un pid vivo, aspetta o riordina i task.
