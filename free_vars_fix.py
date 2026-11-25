# -*- coding: utf-8 -*-
"""Item 2 du backlog : corriger le bug des variables libres (§3.3 du papier).

LE BUG (§3.3, « Free variables: a known encoding limitation ») :
  - l'encodage §2.2 met BIND=(0,0) pour une variable libre (canal FREE_F) ;
  - le masque bound_to_redex declare un VAR « lie au redex » ssi
    (BIND_FINE, BIND_COARSE) == SELF du lambda du redex (§2.6) ;
  - si le lambda du redex est a profondeur 0 (SELF=(0,0)), TOUTES les
    variables libres sont marquees liees -> reduction fausse des termes
    ouverts. (Meme cause pour toute profondeur d ≡ 0 mod 64.)

LE FIX PROPOSE (encodage, zero neurone ajoute) :
  - reserver le code de phase (7,7) — celui de la profondeur 63 — aux
    variables libres : BIND_free = (7,7) ;
  - la profondeur utile des lambda est bornee a 62 (le papier teste
    jusqu'a 25 lambdas, large marge) ;
  - alors SELF(lambda) parcourt {0..62} : jamais (7,7) -> la coincidence
    BIND==SELF ne peut plus matcher une variable libre, structurellement
    (prouve par enumeration ci-dessous). FREE_F reste utilise pour
    l'encode/decode, inchange.
  - residu honnete : sous bruit additif fort (10 % par bit), un libre
    peut encore matcher par hasard (~p^2) ; la variante « inhibition
    FREE_F » du circuit AND annulerait aussi ce residu si on la cable.
"""

import random

import bridge_db as bd

RESERVED = (bd.K_F - 1, bd.K_C - 1)      # (7,7) : code reserve aux libres
MAX_DEPTH = bd.K_F * bd.K_C - 1          # 63 codes ; 0..62 utiles


def rows_papier(db):
    """Encodage du papier : BIND=(0,0) pour une variable libre."""
    return bd.phase_table(db)


def rows_fix(db):
    """Encodage repare : BIND=(7,7) pour une variable libre.
    Les VAR lies sont inchanges (BIND = profondeur de leur binder).

    Garde de profondeur (revue externe) : les phases se replient modulo
    64 et (7,7) est RESERVE aux libres — un token a la profondeur 63
    (SELF=(7,7)) ou au-dela entrerait en collision avec les libres. La
    limite documentee (profondeur utile 0..62 ; le papier teste <= 25
    lambdas) est appliquee ici, au point d'entree unique de l'encodage."""
    out = []
    for (tid, d, sf, sc, bf, bc, libre) in bd.phase_table(db):
        if d >= MAX_DEPTH:
            raise ValueError(
                "token a la profondeur %d >= %d : phases repliees modulo "
                "64, collision avec le code libre (7,7) — borner le terme"
                % (d, MAX_DEPTH))
        if libre and tid >= 4:
            bf, bc = RESERVED
        out.append((tid, d, sf, sc, bf, bc, libre))
    return out


def redex_lam_depth(t):
    """Profondeur du lambda du redex leftmost-outermost (token K+1).
    None si forme normale."""
    K = bd.find_redex(t)
    if K == -1:
        return None
    return bd.to_tokens(bd.to_debruijn(t))[K + 1][1]


def bound_mask_papier(rows, lam_self):
    """Masque bound_to_redex tel que le calcule le circuit §2.6 : un VAR
    est declare lie ssi (bind_f, bind_c) == SELF du lambda. FREE_F n'est
    PAS consulte : c'est exactement le comportement buggue du §3.3."""
    return [i for i, (tid, d, sf, sc, bf, bc, libre) in enumerate(rows)
            if tid >= 4 and (bf, bc) == lam_self]


def truth_bound(rows, d_lam):
    """Verite semantique : VAR non libres dont le binder est a la
    profondeur d_lam (= le lambda du redex), a l'adresse COMPLETE
    (fine + coarse) : la fine seule matchait les lieurs a profondeur
    d_lam + 8k. Independant du circuit."""
    return [i for i, (tid, d, sf, sc, bf, bc, libre) in enumerate(rows)
            if tid >= 4 and not libre
            and bf == d_lam % bd.K_F and bc == d_lam // bd.K_C]


def noise_false_positive_rate(rows, lam_self, p=0.1, trials=4000, seed=1):
    """Bruit additif (§3.2, 10 % sur les canaux de profondeur) : le bit
    actif reste actif, chaque bit inactif s'active avec proba p. Renvoie
    la fraction de tirages ou au moins une variable libre est marquee
    « liee au redex » par la coincidence bruitee (bit du SELF present
    dans les deux canaux bruites)."""
    rng = random.Random(seed)
    lf, lc = lam_self
    bit_f, bit_c = 1 << lf, 1 << lc
    libres = [(1 << bf, 1 << bc)
              for (tid, d, sf, sc, bf, bc, libre) in rows
              if tid >= 4 and libre]
    if not libres:
        return 0.0
    hits = 0
    for _ in range(trials):
        bad = False
        for base_f, base_c in libres:
            pat_f = base_f
            for b in range(8):
                if not (base_f >> b) & 1 and rng.random() < p:
                    pat_f |= 1 << b
            pat_c = base_c
            for b in range(8):
                if not (base_c >> b) & 1 and rng.random() < p:
                    pat_c |= 1 << b
            if (pat_f & bit_f) and (pat_c & bit_c):
                bad = True
                break
        if bad:
            hits += 1
    return hits / trials


def proof_no_self_collision():
    """Preuve par enumeration : aucun lambda de profondeur 0..62 n'a un
    SELF egal au code reserve (7,7) — celui-ci n'appartient qu'a d=63."""
    for d in range(MAX_DEPTH):               # 0..62
        assert (d % bd.K_F, (d // bd.K_F) % bd.K_C) != RESERVED
    assert (63 % bd.K_F, (63 // bd.K_F) % bd.K_C) == RESERVED
