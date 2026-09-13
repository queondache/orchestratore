#!/usr/bin/env bash
# Gate eseguibile degli hook dell'orchestratore. Nessun comando reale viene eseguito:
# si alimenta guard-run.sh con payload JSON e si controlla solo l'exit code.
set -uo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)"
GUARD="$ROOT/hooks/guard-run.sh"
SESS="$ROOT/hooks/session-run-state.sh"
HOOKS_JSON="$ROOT/hooks/hooks.json"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/orchestratore-hooks.XXXXXX")"
cleanup() { [ -n "${TMP:-}" ] && [ -d "$TMP" ] && command rm -r -f -- "$TMP"; }
trap cleanup EXIT

CON_RUN="$TMP/con-run"
SENZA_RUN="$TMP/senza-run"
mkdir -p "$CON_RUN/.orchestratore" "$SENZA_RUN"
printf 'runtime=cc pid=1 session=test updated=ora\n' > "$CON_RUN/.orchestratore/brain.lock"

failures=0
ok() { printf 'OK: %s\n' "$1"; }
ko() { printf 'KO: %s\n' "$1"; failures=$((failures + 1)); }

payload() { # payload <cwd> <comando>
  python3 -c '
import json, sys
print(json.dumps({"tool_name": "Bash", "cwd": sys.argv[1], "tool_input": {"command": sys.argv[2]}}))
' "$1" "$2"
}

payload_con_descrizione() { # payload_con_descrizione <cwd> <comando> <descrizione>
  python3 -c '
import json, sys
print(json.dumps({"tool_name": "Bash", "cwd": sys.argv[1],
                  "tool_input": {"command": sys.argv[2], "description": sys.argv[3]}}))
' "$1" "$2" "$3"
}

expect_guard() { # expect_guard <atteso> <cwd> <comando> <label>
  local want="$1" cwd="$2" cmd="$3" label="$4" body
  body="$(payload "$cwd" "$cmd")"
  printf '%s' "$body" | "$GUARD" >/dev/null 2>&1
  local got=${PIPESTATUS[1]}
  if [ "$got" = "$want" ]; then ok "$label (exit $got)"; else ko "$label (atteso $want, ottenuto $got)"; fi
}

[ -x "$GUARD" ] && ok "guard-run.sh eseguibile" || ko "guard-run.sh eseguibile"
[ -x "$SESS" ] && ok "session-run-state.sh eseguibile" || ko "session-run-state.sh eseguibile"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert 'PreToolUse' in d['hooks'] and 'SessionStart' in d['hooks']" "$HOOKS_JSON" \
  && ok "hooks.json dichiara PreToolUse e SessionStart" || ko "hooks.json dichiara PreToolUse e SessionStart"
grep -q 'CLAUDE_PLUGIN_ROOT' "$HOOKS_JSON" && ok "hooks.json usa CLAUDE_PLUGIN_ROOT" || ko "hooks.json usa CLAUDE_PLUGIN_ROOT"

# Con run attivo: i comandi vietati dalla skill vengono bloccati (exit 2)
expect_guard 2 "$CON_RUN" 'git push --force origin main' "blocca il force-push"
expect_guard 2 "$CON_RUN" 'git push --force-with-lease' "blocca il force-with-lease"
expect_guard 2 "$CON_RUN" 'git push -f origin main' "blocca il force-push con -f e argomenti"
expect_guard 2 "$CON_RUN" 'git push -f' "blocca il force-push corto, -f in fondo alla riga"
expect_guard 2 "$CON_RUN" 'cd sub && git push -f' "blocca il force-push corto in un comando composto"

