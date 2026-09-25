#!/usr/bin/env bash
# Gate eseguibile degli hook dell'orchestratore. Nessun comando reale viene eseguito:
# si alimenta guard-run.sh con payload JSON e si controlla solo l'exit code.
set -uo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)"
GUARD="$ROOT/hooks/guard-run.sh"
WRITE_GUARD="$ROOT/hooks/guard-write.py"
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
[ -x "$WRITE_GUARD" ] && ok "guard-write.py eseguibile" || ko "guard-write.py eseguibile"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert 'PreToolUse' in d['hooks'] and 'SessionStart' in d['hooks']" "$HOOKS_JSON" \
  && ok "hooks.json dichiara PreToolUse e SessionStart" || ko "hooks.json dichiara PreToolUse e SessionStart"
grep -q 'CLAUDE_PLUGIN_ROOT' "$HOOKS_JSON" && ok "hooks.json usa CLAUDE_PLUGIN_ROOT" || ko "hooks.json usa CLAUDE_PLUGIN_ROOT"
grep -q 'Write|Edit|NotebookEdit|apply_patch' "$HOOKS_JSON" && ok "hooks.json registra il guardrail sui tool di scrittura" || ko "hooks.json registra il guardrail sui tool di scrittura"

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

# Nei processi worker il controller conserva push e merge fuori dal bridge.
BODY_PUSH="$(payload "$CON_RUN" 'git push origin feat/a')"
printf '%s' "$BODY_PUSH" | env ORCHESTRATORE_STAGE=build "$GUARD" >/dev/null 2>&1
[ "${PIPESTATUS[1]}" = 2 ] && ok "worker non puo fare push" || ko "worker non puo fare push"
BODY_MERGE="$(payload "$CON_RUN" 'gh pr merge 3 --squash')"
printf '%s' "$BODY_MERGE" | env ORCHESTRATORE_STAGE=finalize "$GUARD" >/dev/null 2>&1
[ "${PIPESTATUS[1]}" = 2 ] && ok "worker blocca ogni gh, incluso merge" || ko "worker blocca ogni gh, incluso merge"
BODY_MERGE_GLOBAL="$(payload "$CON_RUN" 'gh --repo o/r pr merge 3 --squash')"
printf '%s' "$BODY_MERGE_GLOBAL" | env ORCHESTRATORE_STAGE=build "$GUARD" >/dev/null 2>&1
[ "${PIPESTATUS[1]}" = 2 ] && ok "worker non aggira il blocco merge con opzioni globali gh" || ko "worker non aggira il blocco merge con opzioni globali gh"

# I worker non parlano direttamente con GitHub o endpoint remoti: il controller e'
# l'unico owner di query, PR e merge. Pochi casi rappresentativi difendono il confine.
for REMOTE_CMD in \
  'gh pr view 3' \
  'gh api --method GET repos/o/r/pulls/3' \
  'gh issue create --title x --body y' \
  'curl -fsS https://example.invalid/status' \
  'curl --data x=1 https://example.invalid/hook'
do
  BODY_REMOTE="$(payload "$CON_RUN" "$REMOTE_CMD")"
  printf '%s' "$BODY_REMOTE" | env ORCHESTRATORE_STAGE=review "$GUARD" >/dev/null 2>&1
  [ "${PIPESTATUS[1]}" = 2 ] && ok "worker blocca comando remoto: $REMOTE_CMD" || ko "worker blocca comando remoto: $REMOTE_CMD"
done
BODY_BUILD_CURL="$(payload "$CON_RUN" 'curl -I https://example.invalid/status')"
printf '%s' "$BODY_BUILD_CURL" | env ORCHESTRATORE_STAGE=build "$GUARD" >/dev/null 2>&1
[ "${PIPESTATUS[1]}" = 2 ] && ok "build blocca curl come ogni worker" || ko "build blocca curl come ogni worker"

