# -*- coding: utf-8 -*-
"""Demo palier 5 : anneau de phase (§2.7).

1. Calibration : auto-entretien de l'onde (W_ring calibre par mesure),
   ISI mesure (~4.9 ms attendus cf. papier).
2. Mecanique de l'onde : fire ordinal i <-> FINE[(phi_0+i) mod 8],
   sur phi_0 in [0,8) x sh in [0,19].
3. Retenue : nombre de rebouclages sur sh pas = (phi_0+sh)//8
   => registre COARSE exact ; grille de profondeurs d in [0,49] x sh
   (equiv. au test 1 200 paires du papier).
4. sh = 0 : la reponse est l'ordinal 0 (pulse d'activation) — l'onde
   n'a pas besoin d'etre lancee pour un decalage nul.
5. sh < 0 : preuve empirique que sh = d_var - 1 - d_ref >= 0 pour TOUTES
   les substitutions de la batterie (2 I, plus 2 3, mult 2 3, pred 3,
   K I I, (lam x. x x) I, terme a deux profondeurs de la meme variable).
"""

import lambda_beta as lb
import ring_phase as rp

two = "\\f. \\x. f (f x)"
three = "\\f. \\x. f (f (f x))"
eye = "\\x. x"
plus = "\\m. \\n. \\f. m (n f)"
mult = "\\m. \\n. \\f. m (n f)"
pred = "\\m. \\f. \\x. m (\\g. \\h. h (g f)) (\\u. x) (\\u. u)"
kk = "\\x. \\y. x"

battery = [
    "(%s) (%s)" % (two, eye),
    "(%s) (%s) (%s)" % (plus, two, three),
    "(%s) (%s) (%s)" % (mult, two, three),
    "(%s) (%s)" % (pred, three),
    "(%s) a b" % kk,
    "(\\x. x x) (%s)" % eye,
    "(\\x. x (\\w. x w)) (%s)" % eye,   # meme variable liee a deux profondeurs
]


def main():
    print("=" * 64)
    print("PALIER 5 - ANNEAU DE PHASE (§2.7)")
    print("=" * 64)

    # 1. calibration + onde entretenue + ISI
    ring = rp.PhaseRing()
    fires, _t, isis = ring.run(0, 26)
    print("  W_ring=%.2f (epsilon(5,1)=%.3f) ; onde : %d feux "
          "(26 demandes), ISI moyen %.2f ms (papier : ~4.9)"
          % (ring.w_ring, ring.eps51, len(fires),
             sum(isis) / len(isis)))
    assert len(fires) == 26
    assert 3.5 < sum(isis) / len(isis) < 7.0

    # 2+3. mecanique de l'onde + retenue, grille complete
    n_ok, bad = 0, None
    for d in range(50):                    # profondeurs 0..49 (papier)
        for sh in range(20):
            phi0 = d % 8
            f, _t2, _isi = ring.run(phi0, sh + 1)
            ok = all(f[i] == (phi0 + i) % 8 for i in range(sh + 1))
            carries = sum(1 for i in range(1, sh + 1)
                          if f[i] < f[i - 1])
            ok = ok and (d + sh) // 8 == d // 8 + carries
            if ok:
                n_ok += 1
            elif bad is None:
                bad = (d, sh, f, carries)
    print("  grille d in [0,49] x sh in [0,19] : %d/1000 combinaisons "
          "exactes (fine'=(d+sh) mod 8, coarse'+retenues=(d+sh)//8)"
          % n_ok)
    assert n_ok == 1000, bad

    # 4. sh = 0 : reponse = ordinal 0, aucune propagation requise
    f, _t3, _i2 = ring.run(5, 1)
    assert f[0] == 5
    print("  sh = 0 : ordinal 0 = FINE[phi_0] tel quel (l'orchestrateur")
    print("  court-circuite l'onde pour un decalage nul) : OK")

    # 5. preuve sh >= 0 sur toutes les substitutions de la batterie
    total, distinct_seen = 0, set()
    for s in battery:
        t = lb.parse(s)
        for (k, d_lam, d_ref, subs) in rp.all_substitutions(t):
            for (_j, d_var, sh) in subs:
                assert sh >= 0, (s, k, d_var, d_ref, sh)
                distinct_seen.add(sh)
                total += 1
    print("  sh < 0 : %d substitutions verifiees sur %d termes, TOUTES "
          "sh >= 0 (structurel : d_var >= d_lam+1 et d_ref = d_lam)"
          % (total, len(battery)))
    print("  valeurs de sh rencontrees : %s" % sorted(distinct_seen))
    assert total >= 10

    # bonus : decalages PAR OCCURRENCE (meme variable, profondeurs differentes)
    t = lb.parse(battery[-1])
    subs = rp.all_substitutions(t)[0]
    shs = sorted(set(s[2] for s in subs[3]))
    print("  decalages par occurrence dans '%s' (etape 1) : %s"
          % (battery[-1], shs))
    assert len(shs) >= 2

    print()
    print("TOUTES LES VERIFICATIONS ANNEAU SONT VERTES.")


if __name__ == "__main__":
    main()