# Bypass per sottostringa non ancorata: la forma canonica non e' l'unica forma.
expect_guard 2 "$CON_RUN" 'git  push  -f' "blocca il force-push con spazi multipli"
expect_guard 2 "$CON_RUN" "$(printf 'git\tpush\t-f')" "blocca il force-push separato da tabulazioni"
expect_guard 2 "$CON_RUN" 'git push origin +main' "blocca la refspec forzata col +, senza flag"
expect_guard 2 "$CON_RUN" 'git push origin +refs/heads/main:main' "blocca la refspec forzata esplicita"
expect_guard 2 "$CON_RUN" 'git -c core.pager=cat push --force origin main' "blocca il push forzato con opzioni prima di push"
expect_guard 2 "$CON_RUN" 'git -c a=b push -f' "blocca il push forzato corto con opzioni prima di push"
expect_guard 2 "$CON_RUN" 'git push -uf origin main' "blocca i flag corti combinati"
expect_guard 2 "$CON_RUN" '/usr/bin/git push -f' "blocca git invocato per path assoluto"
expect_guard 2 "$CON_RUN" 'git reset  --hard HEAD~1' "blocca il reset distruttivo con spazi multipli"
expect_guard 2 "$CON_RUN" 'git branch  -D vecchia' "blocca la cancellazione di branch con spazi multipli"
expect_guard 2 "$CON_RUN" 'rm -r -f build' "blocca la cancellazione ricorsiva con flag separati"
expect_guard 2 "$CON_RUN" '(cd sub && git push -f)' "blocca il force-push dentro una subshell"
expect_guard 2 "$CON_RUN" 'git push origin +HEAD:main' "blocca la refspec forzata su HEAD"
expect_guard 2 "$CON_RUN" 'git push -fu origin feat/a' "blocca i flag corti combinati invertiti"
expect_guard 2 "$CON_RUN" 'git -c http.sslVerify=false push --force origin main' "blocca git -c minuscolo prima di push"
expect_guard 2 "$CON_RUN" 'git push --delete origin vecchia' "blocca la cancellazione di branch remoto"
expect_guard 2 "$CON_RUN" 'git push origin :vecchia' "blocca la cancellazione remota con refspec vuota"

# Attacco avversariale: forme che un worker puo' scrivere per fretta.
expect_guard 2 "$CON_RUN" '(git push -f)' "blocca il push forzato in una subshell senza cd"
expect_guard 2 "$CON_RUN" 'echo $(git push -f origin main)' "blocca il push forzato in una sostituzione di comando"
expect_guard 2 "$CON_RUN" 'eval "git push -f origin main"' "blocca il push forzato dentro eval"
expect_guard 2 "$CON_RUN" "sh -c 'git push --force origin main'" "blocca il push forzato dentro sh -c"
expect_guard 2 "$CON_RUN" 'git push "-f" origin main' "blocca il flag quotato"
expect_guard 2 "$CON_RUN" 'git push --force-with-l origin main' "blocca il prefisso univoco del flag lungo"
expect_guard 2 "$CON_RUN" 'git push -d origin vecchia' "blocca la cancellazione remota col flag corto"
expect_guard 2 "$CON_RUN" 'git push --del origin vecchia' "blocca la cancellazione remota col prefisso"
expect_guard 2 "$CON_RUN" 'git push --mirror origin' "blocca il push a specchio"
expect_guard 2 "$CON_RUN" 'git push --prune origin' "blocca il push con prune"
expect_guard 2 "$CON_RUN" 'git -c remote.origin.push=+refs/heads/main:refs/heads/main push origin' "blocca la refspec forzata nella configurazione"
expect_guard 2 "$CON_RUN" '\\git push -f origin main' "blocca git con backslash davanti"
expect_guard 2 "$CON_RUN" 'rm -Rf build' "blocca la cancellazione ricorsiva con R maiuscola"
expect_guard 2 "$CON_RUN" 'rm -r --force build' "blocca la cancellazione ricorsiva con flag lungo separato"
expect_guard 2 "$CON_RUN" 'rm --recursive -f build' "blocca la cancellazione con flag lungo e corto"
expect_guard 2 "$CON_RUN" 'find build -delete' "blocca find -delete"
expect_guard 2 "$CON_RUN" 'find . -name pippo -exec rm -f {} +' "blocca find con exec rm"
expect_guard 2 "$CON_RUN" 'git clean -xfd' "blocca il clean con flag combinati"
expect_guard 2 "$CON_RUN" 'git clean -f -d' "blocca il clean con flag separati"
expect_guard 2 "$CON_RUN" 'git reset -q --hard HEAD~1' "blocca il reset distruttivo con opzioni prima"
expect_guard 2 "$CON_RUN" 'git reset --quiet --har HEAD~1' "blocca il reset col prefisso del flag"
expect_guard 2 "$CON_RUN" 'git branch -fD vecchia' "blocca la cancellazione forzata con flag combinati"
expect_guard 2 "$CON_RUN" 'git branch --delete --force vecchia' "blocca la cancellazione forzata con flag lunghi"
expect_guard 2 "$CON_RUN" 'gh api -X DELETE repos/o/r/git/refs/heads/x' "blocca la cancellazione via API GitHub"
expect_guard 2 "$CON_RUN" 'git reset --hard HEAD~3' "blocca il reset --hard"
expect_guard 2 "$CON_RUN" 'git clean -fdx' "blocca il clean distruttivo"
expect_guard 2 "$CON_RUN" 'git branch -D m/vecchia' "blocca la cancellazione di branch"
expect_guard 2 "$CON_RUN" 'gh pr merge 12 --squash --admin' "blocca il merge che scavalca i check"
expect_guard 2 "$CON_RUN" 'rm -rf build' "blocca la cancellazione ricorsiva forzata"

