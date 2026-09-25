#!/usr/bin/env bash
# Deterministic controller smoke test for the durable assignment contract.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CTL="$ROOT/bin/orchestratore-controller"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
DB="$WORK/state.sqlite3"
PROJECT="$WORK/project"
WORKTREES="$WORK/worktrees"

fail() { printf 'check-controller: %s\n' "$1" >&2; exit 1; }
has() { rg -q "$2" <<<"$1" || fail "output lacks: $2"; }

git init -q "$PROJECT"
git -C "$PROJECT" config user.email controller@example.invalid
git -C "$PROJECT" config user.name 'Controller Tests'
printf 'seed\n' > "$PROJECT/seed"
git -C "$PROJECT" add seed
git -C "$PROJECT" commit -qm seed
git -C "$PROJECT" branch -M main
mkdir -p "$WORKTREES" "$PROJECT/.orchestratore"
printf '# RUN\n' > "$PROJECT/.orchestratore/RUN.md"
mkdir -p "$WORK/fakebin"
cat > "$WORK/fakebin/gh" <<'EOF'
#!/usr/bin/env bash
set -eu
sha=$(git rev-parse HEAD)
if [ "$1 $2" = "repo view" ]; then
  printf 'example/orchestratore\n'
elif [ "$1" = "api" ]; then
  git rev-parse refs/heads/main
elif [ "$1 $2" = "pr view" ]; then
  state=OPEN; [ ! -e .gh-merged ] || state=MERGED
  printf '{"headRefOid":"%s","state":"%s","baseRefName":"main"}\n' "$sha" "$state"
elif [ "$1 $2" = "pr checks" ]; then
  printf '[{"name":"unit","state":"SUCCESS","link":"https://ci.invalid/unit"}]\n'
elif [ "$1 $2" = "pr merge" ]; then
  : > .gh-merged; printf 'merged\n'
else exit 64
fi
EOF
chmod +x "$WORK/fakebin/gh"
export PATH="$WORK/fakebin:$PATH"
SHA="$(git -C "$PROJECT" rev-parse HEAD)"

add_task() {
  local run="$1" task="$2" path
  path="$WORKTREES/$task"
  git -C "$PROJECT" worktree add -q -b "check/$task" "$path"
  "$CTL" --db "$DB" add-task "$run" "$task" "$task" \
    --conflict-key "$task" --worktree-path "$path" --risk-tier 2 \
    --auto-merge-glob seed \
    --target-branch main \
    --holder owner-a >/dev/null
}

claim() {
  local run="$1" task="$2" out
  out="$("$CTL" --db "$DB" schedule "$run" --holder owner-a)"
  python3 -c 'import json,sys
task=sys.argv[1]
item=next(x for x in json.load(sys.stdin)["actions"] if x.get("task")==task)
print(item["assignment_id"], item["stage"], item["fence"])' "$task" <<<"$out"
}

complete() {
  local task="$1" evidence="$2" assignment stage fence
  read -r assignment stage fence < <(claim run-a "$task")
  "$CTL" --db "$DB" complete "$task" --evidence "$evidence" \
    --assignment-id "$assignment" --expected-stage "$stage" \
    --holder owner-a --fence "$fence" >/dev/null
}

fail_task() {
  local task="$1" signature="$2" evidence="$3" assignment stage fence
  read -r assignment stage fence < <(claim run-a "$task")
  "$CTL" --db "$DB" fail "$task" "$signature" --evidence "$evidence" \
    --assignment-id "$assignment" --expected-stage "$stage" \
    --holder owner-a --fence "$fence"
}

