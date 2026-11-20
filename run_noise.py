# -*- coding: utf-8 -*-
"""Bloc 9 du papier : bruit WM 5 % et 10 % sur les canaux de profondeur,
applique a NOTRE circuit de liaison (variante « inhibition FREE_F »).

Protocole : les canaux de phase (SELF et BIND, fine et coarse) sont des
mots de 8 bits a un seul bit actif ; le bruit active chaque bit inactif
avec probabilite p (bits actifs conserves) — cf. §3.2. Monte-Carlo :
40 tirages par niveau.

Resultat honnete (finding n°9) :
  - les VAR reellement lies au redex ne sont JAMAIS manques ;
  - les VAR libres ne sont JAMAIS marques (fix (7,7) + inhibition
    FREE_F : 40/40 aux deux niveaux, meme sans inhibition grace au
    code reserve) ;
  - MAIS des faux lies apparaissent : un VAR dont un canal de phase est
    a UN bit du lambda du redex (l'autre canal coincidant) est marque
    lie quand le bruit touche le SELF du lambda (mode a) ou son propre
    BIND (mode b). Taux mesures : ~12 % des tirages a 5 %, ~35 % a 10 %
    sur ce terme. Le bloc 9 du papier (5 termes, un tirage chacun) etait
    statistiquement expose a ces evenements — la robustesse du §3.2
    vaut pour l'encodage, pas pleinement pour le circuit de liaison.
  Mitigation proposee (future) : lecture WTA du pattern SELF du lambda
  (le mecanisme WTA est deja celui du §2.4) — supprime le mode a.
"""

import random
import sys

import lambda_beta as lb
import bridge_db as bd
import free_vars_fix as fv
import intg_body as ig
import bind_gamma as bg

# console Windows cp1252 par defaut : les λ/ε des impressions planteraient
# (revue externe) — forcer l'UTF-8 sur la sortie
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

S = "(\\f. \\x. f (f (f x))) (\\x. x y)"   # 3 f lies + x (autre lieur) + y libre
# 2e terme (revue externe) : une variable libre DANS le corps du redex
# (g) — la protection (7,7) + inhibition FREE_F n'etait exercee que sur
# des libres de l'ARGUMENT, jamais presentes au circuit de liaison
S_BODY_FREE = "(\\f. f (g f)) h"           # 2 f lies + g libre (corps) + h libre


def noisy_channels(rows, k, p, rng, decode="multi"):
    """Patterns bruites : bits inactifs actives avec probabilite p.
    decode="onehot" : chaque canal bruite est decode en UN bit choisi au
    hasard parmi les bits actifs (modele d'un WTA equilibre — le circuit
    de lecture du papier est implicite, §2.2/§2.6)."""
    lam = rows[k + 1]

    def bits(v):
        out = {v}
        for b in range(8):
            if b != v and rng.random() < p:
                out.add(b)
        if decode == "onehot":
            pick = rng.choice(sorted(out))
            out = {pick}
        return out

    sf = bits(lam[2])
    sc = bits(lam[3])
    bind = []
    for (_i, bf, bc) in vars_of(rows, k):
        bind.append((bits(bf), bits(bc)))
    return {"self_f": sf, "self_c": sc, "bind": bind}


def vars_of(rows, k):
    return [(i, r[4], r[5]) for i, r in enumerate(rows) if i > k + 1
            and r[0] >= 4]


def run_term(S, require_body_free=False):
    """Bloc 9 sur UN terme : controle sans bruit + Monte-Carlo 40
    tirages x {5 %, 10 %} x {multi, onehot}, proprietes robustes."""
    t = lb.parse(S)
    db = bd.to_debruijn(t)
    rows = fv.rows_fix(db)                     # encodage fixe (libres=(7,7))
    toks = bd.to_tokens(db)
    k = bd.find_redex(t)
    l_body = ig.body_end_pos(toks, k) + 1
    body_end = k + 2 + l_body
    order = bg.body_var_order(rows, k, body_end)
    truth = [order.index(i) for i in
             bg.truth_bound_indices(rows, k, body_end)]
    free_idx = [order.index(i) for i in order if rows[i][6]]
    print("  terme : %s" % S)
    print("  VARs du corps : %d ; lies attendus : %s ; libres : %s"
          % (len(order), truth, free_idx))
    if require_body_free:
        # revue externe : ce terme doit presenter au moins une libre AU
        # CIRCUIT (dans le corps du redex) — sans lui, la protection
        # (7,7)+inhibition n'etait jamais exercee par ce banc
        assert free_idx, ("pas de libre dans le corps", S)

    c0 = bg.BindCircuit(rows, k, body_end=body_end)
    r0 = c0.run()
    assert r0["bound"] == truth
    print("  controle sans bruit : BOUND=%s == verite ✓" % r0["bound"])

    for p in [0.05, 0.10]:
        for decode in ["multi", "onehot"]:
            n_trials, n_ok, n_miss, n_free_false = 40, 0, 0, 0
            n_fp = 0
            rng = random.Random(1234)
            for _ in range(n_trials):
                nz = noisy_channels(rows, k, p, rng, decode=decode)
                c = bg.BindCircuit(rows, k, body_end=body_end, noisy=nz)
                r = c.run()
                mask = r["bound"]
                if mask == truth:
                    n_ok += 1
                    continue
                missed = [m for m in truth if m not in mask]
                false = [m for m in mask if m not in truth]
                if missed:
                    n_miss += 1
                if any(m in free_idx for m in false):
                    n_free_false += 1
                if false:
                    n_fp += 1
            print("  p=%.0f%% decode=%s : masques exacts %d/%d tirages ; "
                  "manques %d ; libres marques %d ; faux lies %d"
                  % (100 * p, decode, n_ok, n_trials, n_miss, n_free_false,
                     n_fp))
            # proprietes robustes par mode :
            #  - multi   : jamais de manque ni de libre marque ; faux lies
            #    minoritaires (bornes) ;
            #  - onehot  : zero faux lies MAIS les manques explosent quand
            #    le WTA decroche (contre-exemple : le decodage one-hot
            #    naif est CONTRE-PRODUCTIF — finding n°9 bis).
            if decode == "multi":
                assert n_miss == 0 and n_free_false == 0, (p, decode)
                assert n_fp <= 0.5 * n_trials, (p, decode, n_fp)
            else:
                assert n_fp == 0, (p, decode, n_fp)


def main():
    print("=" * 64)
    print("BLOC 9 - BRUIT WM SUR LA LIAISON (avec inhibition FREE_F)")
    print("=" * 64)

    run_term(S)
    print()
    run_term(S_BODY_FREE, require_body_free=True)

    print()
    print("BLOC 9 : en presentation multi-bits, les proprietes robustes")
    print("tiennent (0 manque, 0 libre marque) avec des faux lies minoritaires,")
    print("Y COMPRIS avec une libre dans le corps du redex (presentee au")
    print("circuit) ; le decodage one-hot naif (WTA equilibre) supprime les")
    print("faux lies mais provoque 75 % de manques a 10 % : CONTRE-PRODUCTIF")
    print("(finding n°9 bis). La sensibilité au bruit de la liaison reste un")
    print("probleme ouvert — pistes : majorite sur presentations repetees,")
    print("hysteresis du WTA, ou ne jamais bruite le canal de lecture (choix")
    print("implicite du papier).")


if __name__ == "__main__":
    main()
