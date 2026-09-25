#!/usr/bin/env bash
# Gate dei bridge: usa un repository e un worktree reali, senza chiamare modelli.
set -uo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)"
CX="$ROOT/bin/spawn-cx.sh"; CC="$ROOT/bin/spawn-cc.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/orchestratore-bridge.XXXXXX")"
cleanup() { [ -n "${TMP:-}" ] && [ -d "$TMP" ] && command rm -r -f -- "$TMP"; }
trap cleanup EXIT

PROJECT="$TMP/project"
mkdir -p "$PROJECT/.orchestratore"
PROJECT="$(CDPATH= cd -- "$PROJECT" && pwd -P)"
TASK_CWD="$TMP/task-t007"
git -C "$PROJECT" init -q
git -C "$PROJECT" config user.email test@example.invalid
git -C "$PROJECT" config user.name Test
printf '# fixture\n' > "$PROJECT/README.md"
printf 'outside\n' > "$PROJECT/outside.txt"
printf 'control\n' > "$PROJECT/control.txt"
printf '.ignored-outside\n' > "$PROJECT/.gitignore"
printf '# Run\n' > "$PROJECT/.orchestratore/RUN.md"
git -C "$PROJECT" add README.md outside.txt control.txt .gitignore .orchestratore/RUN.md
git -C "$PROJECT" commit -qm fixture
git -C "$PROJECT" worktree add -q -b task-t007 "$TASK_CWD" HEAD
TASK_CWD="$(CDPATH= cd -- "$TASK_CWD" && pwd -P)"

failures=0
ok() { printf 'OK: %s\n' "$1"; }
ko() { printf 'KO: %s\n' "$1"; failures=$((failures + 1)); }
expect_exit() { local want="$1" label="$2"; shift 2; "$@" >/dev/null 2>&1; local got=$?; [ "$got" = "$want" ] && ok "$label (exit $got)" || ko "$label (atteso $want, ottenuto $got)"; }
expect_stdout() { local needle="$1" label="$2"; shift 2; local out; out="$("$@" 2>/dev/null)"; printf '%s' "$out" | grep -Fq -- "$needle" && ok "$label" || ko "$label — manca: $needle"; }

[ -x "$CX" ] && ok 'spawn-cx.sh eseguibile' || ko 'spawn-cx.sh eseguibile'
[ -x "$CC" ] && ok 'spawn-cc.sh eseguibile' || ko 'spawn-cc.sh eseguibile'

ALLOW='["README.md"]'
CX_BUILD=("$CX" --dry-run gpt-5.6-terra medium "$PROJECT" T-007 build "$TASK_CWD" "$ALLOW")
CC_REVIEW=("$CC" --dry-run opus medium "$PROJECT" T-008 review "$TASK_CWD" "$ALLOW")
expect_stdout 'codex exec --yolo --dangerously-bypass-hook-trust' 'cx forza hook trust dopo il preflight' "${CX_BUILD[@]}"
expect_stdout "-C $TASK_CWD" 'cx esegue nel task worktree' "${CX_BUILD[@]}"
expect_stdout "$PROJECT/.orchestratore/logs/T-007.build.log" 'cx tiene il log nel control plane' "${CX_BUILD[@]}"
expect_stdout 'Fase BUILD:' 'cx costruisce prompt per stage' "${CX_BUILD[@]}"
expect_stdout "RUN di controllo: $PROJECT/.orchestratore/RUN.md" 'cx legge il RUN del project root' "${CX_BUILD[@]}"
expect_stdout "RUN.md e' sola lettura" 'cx vieta la scrittura concorrente del RUN' "${CX_BUILD[@]}"
expect_stdout 'claude -p --model opus --effort medium --permission-mode bypassPermissions' 'cc compone modello, effort e bypass' "${CC_REVIEW[@]}"
expect_stdout "--add-dir $PROJECT" 'cc espone il project root in sola lettura contrattuale' "${CC_REVIEW[@]}"
expect_stdout 'Fase REVIEW:' 'cc costruisce prompt da revisore indipendente' "${CC_REVIEW[@]}"
expect_stdout 'Non correggere, non committare e non fare merge' 'cc impone review senza modifiche' "${CC_REVIEW[@]}"

