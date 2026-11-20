# -*- coding: utf-8 -*-
"""ABLATIONS (idee revue externe ChatGPT, addendum session 14 octies) :
desactiver UN circuit a la fois dans la boucle fermee et verifier que
l'ablation est TOUJOURS attrapee — la boucle refuse de calculer faux.

Deux moities :

  1. NECESSITE : cinq circuits ablates par patch de classe (le sabotage
     de la copie STDP est deja prouve dans run_cube.py 4a/4b — rappel
     seul). Chaque ablation doit lever une exception (asserts
     structurels de orchestrate.step(), actifs y compris en mode
     production, ou filets du cube vivant) — JAMAIS un succes silencieux.

  2. EQUIVALENCE : les chemins neuraux (re-scan, multiplexage, cube
     vivant) et leurs references symboliques produisent les MEMES traces
     — les interrupteurs existants (neural_keep, multiplexed,
     living_cube) sont des modes, pas des ablations.

Les patches sont restaures apres chaque mesure (finally). Verdicts :
ablation -> point d'arret -> type d'exception.
"""

import lambda_beta as lb
import det_redex
import intg_body
import bind_gamma
import ring_phase
import rescan_circuit
import orchestrate as orc

TERM = "(%s) (%s) (%s)" % ("\\m. \\n. \\f. \\x. m f (n f x)",
                           "\\f. \\x. f (f x)",
                           "\\f. \\x. f (f (f x))")
REF_TRACE = [31, 28, 25, 22, 19, 16, 13]


def run_ablation(module, cls_name, method, repl):
    """Patch la methode de la classe, tente la reduction de plus 2 3
    (cube vivant, chemin neural complet), restaure, renvoie le verdict
    (type d'exception ou None si succes silencieux — JAMAIS attendu)."""
    cls = getattr(module, cls_name)
    orig = getattr(cls, method)
    setattr(cls, method, repl)
    try:
        loop = orc.ClosedLoop(living_cube=True, verbose=False)
        loop.run(TERM)
        return None
    except Exception as e:
        return "%s: %s" % (type(e).__name__, str(e)[:70])
    finally:
        setattr(cls, method, orig)


def main():
    print("=" * 72)
    print("ABLATIONS - un circuit desactive a la fois : la boucle doit"
          " s'arreter")
    print("=" * 72)

    ablations = [
        ("DET muet (plus de detection de redex)",
         det_redex, "DetCircuit", "run",
         lambda self, *a, **kw: {"K": -1},
         "assert K == K_oracle (step)"),
        ("INTG muet (plus de mesure du corps)",
         intg_body, "IntgCircuit", "run",
         lambda self, *a, **kw: {"pos": 0},
         "assert l_body == l_body_oracle (step)"),
        ("liaison muette (plus de VAR lies)",
         bind_gamma, "BindCircuit", "run",
         lambda self, *a, **kw: {"bound": []},
         "assert bound == verite (step)"),
        ("ring gele (feux d'onde nuls)",
         ring_phase, "PhaseRing", "run",
         lambda self, phi0, n_fires: ([0] * n_fires,
                                      [0.0] * n_fires, 0.0),
         "assert feux == shifts attendus (step)"),
        ("re-scan muet (profondeur figee a 0)",
         rescan_circuit, "RescanStack", "feed",
         lambda self, kind, binder_n=None: (0, 0),
         "filet composition == re-encodage (cube)"),
    ]
    print("  %-40s %-38s %s" % ("ablation", "attrapee par", "verdict"))
    for name, mod, cls_name, method, repl, expected in ablations:
        verdict = run_ablation(mod, cls_name, method, repl)
        assert verdict is not None, \
            ("ablation PASSEE en silence : la boucle n'est pas porteuse",
             name)
        print("  %-40s %-38s %s"
              % (name, expected, "ARRETEE (" + verdict.split(":")[0] + ")"))

    print()
    print("  rappel : la 6e ablation (copie STDP sans apprentissage) est")
    print("  prouvee par le sabotage in-loop de run_cube.py (canal muet ->")
    print("  ValueError, la reduction s'arrete) — non dupliquee ici.")

    print()
    print("EQUIVALENCE — les interrupteurs sont des MODES, pas des"
          " ablations :")
    print("  les chemins neuraux et leurs references symboliques donnent"
          " les MEMES traces")
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
        _nf, trace, _ = loop.run(TERM)
        assert trace == REF_TRACE, (name, trace, REF_TRACE)
        print("  %-42s trace %s" % (name, trace))

    print()
    print("ABLATIONS VALIDES : chaque circuit desactive arrete la boucle")
    print("(jamais de succes silencieux) ; les modes equivalants produisent")
    print("des traces identiques — les circuits sont NECESSAIRES et les")
    print("chemins neuraux EQUIVALENTS a leurs references.")


if __name__ == "__main__":
    main()
