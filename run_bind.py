# -*- coding: utf-8 -*-
"""Demo palier 5 : detection de liaison theta-gamma (§2.6) en vrais LIF.

1. Calibration : W_coin (paire simultanee sur neurone rapide) et W_AND
   (2 entrees sur l'integrateur tau_m=40) — tous calibres par mesure.
2. Masque BOUND du circuit == verite semantique sur 4 termes
   (VAR lies au redex marques ; VAR lies a un autre lambda, libres,
   silencieux — le fix variables libres (7,7) est integre).
3. Cas adversarial : un VAR a coincident FINE seule et un VAR a
   coincident COARSE seule (binders a profondeurs differentes) — les
   coins firent bien, mais l'integrateur reste silencieux sur leurs
   slots (pas de fausse somme croisee a 20 ms d'ecart).
4. Plein cercle item 2 : avec l'encodage PAPIER (BIND libre = (0,0)),
   le bug §3.3 apparait AU NIVEAU DU CIRCUIT (le libre est marque lie
   quand le lambda du redex est a profondeur 0) ; avec le fix, disparait.
"""

import lambda_beta as lb
import bridge_db as bd
import free_vars_fix as fv
import intg_body as ig
import bind_gamma as bg


def run_term(s, rows_fn):
    t = lb.parse(s)
    db = bd.to_debruijn(t)
    rows = rows_fn(db)
    k = bd.find_redex(t)
    body_end = k + 2 + ig.body_end_pos(bd.to_tokens(db), k) + 1
    order = bg.body_var_order(rows, k, body_end)
    truth_abs = bg.truth_bound_indices(rows, k, body_end)
    truth_rel = [order.index(i) for i in truth_abs]
    c = bg.BindCircuit(rows, k, body_end=body_end)
    r = c.run()
    return c, r, truth_rel, order


def main():
    print("=" * 64)
    print("PALIER 5 - LIAISON THETA-GAMMA (§2.6)")
    print("=" * 64)

    # 1. calibration
    c0, _r, _t, _o = run_term("(\\x. x y) z", fv.rows_fix)
    print("  W_coin=%.3f (paire simultanee=%.3f, 1 EPSP=%.3f) ; "
          "W_AND=%.3f (epsilon(40,2)=%.3f)"
          % (c0.w_coin, c0.pair_coin, c0.pair_coin / 2, c0.w_and,
             c0.eps402))
    assert c0.pair_coin * c0.w_coin > 1 > (c0.pair_coin / 2) * c0.w_coin
    assert 2 * c0.w_and * c0.eps402 > 1 > c0.w_and * c0.eps402

    # 2. masque BOUND == verite, sur 4 termes
    cases = [
        ("(\\x. x y) z", "libre + lie, lambda a d=0"),
        ("(\\f. \\x. f (f x)) (\\x. x)", "2 I : deux f lies, x d'un autre lambda"),
        ("\\a. ((\\x. x a) b)", "lambda du redex a d=1"),
        ("(\\x. x (\\y. y z)) w", "imbrication"),
    ]
    for s, label in cases:
        c, r, truth, _o = run_term(s, fv.rows_fix)
        print("  %-30s BOUND=%s verite=%s" % (label, r["bound"], truth))
        assert r["bound"] == truth, (s, r["bound"], truth)
    print("  -> masque du circuit exact sur %d termes" % len(cases))

    # 3. adversarial : coïncidences FINE seule / COARSE seule
    s = ("\\a.\\b.\\c.\\d.\\e.\\f.\\g.\\h.\\i."
         "((\\x. b ((\\u. u) w)) z)")
    t = lb.parse(s)
    db = bd.to_debruijn(t)
    rows = fv.rows_fix(db)
    k = bd.find_redex(t)
    d_lam = rows[k + 1][1]
    kf, kc = d_lam % 8, (d_lam // 8) % 8
    body_end = k + 2 + ig.body_end_pos(bd.to_tokens(db), k) + 1
    order = bg.body_var_order(rows, k, body_end)
    c = bg.BindCircuit(rows, k, body_end=body_end)
    r = c.run()
    truth = [order.index(i)
             for i in bg.truth_bound_indices(rows, k, body_end)]
    fine_only = [m for m in range(len(order))
                 if rows[order[m]][4] == kf and rows[order[m]][5] != kc]
    coarse_only = [m for m in range(len(order))
                   if rows[order[m]][5] == kc and rows[order[m]][4] != kf]
    print("  adversarial (lambda du redex a d=%d, SELF=(%d,%d)) :" % (d_lam, kf, kc))
    print("    FINE-seule slots=%s -> coins fine firent : %s"
          % (fine_only,
             any(r["coin_t"][("f", kf)] for m in fine_only) or bool(fine_only)))
    print("    COARSE-seule slots=%s -> BOUND circuit=%s, verite=%s"
          % (coarse_only, r["bound"], truth))
    assert r["bound"] == truth
    assert r["bound"] == [m for m in range(len(order))
                          if rows[order[m]][4] == kf
                          and rows[order[m]][5] == kc]
    print("    -> l'integrateur ne s'est pas laisse abuser par les")
    print("       residus croises (residu e^{-20/40}=0.61 < seuil)")

    # 4. plein cercle item 2 : le bug §3.3 au niveau du circuit
    #    (sans inhibition FREE_F : le fix (7,7) suffit seul ; avec
    #     l'inhibition, l'encodage papier est protege aussi)
    s = "(\\x. x y) z"
    t_bug = lb.parse(s)
    db_bug = bd.to_debruijn(t_bug)
    rows_bug = fv.rows_papier(db_bug)
    k_bug = bd.find_redex(t_bug)
    body_end_bug = (k_bug + 2 + ig.body_end_pos(bd.to_tokens(db_bug), k_bug)
                    + 1)
    order_bug = bg.body_var_order(rows_bug, k_bug, body_end_bug)
    c_paper = bg.BindCircuit(rows_bug, k_bug, body_end=body_end_bug,
                             free_ff=False)
    r_paper = c_paper.run()
    c_fix, r_fix, truth, _o = run_term(s, fv.rows_fix)
    print("  bug §3.3 au niveau circuit, '%s' :" % s)
    print("    encodage papier (sans FREE_F) : BOUND=%s (le libre y est "
          % r_paper["bound"])
    print("          marque lie — BUG) ; encodage fix : BOUND=%s (verite=%s)"
          % (r_fix["bound"], truth))
    assert r_paper["bound"] != truth and r_fix["bound"] == truth

    print()
    print("TOUTES LES VERIFICATIONS LIAISON SONT VERTES.")


if __name__ == "__main__":
    main()
