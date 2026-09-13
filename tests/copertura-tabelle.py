# -*- coding: utf-8 -*-
"""Oracolo per le tabelle dell'analizzatore della guardia.

Ogni voce di WRAPPER, SHELL, PAROLE_CHIAVE e OPZIONE_CON_VALORE deve avere un comando che
la esercita davvero. Una voce senza comando e' un pezzo che nessun test difende: sembra
protezione e non lo e'. Qui le tabelle si confrontano con i casi uno a uno, quindi
aggiungere una voce senza il caso corrispondente fa fallire il gate.

Stampa una riga TSV per caso: <atteso> <comando> <etichetta>. Il gate degli hook la
trasforma in un payload vero e controlla l'exit code.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
import guard_run  # noqa: E402

PF = "push -" + "f"
FORZA = "git %s origin main" % PF

# Wrapper: il comando vero viene dopo, con gli argomenti che quel wrapper pretende.
CASI_WRAPPER = {
    "env": "env %s",
    "sudo": "sudo %s",
    "command": "command %s",
    "nice": "nice %s",
    "nohup": "nohup %s",
    "time": "time %s",
    "timeout": "timeout 30 %s",
    "ionice": "ionice -c2 %s",
    "xargs": "echo main | xargs %s",
    "exec": "exec %s",
    "builtin": "builtin %s",
    "stdbuf": "stdbuf -o0 %s",
    "setsid": "setsid %s",
}

# Shell: il comando arriva come stringa dopo -c, e va analizzato a parte.
CASI_SHELL = {nome: "%s -c '%s'" % (nome, FORZA) for nome in ("sh", "bash", "zsh", "dash", "ksh")}

# Parole chiave: ognuna deve stare subito prima del comando vietato, altrimenti non e'
# lei a permettere l'analisi e la voce non serve a niente.
CASI_PAROLE = {
    "do": "for b in main; do %s; done" % FORZA,
    "then": "if true; then %s; fi" % FORZA,
    "else": "if false; then true; else %s; fi" % FORZA,
    "elif": "if false; then true; elif %s; then true; fi" % FORZA,
    "!": "! %s" % FORZA,
    "if": "if %s; then true; fi" % FORZA,
    "while": "while %s; do true; done" % FORZA,
    "until": "until %s; do true; done" % FORZA,
}

# Opzioni che portano un valore separato: senza saltare anche il valore, l'analisi si
# mangia il programma che viene dopo.
CASI_OPZIONE = {
    "-s": "timeout -s KILL 30 %s" % FORZA,
    "-k": "timeout -k 5 30 %s" % FORZA,
    "-u": "sudo -u andrea %s" % FORZA,
    "-n": "nice -n 10 %s" % FORZA,
    "-I": "echo main | xargs -I {} %s" % FORZA,
    "-P": "echo main | xargs -P 4 %s" % FORZA,
    "--signal": "timeout --signal KILL 30 %s" % FORZA,
    "--user": "sudo --user andrea %s" % FORZA,
}

TABELLE = [
    ("WRAPPER", guard_run.WRAPPER,
     {k: v % FORZA for k, v in CASI_WRAPPER.items()}, "wrapper"),
    ("SHELL", guard_run.SHELL, CASI_SHELL, "shell"),
    ("PAROLE_CHIAVE", guard_run.PAROLE_CHIAVE, CASI_PAROLE, "parola chiave"),
    ("OPZIONE_CON_VALORE", guard_run.OPZIONE_CON_VALORE, CASI_OPZIONE, "opzione con valore"),
]


def main():
    righe = []
    for nome, tabella, casi, etichetta in TABELLE:
        senza_caso = sorted(tabella - set(casi))
        senza_voce = sorted(set(casi) - tabella)
        if senza_caso:
            sys.stderr.write("%s: voci senza oracolo: %s\n" % (nome, ", ".join(senza_caso)))
            return 1
        if senza_voce:
            sys.stderr.write("%s: casi senza voce: %s\n" % (nome, ", ".join(senza_voce)))
            return 1
        for voce in sorted(casi):
            righe.append("2\t%s\tblocca il force-push con %s %s" % (casi[voce], etichetta, voce))
    sys.stdout.write("\n".join(righe) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
