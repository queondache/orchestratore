Sei il subagent implementer del Task 1 di M1. Non delegare e non contattare Andrea.

Boundary scrivibile:
- /Users/andreapesce/Dev/.gitignore, ma preserva la modifica preesistente `!/AGENTS.md` e non includerla nel tuo commit.
- /Users/andreapesce/Dev/skills/orchestratore/**

Base umbrella: 4e3c08fea9c96668bfb2fbfc7a61cae9bdba27d6, branch main. Il worktree contiene modifiche altrui in CLAUDE.md, AGENTS.md e dev-cc/audit-fulgaro: non toccarle. I docs M1 sotto orchestratore appartengono alla milestone.

Contratto:
- Task/milestone: T1 / M1 scheletro plugin.
- Risultato: `skills/orchestratore` diventa repo Git annidato e gitignorato dall'umbrella; `tests/check-structure.sh` esiste, è eseguibile e produce rosso.
- Dipendenze: piano e spec approvati; tool bash/jq/git presenti; contratto congelato.
- Tier/runtime/modello/effort: basic / cx / gpt-5.6-terra / medium.
- Skill obbligatorie: nessuna opzionale disponibile; segui AGENTS.md e CLAUDE.md già letti dal coordinatore.
- Verifica ammessa: comandi Git locali e script bash leggero. Niente rete, push, gh, plugin install, symlink o file fuori boundary.
- Stop: qualsiasi file di sotto-progetto diverso da orchestratore finisce staged; impossibilità di separare la modifica preesistente di .gitignore; fallimento inatteso dopo un solo tentativo corretto.
- Checkpoint: commit umbrella isolato, repo plugin inizializzato, gate rosso e relativo output raw salvato.

Esegui esattamente Task 1 nel piano `/Users/andreapesce/Dev/skills/orchestratore/docs/plans/2026-09-12-m1-scheletro-plugin.md`, con queste precisazioni:
1. Usa apply_patch per aggiungere `/skills/orchestratore/` dopo `Marketing/` nel working tree.
2. `git rm -r --cached skills/orchestratore` è autorizzato. Nel commit umbrella stage solo il nuovo ignore e le rimozioni orchestratore; NON stage la riga preesistente `!/AGENTS.md`. Puoi creare/applicare all'index una patch basata su HEAD, poi verifica `git diff --cached` prima del commit.
3. Commit umbrella con il messaggio del piano. I commit locali sono autorizzati.
4. Inizializza il nested repo, sposta SKILL.md e references sotto skills/orchestratore, crea `.gitignore` e lo script del piano.
5. Salva l'output raw di `tests/check-structure.sh; echo "exit=$?"` in `docs/plans/2026-09-12-m1-check-structure-red.log`, mantenendo l'exit reale visibile nel log. Il gate deve restare rosso.
6. Commit nested repo con il messaggio del piano.
7. Aggiorna nel piano solo le checkbox Step 1-6 di Task 1 a `[x]` e lo stato tabellare T1 da `pronto` a `review`; nessun'altra checkbox o stato.

Consegna sintetica obbligatoria: hash dei due commit, file modificati, comando/output essenziale del gate, `git status --short` di entrambi i repo, limiti residui.