expect_exit 64 'cx rifiuta argv incompleto' "$CX" --dry-run gpt-5.6-sol high "$PROJECT"
expect_exit 65 'cx rifiuta modello estraneo' "$CX" --dry-run gpt-4o high "$PROJECT" T-007 build "$TASK_CWD" "$ALLOW"
expect_exit 65 'cx rifiuta effort estraneo' "$CX" --dry-run gpt-5.6-sol estremo "$PROJECT" T-007 build "$TASK_CWD" "$ALLOW"
expect_exit 65 'cx rifiuta Luna low' "$CX" --dry-run gpt-5.6-luna low "$PROJECT" T-007 build "$TASK_CWD" "$ALLOW"
expect_exit 65 'cx rifiuta Terra low' "$CX" --dry-run gpt-5.6-terra low "$PROJECT" T-007 build "$TASK_CWD" "$ALLOW"
expect_exit 0 'cx accetta Sol low' "$CX" --dry-run gpt-5.6-sol low "$PROJECT" T-007 build "$TASK_CWD" "$ALLOW"
expect_exit 0 'cx accetta Astra low' "$CX" --dry-run gpt-6-astra low "$PROJECT" T-007 strategy "$TASK_CWD" "$ALLOW"
expect_exit 65 'cx rifiuta stage estraneo' "$CX" --dry-run gpt-5.6-sol high "$PROJECT" T-007 deploy "$TASK_CWD" "$ALLOW"
expect_exit 65 'cx rifiuta task-id invalido' "$CX" --dry-run gpt-5.6-sol high "$PROJECT" '../T' build "$TASK_CWD" "$ALLOW"
expect_exit 65 'cx rifiuta allowlist vuota' "$CX" --dry-run gpt-5.6-sol high "$PROJECT" T-007 build "$TASK_CWD" '[]'
expect_exit 66 'cx rifiuta il checkout di controllo come task cwd' "$CX" --dry-run gpt-5.6-sol high "$PROJECT" T-007 build "$PROJECT" "$ALLOW"
OUTSIDE="$TMP/outside"; mkdir -p "$OUTSIDE"; git -C "$OUTSIDE" init -q
expect_exit 66 'cx rifiuta un worktree di un altro repository' "$CX" --dry-run gpt-5.6-sol high "$PROJECT" T-007 build "$OUTSIDE" "$ALLOW"
expect_exit 64 'cc rifiuta argv incompleto' "$CC" --dry-run opus "$PROJECT"
expect_exit 65 'cc rifiuta modello fable nei worker' "$CC" --dry-run fable medium "$PROJECT" T-008 review "$TASK_CWD" "$ALLOW"
expect_exit 65 'cc rifiuta effort non instradato' "$CC" --dry-run sonnet max "$PROJECT" T-008 review "$TASK_CWD" "$ALLOW"
expect_exit 65 'cc rifiuta low non congelato dal controller' "$CC" --dry-run sonnet low "$PROJECT" T-008 review "$TASK_CWD" "$ALLOW"

EMPTY="$TMP/empty"; EMPTY_TASK="$TMP/empty-task"
mkdir -p "$EMPTY"; git -C "$EMPTY" init -q
git -C "$EMPTY" config user.email test@example.invalid; git -C "$EMPTY" config user.name Test
printf x > "$EMPTY/x"; git -C "$EMPTY" add x; git -C "$EMPTY" commit -qm x
git -C "$EMPTY" worktree add -q -b empty-task "$EMPTY_TASK" HEAD
expect_exit 66 'cx execute rifiuta RUN mancante prima del runtime' "$CX" gpt-5.6-sol high "$EMPTY" T-007 build "$EMPTY_TASK" '["x"]'
expect_exit 66 'cc execute rifiuta RUN mancante prima del runtime' "$CC" opus medium "$EMPTY" T-008 review "$EMPTY_TASK" '["x"]'

[ ! -d "$PROJECT/.orchestratore/logs" ] && ok 'dry-run non crea log' || ko 'dry-run non crea log'