"$CTL" --db "$DB" init >/dev/null
START="$("$CTL" --db "$DB" start run-a --holder owner-a --seconds 3600 \
  --config '{"brain_model":"gpt-6-astra","brain_effort":"medium","sensitive_paths":["security/**"]}')"
has "$START" '"fence": 1'
add_task run-a task-a

# Dry-run stays read-only; real scheduling creates the durable assignment.
OUT="$("$CTL" --db "$DB" schedule run-a --dry-run)"
has "$OUT" '"action": "strategy"'
has "$OUT" '"provider": "claude"'
has "$("$CTL" --db "$DB" status run-a)" '"owner_provider": null'
read -r ASG STAGE FENCE < <(claim run-a task-a)
if "$CTL" --db "$DB" complete task-a \
    --evidence '{"summary":"strategy","plan_hash":"p1"}' \
    --holder owner-a >/dev/null 2>&1; then
  fail 'completion without assignment was accepted'
fi
"$CTL" --db "$DB" complete task-a \
  --evidence '{"summary":"strategy","plan_hash":"p1"}' \
  --assignment-id "$ASG" --expected-stage "$STAGE" \
  --holder owner-a --fence "$FENCE" >/dev/null

# Evidence is typed at every stage; finalization remains explicit.
complete task-a "{\"sha\":\"$SHA\",\"gate\":{\"command\":\"unit\",\"exit_code\":0,\"output\":\"ok\"}}"
complete task-a "{\"sha\":\"$SHA\",\"verdict\":\"OK\",\"reviewer\":{\"provider\":\"claude\",\"model\":\"opus\"},\"oracle\":{\"command\":\"reverse\",\"exit_code\":0,\"output\":\"red before fix\"},\"raw_output\":\"independent review OK\"}"
has "$("$CTL" --db "$DB" status run-a)" '"recovery_case": "D"'
read -r ASG STAGE FENCE < <(claim run-a task-a)
if "$CTL" --db "$DB" complete task-a --evidence '{"pr":{"number":1}}' \
    --assignment-id "$ASG" --expected-stage "$STAGE" \
    --holder owner-a --fence "$FENCE" >/dev/null 2>&1; then
  fail 'incomplete finalize evidence created DONE'
fi
"$CTL" --db "$DB" complete task-a \
  --evidence "{\"pr\":{\"state\":\"approved-wait\",\"number\":1,\"sha\":\"$SHA\"},\"merge\":{\"state\":\"approved-wait\",\"sha\":\"$SHA\"},\"docs\":true,\"suggest_merge\":true}" \
  --assignment-id "$ASG" --expected-stage "$STAGE" \
  --holder owner-a --fence "$FENCE" >/dev/null
read -r ASG STAGE FENCE < <(claim run-a task-a)
"$CTL" --db "$DB" merge task-a --assignment-id "$ASG" \
  --holder owner-a --fence "$FENCE" >/dev/null
has "$("$CTL" --db "$DB" status run-a)" '"stage": "done"'
has "$("$CTL" --db "$DB" status run-a)" '"finalized": 1'

# Checkpoint emission is one-shot at 50 and rollover is explicit at 70.
add_task run-a task-checkpoint
"$CTL" --db "$DB" checkpoint task-checkpoint 50 --summary boundary \
  --head abc123 --fingerprint worktree:123 --holder owner-a >/dev/null
has "$("$CTL" --db "$DB" schedule run-a --dry-run)" '"action": "checkpoint"'
"$CTL" --db "$DB" schedule run-a --holder owner-a >/dev/null
if rg -q '"action": "checkpoint"' <<<"$("$CTL" --db "$DB" schedule run-a --dry-run)"; then
  fail '50 percent checkpoint repeated indefinitely'
fi
"$CTL" --db "$DB" checkpoint task-checkpoint 70 --summary rollover --holder owner-a >/dev/null
has "$("$CTL" --db "$DB" schedule run-a --dry-run)" '"action": "rollover"'

# Two approaches with two attempts park; a repeated signature from a new
# assignment is a new failure and cannot create a free retry loop.
add_task run-a task-fail
has "$(fail_task task-fail A first)" '"result": "failed"'
has "$(fail_task task-fail B second)" '"result": "failed"'
has "$(fail_task task-fail A duplicate-new-assignment)" '"result": "failed"'
has "$(fail_task task-fail C fourth)" '"result": "parked"'

# Lease behavior fails closed.
if "$CTL" --db "$DB" acquire invalid owner-a --seconds 0 >/dev/null 2>&1; then
  fail 'non-positive lease was accepted'
fi
"$CTL" --db "$DB" acquire brain owner-a --seconds 60 >/dev/null
has "$("$CTL" --db "$DB" acquire brain owner-b --seconds 60)" '"acquired": false'

# Exhaustive routing, concurrency, restart, fencing and bridge contracts.
(cd "$ROOT" && python3 -m unittest controller.test_blockers controller.test_transitions)

echo 'check-controller: ok'
