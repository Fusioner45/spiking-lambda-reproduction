# -*- coding: utf-8 -*-
"""Demo palier 1 du lab commun : lambda-calcul symbolique + LIF/STDP.

Run : python run_demo.py   (stdlib uniquement, aucune dependance)
Chaque demo est suivie d'un assert : si le script se termine sur
"TOUTES LES VERIFICATIONS SONT VERTES", le palier 1 est valide.
"""

import math

import lambda_beta as lb
import lif_stdp as ls


def demo_lambda():
    print("=" * 64)
    print("PALIER 1a - beta-reduction symbolique")
    print("=" * 64)

    # 1. identite
    nf, steps, ok = lb.normalize(lb.parse("(\\x. x) y"))
    lb.show(nf, label="  (\\x. x) y            ->  ")
    assert ok and lb.to_str(nf) == "y"

    # 2. capture evitee : (\\x. \\y. x y) y ne doit PAS donner \y. y y
    nf, steps, ok = lb.normalize(lb.parse("(\\x. \\y. x y) y"))
    lb.show(nf, label="  test-capture         ->  ")
    assert isinstance(nf, lb.Abs) and nf.param != "y"
    body = nf.body
    # le corps doit etre : (le y libre passe en argument) applique au lieur renomme
    assert (isinstance(body, lb.App) and isinstance(body.func, lb.Var)
            and body.func.name == "y" and body.arg.name == nf.param)
    print("      -> lieur renomme, capture evitee : OK")

    # 3. successeur du numeraux de Church 1 -> 2
    succ = "\\m. \\f. \\x. f (m f x)"
    one = "\\f. \\x. f x"
    nf, steps, ok = lb.normalize(
        lb.parse("(%s) (%s)" % (succ, one)))
    lb.show(nf, label="  succ 1               ->  ")
    assert ok and lb.church_to_int(nf) == 2

    # 4. multiplication 2 x 3 -> 6
    mult = "\\m. \\n. \\f. m (n f)"
    two = "\\f. \\x. f (f x)"
    three = "\\f. \\x. f (f (f x))"
    nf, steps, ok = lb.normalize(
        lb.parse("(%s) (%s) (%s)" % (mult, two, three)))
    lb.show(nf, label="  mult 2 3             ->  ")
    assert ok and lb.church_to_int(nf) == 6
    print("      -> %d etapes de reduction" % steps)

    # 5. divergence detectee proprement (omega) : taille x2 par etape,
    #    on coupe volontairement tot pour ne pas exploser la memoire.
    nf, steps, ok = lb.normalize(lb.parse("(\\x. x x) (\\x. x x)"),
                                 max_steps=12)
    print("  omega : pas de forme normale, arret propre apres %d etapes" % steps)
    assert not ok

    # 6. aller-retour parse <-> impression
    for s in ["\\x y. x y", "(\\x. x) (\\y. y x)", "a b (c d)"]:
        assert lb.to_str(lb.parse(s)) == s, s
    print("  aller-retour parse/impression : OK")


def demo_lif_stdp():
    print()
    print("=" * 64)
    print("PALIER 1b - LIF + STDP")
    print("=" * 64)

    # 1. tir regulier du LIF sous courant constant : mesure vs theorie
    n = ls.LIF()
    isi, last = [], None
    for k in range(2000):                     # 200 ms a dt = 0.1
        t = k * n.dt
        if n.step(i=1.0):
            if last is not None:
                isi.append(t - last)
            last = t
    period = sum(isi) / len(isi)
    theory = ls.lif_period(i=1.0)
    print("  LIF i=1.0 : %d spikes, periode %.2f ms (theorie %.2f ms)"
          % (len(isi), period, theory))
    assert 26.0 < period < 29.0 and abs(period - theory) < 0.5

    # 2. fenetre STDP theorique
    print("  fenetre STDP (delta_t = t_post - t_pre) :")
    for d in (-40, -20, -10, -2, 0, 2, 10, 20, 40):
        print("    %+3d ms -> %+.5f" % (d, ls.stdp_window(d)))

    # 3. LTP : post force a spiker ~2 ms APRES chaque pre
    w0, w1, dts = ls.run_stdp_protocol(n_cycles=5, post_offset_ms=+2.0)
    m = sum(dts) / len(dts)
    print("  LTP  (post %+.1f ms apres pre) : w %.3f -> %.3f  (%+.1f %%)"
          % (m, w0, w1, 100 * (w1 / w0 - 1)))
    assert w1 > w0 * 1.04

    # 4. LTD : post force a spiker ~2 ms AVANT chaque pre
    w0, w1, dts = ls.run_stdp_protocol(n_cycles=5, post_offset_ms=-2.0)
    m = sum(dts) / len(dts)
    print("  LTD  (post %.1f ms avant pre) : w %.3f -> %.3f  (%+.1f %%)"
          % (abs(m), w0, w1, 100 * (w1 / w0 - 1)))
    assert w1 < w0 * 0.96
    print("      (gain/deperdition nets < |0.9 %|/cycle : les fenetres")
    print("       des cycles adjacents se recouvrent, effet attendu)")

    print()
    print("TOUTES LES VERIFICATIONS SONT VERTES.")


if __name__ == "__main__":
    demo_lambda()
    demo_lif_stdp()
