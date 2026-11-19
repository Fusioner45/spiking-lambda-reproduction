# -*- coding: utf-8 -*-
r"""Banc v3a+v3b-1 : la pile d'INTG LIF du re-scan
(rescan_circuit.RescanStack) validee contre la specification executable
rescan_body (cube_write.py) sur la batterie — le circuit est juge
token-par-token contre cette spec, comme le moteur C contre son
prototype Python.

Deux modes de gating, traces identiques attendus :
  - 'selective' (v3a) : ports par niveau, injection selective ;
  - 'global' (v3b-1) : ports VAR/APP GLOBAUX connectes a tous les INTG
    au push, coupure par refractaire long au discharge — chaque INTG
    decharge au plus UNE fois (verifie).

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


def run_battery(gating):
    """Differentiel circuit vs spec sur toute la batterie. Renvoie
    (total_steps, total_tokens, max_simul, max_closes, binder_stats)."""
    total_tokens = 0
    total_steps = 0
    max_simul = 0
    max_closes = 0
    b_stats = {"interne": 0, "hors-corps": 0, "libre": 0}
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
            stack = rc.RescanStack(d_lam, gating=gating,
                                   max_tokens=len(body_rows))
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
                binder_n = (tid - 4) if kind == "VAR" else None
                cur, b_circuit = stack.feed(kind, binder_n)
                if kind != "SKIP":
                    self_spec = spec[gi][0] + 8 * spec[gi][1]
                    assert cur == self_spec, \
                        (term, step + 1, pos, cur, self_spec)
                if kind == "VAR":
                    # lecture v3b-2 du canal BIND depuis l'etat de la pile
                    _tid, _d, _sf, _sc, bf, bc, libre = row
                    b_src = bf + 8 * bc
                    if libre:
                        assert b_circuit is None, (term, "libre: pile muette")
                        assert (spec[gi][2], spec[gi][3]) == (7, 7)
                        b_stats["libre"] += 1
                    elif b_src > d_lam:
                        # binder interne : le (n+1)-ieme LAM actif, a sa
                        # profondeur d'ancrage (= b_src - 1)
                        assert b_circuit == b_src - 1, \
                            (term, binder_n, b_circuit, b_src)
                        assert spec[gi][2] + 8 * spec[gi][3] == b_src - 1
                        b_stats["interne"] += 1
                    else:
                        # binder hors du corps : pile muette, BIND source
                        assert b_circuit is None, (term, "hors corps")
                        assert (spec[gi][2], spec[gi][3]) == (bf, bc)
                        b_stats["hors-corps"] += 1
                if kind != "SKIP":
                    gi += 1
            assert stack.levels == [], (term, "BODY doit fermer au dernier")
            for lv in stack.all:
                assert lv["closes"] == 1, (term, gating, lv)
                max_closes = max(max_closes, lv["closes"])
            max_simul = max(max_simul, stack.last_closures)
            total_tokens += len(spec)
            total_steps += 1
            cur_term, _ = lb.beta_step(cur_term)
    return total_steps, total_tokens, max_simul, max_closes, b_stats


def main():
    print("=" * 64)
    print("PILE D'INTG DU RE-SCAN (v3a + v3b-1) - circuit LIF vs spec")
    print("=" * 64)

    # 1. v3a : injection selective par niveau
    st, tk, simul, _c, bs = run_battery("selective")
    print("  v3a  selective : %d etapes, %d tokens, profondeur + binders "
          "exactes ; fermetures simultanees max = %d" % (st, tk, simul))

    # 2. v3b-1 : injection GLOBALE + coupure par refractaire long :
    #    chaque INTG decharge AU PLUS une fois (max_closes <= 1)
    st2, tk2, simul2, mc, _ = run_battery("global")
    print("  v3b  global    : %d etapes, %d tokens, profondeur + binders "
          "exactes ; fermetures simultanees max = %d ; decharges/INTG = %d "
          "(coupure OK)" % (st2, tk2, simul2, mc))
    assert mc == 1, "le refractaire long doit rendre chaque INTG sourd \
        apres son discharge"
    assert (st, tk, simul) == (st2, tk2, simul2), "les deux modes doivent \
        produire les memes traces"

    print()
    print("PILE RE-SCAN VALIDEE : %d etapes, %d tokens gardes, "
          "profondeur + binders exacts dans les deux modes" % (st, tk))
    print("binders lus sur l'etat de la pile : %d internes, %d hors corps, "
          "%d libres (detection automatique par pile muette)"
          % (bs["interne"], bs["hors-corps"], bs["libre"]))
    print("fermetures simultanees max observees sur un slot : %d "
          "(sommee, pas « -1 par slot »)" % simul)
    assert simul >= 3, "le cas limite des fermetures simultanees doit \
        etre exerce par la batterie"


if __name__ == "__main__":
    main()