# Con run attivo: il lavoro normale passa
expect_guard 0 "$CON_RUN" 'git status --short' "lascia passare git status"
expect_guard 0 "$CON_RUN" 'git push origin m/nuova' "lascia passare un push normale"
expect_guard 0 "$CON_RUN" 'gh pr merge 12 --squash' "lascia passare il merge al gate"
expect_guard 0 "$CON_RUN" 'npm test' "lascia passare la suite"
expect_guard 0 "$CON_RUN" 'grep -f pattern.txt src/app.ts' "lascia passare grep -f, che non e un push"
expect_guard 0 "$CON_RUN" 'git push origin feat/a && rm -f /tmp/lock.pid' "lascia passare push seguito da rm -f di un file"
expect_guard 0 "$CON_RUN" 'git add -f vendor/lib.js && git commit -m x && git push origin feat/a' "lascia passare add -f seguito da push normale"
expect_guard 0 "$CON_RUN" 'npm install --force && git push origin feat/a' "lascia passare npm install --force con push normale"
expect_guard 0 "$CON_RUN" 'grep -rn pushState src/ | sed -f script.sed' "lascia passare pushState con sed -f, nessun git push"
expect_guard 0 "$CON_RUN" 'git push origin HEAD && curl -sS -f -o out.json https://esempio' "lascia passare push seguito da curl -f"
expect_guard 0 "$CON_RUN" 'git push origin main; ls -f' "lascia passare push seguito da ls -f"
expect_guard 0 "$CON_RUN" 'git push origin feature+x' "lascia passare un branch col + dentro il nome"
expect_guard 0 "$CON_RUN" 'echo "+main" > nota.txt' "lascia passare un + fuori da un push"
expect_guard 0 "$CON_RUN" 'git push --set-upstream origin feat/a' "lascia passare set-upstream"
expect_guard 0 "$CON_RUN" 'rm -f /tmp/lock.pid' "lascia passare la rimozione di un singolo file"
expect_guard 0 "$CON_RUN" 'git push origin feat/a && gh pr merge 3 --squash --delete-branch' "lascia passare push e merge con pulizia del branch"
expect_guard 0 "$CON_RUN" 'git push origin feat/a && git branch --delete old-local' "lascia passare la cancellazione non forzata di un branch locale"
expect_guard 0 "$CON_RUN" 'git tag -f v1.0 && git push origin --tags' "lascia passare tag forzato locale e push dei tag"
expect_guard 0 "$CON_RUN" 'git push -u origin feat/m2 && gh pr create --fill --base main' "lascia passare push e apertura PR"
expect_guard 0 "$CON_RUN" 'printf %s >> lessons.md' "lascia passare la scrittura di lessons"
expect_guard 0 "$CON_RUN" 'git commit -m "fix: la guardia blocca git push -f nel run"' "lascia passare un commit che nomina il comando vietato"
expect_guard 0 "$CON_RUN" "printf '%%s' 'mai git push -f dentro un run' >> lessons.md" "lascia passare una lezione che nomina il comando vietato"
expect_guard 0 "$CON_RUN" 'echo "regola: git push origin :branch e vietato" >> SPEC.md' "lascia passare una regola scritta nella SPEC"
expect_guard 0 "$CON_RUN" 'git push origin feat/a # non usare mai -f qui' "lascia passare un commento dopo il comando"
expect_guard 0 "$CON_RUN" 'git branch -d vecchia' "lascia passare la cancellazione non forzata di un branch"
expect_guard 0 "$CON_RUN" 'git clean -n' "lascia passare il clean in sola simulazione"
expect_guard 0 "$CON_RUN" 'rm -r build' "lascia passare una rimozione ricorsiva non forzata"
expect_guard 0 "$CON_RUN" 'git push origin HEAD:refs/heads/main' "lascia passare una refspec normale"
expect_guard 0 "$CON_RUN" 'gh pr merge 3 --squash' "lascia passare il merge al gate"

