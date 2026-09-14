---
description: Avvia, ispeziona o governa un run dell'orchestratore (start, status, peso, credito, stop, riprendi)
argument-hint: start | status | peso dev cx <n> | credito <cc|cx> <ok|esaurito> | stop | riprendi
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, Skill, Agent, TodoWrite, AskUserQuestion
---

Sottocomando richiesto: **$ARGUMENTS** (vuoto = `start`).

Carica la skill `orchestratore` e seguila per intero: è lei la fonte di verità, questo comando
è solo la porta d'ingresso. Prima di qualsiasi azione esegui l'avvio sicuro (§0 della skill):
istruzioni del repo, `brain.lock`, stato credito, working tree, toolchain.

Instradamento del sottocomando:

- **`start`** (o argomento vuoto) — run nuovo. Avvio sicuro, poi contratto di autonomia con i
  default di §1 senza chiederli, `## Piano di parallelizzazione` con la prova di indipendenza
  sui file reali, routing `cheapest-capable` per task, e apertura delle lane. L'unica domanda ammessa all'avvio è `standard` o
  `alternativo` per il cervello.
- **`status`** — report di §7 dal contenuto reale di `.orchestratore/run.md` e dallo stato Git,
  mai dalla conversazione. Include slot builder occupati, verifiche in volo, domande aperte,
  modalità credito e prossimo checkpoint.
- **`peso dev cx <n>`** — override del peso in corsa. Non tocca i flag credito. Scrivilo in
  `run.md` e applicalo solo alle assegnazioni nuove.
- **`credito <cc|cx> <ok|esaurito>`** — aggiorna `~/.orchestratore/state.toml` e applica il
  failover di `references/credito.md`. Riconosci anche le formulazioni naturali equivalenti.
- **`stop`** — chiudi solo il checkpoint atomico sicuro, scrivi l'handoff completo in `run.md`,
  metti `stato: handoff`, rilascia `brain.lock`. Non interrompere un merge a metà.
- **`riprendi`** — ripresa di §7: agenti vivi riconciliati con `run.md`, impronta del
  filesystem e stato Git verificati, consegne e review chiuse prima di aprire fronti nuovi.

Un sottocomando non riconosciuto: dillo in una riga ed elenca quelli validi. Non inventare
comportamenti nuovi.
