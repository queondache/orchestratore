# Orchestratore 0.4.1 — routing economico per task

Data: 14/09/2026. Release compatibile con 0.4.0 che rende esplicita e verificabile la
selezione del modello e dell'effort più economici capaci di chiudere ogni task.

## Risultato

- Il cervello del run usa `gpt-6-astra` con effort `medium`.
- I worker partono dal modello meno costoso adatto: Luna da `medium`, Terra da `medium`,
  Sol da `low`; Astra da `low` soltanto quando un trigger documentato richiede escalation.
- Modello ed effort dipendono dal task: `low` non è più un default indiscriminato.
- Il verificatore resta distinto dal builder e sceglie il profilo meno costoso compatibile
  con indipendenza, rischio e qualità richiesta.
- Il bridge Codex rifiuta prima della spesa le coppie vietate `Luna low` e `Terra low`.
- `run.md` registra scelta, trigger ed eventuale escalation per rendere il costo auditabile.
- I KO usano firma persistita, deduplica e budget finito: due tentativi per approccio, due
  approcci automatici, poi lane parcheggiata mentre il run continua altrove. Il pattern è
  adattato da [Untrivial AI Agent Orchestrator](https://github.com/Untrivial-ai/agent-orchestrator/blob/a342f8eb518bc9a389ed4cf6e7d20e047de8160d/backend/internal/lifecycle/reactions.go),
  progetto Apache-2.0 con 12.010 stelle al momento della release.

## Compatibilità

I comandi, gli hook, i bridge e il formato base del run restano compatibili con 0.4.0. I
template aggiungono campi di routing; i run esistenti possono adottarli alla ripresa.

## Verifica richiesta

- `tests/check-structure.sh`
- `tests/check-regressions.sh`
- `tests/check-regressions-mutations.sh`
- review indipendente del commit esatto pubblicato

## Limiti aperti

Restano aperte M8, il run pilota end-to-end su un progetto reale, e M9, la raccolta
automatica dell'evidenza del modello effettivamente eseguito.
