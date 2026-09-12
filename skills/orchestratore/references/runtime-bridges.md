# Runtime bridges

Use tier names in the portable protocol. Map them to models actually available in the
current runtime; model names and availability change independently from the skill.

## Codex mapping approved for the current workflow

| Tier | Preferred model | Typical work |
|---|---|---|
| Strategic | `gpt-6-astra` | Orchestration, architecture, conflicts, integration |
| High-risk | `gpt-5.6-sol` | Security/backend review, data and concurrency |
| Implementation | `gpt-5.6-terra` | Bounded product implementation, especially frontend |
| Mechanical | `gpt-5.6-luna` | Inventories and deterministic checks |

Use the session's collaboration tools. A persisted plan does not start or monitor agents.

## Claude Code mapping

Use the strongest reasoning model available for orchestration and high-risk review, the
general coding model for bounded implementation, and the fastest adequate model for
mechanical work. Map the protocol onto Claude Code's current Agent/Task primitives. Do not
hard-code OpenAI model identifiers into Claude configuration.

If model selection is unavailable, keep one model and vary reasoning effort, task size and
context breadth. Never claim a model ran unless the runtime reports it.

## External-compute mapping

LLM agent calls already use provider compute. Build, test, browser and database workloads are
not LLM inference and generally need a remote CPU/RAM runner rather than a GPU runner. Use an
existing authorized CI or development runner. If none is available, stop before a heavy local
command and record the missing runner as a blocker.

Do not claim a particular GPU for a hosted model unless the provider exposes it. For local or
remote application workloads, record the detected accelerator, runner identity and workload
compatibility. A present GPU is not automatically the right target for CPU-bound software.