# Tool Write/Edit/NotebookEdit: review sempre read-only; build confinato a worktree e allowlist.
WRITE_OK="$(python3 -c 'import json; print(json.dumps({"tool_name":"Write","tool_input":{"file_path":"src/ok.py"}}))')"
WRITE_NO="$(python3 -c 'import json; print(json.dumps({"tool_name":"Write","tool_input":{"file_path":"secrets.txt"}}))')"
printf '%s' "$WRITE_OK" | env ORCHESTRATORE_STAGE=review ORCHESTRATORE_TASK_CWD="$CON_RUN" ORCHESTRATORE_ALLOWLIST_JSON='["src/**"]' "$WRITE_GUARD" >/dev/null 2>&1
[ "${PIPESTATUS[1]}" = 2 ] && ok "review blocca Write" || ko "review blocca Write"
NOTEBOOK_NO="$(python3 -c 'import json; print(json.dumps({"tool_name":"NotebookEdit","tool_input":{"notebook_path":"notes.ipynb"}}))')"
printf '%s' "$NOTEBOOK_NO" | env ORCHESTRATORE_STAGE=strategy ORCHESTRATORE_TASK_CWD="$CON_RUN" ORCHESTRATORE_ALLOWLIST_JSON='["**"]' "$WRITE_GUARD" >/dev/null 2>&1
[ "${PIPESTATUS[1]}" = 2 ] && ok "strategy blocca NotebookEdit" || ko "strategy blocca NotebookEdit"
printf '%s' "$WRITE_OK" | env ORCHESTRATORE_STAGE=build ORCHESTRATORE_TASK_CWD="$CON_RUN" ORCHESTRATORE_ALLOWLIST_JSON='["src/**"]' "$WRITE_GUARD" >/dev/null 2>&1
[ "${PIPESTATUS[1]}" = 0 ] && ok "build consente Write in ownership" || ko "build consente Write in ownership"
printf '%s' "$WRITE_NO" | env ORCHESTRATORE_STAGE=build ORCHESTRATORE_TASK_CWD="$CON_RUN" ORCHESTRATORE_ALLOWLIST_JSON='["src/**"]' "$WRITE_GUARD" >/dev/null 2>&1
[ "${PIPESTATUS[1]}" = 2 ] && ok "build blocca Write fuori ownership" || ko "build blocca Write fuori ownership"

# Quinto giro di verifica: bypass non deliberati che passavano.
expect_guard 2 "$CON_RUN" 'echo build | xargs -0 rm -rf' 'blocca la cancellazione passata a xargs con flag'
expect_guard 2 "$CON_RUN" 'sudo -E git push -f origin main' 'blocca il force-push sotto sudo con opzione'
expect_guard 2 "$CON_RUN" 'nice -n 10 git push -f origin main' 'blocca il force-push sotto nice, che porta un valore separato'
expect_guard 2 "$CON_RUN" 'timeout -s KILL 30 git push -f origin main' 'blocca il force-push sotto timeout con segnale e durata'
expect_guard 2 "$CON_RUN" 'bash -lc '\''git push --force origin main'\''' 'blocca il force-push dentro bash -lc'
expect_guard 2 "$CON_RUN" 'exec git push -f origin main' 'blocca il force-push passato a exec'
expect_guard 2 "$CON_RUN" 'for b in a b; do git push -f origin $b; done' 'blocca il force-push dentro un ciclo for'
expect_guard 2 "$CON_RUN" 'git push -f origin main &' 'blocca il force-push mandato in background con &'
expect_guard 2 "$CON_RUN" 'git reset --ha HEAD~1' 'blocca il reset con l abbreviazione --ha che git accetta'
expect_guard 2 "$CON_RUN" 'git push --de origin vecchia' 'blocca la cancellazione remota con l abbreviazione --de'
expect_guard 2 "$CON_RUN" 'gh api -XDELETE repos/o/r/git/refs/heads/x' 'blocca la cancellazione via API col metodo attaccato al flag'
expect_guard 2 "$CON_RUN" 'git -C "a b" push -f' 'blocca il force-push con -C e una directory che contiene uno spazio'

# Quinto giro di verifica: lavoro legittimo che veniva bloccato.
expect_guard 0 "$CON_RUN" 'git commit -m "$(cat <<'\''EOF'\''
fix: ogni regola della guardia vale sul segmento, non sulla riga intera

Casi legittimi che finivano bloccati:
- git push origin feat/a && gh pr merge 3 --squash --delete-branch
- git push origin feat/a && git branch --delete old-local

Ora reset --hard, clean distruttivo e cancellazione di branch si cercano solo nel
segmento che li contiene davvero.
EOF
)"' 'lascia passare un commit reale del branch che elenca comandi vietati'
expect_guard 0 "$CON_RUN" 'git commit -m "$(cat <<'\''EOF'\''
fix(security): la guardia riconosce il force-push per token

