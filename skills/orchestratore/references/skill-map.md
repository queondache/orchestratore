# Skill obbligatorie per tipo di task

Il cervello scrive nel contratto del task nome e path esatto di ogni skill richiesta. Un
worker non inventa né installa skill. Se una skill manca sul runtime scelto, il cervello usa
una skill equivalente già installata o procedura base e continua quando possibile; passa il
file per path o registra solo un blocco realmente impeditivo. Mai abilitare o modificare
globalmente skill/plugin, né ampliare i permessi di tool o app.

| Tipo di task | Skill | CC | cx |
|---|---|---|---|
| Architettura, DB, tier, sicurezza | `senior-architect` + skill di progetto (`mesa-senior-architect`, `pau-senior-architect`, `zerocampo-senior-architect`) | nativa | per path `~/Dev/skills/<nome>/SKILL.md` |
| Implementazione con test | `superpowers:test-driven-development`, `superpowers:systematic-debugging` | nativa | per path nella cache plugin CC (`~/.claude/plugins/cache/claude-plugins-official/superpowers/<versione>/skills/<nome>/SKILL.md`) |
| Piano di una lane | `superpowers:writing-plans` | nativa | per path come sopra |
| UI nuova | CC: `frontend-design` o `impeccable`; cx: `design-taste-frontend`, `high-end-visual-design`, `ui-ux-pro-max` | nativa | nativa |
| Redesign | `redesign-existing-projects` | nativa | nativa |
| Lane milestone | `milestone` | nativa | per path `~/Dev/skills/milestone/SKILL.md` |
| Verifica | agent `verificatore` del plugin | nativo | opus via bridge, o thread `gpt-5.6-sol` con il testo dell'agent per path |
| Deploy Vercel | plugin `vercel` | nativo | nativo |
| Output per Andrea | `i-have-adhd` sempre attiva; `caveman` se attiva | nativa | nativa |

Prima di ogni assegnazione UI il cervello controlla se il progetto impone una skill di design
(CLAUDE.md del progetto): quella vince sulla tabella.

Inventario completo lato CC: `~/Dev/skills/cc-installed-plugins.md`. Lato cx:
`references/codex-skills-catalog.jsonl` (cerca con `rg -i <parola>`; non caricarlo intero).
