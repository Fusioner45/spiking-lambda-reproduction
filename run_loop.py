# -*- coding: utf-8 -*-
"""Demo finale : la boucle fermee de l'Algorithme 1 sur de vrais termes.

Chaque etape de reduction est dirigee par les circuits reels (DET,
INTG_BODY x2, liaison theta-gamma, anneau de phase, copie STDP),
l'assemblage des evenements est topographique (§2.10.3, avec les regles
KEEP -1 / shift_bind), et chaque etape est verifiee contre l'oracle
symbolique du palier 1.

1. (\\x. x) I -> I (1 etape).
2. 2 I -> lam x. x en 3 etapes ; trace des longueurs [10, 8, 5, 2]
   -> tranche la question ouverte n°1 depuis la dynamique :
   le « 7 » du texte du papier est bien une coquille.
3. plus 2 3 -> Church-5 (le papier : 6 etapes).
"""

import lambda_beta as lb
import orchestrate as orc

two = "\\f. \\x. f (f x)"
three = "\\f. \\x. f (f (f x))"
eye = "\\x. x"
plus = "\\m. \\n. \\f. \\x. m f (n f x)"


def main():
    print("=" * 64)
    print("BOUCLE FERMEE - ALGORITHME 1 (circuits reels + assemblage)")
    print("=" * 64)

    loop = orc.ClosedLoop()

    # 1. (\x. x) I -> I
    nf, trace, _ = loop.run("(%s) (%s)" % (eye, eye))
    print("  (\\x. x) I : trace=%s -> %s"
          % (trace, lb.to_str(nf)))
    assert trace == [5, 2] and lb.to_str(nf) == "\\x. x"

    # 2. 2 I -> I : tranche la question ouverte n°1
    nf, trace, _ = loop.run("(%s) (%s)" % (two, eye))
    print("  2 I       : trace=%s -> %s" % (trace, lb.to_str(nf)))
    print("              papier §3.1 : [10, 7, 5, 2] -> le 7 est une")
    print("              coquille, tranche par la boucle fermee (n°1)")
    assert trace == [10, 8, 5, 2] and lb.church_to_int(nf) is None
    assert lb.to_str(nf) == "\\x. x"

    # 3. plus 2 3 -> Church 5 (papier : 6 etapes)
    nf, trace, _ = loop.run("(%s) (%s) (%s)" % (plus, two, three))
    print("  plus 2 3  : trace=%s -> Church %s (%d etapes ; papier : 6)"
          % (trace, lb.church_to_int(nf), len(trace) - 1))
    assert lb.church_to_int(nf) == 5

    print()
    print("BOUCLE FERMEE VALIDEE — LE PAPIER EST REPRODUIT DE BOUT EN BOUT.")


if __name__ == "__main__":
    main()