Bypass trovati dalla review:
- spazi multipli (git  push  -f);
- refspec forzata senza flag: git push origin +main;
- flag corti combinati: git push -uf origin main.
EOF
)"' 'lascia passare un commit reale che elenca i bypass trovati'
expect_guard 0 "$CON_RUN" 'cat >> lessons.md <<'\''EOF'\''
- Mai `git push -f` dentro un run: il gate lo blocca e chiama Andrea.
- `git reset --hard HEAD~1` e `rm -rf build` valgono come distruttivi.
EOF' 'lascia passare una lezione in heredoc che nomina i comandi vietati'
expect_guard 0 "$CON_RUN" 'cat >> SPEC.md <<'\''EOF'\''
I7: durante un run sono vietati `git push --force`, `git push --delete` e `rm -rf`.
EOF' 'lascia passare una regola della SPEC scritta in heredoc'
expect_guard 0 "$CON_RUN" 'gh pr create --title "guardia" --body "vieta git push -f e git reset --hard durante il run"' 'lascia passare l apertura di una PR che descrive i comandi vietati'
expect_guard 0 "$CON_RUN" 'gh pr comment 1 --body "il gate ora blocca git push -f e rm -rf build"' 'lascia passare un commento di PR che nomina i comandi vietati'
expect_guard 0 "$CON_RUN" 'cat >> lessons.md <<'\''EOF'\''
Esempio di comando vietato durante un run:
    git push -f origin main
Il gate lo blocca e chiama Andrea.
EOF' 'lascia passare un esempio di comando vietato scritto a inizio riga in lessons'
expect_guard 0 "$CON_RUN" 'cat >> docs/gate.md <<'\''EOF'\''
git reset --hard HEAD~1
rm -rf build
EOF' 'lascia passare un blocco di esempi vietati scritto in un documento'

# L'a capo separa due comandi come il punto e virgola.
expect_guard 2 "$CON_RUN" 'git status --short
git push -f origin main' 'blocca il force-push su una riga successiva'
expect_guard 2 "$CON_RUN" 'npm test
npm run build
git push --force origin main' 'blocca il force-push in fondo a un comando di piu righe'
expect_guard 2 "$CON_RUN" 'cd sub
rm -rf build' 'blocca la cancellazione ricorsiva su una riga successiva'
expect_guard 0 "$CON_RUN" 'git commit -m "riga uno
riga due che nomina git push -f"
git push origin feat/a' 'lascia passare un messaggio di commit su piu righe che nomina il comando vietato'

# Sonda avversariale sull'analizzatore: apici inversi, continuazioni, wrapper.
expect_guard 2 "$CON_RUN" 'echo `git push -f origin main`' 'blocca il force-push dentro apici inversi'
expect_guard 2 "$CON_RUN" 'git \
  push -f origin main' 'blocca il force-push spezzato da una continuazione di riga'
expect_guard 2 "$CON_RUN" 'env -i git push -f' 'blocca il force-push sotto env -i, che non porta un valore'
expect_guard 2 "$CON_RUN" 'gh api --method DELETE repos/o/r/git/refs/heads/x' 'blocca la cancellazione via API col metodo per flag lungo'
expect_guard 2 "$CON_RUN" '{ git push -f origin main; }' 'blocca il force-push dentro un gruppo di comandi'
expect_guard 2 "$CON_RUN" 'if true; then git push -f; fi' 'blocca il force-push dentro un if'
expect_guard 2 "$CON_RUN" 'git push -f origin main 2>/dev/null' 'blocca il force-push con la diagnostica rediretta'
expect_guard 2 "$CON_RUN" 'command git push -f' 'blocca il force-push invocato con command'
expect_guard 2 "$CON_RUN" 'PATH=/x git push -f' 'blocca il force-push preceduto da un assegnazione'
expect_guard 0 "$CON_RUN" 'HASH=`git rev-parse HEAD` && echo $HASH' 'lascia passare una sostituzione in apici inversi che non e vietata'
expect_guard 0 "$CON_RUN" 'git stash push -u' 'lascia passare stash push, che non e il push di git'
expect_guard 0 "$CON_RUN" 'python3 -c "print('\''git push -f'\'')"' 'lascia passare un programma che stampa il comando vietato'
expect_guard 0 "$CON_RUN" 'rsync -a --delete src/ dst/' 'lascia passare rsync --delete, che non e un comando di git'
expect_guard 0 "$CON_RUN" 'echo '\''niente rm -rf qui'\'' >> note.md' 'lascia passare una nota che nomina la cancellazione ricorsiva'

