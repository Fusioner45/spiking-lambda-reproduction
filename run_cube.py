# -*- coding: utf-8 -*-
"""Banc « cube vivant » : le prochain cube est ECRIT par les copies
STDP (§2.8, un canal de copie par slot) et LU par rappel — l'etat
effectif de la boucle vit dans les memoires STDP au lieu d'etre
re-encode symboliquement (chantier « cube comme etat vivant », revue
ChatGPT, addendum session 14 octies).

Encodage d'un slot : 7 canaux x 8 phases (4 canaux du papier §2.2 +
canal TYPE + 2 canaux d'indice libre) — cf. cube_state.py.

1. batterie fermee + terme ouvert via le cube vivant (moteur C) :
   traces identiques a la boucle standard ;
2. differentiel moteur : Python -> memes traces (C == Python) ;
3. sabotage : demonter un poids appris rend un canal muet — la lecture
   le detecte (unite) et la reduction s'arrete (le cube est PORTEUR,
   pas decoratif : l'etat passe reellement par les memoires).
"""

import lambda_beta as lb
import bridge_db as bd
import cube_state as cs
import orchestrate as orc
import copy_stdp

two = "\\f. \\x. f (f x)"
three = "\\f. \\x. f (f (f x))"
eye = "\\x. x"
plus = "\\m. \\n. \\f. \\x. m f (n f x)"


def main():
    print("=" * 64)
    print("CUBE VIVANT - le prochain cube vit dans les memoires STDP")
    print("=" * 64)

    # 1. batterie via le cube vivant (moteur C)
    loop = orc.ClosedLoop(living_cube=True, copy_engine="c", verbose=False)
    nf, trace, _ = loop.run("(%s) (%s)" % (eye, eye))
    print("  (\\x. x) I : trace=%s -> %s" % (trace, lb.to_str(nf)))
    assert trace == [5, 2] and lb.to_str(nf) == "\\x. x"

    nf, trace, _ = loop.run("(%s) (%s)" % (two, eye))
    print("  2 I       : trace=%s -> %s" % (trace, lb.to_str(nf)))
    assert trace == [10, 8, 5, 2] and lb.to_str(nf) == "\\x. x"

    nf, trace, _ = loop.run("(%s) (%s) (%s)" % (plus, two, three))
    print("  plus 2 3  : trace=%s -> Church %s"
          % (trace, lb.church_to_int(nf)))
    assert lb.church_to_int(nf) == 5

    # terme ouvert : les indices libres (canal reserve (7,7) + canaux
    # 5-6) sortent exactement — (\x. x y) z -> z y
    nf, trace, _ = loop.run("(\\x. x y) z")
    print("  (\\x. x y) z : trace=%s -> %s" % (trace, lb.to_str(nf)))
    assert trace == [6, 3]

    # 2. differentiel moteur : Python == C
    loop = orc.ClosedLoop(living_cube=True, copy_engine="py", verbose=False)
    _nf, trace, _ = loop.run("(%s) (%s) (%s)" % (plus, two, three))
    print("  plus 2 3 (moteur Python) : trace=%s (identique)" % (trace,))
    assert trace == [31, 28, 25, 22, 19, 16, 13]

    # 3a. sabotage au niveau unite : poids demonte -> canal muet detecte
    cube = cs.CubeState(engine="py")
    cube.write(0, (1, 0, 0, 0, cs.TY_VAR, 0, 0))   # VAR(0) lie, d=1, b=0
    assert cube.read(0) == (bd.VAR(0), 1)
    _src, b = cube.slots[0]
    b.w[8 * 4 + cs.TY_VAR] = copy_stdp.W0          # canal TYPE demonte
    try:
        cube.read(0)
        raise AssertionError("sabotage NON detecte a la lecture")
    except ValueError:
        print("  sabotage unite : canal muet DETECTE a la lecture")

    # 3b. sabotage dans la boucle : l'etat corrompu arrete la reduction
    _BaseCube = cs.CubeState             # classe reelle, avant le patch

    class _Sabotage(_BaseCube):
        def __init__(self, engine="py"):
            _BaseCube.__init__(self, engine)
            self.n_writes = 0

        def write(self, slot, pattern):
            _BaseCube.write(self, slot, pattern)
            self.n_writes += 1
            if self.n_writes == 3:                 # un slot du 1er cube
                _src, bb = self.slots[slot]
                bb.w[8 * 4 + pattern[4]] = copy_stdp.W0

    saved = cs.CubeState
    cs.CubeState = _Sabotage
    try:
        loop = orc.ClosedLoop(living_cube=True, copy_engine="py",
                              verbose=False)
        loop.run("(%s) (%s)" % (two, eye))
        raise AssertionError("corruption in-loop NON detectee")
    except (ValueError, AssertionError):
        print("  sabotage boucle : la reduction s'arrete a la corruption"
              " — le cube est PORTEUR")
    finally:
        cs.CubeState = saved

    print()
    print("CUBE VIVANT VALIDE — l'etat de la boucle vit dans les memoires.")


if __name__ == "__main__":
    main()
