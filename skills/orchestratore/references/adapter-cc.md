# Adapter Claude Code: il cervello è Fable in CC

## Worker CC nativi

Tool `Agent`. Regole:
- Usa skill già installate e disponibili utili al task liberamente: passa nome/path, leggi e
  segui il `SKILL.md` completo, senza consenso o stop sul silenzio. Mai installare, abilitare
  o modificare globalmente skill o plugin; una skill non amplia permessi di tool o app.
- `subagent_type`: `orchestratore:worker-impl`, `orchestratore:worker-mech`,
  `orchestratore:verificatore`, `orchestratore:pre-merge`, `orchestratore:integratore`, dal
  plugin (`agents/`). Se il plugin non è installato nella sessione corrente, usa
  `general-purpose` passando il testo dell'agent per path (`agents/<nome>.md`): il `model`
  resta esplicito e diverso da quello del builder. Mancanza di un agent non è mai un motivo
  per saltare la verifica.
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

`bin/spawn-cx.sh [--dry-run] <modello> <effort> <cwd> <prompt-file>`, che esegue
`codex exec --yolo -m <modello> -c model_reasoning_effort=<effort> -C <cwd> -` (`--yolo` è
l'alias di `--dangerously-bypass-approvals-and-sandbox`) con il prompt su stdin, log in
`<cwd>/.orchestratore/logs/<task-id>.log`, exit code restituito. Rifiuta prima di spendere
credito: modello fuori routing `65`, effort non ammesso `65`, cwd o prompt mancanti `66`.
`--dry-run` stampa la riga di comando senza eseguire: usalo per provare il cablaggio.
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