# Execute sintetico: il log del bridge e' control-plane e non deve falsare il diff acceptance.
FAKE_BIN="$TMP/fake-bin"; mkdir -p "$FAKE_BIN"
{
  printf '%s\n' '#!/usr/bin/env bash' \
    'if [ "${1:-}" = plugin ] && [ "${2:-}" = list ] && [ "${3:-}" = --json ]; then' \
    '  root="${FAKE_PLUGIN_ROOT:-'"$ROOT"'}"' \
    '  printf '\''{"installed":[{"pluginId":"orchestratore@orchestratore","name":"orchestratore","marketplaceName":"orchestratore","version":"test","installed":true,"enabled":true,"installPath":"%s"}]}\n'\'' "$root"; exit 0' \
    'fi' \
    'if [ "${1:-}" = exec ]; then' \
    '  [ -z "${FAKE_TOUCH:-}" ] || printf x > "$ORCHESTRATORE_TASK_CWD/$FAKE_TOUCH"' \
    '  [ -z "${FAKE_STAGE:-}" ] || { printf staged > "$ORCHESTRATORE_TASK_CWD/$FAKE_STAGE"; git -C "$ORCHESTRATORE_TASK_CWD" add -- "$FAKE_STAGE"; }' \
    '  [ -z "${FAKE_COMMIT:-}" ] || { printf committed > "$ORCHESTRATORE_TASK_CWD/$FAKE_COMMIT"; git -C "$ORCHESTRATORE_TASK_CWD" add -- "$FAKE_COMMIT"; git -C "$ORCHESTRATORE_TASK_CWD" commit -qm worker; }' \
    '  [ -z "${FAKE_SYMLINK:-}" ] || ln -s README.md "$ORCHESTRATORE_TASK_CWD/$FAKE_SYMLINK"' \
    '  [ -z "${FAKE_CACHEINFO_OUTSIDE:-}" ] || { blob=$(printf bypass | git -C "$ORCHESTRATORE_TASK_CWD" hash-object -w --stdin); git -C "$ORCHESTRATORE_TASK_CWD" update-index --cacheinfo 100644,$blob,"$FAKE_CACHEINFO_OUTSIDE"; git -C "$ORCHESTRATORE_TASK_CWD" commit -qm cacheinfo-bypass; }' \
    '  [ -z "${FAKE_REMOVE:-}" ] || rm -f -- "$ORCHESTRATORE_TASK_CWD/$FAKE_REMOVE"' \
    '  [ -z "${FAKE_RESTORE:-}" ] || git -C "$ORCHESTRATORE_TASK_CWD" checkout -q -- "$FAKE_RESTORE"' \
    '  [ -z "${FAKE_CONTROL_TOUCH:-}" ] || printf "%s" "$FAKE_CONTROL_TOUCH" > "$ORCHESTRATORE_PROJECT_ROOT/control.txt"' \
    '  cat >/dev/null; exit 0' \
    'fi' 'exit 64'
} > "$FAKE_BIN/codex"
chmod +x "$FAKE_BIN/codex"
expect_exit 0 'cx execute non scambia il proprio log per modifica al control plane' \
  env PATH="$FAKE_BIN:$PATH" "$CX" gpt-5.6-sol low "$PROJECT" T-009 build "$TASK_CWD" "$ALLOW"
[ -s "$PROJECT/.orchestratore/logs/T-009.build.log" ] && ok 'cx execute conserva il log stage-specific' || ko 'cx execute conserva il log stage-specific'
expect_exit 74 'cx build rifiuta path modificati fuori ownership' \
  env PATH="$FAKE_BIN:$PATH" FAKE_TOUCH=forbidden.txt "$CX" gpt-5.6-sol low "$PROJECT" T-010 build "$TASK_CWD" "$ALLOW"
rm -f "$TASK_CWD/forbidden.txt"
expect_exit 74 'cx post-gate rifiuta tracked unstaged fuori ownership' \
  env PATH="$FAKE_BIN:$PATH" FAKE_TOUCH=outside.txt "$CX" gpt-5.6-sol low "$PROJECT" T-010o build "$TASK_CWD" "$ALLOW"
git -C "$TASK_CWD" checkout -q -- outside.txt
expect_exit 74 'cx post-gate rifiuta staged fuori ownership' \
  env PATH="$FAKE_BIN:$PATH" FAKE_STAGE=outside.txt "$CX" gpt-5.6-sol low "$PROJECT" T-010os build "$TASK_CWD" "$ALLOW"
git -C "$TASK_CWD" checkout -q HEAD -- outside.txt
expect_exit 74 'cx post-gate rifiuta commit fuori ownership' \
  env PATH="$FAKE_BIN:$PATH" FAKE_COMMIT=outside.txt "$CX" gpt-5.6-sol low "$PROJECT" T-010oc build "$TASK_CWD" "$ALLOW"
git -C "$TASK_CWD" reset -q --hard HEAD~1
expect_exit 74 'cx build rileva un ignored modificato fuori ownership' \
  env PATH="$FAKE_BIN:$PATH" FAKE_TOUCH=.ignored-outside "$CX" gpt-5.6-sol low "$PROJECT" T-010i build "$TASK_CWD" "$ALLOW"
rm -f "$TASK_CWD/.ignored-outside"

# Ogni task parte da uno stato completamente pulito: non esistono baseline
# worker-modificabili e il modello non parte se trova lavoro preesistente.
printf 'dirty-before\n' > "$TASK_CWD/outside.txt"
expect_exit 74 'cx preflight rifiuta tracked dirty preesistente' \
  env PATH="$FAKE_BIN:$PATH" "$CX" gpt-5.6-sol low "$PROJECT" T-010p build "$TASK_CWD" "$ALLOW"
