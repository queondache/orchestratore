#!/usr/bin/env bash
# Structural gate for the orchestratore plugin. Exit 0 only if every check passes.
# Usage: bash tests/check-structure.sh   (from any directory)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0

check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then printf 'OK  %s\n' "$desc"; else printf 'KO  %s\n' "$desc"; FAIL=$((FAIL+1)); fi
}

VERSION="$(jq -r .version "$ROOT/.claude-plugin/plugin.json")"
SHIPPED=("$ROOT/skills" "$ROOT/agents" "$ROOT/commands" "$ROOT/hooks" "$ROOT/bin" "$ROOT/templates")

# Manifests
check "Claude plugin.json valid" jq -e '.name=="orchestratore" and (.version|test("^[0-9]+\\.[0-9]+\\.[0-9]+$")) and .license=="MIT"' "$ROOT/.claude-plugin/plugin.json"
check "Claude marketplace lists the plugin at ./" jq -e '.plugins|length==1 and .[0].source=="./"' "$ROOT/.claude-plugin/marketplace.json"
check "Codex plugin.json valid" jq -e '.name=="orchestratore" and .skills=="./skills/" and .license=="MIT" and (.interface.displayName|length>0)' "$ROOT/.codex-plugin/plugin.json"
check "Codex marketplace valid" jq -e '.name=="orchestratore" and (.plugins|length==1)' "$ROOT/.agents/plugins/marketplace.json"
for f in .claude-plugin/marketplace.json .codex-plugin/plugin.json .agents/plugins/marketplace.json; do
  check "$f version = $VERSION" jq -e --arg v "$VERSION" '.version==$v' "$ROOT/$f"
done
check "LICENSE is MIT" grep -q '^MIT License$' "$ROOT/LICENSE"
check "CHANGELOG has an entry for $VERSION" grep -q "^## $VERSION" "$ROOT/CHANGELOG.md"

