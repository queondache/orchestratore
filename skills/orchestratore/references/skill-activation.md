# Skill activation on demand — Andrea, 2026-09-11

## Minimal Codex startup

The approved startup set is `i-have-adhd:i-have-adhd`, `orchestratore`, and
`openai-docs`. Optional skills remain installed but disabled in Codex's automatic
catalog. The `codex-app-tools` host adapter is retained as infrastructure; it does
not authorize using any connected service. Do not modify plugin cache metadata.

At startup, read the user's task and applicable project instructions. Do not load
optional skill bodies, launch apps, start services, or activate a whole tool bundle.

## Identify a skill only when a concrete need appears

The sibling [Codex catalog](codex-skills-catalog.jsonl) records names, purposes,
local paths, and owning plugin IDs as inspected on 2026-09-11. Search its metadata
with `rg -i` using the current task's keywords; do not dump the complete catalog
into context. Cached installation is not proof of current tool availability.

Propose the smallest useful skill. Prefer a project-required skill over a generic
alternative. Ordinary shell, edits, and tests do not need an extra skill merely
because one exists. An unrelated optional skill never blocks authorized work.

Before loading an optional skill, ask one concrete question in Italian, such as:

> Per modificare questa schermata serve `design-taste-frontend`, prevista da Pau.
> Posso caricarne le istruzioni soltanto in questa sessione?

Mention the specific work the skill will help and whether the request is for local
instructions or for plugin tools. A generic project task or repository requirement
does not itself approve optional skill activation. An explicit user instruction to
use that named skill already supplies approval: do not ask twice. Never interpret
silence or a timeout as consent. Continue independent work while waiting. If Andrea
declines, use the built-in workflow when it meets the contract; otherwise stop only
the affected task and state the concrete missing requirement.

## After approval

1. **Local skill instructions:** verify the catalog path still exists, then read
   that `SKILL.md` and only its relevant references. State `Istruzioni di <nome>
   caricate per questa sessione`. This is an explicitly approved local read, not
   native runtime re-registration or plugin activation. Keep the global skill
   disabled so future sessions still start with the minimal set. A scoped approval
   may be passed to workers of this same task; do not repeat the question for each
   worker or carry it to another session.
2. **Plugin tools:** inspect whether the actual tool is exposed in this session.
   Reading a cached skill cannot add MCP tools. Prefer a documented session-scoped
   activation capability if the current host exposes one. Otherwise explain whether
   enabling it changes global configuration and requires a new session; obtain
   approval for that exact scope before changing it. Do not claim that a global
   toggle expires when the conversation ends, silently re-enable an entire bundle,
   restart the user's app, or create another model session on their behalf.
3. **Missing files or dependencies:** report the precise missing item. Installing,
   downloading, authenticating, or enabling another skill/plugin needs its own
   applicable authorization; do not perform it as a hidden consequence of loading
   instructions. After an authorized upgrade, refresh only affected catalog entries
   and disabled-name selectors; never trust an old versioned path blindly.

Activation approval covers only the named skill and stated scope. All existing
approvals for external services, publication, destructive operations, and each
individual mouse action remain in force. Do not treat tool availability as consent.

## State and verification

Record granted or declined activation only in the current task/session state. On
resume after compaction within the same session, preserve granted scope; a new
session starts without optional grants. Do not maintain a global consent ledger.

Native checks can use the installed Codex app-server `skills/list` method without
starting a model turn. `enabled: false` entries may remain in that management list;
count only enabled entries when checking the startup set. Verify the actual host
when available, and distinguish a CLI check from a desktop check. Existing chats
retain already injected context; the minimal startup applies to new sessions.

`[[skills.config]]` name selectors disable the currently audited names, not every
possible future installation. New skills/plugins need a focused audit to preserve
the minimal set. Keep the three core skills enabled and avoid rewriting unrelated
model, permission, authentication, MCP, or project configuration.