# Copertura delle tabelle dell'analizzatore: wrapper, shell, parole chiave e opzioni che
# portano un valore. Il generatore fallisce se una voce non ha un comando che la esercita,
# cosi' nessun pezzo resta senza oracolo.
COPERTURA="$(python3 "$SCRIPT_DIR/copertura-tabelle.py")"
if [ $? = 0 ] && [ -n "$COPERTURA" ]; then
  ok "ogni voce delle tabelle dell analizzatore ha un oracolo"
  while IFS=$'\t' read -r atteso comando etichetta; do
    [ -n "$comando" ] || continue
    expect_guard "$atteso" "$CON_RUN" "$comando" "$etichetta"
  done <<< "$COPERTURA"
else
  ko "ogni voce delle tabelle dell analizzatore ha un oracolo"
fi


# Riserve del sesto giro di verifica: commenti che si mangiavano l'a capo,
# opzioni dei wrapper lette senza guardare di quale wrapper fossero, sostituzioni
# dentro le virgolette, clean forzato senza -d.
expect_guard 2 "$CON_RUN" 'git status # nota
git push -f origin main' 'blocca il force-push dopo una riga che finisce con un commento'
expect_guard 2 "$CON_RUN" 'git status # nota
rm -rf build' 'blocca la cancellazione dopo una riga che finisce con un commento'
expect_guard 2 "$CON_RUN" 'echo ok # x
gh pr merge 1 --admin' 'blocca il merge amministrativo dopo una riga con commento'
expect_guard 2 "$CON_RUN" 'sudo -n git push -f origin main' 'blocca il force-push con sudo -n, che non porta un valore'
expect_guard 2 "$CON_RUN" 'timeout 1.5 git push -f origin main' 'blocca il force-push con timeout a durata frazionaria'
expect_guard 2 "$CON_RUN" 'timeout .5 git push -f origin main' 'blocca il force-push con timeout a durata sotto l unita'
expect_guard 2 "$CON_RUN" 'bash -o pipefail -c '\''git push -f origin main'\''' 'blocca il force-push con un opzione prima di -c'
expect_guard 2 "$CON_RUN" 'bash -c -x '\''git push -f origin main'\''' 'blocca il force-push con un opzione dopo -c'
expect_guard 2 "$CON_RUN" 'git clean -f' 'blocca il clean forzato anche senza -d'
expect_guard 2 "$CON_RUN" 'git clean -fx' 'blocca il clean forzato con -x e senza -d'
expect_guard 2 "$CON_RUN" 'echo "$(git push -f origin main)"' 'blocca una sostituzione dentro le virgolette'
expect_guard 2 "$CON_RUN" 'git commit -m "$(git push -f origin main)"' 'blocca una sostituzione dentro il messaggio di commit'
expect_guard 0 "$CON_RUN" 'git commit -m "fix #123: niente push -f"' 'lascia passare un cancelletto dentro il messaggio di commit'
expect_guard 0 "$CON_RUN" 'echo '\''# titolo'\'' >> note.md' 'lascia passare un cancelletto dentro apici singoli'
expect_guard 0 "$CON_RUN" 'git clean -nd' 'lascia passare il clean simulato ricorsivo'
expect_guard 0 "$CON_RUN" 'sudo -n true' 'lascia passare sudo -n su un comando innocuo'
expect_guard 0 "$CON_RUN" 'echo "$(git rev-parse HEAD)"' 'lascia passare una sostituzione innocua dentro le virgolette'
expect_guard 0 "$CON_RUN" 'bash -o pipefail -c '\''npm test | tee out'\''' 'lascia passare bash con opzioni su un comando innocuo'