git -C "$TASK_CWD" checkout -q -- outside.txt
printf 'staged-before\n' > "$TASK_CWD/outside.txt"; git -C "$TASK_CWD" add outside.txt
expect_exit 74 'cx preflight rifiuta index staged preesistente' \
  env PATH="$FAKE_BIN:$PATH" "$CX" gpt-5.6-sol low "$PROJECT" T-010st build "$TASK_CWD" "$ALLOW"
git -C "$TASK_CWD" checkout -q HEAD -- outside.txt
printf x > "$TASK_CWD/preexisting.tmp"
expect_exit 74 'cx preflight rifiuta untracked preesistente' \
  env PATH="$FAKE_BIN:$PATH" "$CX" gpt-5.6-sol low "$PROJECT" T-010u build "$TASK_CWD" "$ALLOW"
rm -f "$TASK_CWD/preexisting.tmp"
printf x > "$TASK_CWD/.ignored-outside"
expect_exit 74 'cx preflight rifiuta ignored preesistente' \
  env PATH="$FAKE_BIN:$PATH" "$CX" gpt-5.6-sol low "$PROJECT" T-010ig build "$TASK_CWD" "$ALLOW"
rm -f "$TASK_CWD/.ignored-outside"
git -C "$TASK_CWD" update-index --assume-unchanged outside.txt
expect_exit 74 'cx preflight rifiuta assume-unchanged' \
  env PATH="$FAKE_BIN:$PATH" "$CX" gpt-5.6-sol low "$PROJECT" T-010a build "$TASK_CWD" "$ALLOW"
git -C "$TASK_CWD" update-index --no-assume-unchanged outside.txt
git -C "$TASK_CWD" update-index --skip-worktree outside.txt
expect_exit 74 'cx preflight rifiuta skip-worktree/sparse' \
  env PATH="$FAKE_BIN:$PATH" "$CX" gpt-5.6-sol low "$PROJECT" T-010sk build "$TASK_CWD" "$ALLOW"
git -C "$TASK_CWD" update-index --no-skip-worktree outside.txt

# Il post-gate copre working tree, index, commit e ignored dentro la stessa allowlist.
expect_exit 0 'cx build consente tracked unstaged dentro ownership' \
  env PATH="$FAKE_BIN:$PATH" FAKE_TOUCH=README.md "$CX" gpt-5.6-sol low "$PROJECT" T-010w build "$TASK_CWD" "$ALLOW"
git -C "$TASK_CWD" checkout -q -- README.md
expect_exit 0 'cx build consente staged dentro ownership' \
  env PATH="$FAKE_BIN:$PATH" FAKE_STAGE=README.md "$CX" gpt-5.6-sol low "$PROJECT" T-010x build "$TASK_CWD" "$ALLOW"
git -C "$TASK_CWD" checkout -q HEAD -- README.md
expect_exit 0 'cx build consente commit dentro ownership' \
  env PATH="$FAKE_BIN:$PATH" FAKE_COMMIT=README.md "$CX" gpt-5.6-sol low "$PROJECT" T-010y build "$TASK_CWD" "$ALLOW"
git -C "$TASK_CWD" reset -q --hard HEAD~1
expect_exit 0 'cx build consente untracked dentro ownership' \
  env PATH="$FAKE_BIN:$PATH" FAKE_TOUCH=allowed.tmp "$CX" gpt-5.6-sol low "$PROJECT" T-010un build "$TASK_CWD" '["allowed.tmp"]'
rm -f "$TASK_CWD/allowed.tmp"
expect_exit 0 'cx build consente ignored creato dentro ownership' \
  env PATH="$FAKE_BIN:$PATH" FAKE_TOUCH=.ignored-outside "$CX" gpt-5.6-sol low "$PROJECT" T-010z build "$TASK_CWD" '[".ignored-outside"]'
rm -f "$TASK_CWD/.ignored-outside"

expect_exit 74 'cx post-gate blocca commit cacheinfo fuori ownership' \
  env PATH="$FAKE_BIN:$PATH" FAKE_CACHEINFO_OUTSIDE=outside.txt "$CX" gpt-5.6-sol low "$PROJECT" T-010ci build "$TASK_CWD" "$ALLOW"
git -C "$TASK_CWD" reset -q --hard HEAD~1
TASK_HEAD="$(git -C "$TASK_CWD" rev-parse HEAD)"
git -C "$TASK_CWD" update-index --add --cacheinfo 160000,"$TASK_HEAD",fake-submodule
expect_exit 74 'cx preflight rifiuta gitlink/submodule' \
  env PATH="$FAKE_BIN:$PATH" "$CX" gpt-5.6-sol low "$PROJECT" T-010sm build "$TASK_CWD" "$ALLOW"
