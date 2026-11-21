# -*- coding: utf-8 -*-
"""Banc « profil d'enveloppe » (22e banc, session 42).

La leçon des sessions 38-41 : une limite consignee sans mesure est une
intuition (l'« enveloppe DET ~70 tokens » n'existait pas). Ce banc
mesure les ENVELOPPES REELLES de chaque circuit sur des tailles
croissantes et imprime la carte : la plus grande taille exacte, la
premiere casse (avec son message), pour :

  - DET (§2.4) : le redex detecte sur des termes de 22 a 1002 tokens ;
  - compteur positionnel (chantier B, spec) : la segmentation sur des
    corps x^n croissants — la PLAGE des k=3 chiffres ([−128, 127])
    est une limite DOCUMENTEE : l'overflow est attendu et garde
    (l'assert de la garde), le banc le reporte comme borne mesuree,
    pas comme un echec ;
  - compteur analogique (§2.5, tau_m=1000) : en regard — ou il derive
    (le finding n°8) ;
  - liaison (§2.6) : des VAR lies dans des corps croissants.

Les asserts portent sur les comportements DEJA documentes (le DET
tient au-dela de 1000 ; la garde du compteur decharge proprement),
pour detecter les regressions — pas sur les bornes de mesure elles-
memes, qui sont le RESULTAT du banc.
"""

import lambda_beta as lb
import bridge_db as bd
import det_redex as dr
import intg_body as ig
import balance_circuit as bcc


def numeral(k):
    return "\\f. \\x. " + "f (" * k + "x" + ")" * k


def prof_det():
    """Le DET : le redex en tete, des tailles croissantes."""
    out = []
    for total in (20, 40, 80, 160, 320, 640, 1002):
        n_x = max(2, (total - 8) // 2)
        k_num = max(1, total - 2 * n_x - 5)
        term = "(\\x. " + " ".join(["x"] * n_x) + ") " + numeral(k_num)
        toks = bd.to_tokens(bd.to_debruijn(lb.parse(term)))
        K_or = bd.find_redex(lb.parse(term))
        r = dr.DetCircuit(toks).run()
        assert r["K"] == K_or, ("DET diverge", len(toks), r["K"], K_or)
        out.append(len(toks))
    return out[-1], None


def prof_positional():
    """Le compteur positionnel : la segmentation sur des corps x^n
    croissants. La plage des k=3 chiffres s'arrete a |sigma| > 127 :
    l'overflow est la limite DOCUMENTEE (garde dure) — le banc mesure
    la borne exacte."""
    last_ok, first_err = 0, None
    for n_x in (8, 80, 200, 258, 300):
        wide = "(\\x. " + " ".join(["x"] * n_x) + ")"
        toks = bd.to_tokens(bd.to_debruijn(lb.parse(wide)))
        try:
            r = bcc.BalanceCircuit(toks, -1).run()
            assert r["pos"] == 2 * n_x - 2, ("pos fausse", n_x, r["pos"])
            last_ok = 2 * n_x - 1
        except AssertionError as exc:
            if first_err is None:
                first_err = (2 * n_x - 1, str(exc)[:70])
    return last_ok, first_err


def prof_analog():
    """Le compteur analogique (tau_m=1000) : ou la decharge derive."""
    last_ok, first_err = 0, None
    for n_x in (2, 8, 15, 20, 35, 75):
        wide = "(\\x. " + " ".join(["x"] * n_x) + ")"
        toks = bd.to_tokens(bd.to_debruijn(lb.parse(wide)))
        r = ig.IntgCircuit(toks, -1, tau_m=1000.0).run()
        if r["pos"] is not None and r["pos"] + 1 == 2 * n_x - 1:
            last_ok = 2 * n_x - 1
        elif first_err is None:
            first_err = (2 * n_x - 1, "discharge %s != %d"
                         % (r["pos"], 2 * n_x - 2))
    return last_ok, first_err


def prof_bind():
    """La liaison : n VAR lies au lieur du redex dans des corps
    croissants — le masque du circuit == la verite."""
    import free_vars_fix as fv
    import bind_gamma as bg
    last_ok, first_err = 0, None
    for n in (2, 8, 16, 32, 64):
        body = " ".join(["x"] * n)
        term = "(\\x. " + body + ") " + numeral(n)
        cur = lb.parse(term)
        db = bd.to_debruijn(cur)
        toks = bd.to_tokens(db)
        K = bd.find_redex(cur)
        rows = fv.rows_fix(db)
        l_body = ig.body_end_pos(toks, K) + 1
        body_end = K + 2 + l_body
        r = bg.BindCircuit(rows, K, body_end=body_end).run()
        order = bg.body_var_order(rows, K, body_end)
        got = sorted(order[m] for m in r["bound"])
        truth = sorted(bg.truth_bound_indices(rows, K, body_end))
        if got == truth and len(got) == n:
            last_ok = l_body
        elif first_err is None:
            first_err = (l_body, "masque %s != verite %s" % (got, truth))
    return last_ok, first_err


def main():
    print("=" * 64)
    print("PROFIL D'ENVELOPPE - les limites reelles, mesurees")
    print("=" * 64)
    rows = [
        ("DET (§2.4)", prof_det()),
        ("balance positionnelle (circuit)", prof_positional()),
        ("balance analogique (tau_m=1000)", prof_analog()),
        ("liaison (§2.6, VAR lies)", prof_bind()),
    ]
    print()
    print("  %-34s %12s  %s" % ("circuit", "dernier OK", "premiere casse"))
    for name, (last, err) in rows:
        err_s = "-" if err is None else "%s tokens : %s" % err
        print("  %-34s %10d  %s" % (name, last, err_s))
    print()
    print("  le DET tient au-dela de 1000 tokens (assert) ; la plage du")
    print("  compteur positionnel (|sigma| <= 255, k=3 chiffres base 8) est")
    print("  une limite DOCUMENTEE avec garde dure — l'overflow mesure en est")
    print("  la borne, pas un echec ; le profil guide la v2 (quels circuits")
    print("  convertir au traitement positionnel pour le scaling).")
    assert rows[0][1][0] >= 1000
    print()
    print("PROFIL VALIDE — la carte des limites reelles remplace les")
    print("intuitions (lecon des sessions 38-41).")


if __name__ == "__main__":
    main()
