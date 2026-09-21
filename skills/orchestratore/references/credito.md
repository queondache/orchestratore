# Credito: failover persistente fra CC e cx

Lo stato credito vive in `~/.orchestratore/state.toml`, è condiviso fra le sessioni e va
riletto prima di ogni assegnazione. Un flag `esaurito` non scade: cambia solo con un
ripristino esplicito. Tabella dei modelli in modalità solo-CC e solo-cx: [routing](routing.md).

Riconosci `/orchestra credito <cc|cx> esaurito` e gli equivalenti naturali («CC ha finito i
crediti, vai tutto su cx fino a nuovo avviso», e viceversa); per il ripristino
`/orchestra credito <cc|cx> ok`, «<runtime> di nuovo disponibile», «ripristina <runtime>».

Quando un runtime passa a `esaurito`:

1. Se la modalità era `normale`, salva il peso corrente in `credito.peso_precedente`; non
   sovrascriverlo durante ulteriori cambi di credito. Marca runtime, timestamp, motivo e
   modalità: `solo-cx` se è esaurito CC, `solo-cc` se è esaurito cx, `fermo` se lo sono entrambi.
2. I task in volo su quel runtime completano solo il checkpoint atomico sicuro; esito e lavoro
   residuo in `RUN.md`, poi nessuna nuova assegnazione a quel runtime.
3. Se è esaurito il runtime del cervello e l'altro è disponibile, scrivi l'handoff esplicito
   all'altro runtime dopo aver completato solo il proprio checkpoint atomico, aggiornato
   `RUN.md` e lo stato credito e rilasciato `brain.lock`; quindi fermati. La ripresa usa
   `riprendi` sul runtime disponibile.
4. Se è esaurito l'altro runtime, il cervello continua in `solo-cc` o `solo-cx`: builder,
   verificatore e pre-merge nel proprio runtime, su modelli diversi secondo
   [routing](references/routing.md).
5. Se entrambi sono esauriti, modalità fermo: checkpoint, handoff, rilascio del lock, stop.
   Non aprire task, simulare capacità o dichiarare verifiche non eseguite.

Al ripristino togli solo il flag del runtime indicato; se l'altro resta esaurito rimani sul
runtime disponibile e aggiorna `modalita`; quando entrambi sono `ok`, ripristina
il peso salvato, torna a `normale` e conserva quel peso come traccia dell'ultimo failover.
