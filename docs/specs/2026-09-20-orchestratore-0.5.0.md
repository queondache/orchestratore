# Orchestratore 0.5.0 — controller persistente e ripresa verificata

Data: 20/09/2026. Release candidate locale; non pubblicata e non installata in produzione.

## Comportamento verificato

- `bin/orchestratore-controller` espone una CLI JSON congelata con `--db` e transizioni
  `init`, `start`, `add-task`, `schedule`, `complete`, `fail`, `checkpoint`, `status`,
  `acquire` e `release`.
- SQLite usa WAL; il lease autorevole è verificato nel database. `brain.lock` resta una
  proiezione compatibile e non la fonte di verità.
- Gli ingressi app Codex locale, Codex CLI e Claude CLI possono riusare lo stesso `run_id`.
- Il flusso economico standard è strategia Claude, massimo due builder Codex e review Claude
  separata. Il modello e l'effort restano configurabili per run secondo il routing cheapest-capable.
- La ripresa A-E parte dalla prima fase senza evidenza. La fase E è finale solo con evidenza
  dell'outcome PR, merge o attesa approvata e documentazione allineata.
- Il checkpoint persiste summary, fase, hash/impronta e sessione; la soglia 50 salva il
  checkpoint e la soglia 70 apre una nuova sessione. Non si assume auto-compact del runtime.
- Il retry è finito a due tentativi per approccio e due approcci. Le firme duplicate sono
  deduplicate e il caso terminale è idempotente.

## Gate della candidate

I gate locali da eseguire prima di dichiarare la candidate pronta sono elencati in `RUN.md`:
struttura, regressioni, controller, bridge, hook, compilazione e controllo diff. La suite di
mutazione è stata eseguita sul tree finale e ha concluso `GREEN: tutte le mutazioni sono
respinte` con exit 0. La release candidate resta locale: produzione e installazione non sono
state eseguite.