# Riserve del settimo giro: sostituzioni fra apici singoli (che la shell non
# esegue), cancelletto a meta parola, redirezioni, abbreviazioni dei flag,
# bundle di opzioni corte, here-string, continuazione dentro la parola.
expect_guard 2 "$CON_RUN" 'echo abc#def
git push -f origin main' 'blocca il force-push dopo una riga con un cancelletto a meta parola'
expect_guard 2 "$CON_RUN" 'echo url#L20
rm -rf build' 'blocca la cancellazione dopo un cancelletto a meta parola'
expect_guard 2 "$CON_RUN" 'bash -euo pipefail -c '\''git push -f origin main'\''' 'blocca il force-push con un bundle di opzioni corte con valore'
expect_guard 2 "$CON_RUN" 'git push --mirr origin' 'blocca l abbreviazione di --mirror'
expect_guard 2 "$CON_RUN" 'git push --prun origin' 'blocca l abbreviazione di --prune'
expect_guard 2 "$CON_RUN" 'git branch --delet --forc x' 'blocca le abbreviazioni di --delete e --force'
expect_guard 2 "$CON_RUN" 'git branch --del --for x' 'blocca le abbreviazioni corte di --delete e --force'
expect_guard 2 "$CON_RUN" 'git clean --forc' 'blocca l abbreviazione di --force per clean'
expect_guard 2 "$CON_RUN" 'git >out push -f' 'blocca il force-push con una redirezione fra git e il sottocomando'
expect_guard 2 "$CON_RUN" '>out git push -f' 'blocca il force-push con una redirezione prima del comando'
expect_guard 2 "$CON_RUN" 'git pu\
sh -f origin main' 'blocca il force-push spezzato dentro la parola'
expect_guard 2 "$CON_RUN" 'cat <<<x
git push -f origin main' 'blocca il force-push dopo una here-string'
expect_guard 2 "$CON_RUN" 'gh pr merge 1 --admin=true' 'blocca --admin con il valore attaccato'
expect_guard 2 "$CON_RUN" 'caffeinate -t 3600 git push -f origin main' 'blocca il force-push sotto caffeinate -t'
expect_guard 2 "$CON_RUN" 'echo x | xargs -J % rm -rf build' 'blocca la cancellazione sotto xargs -J'
expect_guard 2 "$CON_RUN" 'sudo -h esempio git push -f origin main' 'blocca il force-push sotto sudo -h'
expect_guard 2 "$CON_RUN" 'time -o t.txt git push -f origin main' 'blocca il force-push sotto time -o'
expect_guard 0 "$CON_RUN" 'git commit -m '\''vedi `git push -f` nella doc'\''' 'lascia passare apici inversi dentro apici singoli'
expect_guard 0 "$CON_RUN" 'git commit -m '\''usa `rm -rf build` con cautela'\''' 'lascia passare una cancellazione citata fra apici inversi e singoli'
expect_guard 0 "$CON_RUN" 'gh pr comment 1 --body '\''verificato: `gh pr merge 1 --admin` bloccato'\''' 'lascia passare apici inversi nel body di un commento'
expect_guard 0 "$CON_RUN" 'gh pr comment 1 --body '\''uso $(git push -f) come esempio'\''' 'lascia passare una sostituzione citata fra apici singoli'
expect_guard 0 "$CON_RUN" 'echo '\''niente $(git push -f) qui'\'' >> note.md' 'lascia passare una sostituzione citata in una nota'
expect_guard 0 "$CON_RUN" 'npm test 2>&1 | tee out.log' 'lascia passare la redirezione della diagnostica'
expect_guard 0 "$CON_RUN" 'git log --oneline > /tmp/log.txt' 'lascia passare una redirezione su file'
expect_guard 0 "$CON_RUN" 'cat <<<'\''una riga'\'' | wc -l' 'lascia passare una here-string innocua'
expect_guard 0 "$CON_RUN" 'bash -euo pipefail -c '\''npm test'\''' 'lascia passare un bundle di opzioni su un comando innocuo'
expect_guard 0 "$CON_RUN" 'echo abc#def' 'lascia passare un cancelletto a meta parola'
expect_guard 0 "$CON_RUN" 'git push origin '\''feat/#42'\''' 'lascia passare un cancelletto nel nome del branch'

# Senza run attivo: l'hook non interferisce mai
expect_guard 0 "$SENZA_RUN" 'git push --force origin main' "fuori da un run non blocca nulla"
expect_guard 0 "$SENZA_RUN" 'git reset --hard HEAD~1' "fuori da un run non blocca il reset"

# Il root del run non coincide necessariamente col cwd del comando.
mkdir -p "$CON_RUN/src/deep"
expect_guard 2 "$CON_RUN/src/deep" 'git push --force origin main' "blocca dal cwd annidato risalendo al root del run"