git -C "$TASK_CWD" read-tree HEAD
ln -s README.md "$TASK_CWD/preexisting-link"
git -C "$TASK_CWD" add preexisting-link
git -C "$TASK_CWD" commit -qm symlink-fixture
expect_exit 74 'cx preflight rifiuta symlink tracked' \
  env PATH="$FAKE_BIN:$PATH" "$CX" gpt-5.6-sol low "$PROJECT" T-010sl build "$TASK_CWD" '["preexisting-link"]'
git -C "$TASK_CWD" reset -q --hard HEAD~1
expect_exit 74 'cx post-gate rifiuta symlink creato dal worker' \
  env PATH="$FAKE_BIN:$PATH" FAKE_SYMLINK=allowed-link "$CX" gpt-5.6-sol low "$PROJECT" T-010sn build "$TASK_CWD" '["allowed-link"]'
rm -f "$TASK_CWD/allowed-link"

printf 'dirty-before\n' > "$PROJECT/control.txt"
expect_exit 74 'cx rileva cambio contenuto del control plane gia dirty' \
  env PATH="$FAKE_BIN:$PATH" FAKE_CONTROL_TOUCH=dirty-after "$CX" gpt-5.6-sol low "$PROJECT" T-010c build "$TASK_CWD" "$ALLOW"

TAMPERED="$TMP/tampered-plugin"; mkdir -p "$TAMPERED/hooks" "$TAMPERED/controller"
cp "$ROOT/hooks/hooks.json" "$ROOT/hooks/guard-run.sh" "$ROOT/hooks/guard_run.py" "$ROOT/hooks/guard-write.py" "$ROOT/hooks/session-run-state.sh" "$TAMPERED/hooks/"
cp "$ROOT/controller/path_policy.py" "$TAMPERED/controller/"
printf '\n# tampered\n' >> "$TAMPERED/hooks/guard-run.sh"
expect_exit 69 'cx preflight rifiuta hook installato di contenuto diverso' \
  env PATH="$FAKE_BIN:$PATH" FAKE_PLUGIN_ROOT="$TAMPERED" "$CX" gpt-5.6-sol low "$PROJECT" T-010h build "$TASK_CWD" "$ALLOW"
cp "$ROOT/hooks/guard-run.sh" "$TAMPERED/hooks/guard-run.sh"
printf '\n# tampered session hook\n' >> "$TAMPERED/hooks/session-run-state.sh"
expect_exit 69 'cx preflight attesta anche session-run-state.sh dal manifest' \
  env PATH="$FAKE_BIN:$PATH" FAKE_PLUGIN_ROOT="$TAMPERED" "$CX" gpt-5.6-sol low "$PROJECT" T-010s build "$TASK_CWD" "$ALLOW"

{
  printf '%s\n' '#!/usr/bin/env bash' \
    'if [ "${1:-}" = plugin ] && [ "${2:-}" = list ] && [ "${3:-}" = --json ]; then'
  printf '  root="${FAKE_PLUGIN_ROOT:-%s}"\n' "$ROOT"
  printf '  printf '\''[{"id":"orchestratore@orchestratore","enabled":true,"installPath":"%%s"}]\\n'\'' "$root"; exit 0\n'
  printf '%s\n' 'fi' 'if [ "${1:-}" = -p ]; then cat >/dev/null; exit 0; fi' 'exit 64'
} > "$FAKE_BIN/claude"
chmod +x "$FAKE_BIN/claude"
expect_exit 0 'cc execute usa effort e guard con worktree pulito' \
  env PATH="$FAKE_BIN:$PATH" "$CC" sonnet medium "$PROJECT" T-011 review "$TASK_CWD" "$ALLOW"
[ -s "$PROJECT/.orchestratore/logs/T-011.review.log" ] && ok 'cc execute conserva il log stage-specific' || ko 'cc execute conserva il log stage-specific'
expect_exit 69 'cc preflight rifiuta hook installato di contenuto diverso' \
  env PATH="$FAKE_BIN:$PATH" FAKE_PLUGIN_ROOT="$TAMPERED" "$CC" sonnet medium "$PROJECT" T-011h review "$TASK_CWD" "$ALLOW"

[ "$failures" -eq 0 ] || { printf 'ROSSO: %d controlli bridge falliti\n' "$failures"; exit 1; }
printf 'VERDE: bridge conformi\n'
