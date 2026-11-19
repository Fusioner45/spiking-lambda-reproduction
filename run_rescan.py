# -*- coding: utf-8 -*-
r"""Banc v3a : la pile d'INTG LIF du re-scan (rescan_circuit.RescanStack)
validee contre la specification executable rescan_body (cube_write.py)
sur la batterie — le futur circuit sera juge spike-a-spike contre cette
spec, comme le moteur C contre son prototype Python.

Calibrage : tau_m = 1000 ms / W_CNT = 1/epsilon(tau_m, 1) (finding n°8 :
les niveaux externes de la pile restent sous le seuil pendant la
traversee des sous-termes internes ; les 300 ms du papier derivent).

Edge case du banc : (\x. f (x y)) z — sur le dernier token, les INTG
APP2, APP1 et BODY franchissent +1 au MEME slot : trois fermetures
simultanees, chacune projetee independamment (pas de « -1 par slot
actif »). Le terme (\x. (\\y. x (y x))) I pousse jusqu'a quatre
fermetures simultanees (APP2, APP1, LAM, BODY).
"""

import lambda_beta as lb
import bridge_db as bd
import free_vars_fix as fv
import cube_write as cw
import intg_body
import bind_gamma
import rescan_circuit as rc

two = "\\f. \\x. f (f x)"
three = "\\f. \\x. f (f (f x))"
eye = "\\x. x"
plus = "\\m. \\n. \\f. \\x. m f (n f x)"

TERMS = [
    "(%s) (%s)" % (eye, eye),
    "(%s) (%s)" % (two, eye),
    "(%s) (%s) (%s)" % (plus, two, three),
    "(\\x. x y) z",
    "(\\x. z) (%s)" % eye,
    "(\\x. (\\y. y x)) (%s)" % eye,
    "(\\x. (\\y. x (y x))) (%s)" % eye,
    "(\\x. f (x y)) z",            # fermetures simultanees APP2/APP1/BODY
]


def main():
    print("=" * 64)
    print("PILE D'INTG DU RE-SCAN (v3a) - circuit LIF vs spec")
    print("=" * 64)

    total_tokens = 0
    total_steps = 0
    max_simul = 0
    for term in TERMS:
        cur_term = lb.parse(term)
        for step in range(12):
            db = bd.to_debruijn(cur_term)
            toks = bd.to_tokens(db)
            rows = fv.rows_fix(db)
            K = bd.find_redex(cur_term)
            if K == -1:
                break
            l_body = intg_body.IntgCircuit(toks, K).run()["pos"] + 1
            l_arg = intg_body.IntgCircuit(toks, K + l_body).run()["pos"] + 1
            body_end = K + 2 + l_body
            bound_abs = bind_gamma.truth_bound_indices(rows, K, body_end)
            d_lam = toks[K + 1][1]
            body_rows = rows[K + 2:body_end]
            skip = {j - (K + 2) for j in bound_abs}

            # spec (semantique evenementielle)
            spec = cw.rescan_body(body_rows, d_lam, skip)
            # circuit LIF : meme flux de tokens
            stack = rc.RescanStack(d_lam)
            gi = 0
            for pos, row in enumerate(body_rows):
                tid = row[0]
                if pos in skip:
                    kind = "SKIP"
                elif tid >= 4:
                    kind = "VAR"
                elif tid == bd.LAM:
                    kind = "LAM"
                else:
                    kind = "APP"
                cur = stack.feed(kind)
                if kind != "SKIP":
                    self_spec = spec[gi][0] + 8 * spec[gi][1]
                    assert cur == self_spec, \
                        (term, step + 1, pos, cur, self_spec)
                    gi += 1
            assert stack.levels == [], (term, "BODY doit fermer au dernier")
            max_simul = max(max_simul, stack.last_closures)
            total_tokens += len(spec)
            total_steps += 1
            cur_term, _ = lb.beta_step(cur_term)
        print("  %-34s : %d etapes, profondeur exacte token par token"
              % (term, step + 1))

    print()
    print("PILE RE-SCAN VALIDEE : %d etapes, %d tokens gardes, "
          "profondeur exacte" % (total_steps, total_tokens))
    print("fermetures simultanees max observees sur un slot : %d "
          "(sommee, pas « -1 par slot »)" % max_simul)
    assert max_simul >= 3, "le cas limite des fermetures simultanees doit \
        etre exerce par la batterie"


if __name__ == "__main__":
    main()