# Payload malformato: il lavoro normale passa, ma il distruttivo non si infila
# approfittando di un parser che non ha capito niente.
printf 'non json' | "$GUARD" >/dev/null 2>&1
[ $? = 0 ] && ok "payload malformato non blocca il lavoro normale" || ko "payload malformato non blocca il lavoro normale"

# Senza python3 non c'e' feedback anticipato e il guardrail deve dichiararlo; non viene
# presentato come sandbox o barriera contro codice worker ostile.
SENZA_PY="$TMP/bin-vuoto"
mkdir -p "$SENZA_PY"
for c in sh bash cat printf grep sed dirname pwd; do
  src="$(command -v "$c" 2>/dev/null)"
  [ -n "$src" ] && ln -sf "$src" "$SENZA_PY/$c"
done
BODY_FORZA="$(payload "$CON_RUN" 'git push --force origin main')"
BODY_SANO="$(payload "$CON_RUN" 'git status --short')"
ERR_PY="$TMP/senza-py.err"
# Senza parser non si puo' leggere il campo cwd: vale la directory del processo,
# che nella sessione reale e' proprio quella del progetto. Il test la riproduce.
( cd "$CON_RUN" && printf '%s' "$BODY_FORZA" | env PATH="$SENZA_PY" "$GUARD" 2>"$ERR_PY" >/dev/null; exit "${PIPESTATUS[1]}" )
[ $? = 0 ] && ok "senza python3 la guardia non blocca" || ko "senza python3 la guardia non blocca"
grep -q 'NON e attivo' "$ERR_PY" \
  && ok "senza python3 la guardia dichiara di non essere attiva" \
  || ko "senza python3 la guardia dichiara di non essere attiva"
( cd "$CON_RUN" && printf '%s' "$BODY_SANO" | env PATH="$SENZA_PY" "$GUARD" >/dev/null 2>&1; exit "${PIPESTATUS[1]}" )
[ $? = 0 ] && ok "senza python3 lascia passare il lavoro normale" || ko "senza python3 lascia passare il lavoro normale"
ERR_NO_RUN="$TMP/senza-py-no-run.err"
( cd "$SENZA_RUN" && printf '%s' "$BODY_FORZA" | env PATH="$SENZA_PY" "$GUARD" 2>"$ERR_NO_RUN" >/dev/null; exit "${PIPESTATUS[1]}" )
[ $? = 0 ] && ok "senza python3 e senza run non interferisce" || ko "senza python3 e senza run non interferisce"
[ -s "$ERR_NO_RUN" ] && ko "senza run la guardia tace anche l'avviso" || ok "senza run la guardia tace anche l'avviso"

# SessionStart: silenzioso senza run, informativo con run.
# Niente pipe verso grep -q: con pipefail il SIGPIPE falserebbe l'esito.
OUT_SENZA="$( cd "$SENZA_RUN" && "$SESS" )"
[ -z "$OUT_SENZA" ] && ok "session hook silenzioso senza run" || ko "session hook silenzioso senza run"
printf 'stato: attivo\ncervello: cc-fable\n' > "$CON_RUN/.orchestratore/RUN.md"
OUT_CON="$( cd "$CON_RUN" && "$SESS" )"
case "$OUT_CON" in *"stato: attivo"*) ok "session hook riporta lo stato del run" ;; *) ko "session hook riporta lo stato del run" ;; esac
case "$OUT_CON" in *"brain.lock"*) ok "session hook segnala il lock" ;; *) ko "session hook segnala il lock" ;; esac
BODY_BRIDGE="$(payload "$SENZA_RUN" 'git push --force origin main')"
printf '%s' "$BODY_BRIDGE" | env ORCHESTRATORE_PROJECT_ROOT="$CON_RUN" "$GUARD" >/dev/null 2>&1
[ "${PIPESTATUS[1]}" = 2 ] && ok "bridge root esplicito attiva il guard fuori dal cwd di controllo" || ko "bridge root esplicito attiva il guard fuori dal cwd di controllo"
OUT_NESTED="$(cd "$CON_RUN/src/deep" && "$SESS")"
case "$OUT_NESTED" in *"stato: attivo"*) ok "session hook trova RUN dal cwd annidato" ;; *) ko "session hook trova RUN dal cwd annidato" ;; esac

if [ "$failures" -gt 0 ]; then printf 'ROSSO: %d controlli hook falliti\n' "$failures"; exit 1; fi
printf 'VERDE: hook conformi\n'
