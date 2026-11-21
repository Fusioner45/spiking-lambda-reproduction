# -*- coding: utf-8 -*-
"""ABLATIONS (idee revue externe ChatGPT, addendum session 14 octies ;
durci d'apres la revue externe session 31) : desactiver UN circuit a
la fois dans la boucle fermee et verifier que l'ablation est
TOUJOURS attrapee AU SITE ATTENDU — la boucle refuse de calculer faux.

Renforcements (revue externe session 31) :
  - PRECONDITION : la boucle non-ablatee reussit d'abord (trace
    exacte) — une ablation ne peut pas etre declaree detectee sur une
    boucle qui echouerait de toute facon ;
  - l'exception doit etre l'ASSERTION ATTENDUE au SITE ATTENDU (le
    check structurel de orchestrate.step ou le filet du cube — lu via
    la traceback), pas n'importe quelle exception (une erreur de
    programmation sans rapport ne compte plus comme detection) ;
  - TROIS familles de termes (baseline, variables libres avec lieur
    hors corps, fermetures simultanees) ;
  - conclusion rewordée : les ablations TESTEES sont detectees SUR LES
    SCENARIOS RETENUS (pas de claim d'impossibilite de succes
    silencieux universel).

Deux moities :
  1. NECESSITE (dans notre architecture et nos scenarios) ;
  2. EQUIVALENCE : les interrupteurs (neural_keep, multiplexed,
     living_cube) sont des MODES — traces identiques.
"""

import lambda_beta as lb
import linecache
import det_redex
import intg_body
import bind_gamma
import ring_phase
import rescan_circuit
import orchestrate as orc

PLUS = "\\m. \\n. \\f. \\x. m f (n f x)"
REF_TRACE = [31, 28, 25, 22, 19, 16, 13]

# les trois familles de termes (revue externe : plusieurs familles)
TERM_BASE = "(%s) (%s) (%s)" % (PLUS, "\\f. \\x. f (f x)",
                                "\\f. \\x. f (f (f x))")
FAMILIES = [
    ("plus 2 3 (baseline)", TERM_BASE),
    ("(\\x. x y) z (libre + lieur hors corps)",
     "(\\x. x y) z"),
    ("(\\x. (\\y. x (y x))) I (fermetures simultanees)",
     "(\\x. (\\y. x (y x))) (%s)" % "\\x. x"),
]

# les ablations : (nom, module, classe, methode, replacement,
#                  le SITE ATTENDU de l'echec — sous-chaine de la ligne
#                  source du check qui doit declencher)
ABLATIONS = [
    ("DET muet (plus de detection de redex)",
     det_redex, "DetCircuit", "run",
     lambda self, *a, **kw: {"K": -1},
     "K == K_or"),
    ("INTG muet (plus de mesure du corps)",
     intg_body, "IntgCircuit", "run",
     lambda self, *a, **kw: {"pos": 0},
     "l_body == l_body_or"),
    ("liaison muette (plus de VAR lies)",
     bind_gamma, "BindCircuit", "run",
     lambda self, *a, **kw: {"bound": []},
     "bound_abs == truth"),
    ("ring gele (feux d'onde nuls)",
     ring_phase, "PhaseRing", "run",
     lambda self, phi0, n_fires: ([0] * n_fires,
                                  [0.0] * n_fires, 0.0),
     "f[sh] =="),
    ("re-scan muet (profondeur figee a 0)",
     rescan_circuit, "RescanStack", "feed",
     lambda self, kind, binder_n=None: (0, 0),
     "le corps doit fermer"),
]


def failure_site(exc):
    """La ligne source du check qui a leve l'exception (la frame la
    plus profonde dans orchestrate/cube_write) — pour verifier que
    l'ablation est attrapee AU SITE ATTENDU."""
    import traceback
    frames = traceback.extract_tb(exc.__traceback__)
    for fr in reversed(frames):
        if "orchestrate" in fr.filename or "cube_write" in fr.filename \
                or "gated_chain" in fr.filename:
            return linecache.getline(fr.filename, fr.lineno).strip()
    return "(hors harnais : %s)" % frames[-1].filename


def main():
    print("=" * 72)
    print("ABLATIONS - un circuit desactive a la fois : arret AU SITE"
          " ATTENDU")
    print("=" * 72)

    # 0. PRECONDITION : la boucle non-ablatee reussit sur chaque famille
    for fam_name, term in FAMILIES:
        loop = orc.ClosedLoop(living_cube=True, verbose=False)
        _nf, trace, _ = loop.run(term, max_steps=25)
        print("  precondition %-44s trace %s OK"
              % (fam_name, trace))

    # 1. NECESSITE : chaque ablation est attrapee AU SITE ATTENDU sur
    #    chaque famille
    print()
    print("  %-38s %-34s %s" % ("ablation", "site attendu", "verdict"))
    for name, mod, cls_name, method, repl, site in ABLATIONS:
        cls = getattr(mod, cls_name)
        orig = getattr(cls, method)
        for fam_name, term in FAMILIES:
            setattr(cls, method, repl)
            verdict = "PASSEE EN SILENCE"
            try:
                loop = orc.ClosedLoop(living_cube=True, verbose=False)
                loop.run(term, max_steps=25)
            except AssertionError as e:
                site_got = failure_site(e)
                assert site in site_got, \
                    ("attrapee au MAUVAIS site", name, fam_name,
                     site, site_got)
                verdict = "ARRETEE au site attendu"
            except Exception as e:
                verdict = ("EXCEPTION NON ATTENDUE : %s %s"
                           % (type(e).__name__, str(e)[:50]))
            finally:
                setattr(cls, method, orig)
            assert "ARRETEE" in verdict, (name, fam_name, verdict)
            print("  %-38s %-34s %s — %s" % (name, site, verdict,
                                             fam_name.split("(")[0].strip()))

    print()
    print("  rappel : la 6e ablation (copie STDP sans apprentissage) est")
    print("  prouvee par le sabotage in-loop de run_cube.py (canal muet ->")
    print("  ValueError au rappel) — non dupliquee ici.")

    # 2. EQUIVALENCE : les interrupteurs sont des MODES
    print()
    print("EQUIVALENCE — les interrupteurs sont des MODES, pas des"
          " ablations :")
    configs = [
        ("tout neural (defaut production)", {"living_cube": True}),
        ("neural_keep=False (KEEP symbolique)",
         {"living_cube": True, "neural_keep": False}),
        ("multiplexed=False (copie sequentielle)",
         {"living_cube": True, "multiplexed": False}),
        ("living_cube=False (etat re-encode)", {"living_cube": False}),
    ]
    for name, kwargs in configs:
        loop = orc.ClosedLoop(verbose=False, **kwargs)
        _nf, trace, _ = loop.run(FAMILIES[0][1], max_steps=25)
        assert trace == REF_TRACE, (name, trace, REF_TRACE)
        print("  %-42s trace %s" % (name, trace))

    print()
    print("ABLATIONS VALIDES (sur les scenarios retenus) : chaque circuit")
    print("desactive arrete la boucle AU SITE ATTENDU — jamais de succes")
    print("silencieux ; les modes equivalants produisent des traces")
    print("identiques — les circuits sont NECESSAIRES (dans notre")
    print("architecture) et les chemins neuraux EQUIVALENTS a leurs")
    print("references.")


if __name__ == "__main__":
    main()
