# -*- coding: utf-8 -*-
"""Finding n°8 : test d'enveloppe de tau_m sur l'INTG.

Cas : mult 5 5, etape 4 (80 tokens), argument de 65 tokens — le discharge
verite est au slot 64 (l_arg = 65). tau_m=300 (papier) decharge au slot
31 (derive). Hypothese (Gemini + Seung [53]) : la compensation de fuite
= approcher l'attracteur lineaire, i.e. tau_m >> duree de la sequence.
On balaie tau_m et on regarde le discharge converger vers la verite.
"""

import lambda_beta as lb
import bridge_db as bd
import intg_body as ig
import snn_core as sc

mult = "\\m. \\n. \\f. m (n f)"
c5 = "(\\a. \\b. a (a (a (a (a b)))))"
S = "(%s) %s %s" % (mult, c5, c5)
cur = lb.parse(S)
for _ in range(4):
    cur, _d = lb.beta_step(cur)
toks = bd.to_tokens(bd.to_debruijn(cur))
K = bd.find_redex(cur)
l_body = ig.body_end_pos(toks, K) + 1
truth = ig.body_end_pos(toks, K + l_body)
print("tokens=%d K=%d l_body=%d arg_start=%d verite(l_arg)=%s"
      % (len(toks), K, l_body, K + 2 + l_body,
         (truth + 1) if truth is not None else None))

print("\n  tau_m (ms) : decharge (slot) | ecart vs verite")
for tau in [300.0, 1000.0, 3000.0, 10000.0, 30000.0, 100000.0]:
    r = ig.IntgCircuit(toks, K + l_body, net_factory=sc.CNetwork,
                       tau_m=tau).run()
    pos = r["pos"]
    ecart = ("+%d" % (pos - truth)) if (pos is not None and truth is not None
                                        and pos >= truth) else (
        "%d" % (pos - truth) if pos is not None else "aucun")
    print("  %8.0f     : %8s           | %s"
          % (tau, pos, ("slot verite-1 ( parfait)" if pos == truth
                        else ecart)))

# et le banc nominal (tau_m=300, enveloppe papier) reste vert
print("\n  (le banc nominal run_intg.py tourne toujours en tau_m=300 : "
      "fidelite au papier)")
