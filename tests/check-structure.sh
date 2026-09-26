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
check "orchestratore SKILL.md <= 200 lines" bash -c "[ \$(wc -l < '$ROOT/skills/orchestratore/SKILL.md') -le 200 ]"
check "brief SKILL.md <= 120 lines" bash -c "[ \$(wc -l < '$ROOT/skills/brief/SKILL.md') -le 120 ]"

# Agents
for a in builder verifier; do
  f="$ROOT/agents/$a.md"
  check "agent $a: name, model, tools" bash -c "grep -q '^name: $a\$' '$f' && grep -q '^model: ' '$f' && grep -q '^tools: ' '$f'"
done
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
mkdir -p "$TMP/.orchestratore"; printf 'status: active\nupdated: now\nnext: verify U-1\n' > "$TMP/.orchestratore/RUN.md"
check "session hook reports an active run" bash -c "cd '$TMP' && bash '$ROOT/hooks/session-state.sh' | grep -q 'next: verify U-1'"
mkdir "$TMP/.orchestratore/coordinator.lock"; printf 'session: s1\n' > "$TMP/.orchestratore/coordinator.lock/owner"
check "session hook shows the coordinator lock owner" bash -c "cd '$TMP' && bash '$ROOT/hooks/session-state.sh' | grep -q 'coordinator lock: session: s1'"
printf 'status: done\n' > "$TMP/.orchestratore/RUN.md"
check "session hook silent when the run is done" bash -c "cd '$TMP' && [ -z \"\$(bash '$ROOT/hooks/session-state.sh')\" ]"

# Scripts
check "codex-task.sh parses" bash -n "$ROOT/bin/codex-task.sh"
check "merge-gate.py parses" python3 -c "import ast; ast.parse(open('$ROOT/bin/merge-gate.py').read())"
check "scripts are executable" bash -c "test -x '$ROOT/bin/codex-task.sh' && test -x '$ROOT/bin/merge-gate.py' && test -x '$ROOT/hooks/session-state.sh'"

# Templates
check "RUN template has the fields the hook reads" bash -c "grep -q '^status: ' '$ROOT/templates/RUN.md' && grep -q '^next: ' '$ROOT/templates/RUN.md'"
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
check "no TODO/TBD in shipped files" shipped_grep '\bTODO\b|\bTBD\b'
check "0.6 controller is gone" bash -c "! test -e '$ROOT/controller' && ! test -e '$ROOT/bin/orchestratore-controller'"

echo
if [ "$FAIL" -eq 0 ]; then echo "GREEN: all checks pass"; exit 0; fi
echo "RED: $FAIL checks failed"; exit 1
