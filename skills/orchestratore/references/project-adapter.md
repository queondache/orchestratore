# Project adapter: progetto nuovo o ripresa

## Progetto nuovo per l'orchestratore

1. Leggi CLAUDE.md, AGENTS.md, SPEC.md, ROADMAP.md, progress.md, `.claude/decisioni.md`,
   `lessons.md`. Se ROADMAP.md manca o è più vecchia di SPEC.md: fermati, «serve
   `/allineamento` prima». Se SPEC.md manca: «serve `spec-builder` prima».
2. Individua comandi di build, test, lint e l'ambiente disponibile (locale, CI, DB di test).
3. Crea `.orchestratore/` (aggiungila a `.gitignore` del progetto se manca) e copia
   `templates/run.md` in `.orchestratore/run.md`. Opzionale: `.orchestratore/config.toml`
   dal template per un peso diverso dal globale.
4. Cattura stato Git in sola lettura: branch, hash, worktree, PR aperte (`gh pr list`).
5. Conta le milestone aperte in ROADMAP.md e le loro dipendenze: è il totale per i contatori
   della celebrazione. Fissalo in `run.md`.
6. Registra in `run.md` il mandato Git del progetto (Mesa e Pau: commit+push+PR delegati;
   altri: chiedi all'avvio).
7. Valida prima di delegare: un owner per file, nessun ciclo di dipendenze, milestone attive
   ≤ tetto, worker ≤ tetto. Se non c'è un validatore, fallo a mano e scrivilo.

Non copiare regole di dominio da un altro progetto. Le istruzioni e le decisioni di prodotto
del repo corrente prevalgono sempre su questa skill.

## Ripresa

1. Leggi `run.md` (ultimo handoff) e `~/.orchestratore/state.toml` (credito).
2. Elenca gli agenti vivi con i tool della sessione e riconciliali con `run.md`: uno stato
   `running` senza agente vivo diventa `da riassegnare`.
3. Confronta revisione base e impronta delle modifiche non committate con il filesystem
   reale prima di qualsiasi scrittura.
4. Chiudi consegne e review verificabili prima di aprire fronti nuovi.
5. Riparti dalla prossima azione registrata; non ripetere ricognizioni già fatte.

## Stati dei task in `run.md`

`in coda` (dipendenze incomplete) · `pronto` · `in corso` · `in review` · `verificato` ·
`pronto al merge` (pre-merge sì) · `integrato` · `chiuso` · `bloccato` (condizione esterna
nominata, con owner dello sblocco) · `esterno` (di un'altra lane o sessione: non duplicare).
Se il progetto ha già un vocabolario di stati, adotta quello.

## Scelte di provider e servizi

Hosting, database, storage, email, pagamenti sono decisioni di architettura: confronto in
sola lettura (vincoli di prodotto, regione dati, DPA, backup, costo di uscita) e domanda nel
registro quesiti. Login, provisioning, DNS, deploy, acquisti e rotazione segreti richiedono
ciascuno l'autorizzazione del progetto.
