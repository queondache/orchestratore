# Routing: tier, modelli, effort

Il cervello sceglie per ogni task tier, runtime, modello ed effort. Li scrive nel contratto
del task. I nomi modello sono quelli esposti oggi dai due runtime; se un runtime non li
espone, usa il più vicino e scrivi nel contratto quale hai usato.

| Tier | Quando | CC | cx | Effort default |
|---|---|---|---|---|
| cervello | sempre | fable | gpt-6-astra | alto |
| verifica | ogni consegna | opus | gpt-5.6-sol | alto |
| importante | tocca schema, migrazioni, auth, pagamenti, multi-tenancy, PII, sicurezza, concorrenza | opus | gpt-5.6-sol | alto |
| basic | tutto il resto | sonnet | gpt-5.6-terra | medio |
| meccanico | inventari, lint, rinomine, test deterministici | haiku | gpt-5.6-luna | basso |

Criterio "importante": tier 2 e 3 di `senior-architect` §5.

## Regole

1. **Builder ≠ verificatore**, sempre a livello di modello. Runtime opposto quando il peso
   lo consente. Il gate pre-merge usa un terzo modello, diverso dal builder e, se i modelli
   disponibili lo consentono, dal verificatore.
   Prima di ogni nuova assegnazione rileggi `~/.orchestratore/state.toml`: un runtime
   `esaurito` non riceve nuovi task, indipendentemente dal peso configurato.
2. Default (peso `dev cx 100 / cc 0`, `verifica cc`): builder terra o sol su cx,
   verificatore opus su CC, pre-merge sol su cx (o astra se il builder era sol).
3. **Solo-CC** (cx esaurito): basic → sonnet costruisce, opus verifica, pre-merge haiku in
   lettura con checklist; importante → opus costruisce, **fable verifica** (unica eccezione a
   "Fable non verifica"), pre-merge sonnet.
4. **Solo-cx** (CC esaurito): basic → terra costruisce, sol verifica, pre-merge luna con
   checklist; importante → sol costruisce, gpt-6-astra verifica, pre-merge terra.
5. Il failover è simmetrico e persistente. I task in volo sul runtime esaurito finiscono
   solo il checkpoint atomico sicuro. Se quel runtime ospita il cervello e l'altro è
   disponibile: stato e handoff in `run.md`, rilascio di `brain.lock`, passaggio esplicito
   all'altro runtime e stop. Se è l'altro runtime: il cervello continua e usa la tabella
   sopra, mantenendo builder, verificatore e pre-merge su modelli diversi. Con entrambi
   esauriti, modalità
   `fermo`: nessuna assegnazione e nessuna capacità simulata.
6. Il ripristino esplicito di un runtime lo riabilita alle nuove assegnazioni. Se l'altro è
   ancora esaurito resta la modalità solo-runtime; quando entrambi sono `ok` torna il peso
   salvato prima del failover.
7. Escalation di un tier solo su trigger concreto: contratto ambiguo, due tentativi
   falliti, disaccordo builder/verificatore, rischio alto scoperto in corso.
   De-escalation sul follow-up meccanico.
7-bis. **Due KO consecutivi sullo stesso gate obbligano a cambiare modello**, non solo
   strategia: riassegna il task a un modello diverso da quello che ha fallito, al runtime
   opposto quando il peso lo consente, e annota il cambio in `run.md`. Riprovare lo stesso
   gate con lo stesso modello e lo stesso approccio non è un tentativo nuovo. Nessun tetto
   ai giri: il rosso tecnico non sospende la lane.
8. Effort: il cervello può alzare o abbassare l'effort default di un livello; lo scrive nel
   contratto. In cx si passa con `-c model_reasoning_effort=<low|medium|high>`; in CC con la
   definizione dell'agent o l'istruzione nel prompt.
9. Mai dichiarare che un modello ha girato se il runtime non lo riporta. Il log del bridge
   e il campo `model` della risposta sono l'unica evidenza.
10. **Tetti separati**: 9 slot builder (3 milestone × 3 task) e un pool di verifica a parte,
   massimo 3 verifiche in volo. Verificatore, pre-merge e integratore non consumano slot
   builder, altrimenti la verifica affama l'implementazione. Dettaglio in
   [parallelismo](parallelismo.md).
11. Il verificatore esegue i quattro passi di [verifica](verifica.md), oracolo incluso. Un
   verdetto senza output raw si riassegna a un modello diverso, non si accetta.

## Agent CC del plugin (`agents/`)

| Agent | Modello | Uso |
|---|---|---|
| `worker-impl` | opus o sonnet, scelto dal cervello | implementazione importante o basic |
| `worker-mech` | haiku | lavoro meccanico |
| `verificatore` | opus | verifica indipendente, sola lettura |
| `pre-merge` | scelto dal cervello, diverso da builder e verificatore | gate pre-merge, sola lettura + `gh` |
| `integratore` | sonnet o `gpt-5.6-terra` | fonde i branch task in `m/<slug>`, nessuna implementazione nuova |

Il `model` del frontmatter è il default: il cervello può passarne uno diverso a ogni chiamata
e lo scrive nel contratto del task. I bridge `bin/spawn-cx.sh` e `bin/spawn-cc.sh` validano il
modello contro questa tabella e rifiutano con exit 65 quello che non c'è.

In cx non esistono agent dichiarati: il cervello cx passa modello ed effort a ogni thread
o a ogni `codex exec`.