# Skills
for dir in "$ROOT"/skills/*/; do
  name="$(basename "$dir")"; skill="$dir/SKILL.md"
  check "skill $name: name matches directory" grep -q "^name: $name$" "$skill"
  check "skill $name: description starts with 'Use when'" grep -q '^description: Use when ' "$skill"
  check "skill $name: frontmatter <= 1024 chars" bash -c "[ \$(awk '/^---\$/{n++; next} n==1' '$skill' | wc -c) -le 1024 ]"
  check "skill $name: relative links resolve" bash -c "cd '$dir' && grep -o '](references/[^)]*)' SKILL.md | sed 's/](//;s/)\$//' | while read -r l; do test -f \"\$l\" || exit 1; done"
done
check "brief SKILL.md <= 160 lines" bash -c "[ \$(wc -l < '$ROOT/skills/brief/SKILL.md') -le 160 ]"

# Agents
for a in builder verifier diagnostician; do
  f="$ROOT/agents/$a.md"
  check "agent $a: name, model, tools" bash -c "grep -q '^name: $a\$' '$f' && grep -q '^model: ' '$f' && grep -q '^tools: ' '$f'"
done
check "diagnostician is read-only" bash -c "grep -q '^tools: ' '$ROOT/agents/diagnostician.md' && ! grep -qE '^tools:.*(Write|Edit)' '$ROOT/agents/diagnostician.md'"
check "diagnostician returns the fixed diagnosis format" bash -c "grep -q '^DIAGNOSIS <ID>' '$ROOT/agents/diagnostician.md' && grep -q '^cause: code | test | brief | environment' '$ROOT/agents/diagnostician.md' && grep -q '^question: ' '$ROOT/agents/diagnostician.md'"
check "verifier is read-only" bash -c "! grep -qE '^tools:.*(Write|Edit)' '$ROOT/agents/verifier.md'"
check "builder and verifier default to different models" bash -c "[ \"\$(sed -n 's/^model: //p' '$ROOT/agents/builder.md')\" != \"\$(sed -n 's/^model: //p' '$ROOT/agents/verifier.md')\" ]"

# Command and hooks
check "command orchestra has description" grep -q '^description: ' "$ROOT/commands/orchestra.md"
check "command lists start status resume stop" bash -c "for s in start status resume stop; do grep -q \"\\*\\*\$s\\*\\*\" '$ROOT/commands/orchestra.md' || exit 1; done"
check "hooks.json valid" jq -e '.hooks.SessionStart' "$ROOT/hooks/hooks.json"
check "hook scripts referenced by hooks.json exist" bash -c "jq -r '.. | .command? // empty' '$ROOT/hooks/hooks.json' | grep -o 'hooks/[a-z-]*\.sh' | while read -r s; do test -f '$ROOT/'\$s || exit 1; done"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
git -C "$TMP" init -q
check "session hook silent without a run" bash -c "cd '$TMP' && [ -z \"\$(bash '$ROOT/hooks/session-state.sh')\" ]"
mkdir -p "$TMP/.orchestratore"; printf 'status: active\nupdated: now\ngoal: fix the login bugs\nnext: verify U-1\n' > "$TMP/.orchestratore/RUN.md"
check "session hook reports an active run" bash -c "cd '$TMP' && bash '$ROOT/hooks/session-state.sh' | grep -q 'next: verify U-1'"
check "session hook surfaces the run goal" bash -c "cd '$TMP' && bash '$ROOT/hooks/session-state.sh' | grep -q 'goal: fix the login bugs'"
mkdir "$TMP/.orchestratore/coordinator.lock"; printf 'session: s1\n' > "$TMP/.orchestratore/coordinator.lock/owner"
check "session hook shows the coordinator lock owner" bash -c "cd '$TMP' && bash '$ROOT/hooks/session-state.sh' | grep -q 'coordinator lock: session: s1'"
check "session hook surfaces RUN.md check problems" bash -c "cd '$TMP' && bash '$ROOT/hooks/session-state.sh' | grep -q 'RUN.md check: '"
mkdir -p "$TMP/.orchestratore/menu"; printf 'status: active\nupdated: now\ngoal: rework the menu\nnext: merge PR 7\n' > "$TMP/.orchestratore/menu/RUN.md"
check "session hook also finds a run kept in a subfolder" bash -c "cd '$TMP' && bash '$ROOT/hooks/session-state.sh' | grep -q 'next: merge PR 7' && bash '$ROOT/hooks/session-state.sh' | grep -q 'next: verify U-1'"
check "session hook names the page to resume for a subfolder run" bash -c "cd '$TMP' && bash '$ROOT/hooks/session-state.sh' | grep -qF 'resume .orchestratore/menu/RUN.md'"
printf 'status: done\nupdated: now\ngoal: old\nnext: none\n' > "$TMP/.orchestratore/menu/RUN.md"
check "session hook skips a done run in a subfolder" bash -c "cd '$TMP' && ! bash '$ROOT/hooks/session-state.sh' | grep -q 'goal: old'"
for r in r2 r3 r4; do mkdir -p "$TMP/.orchestratore/$r"; printf 'status: active\nupdated: now\ngoal: g\nnext: n\n' > "$TMP/.orchestratore/$r/RUN.md"; done
check "session hook counts runs beyond three" bash -c "cd '$TMP' && bash '$ROOT/hooks/session-state.sh' | grep -qF '+1 more runs'"
mkdir -p "$TMP/.orchestratore/notes"; printf '# notes\nnext: nothing\n' > "$TMP/.orchestratore/notes/RUN.md"
check "session hook ignores a page without a status line" bash -c "cd '$TMP' && bash '$ROOT/hooks/session-state.sh' | grep -qF '+1 more runs'"
for r in r2 r3 r4; do printf 'status: done\n' > "$TMP/.orchestratore/$r/RUN.md"; done
printf 'status: done\n' > "$TMP/.orchestratore/RUN.md"
check "session hook silent when the run is done" bash -c "cd '$TMP' && [ -z \"\$(bash '$ROOT/hooks/session-state.sh')\" ]"

# Scripts
check "codex-task.sh parses" bash -n "$ROOT/bin/codex-task.sh"
check "merge-gate.py parses" python3 -c "import ast; ast.parse(open('$ROOT/bin/merge-gate.py').read())"
check "verdict-check.py parses" python3 -c "import ast; ast.parse(open('$ROOT/bin/verdict-check.py').read())"
check "verdict-check.py is executable" test -x "$ROOT/bin/verdict-check.py"
check "verifier agent and verify.md share the verdict format" bash -c "for f in '$ROOT/agents/verifier.md' '$ROOT/skills/orchestratore/references/verify.md'; do grep -q '^result: OK | KO | BLOCKED\$' \"\$f\" && grep -q '^blocked: ' \"\$f\" && grep -q '\[ran | ran expect-fail | ci <run url or id> | reused <what>\]' \"\$f\" || exit 1; done"
check "run-check.py parses" python3 -c "import ast; ast.parse(open('$ROOT/bin/run-check.py').read())"
check "scripts are executable" bash -c "test -x '$ROOT/bin/codex-task.sh' && test -x '$ROOT/bin/merge-gate.py' && test -x '$ROOT/bin/run-check.py' && test -x '$ROOT/hooks/session-state.sh'"

# Templates
check "RUN template has the fields the hook reads" bash -c "grep -q '^status: ' '$ROOT/templates/RUN.md' && grep -q '^next: ' '$ROOT/templates/RUN.md' && grep -q '^goal: ' '$ROOT/templates/RUN.md'"
check "RUN template counts KO verdicts per unit" grep -q '| KO |' "$ROOT/templates/RUN.md"
check "RUN template keeps the Log as the last section" bash -c "[ \"\$(grep '^## ' '$ROOT/templates/RUN.md' | tail -n 1)\" = '## Log' ]"

# Focus rules: the run page is overwritten in place, KO verdicts are capped per unit
# whatever the findings, and new work never stacks on a lane that is red or waiting.
skill_says() { # skill_says <phrase>: the phrase appears in SKILL.md, line breaks ignored
  tr '\n' ' ' < "$ROOT/skills/orchestratore/SKILL.md" | tr -s ' ' | grep -qF "$1"
}
check "skill: RUN header overwritten in place, never a second header" skill_says 'never add a second header'
check "skill: merge and deploy details live in references/merge.md" test -f "$ROOT/skills/orchestratore/references/merge.md"
check "skill: goal recorded at start" skill_says 'run-check.py --record-goal'
# Mixed mode: Claude Code coordinates, Codex builds, Claude verifies.
check "skill: mixed mode named" skill_says '**Mixed**: Codex builds for a Claude Code coordinator'
check "engines: mixed section exists" grep -q '^## Mixed: Claude Code coordinates, Codex builds' "$ROOT/skills/orchestratore/references/engines.md"
check "engines: mixed preflight checks codex login" grep -q 'codex login status' "$ROOT/skills/orchestratore/references/engines.md"
check "engines: mixed dispatch is one background Bash per unit" grep -q 'one Bash call per unit' "$ROOT/skills/orchestratore/references/engines.md"
check "engines: mixed records the model that ran" grep -q 'Write the `model=` value in the' "$ROOT/skills/orchestratore/references/engines.md"
check "engines: mixed falls back to Claude builders" grep -q 'send its queued and correction work to Claude builders' "$ROOT/skills/orchestratore/references/engines.md"
check "config template has engines.mode" grep -q '^mode = "single"' "$ROOT/templates/config.toml"
check "config template parses as TOML" python3 -c "import sys
try:
    import tomllib
except ModuleNotFoundError:
    sys.exit(0)
tomllib.load(open('$ROOT/templates/config.toml','rb'))"

# Hygiene: shipped files are portable and in English. Perl, not grep: \b must mean the
# same on macOS and Linux. Only git-tracked text files count, never build artefacts.
shipped_grep() { # shipped_grep <perl-regex>: prints matches, succeeds if there are none
  (cd "$ROOT" && git ls-files -z skills agents commands hooks bin templates | xargs -0 perl -ne "print \"\$ARGV:\$.: \$_\" if m{$1}; close ARGV if eof" | grep . && return 1 || return 0)
}
check "no absolute user paths or personal names in shipped files" shipped_grep '/Users/|/home/[a-z]|andreapesce|~/Dev|\bAndrea\b'
check "no Italian leftovers in shipped files" shipped_grep '(?i)\b(della|degli|perché|quando|milestone meno|cervello|verificatore)\b'
# Claude models: opus for the complex work (coordinate, verify, diagnose), sonnet builds.
agent_model() { grep -qx "model: $2" "$ROOT/agents/$1.md"; }
check "agents: builder runs on sonnet" agent_model builder sonnet
check "agents: verifier runs on opus" agent_model verifier opus
check "agents: diagnostician runs on opus" agent_model diagnostician opus
check "config: claude builder sonnet, verifier opus" bash -c "grep -qx 'claude_builder = \"sonnet\"' '$ROOT/templates/config.toml' && grep -qx 'claude_verifier = \"opus\"' '$ROOT/templates/config.toml'"
check "engines: unit verify command uses codex_unit_verifier" grep -q 'codex-task.sh --model "<codex_unit_verifier>" --effort low' "$ROOT/skills/orchestratore/references/engines.md"
check "config: codex_unit_verifier key present" grep -q '^codex_unit_verifier = ' "$ROOT/templates/config.toml"
check "engines: coordinator session runs on opus" bash -c "tr '\\n' ' ' < '$ROOT/skills/orchestratore/references/engines.md' | tr -s ' ' | grep -qF 'Run the coordinator session on **opus**'"
check "verify: rejected verdict reruns once on the same verifier model" bash -c "tr '\\n' ' ' < '$ROOT/skills/orchestratore/references/verify.md' | tr -s ' ' | grep -qF 'on the same verifier model (never the builder'"
# 0.10.0: spec and ready tickets before dispatch, no fixed agent cap, done = goal reached.
check "brief: ready check section" grep -q '^## 5. Ready check' "$ROOT/skills/brief/SKILL.md"
check "brief: run context section" grep -q '^## 3. Run context' "$ROOT/skills/brief/SKILL.md"
check "brief: template carries spec, code, pattern, pitfalls" bash -c "for f in spec code pattern pitfalls; do grep -q \"^\$f: \" '$ROOT/skills/brief/SKILL.md' || exit 1; done"
engines_says() { tr '\n' ' ' < "$ROOT/skills/orchestratore/references/engines.md" | tr -s ' ' | grep -qF "$1"; }
check "engines: unit verify brief carries CONTEXT.md" engines_says 'base: <unit base sha>` + `.orchestratore/CONTEXT.md` + the unit brief'
check "engines: Claude Code builder prompt carries CONTEXT.md" engines_says 'prompt=<CONTEXT.md> + <brief content>)'
check "engines: Claude Code verifier prompt carries CONTEXT.md" engines_says 'base: <unit base sha>\n" + <CONTEXT.md> + <brief content>)'
check "engines: Codex spawn_agent message carries CONTEXT.md" engines_says '+ <CONTEXT.md> + <brief content>)'
check "engines: Codex batch verify brief carries CONTEXT.md" engines_says 'the hash, `CONTEXT.md` and the unit brief'
check "engines: mixed build brief carries CONTEXT.md" engines_says '+ `.orchestratore/CONTEXT.md` + the unit brief. Brief commands'
check "engines: mixed first-KO correction carries CONTEXT.md" engines_says 'codex-fix1/<ID>.md` = the builder body + `workdir:` + `CONTEXT.md` +'
check "engines: diagnostician gets CONTEXT.md on every runtime" bash -c "[ \$(tr '\\n' ' ' < '$ROOT/skills/orchestratore/references/engines.md' | tr -s ' ' | grep -oF 'diagnostician' | wc -l) -ge 2 ] && tr '\\n' ' ' < '$ROOT/skills/orchestratore/references/engines.md' | tr -s ' ' | grep -qF 'diagnostician.md\`, \`CONTEXT.md\`,' && grep -q 'run context (\`CONTEXT.md\`), the unit brief' '$ROOT/agents/diagnostician.md'"
check "engines: repo rules reach Codex sub-agents through CONTEXT.md" engines_says 'the repository rules reach it through `CONTEXT.md` in the message'
check "command: resume takes a page" bash -c "grep -qF 'resume** \`[page]\`' '$ROOT/commands/orchestra.md'"
check "brief: proof names the wrong code that turns each test red" bash -c "grep -qF 'A test that would stay green with the wrong code is not a proof.' '$ROOT/skills/brief/SKILL.md'"
check "merge: no checks anywhere + final OK means --no-required-checks-ok" bash -c "tr '\\n' ' ' < '$ROOT/skills/orchestratore/references/merge.md' | tr -s ' ' | grep -qF 'When that verdict is \`OK\`, pass \`--no-required-checks-ok\`; this is the rule, not a loophole.'"

check "verify: fresh environment in the copy, no stale bytecode" bash -c "grep -q 'PYTHONDONTWRITEBYTECODE=1' '$ROOT/skills/orchestratore/references/verify.md' && grep -q 'PYTHONDONTWRITEBYTECODE=1' '$ROOT/agents/verifier.md'"
check "config: max_parallel defaults to no cap" grep -q '^max_parallel = 0 ' "$ROOT/templates/config.toml"
check "config: auto-merge default everything outside sensitive" grep -qx 'auto_merge_globs = \["\*\*"\]' "$ROOT/templates/config.toml"
check "verify: FIX oracle in a throwaway copy of the exact hash, no reinstall" bash -c "grep -q 'git -C <worktree> archive <hash> |' '$ROOT/skills/orchestratore/references/verify.md' && grep -q 'git -C <worktree> archive <hash> |' '$ROOT/agents/verifier.md'"
check "verify: never link dependencies that point back into the reviewed worktree" bash -c "grep -q 'Do not link' '$ROOT/skills/orchestratore/references/verify.md' && grep -q 'Never link dependencies that point back' '$ROOT/agents/verifier.md'"
check "engines: unit verify never runs without an explicit model" grep -q 'Never call `codex-task.sh verify` without `--model`' "$ROOT/skills/orchestratore/references/engines.md"
check "no Claude verifier left in mixed-mode wording" bash -c "! grep -rn 'Claude verif' '$ROOT/skills' '$ROOT/templates' '$ROOT/README.md'"
check "no fable or haiku in shipped files" shipped_grep '(?i)\b(fable|haiku)\b'
check "no TODO/TBD in shipped files" shipped_grep '\bTODO\b|\bTBD\b'
check "0.6 controller is gone" bash -c "! test -e '$ROOT/controller' && ! test -e '$ROOT/bin/orchestratore-controller'"

# 0.12.0: speed first. No lanes or waves, one PR per verified unit, second KO parks.
check "skill: orchestratore SKILL.md under 100 lines" bash -c "[ \$(wc -l < '$ROOT/skills/orchestratore/SKILL.md') -lt 100 ]"
check "skill: no lanes or waves left" bash -c "! grep -rniE '\\blanes?\\b|two-wave|per wave|final pass' '$ROOT/skills' '$ROOT/agents' '$ROOT/templates' '$ROOT/commands' '$ROOT/README.md'"
check "skill: one PR per verified unit" skill_says 'one PR per verified unit'
check "skill: a waiting PR holds only its dependents" skill_says 'A PR waiting for the user holds only its dependents; all else builds.'
check "skill: two units writing one file depend on each other" skill_says 'Two units writing one file: the second `depends on` the first.'
check "skill: all ready units in one message" skill_says 'All ready units go out **in one message**'
check "skill: no fixed number of agents" skill_says 'No waves, no fixed number'
check "skill: second KO parks after a diagnosis" skill_says '**Second KO** → `orchestratore:diagnostician`'
check "skill: verifier runs class proof plus full gate" skill_says 'class proof plus full gate on that hash'
check "skill: only a verdict accepted by verdict-check counts" skill_says 'Only a verdict `bin/verdict-check.py --hash <hash>` accepts counts'
check "skill: BLOCKED is not a KO" skill_says '**BLOCKED** is not a KO'
check "skill: run-check after each RUN.md event" skill_says 'never add a second header, one sentence under `## Log`; then `python3 <plugin>/bin/run-check.py`'
check "skill: only the user removes a lock" skill_says 'only the user removes it, however old.'
check "skill: resume takes a page" skill_says '`bin/run-check.py --run <page>`'
check "skill: done only when the goal is reached" skill_says '**Done** only when every unit is'
check "skill: every agent gets the run context" skill_says 'Each agent gets `CONTEXT.md`'
check "skill: opus coordinates and verifies tier 3, sonnet builds" skill_says 'builders always run on an economical model (**sonnet**, or a cheap Codex model)'
check "skill: questions never stop independent work" skill_says 'keep building what does not depend on it.'
check "skill: token not yours → stop without writing" skill_says 'if not, stop at once without writing.'
check "skill: unlock only with your token" skill_says '**Unlock**, only with your token there: `rm .orchestratore/coordinator.lock/owner && rmdir .orchestratore/coordinator.lock`'
check "skill: red check not caused by the change becomes a unit" skill_says 'A red check the change did not cause becomes a FIX or CHECK unit; a flaky test gets one rerun, billing/quota/infra none.'
check "skill: base moved → merge base in, update base, new verdict" skill_says 'Base moved since the verdict (conflict or not) → before the merge gate, the same builder merges the base in (never rebase), `base` updated to that head, new verdict.'
check "skill: exclusive resources handed to one verifier at a time" skill_says 'you hand each `exclusive:` resource to one verifier at a time.'
check "skill: dependents of a parked unit resume with it" skill_says 'resume with it'
check "skill: per-unit behaviour lives in the brief" skill_says 'goes in its own brief (`spec:`)'
check "command: section references match the skill" bash -c "grep -qF 'the §7 report' '$ROOT/commands/orchestra.md' && grep -qF 'then §6 on' '$ROOT/commands/orchestra.md' && grep -qF 'stop** — skill §6' '$ROOT/commands/orchestra.md'"
check "template: verifier line names both tiers" grep -qF 'verifier: <economical model> (tier 1-2), <strong model> (tier 3)' "$ROOT/templates/RUN.md"
check "template: units carry depends on and PR" grep -qF '| depends on |' "$ROOT/templates/RUN.md"
check "engines: unit branches under orch-unit" grep -qF 'git worktree add -b orch-unit/<run>/<ID>' "$ROOT/skills/orchestratore/references/engines.md"
check "engines: worktree removed once merged or parked" grep -q 'as soon as its branch is merged or the' "$ROOT/skills/orchestratore/references/engines.md"
check "verify: verdict is the PR quality proof" bash -c "tr '\\n' ' ' < '$ROOT/skills/orchestratore/references/verify.md' | tr -s ' ' | grep -qF 'this verdict is the quality proof for the unit'"
check "diagnostician: runs at the second KO" grep -q "second KO" "$ROOT/agents/diagnostician.md"

check "brief: BUILD criteria numbered C1..Cn" bash -c "grep -qF 'numbered \`C1..Cn\`' '$ROOT/skills/brief/SKILL.md'"
check "brief: commands proven to run at least one test" bash -c "grep -qF 'run at least one test' '$ROOT/skills/brief/SKILL.md'"
check "merge: always pass --merge" grep -qF 'Always pass `--merge`' "$ROOT/skills/orchestratore/references/merge.md"

echo
if [ "$FAIL" -eq 0 ]; then echo "GREEN: all checks pass"; exit 0; fi
echo "RED: $FAIL checks failed"; exit 1
