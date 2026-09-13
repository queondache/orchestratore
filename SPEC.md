# SPEC — orchestratore

Plugin dual-runtime (Claude Code + Codex) che trasforma una ROADMAP in consegne verificate,
lavorando in parallelo su più milestone e su più task dentro ogni milestone.

## 1. Problema

Un run di sviluppo autonomo fallisce in tre modi, tutti osservati:

1. **Si ferma.** Chiede un'autorizzazione che ha già, lascia un gate rosso, consegna una
   milestone e aspetta invece di aprire la successiva.
2. **Consegna lavoro non verificato.** Il report di chi ha implementato viene preso per
   verifica; i test nuovi non provano niente; il merge avviene senza evidenza eseguita.
3. **Non parallelizza davvero.** Le lane si toccano, i worker si pestano, il cervello satura
   il contesto integrando a mano.

## 2. Obiettivo

Dopo un run non presidiato Andrea trova **main avanzato sulle milestone sicure e PR pronte su
quelle rischiose**, con i doc allineati, senza essere stato svegliato.

Metrica principale: **numero di interruzioni chieste ad Andrea**. Metriche di supporto:
milestone chiuse, giri di KO, rilavorazioni dopo verifica.

Velocità e qualità non sono in trade-off: un run veloce che consegna lavoro non verificato è
un run fallito.

## 3. Invarianti — non negoziabili

| # | Invariante |
|---|---|
| I1 | Chi scrive non verifica. Verificatore e pre-merge su modelli diversi dal builder. |
| I2 | Nessuno stato avanza senza verdetto con hash e output raw dei comandi eseguiti. |
| I3 | Un test nuovo deve essere visto rosso senza la modifica, altrimenti non prova niente. |
| I4 | Un gate rosso non è mai una condizione di stop: dopo due KO si cambia strategia e modello. |
| I5 | Uno slot di parallelismo si occupa solo con prova di indipendenza scritta sui file reali. |
| I6 | Il cervello non scrive codice e non integra branch. |
| I7 | Auto-merge solo tier 1-2 sul diff reale; tier 3 e aree sensibili restano PR in attesa. |
| I8 | Ad Andrea si chiede solo di prodotto, SPEC o autorizzazione fuori perimetro. |
| I9 | Una risposta di Andrea si propaga nello stesso turno in SPEC, ROADMAP e perimetri. |
| I10 | Nessun aumento di budget, spend limit o credito. Mai. Prevale su ogni altra regola. |

## 4. Perimetro

**Dentro**: contratto di autonomia, piano di parallelizzazione, delega a worker CC e cx,
protocollo di verifica, gate pre-merge, merge condizionato, registro quesiti e assunzioni,
failover del credito, handoff e ripresa, celebrazione, metriche.

**Fuori**: costruire strumenti di coordinamento nuovi (code server, dashboard, DB di stato);
sostituire `milestone`, `allineamento` o `spec-builder`; decidere regole di prodotto dei
progetti ospiti; installare o abilitare skill e plugin; qualunque azione che aumenti la spesa.

## 5. Superficie

- **Skill** `skills/orchestratore/SKILL.md` (≤ 250 righe) + reference: `routing`,
  `parallelismo`, `lane`, `verifica`, `credito`, `skill-map`, `adapter-cc`, `adapter-cx`,
  `project-adapter`.
- **Agent** (CC): `worker-impl`, `worker-mech`, `verificatore`, `pre-merge`, `integratore`.
- **Bridge**: `bin/spawn-cx.sh`, `bin/spawn-cc.sh`, entrambi con `--dry-run`.
- **Comandi**: `/orchestratore:orchestra`, `/orchestratore:orchestra-status`.
- **Hook**: guardia `PreToolUse` attiva solo con un run vivo; stato del run a `SessionStart`.
- **Stato su file**: `.orchestratore/run.md`, `recon.md`, `brain.lock`, `config.toml`;
  `~/.orchestratore/state.toml` per il credito.

## 6. Definition of done del plugin

Un gate mai visto rosso non è un gate. Ogni regola di metodo ha un invariante di testo, e ogni
invariante ha una mutazione che lo uccide. Ogni componente eseguibile ha un gate che lo prova
senza spendere credito.

| Gate | Prova |
|---|---|
| `tests/check-structure.sh` | struttura, manifest, presenza e forma dei componenti |
| `tests/check-regressions.sh` | ogni regola di metodo è ancora scritta |
| `tests/check-regressions-mutations.sh` | ogni invariante è stato visto rosso |
| `tests/check-bridge.sh` | i bridge compongono la riga giusta e rifiutano l'input invalido |
| `tests/check-hooks.sh` | la guardia blocca il distruttivo con un run vivo, e solo allora |

## 7. Quesiti aperti

- `[APERTO-01]` Nessun run reale end-to-end è mai stato eseguito: i gate provano il testo e il
  cablaggio, non il comportamento. Serve un pilota su due milestone con una contract-first, e
  la lettura delle metriche prodotte. Decisione richiesta: su quale progetto e con che budget.
- `[APERTO-02]` Il plugin non ha un modo per provare che un modello ha davvero girato quando il
  runtime non espone il campo `model`. Oggi si scrive «non disponibile».
- `[APERTO-03]` Codex non ha agent dichiarati: i ruoli lato cx vivono nel prompt. Se cx
  introduce un formato di agent, va allineato a `agents/`.
