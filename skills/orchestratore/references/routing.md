# Routing: tier, modelli, effort e costo

Il cervello sceglie per ogni task tier, runtime, modello ed effort. Li scrive nel contratto
del task. La politica predefinita è `cheapest-capable`: usa il modello meno costoso adatto
al rischio e l'effort minimo ammesso per quel modello e quella task, poi scala solo su un
trigger osservabile. I nomi modello sono quelli esposti oggi dai due runtime; se un runtime
non li espone, usa il più vicino e scrivi nel contratto quale hai usato.

| Tier | Quando | CC | cx dev | Effort cx iniziale |
|---|---|---|---|---|
| cervello | sempre | fable | gpt-6-astra | **medium fisso** |
| importante | schema, migrazioni, auth, pagamenti, multi-tenancy, PII, sicurezza, concorrenza | sonnet | gpt-5.6-sol | low se il contratto è stretto; medium negli altri casi |
| basic | implementazione ordinaria con scelte locali | sonnet | gpt-5.6-terra | **medium minimo** |
| meccanico | inventari, lint, rinomine, test deterministici | haiku | gpt-5.6-luna | **medium minimo** |

Criterio "importante": tier 2 e 3 di `senior-architect` §5.

## Fasce cx e trigger

- `gpt-5.6-luna`: solo task meccaniche e delimitate; `medium` o `high`, mai `low`.
- `gpt-5.6-terra`: task basic; `medium` o `high`, mai `low`.
- `gpt-5.6-sol`: task importanti; parte da `low` se criteri e test sono deterministici,
  altrimenti `medium`; `high` solo con un trigger di escalation.
- `gpt-6-astra`: cervello a `medium`; nei worker parte da `low` ed entra solo per
  escalation, disaccordo o verifica ad alto rischio, mai come dev di primo tentativo.

Trigger di escalation: contratto ambiguo non risolvibile localmente, due KO sullo stesso
gate, disaccordo builder/verificatore, rischio alto emerso nel diff. Ogni uso di `high`,
`Astra` o `Opus` registra il trigger nel contratto. Un gate verde senza riserve riporta il
task successivo al default del suo tier: l'escalation non diventa un nuovo default.

## Regole

1. **Builder ≠ verificatore**, sempre a livello di modello. Runtime opposto quando il peso
   lo consente. Il gate pre-merge è diverso dal builder; differisce anche dal verificatore
   quando il routing disponibile lo consente senza promuovere inutilmente a un modello premium.
   Prima di ogni nuova assegnazione rileggi `~/.orchestratore/state.toml`: un runtime
   `esaurito` non riceve nuovi task, indipendentemente dal peso configurato.
2. Default (peso `dev cx 100 / cc 0`, `verifica cc`): meccanico → Luna medium; basic →
   Terra medium; importante → Sol low o medium secondo la tabella. CC verifica con Haiku
   per meccanico/basic e Sonnet per importante; pre-merge cx usa Terra medium per consegne
   costruite da Luna/Sol e Luna medium per quelle costruite da Terra.
3. **Solo-CC** (cx esaurito): meccanico/basic → Haiku costruisce, Sonnet verifica e fa il
   pre-merge; importante → Sonnet costruisce, Opus verifica, Haiku fa il pre-merge. Opus è
   ammesso solo qui o su un trigger registrato.
4. **Solo-cx** (CC esaurito): meccanico → Luna medium costruisce, Terra medium verifica;
   basic → Terra medium costruisce, Luna medium verifica; importante → Sol low/medium
   costruisce, Terra high verifica, Luna medium fa il pre-merge. Astra parte da low solo se
   scatta un trigger; non è il verificatore predefinito.
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
7. Modello ed effort non si alzano per prudenza generica: valgono solo i trigger della
   sezione precedente. De-escalation sul follow-up meccanico e dopo un gate verde.
7-bis. **Due KO consecutivi sullo stesso gate obbligano a cambiare modello**, non solo
   strategia: riassegna il task a un modello diverso da quello che ha fallito, al runtime
   opposto quando il peso lo consente, e annota il cambio in `run.md`. Riprovare lo stesso
   gate con lo stesso modello e lo stesso approccio non è un tentativo nuovo. Nessun tetto
   ai giri: il rosso tecnico non sospende la lane.
8. Effort: il cervello rispetta i minimi per modello (`Luna ≥ medium`, `Terra ≥ medium`,
   `Sol ≥ low`, `Astra ≥ low`; cervello Astra = `medium`) e scrive scelta e motivo nel
   contratto. In cx si passa con `-c model_reasoning_effort=<low|medium|high>`; in CC con
   la definizione dell'agent o l'istruzione nel prompt.
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
| `worker-impl` | sonnet di default; opus solo su trigger | implementazione importante o basic |
| `worker-mech` | haiku | lavoro meccanico |
| `verificatore` | haiku/sonnet di default; opus solo su trigger o solo-CC importante | verifica indipendente, sola lettura |
| `pre-merge` | diverso dal builder; anche dal verificatore se non richiede premium | gate pre-merge, sola lettura + `gh` |
| `integratore` | sonnet o `gpt-5.6-terra` | fonde i branch task in `m/<slug>`, nessuna implementazione nuova |

Il `model` del frontmatter è il default: il cervello può passarne uno diverso a ogni chiamata
e lo scrive nel contratto del task. I bridge `bin/spawn-cx.sh` e `bin/spawn-cc.sh` validano il
modello contro questa tabella e rifiutano con exit 65 quello che non c'è.

In cx non esistono agent dichiarati: il cervello cx passa modello ed effort a ogni thread
o a ogni `codex exec`.
