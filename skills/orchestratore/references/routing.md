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
2. Default (peso `dev cx 100 / cc 0`, `verifica cc`): builder terra o sol su cx,
   verificatore opus su CC, pre-merge sol su cx (o astra se il builder era sol).
3. **Solo-CC** (cx esaurito): basic → sonnet costruisce, opus verifica, pre-merge haiku in
   lettura con checklist; importante → opus costruisce, **fable verifica** (unica eccezione a
   "Fable non verifica"), pre-merge sonnet.
4. **Solo-cx** (CC esaurito): basic → terra costruisce, sol verifica, pre-merge luna con
   checklist; importante → sol costruisce, gpt-6-astra verifica, pre-merge terra.
5. Escalation di un tier solo su trigger concreto: contratto ambiguo, due tentativi
   falliti, disaccordo builder/verificatore, rischio alto scoperto in corso.
   De-escalation sul follow-up meccanico.
6. Effort: il cervello può alzare o abbassare l'effort default di un livello; lo scrive nel
   contratto. In cx si passa con `-c model_reasoning_effort=<low|medium|high>`; in CC con la
   definizione dell'agent o l'istruzione nel prompt.
7. Mai dichiarare che un modello ha girato se il runtime non lo riporta. Il log del bridge
   e il campo `model` della risposta sono l'unica evidenza.

## Agent CC del plugin (M2)

| Agent | Modello | Uso |
|---|---|---|
| `worker-impl` | opus o sonnet, scelto dal cervello | implementazione importante o basic |
| `worker-mech` | haiku | lavoro meccanico |
| `verificatore` | opus | verifica indipendente, sola lettura |
| `pre-merge` | scelto dal cervello, diverso da builder e verificatore | gate pre-merge, sola lettura + `gh` |

In cx non esistono agent dichiarati: il cervello cx passa modello ed effort a ogni thread
o a ogni `codex exec`.