# Senza run attivo: l'hook non interferisce mai
expect_guard 0 "$SENZA_RUN" 'git push --force origin main' "fuori da un run non blocca nulla"
expect_guard 0 "$SENZA_RUN" 'git reset --hard HEAD~1' "fuori da un run non blocca il reset"

# Payload malformato: il lavoro normale passa, ma il distruttivo non si infila
# approfittando di un parser che non ha capito niente.
printf 'non json' | "$GUARD" >/dev/null 2>&1
[ $? = 0 ] && ok "payload malformato non blocca il lavoro normale" || ko "payload malformato non blocca il lavoro normale"

# Senza python3 il guardrail non deve spegnersi in silenzio: cade sul testo grezzo.
SENZA_PY="$TMP/bin-vuoto"
mkdir -p "$SENZA_PY"
for c in sh bash cat printf grep sed; do
  src="$(command -v "$c" 2>/dev/null)"
  [ -n "$src" ] && ln -sf "$src" "$SENZA_PY/$c"
done
BODY_FORZA="$(payload "$CON_RUN" 'git push --force origin main')"
BODY_SANO="$(payload "$CON_RUN" 'git status --short')"
# Senza parser non si puo' leggere il campo cwd: vale la directory del processo,
# che nella sessione reale e' proprio quella del progetto. Il test la riproduce.
( cd "$CON_RUN" && printf '%s' "$BODY_FORZA" | env PATH="$SENZA_PY" "$GUARD" >/dev/null 2>&1; exit "${PIPESTATUS[1]}" )
[ $? = 2 ] && ok "senza python3 blocca comunque il force-push" || ko "senza python3 blocca comunque il force-push"
( cd "$CON_RUN" && printf '%s' "$BODY_SANO" | env PATH="$SENZA_PY" "$GUARD" >/dev/null 2>&1; exit "${PIPESTATUS[1]}" )
[ $? = 0 ] && ok "senza python3 lascia passare il lavoro normale" || ko "senza python3 lascia passare il lavoro normale"
BODY_CORTO="$(payload "$CON_RUN" 'git push -f')"
( cd "$CON_RUN" && printf '%s' "$BODY_CORTO" | env PATH="$SENZA_PY" "$GUARD" >/dev/null 2>&1; exit "${PIPESTATUS[1]}" )
[ $? = 2 ] && ok "senza python3 blocca anche il force-push corto" || ko "senza python3 blocca anche il force-push corto"
BODY_DESCR="$(payload_con_descrizione "$CON_RUN" 'npm test' 'ricorda: mai usare git reset --hard qui')"
( cd "$CON_RUN" && printf '%s' "$BODY_DESCR" | env PATH="$SENZA_PY" "$GUARD" >/dev/null 2>&1; exit "${PIPESTATUS[1]}" )
[ $? = 0 ] && ok "senza python3 ignora la descrizione e guarda solo il comando" || ko "senza python3 ignora la descrizione e guarda solo il comando"
( cd "$SENZA_RUN" && printf '%s' "$BODY_FORZA" | env PATH="$SENZA_PY" "$GUARD" >/dev/null 2>&1; exit "${PIPESTATUS[1]}" )
[ $? = 0 ] && ok "senza python3 e senza run non interferisce" || ko "senza python3 e senza run non interferisce"

# SessionStart: silenzioso senza run, informativo con run.
# Niente pipe verso grep -q: con pipefail il SIGPIPE falserebbe l'esito.
OUT_SENZA="$( cd "$SENZA_RUN" && "$SESS" )"
[ -z "$OUT_SENZA" ] && ok "session hook silenzioso senza run" || ko "session hook silenzioso senza run"
printf 'stato: attivo\ncervello: cc-fable\n' > "$CON_RUN/.orchestratore/run.md"
OUT_CON="$( cd "$CON_RUN" && "$SESS" )"
case "$OUT_CON" in *"stato: attivo"*) ok "session hook riporta lo stato del run" ;; *) ko "session hook riporta lo stato del run" ;; esac
case "$OUT_CON" in *"brain.lock"*) ok "session hook segnala il lock" ;; *) ko "session hook segnala il lock" ;; esac

if [ "$failures" -gt 0 ]; then printf 'ROSSO: %d controlli hook falliti\n' "$failures"; exit 1; fi
printf 'VERDE: hook conformi\n'
