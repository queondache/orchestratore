---
description: Report immediato dello stato del run dell'orchestratore, letto da RUN.md e da Git
allowed-tools: Read, Bash, Grep, Glob
---

Report di sola lettura. Non aprire task, non delegare, non modificare file.

1. Leggi `.orchestratore/RUN.md`. Se manca: «nessun run in corso in questo progetto», fine.
2. Leggi `.orchestratore/brain.lock`: riporta runtime, pid e da quanto è aggiornato; segnala
   se è stantio (oltre 10 minuti).
3. Leggi `~/.orchestratore/state.toml` per credito e modalità.
4. Stato Git reale: `git status --short`, `git branch --list 'm/*'`, `gh pr list --state open`
   se `gh` è disponibile. Conta gli slot builder occupati dai branch task vivi.

Poi stampa il blocco di §7 della skill `orchestratore`, con i conteggi ricalcolati da `RUN.md`
e dai comandi appena eseguiti — mai dalla conversazione. Se un dato non è osservabile, scrivi
`non disponibile`: non stimare.
