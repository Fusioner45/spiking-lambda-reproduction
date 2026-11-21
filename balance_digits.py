# -*- coding: utf-8 -*-
"""Spec executable du compteur de balance POSITIONNEL (chantier B).

Le compteur analogique du papier (§2.5) derive sur les longs corps :
chaque contribution decroit avec tau_m, et sur un corps x^n (prefixe
APP^(n-1) VAR^n) les pulls APP negatifs decroient pendant la plongee —
V depasse la vraie balance pendant la remontee et croise le seuil trop
tot (mesure, corps de 39 tokens, tau_m=1000 : au slot 37 sigma = -1
mais V = +1.495, decharge 2 slots tot ; -10 % a 69, -18 % a 149).

Fix propose (la boite a outils du PAPIER lui-meme) : tenir la meme
balance sur des CHIFFRES CYCLIQUES base 8 — la grille fine+coarse du
ring (§2.7) etendue en marche arriere — avec retenues signees et un
comparateur de coincidence (§2.6). Aucune decroissance analogique : la
valeur vit dans des phases, pas dans des potentiels ; l'erreur par
fenetre est bornee par construction, la retenue la reporte exactement.

Semantique : complement a deux base 8, k chiffres (k=3 couvre
sigma dans [-256, 255] : b^k/2 = 256 ; la famille de stress plonge
a -199). Le
discharge (eq. 7) = sigma atteint +1 pour la premiere fois =
(d0 == 1) et (tous les chiffres superieurs == 0) ; le latch ARG_MODE
(§2.5.1) garde le premier feu.

Le circuit spiking (B-2) devra reproduire, spike par spike, la trace
d'evenements de cette spec : pas de chiffre (VAR +1 / APP -1), retenues
signees par chiffre, feu du comparateur. La marche arriere (APP) est le
seul element mecanique nouveau — le ring du papier n'avance jamais en
arriere ; c'est le prolongement documente, pas une re-attribution.
"""

import bridge_db as bd

N_BASE = 8


def value_of(digits):
    """Valeur signee des chiffres (complement a deux base 8)."""
    k = len(digits)
    v = sum(d * (N_BASE ** i) for i, d in enumerate(digits))
    if v >= N_BASE ** k // 2:              # bit de poids fort = signe
        v -= N_BASE ** k
    return v


class DigitCounter:
    """La balance sigma en chiffres base 8, retenues signees, spec
    step par step. Les evenements (pas de chiffre, retenues, feu du
    comparateur) sont le contrat que le circuit B-2 devra reproduire."""

    def __init__(self, n_digits=3):
        self.digits = [0] * n_digits

    def step(self, kind):
        """Un token du corps : 'var' (+1) ou 'app' (-1). Renvoie le
        dict d'evenements de ce pas (retenues, feu). Le report du
        chiffre de poids fort est le wrap LEGITIME du complement a deux
        (-1 = (...7,7,7) ; +1 -> 0) : il est laisse sortir ; la garde
        d'overflow est la PLAGE du complement a deux, verifiee avant le
        pas (motif de la garde de profondeur de rows_fix)."""
        s = 1 if kind == 'var' else -1
        lim = N_BASE ** len(self.digits) // 2
        v = self.value()
        assert -lim <= v + s < lim, \
            ("overflow du compteur positionnel : k chiffres insuffisants",
             list(self.digits), s)
        carry, i, carries = s, 0, []
        while carry != 0 and i < len(self.digits):
            self.digits[i] += carry
            if self.digits[i] == N_BASE:
                self.digits[i] = 0
                carry, ev = 1, (i, +1)
            elif self.digits[i] == -1:
                self.digits[i] = N_BASE - 1
                carry, ev = -1, (i, -1)
            else:
                carry, ev = 0, None
            if ev is not None:
                carries.append(ev)
            i += 1
        fired = self.digits[0] == 1 and all(d == 0 for d in self.digits[1:])
        return {"carries": carries, "fired": fired,
                "digits": tuple(self.digits)}

    def value(self):
        return value_of(self.digits)


def run_counter(tokens, k_redex, n_digits=3):
    """La spec sur un corps : pas par pas depuis K+2 (meme fenetre que
    IntgCircuit et body_end_pos, K = -1 accepte = le corps du lambda
    seul). Un evenement PAR token du corps (les LAM ne changent pas
    sigma : pas vide — le circuit B-2 devra les traverser sans feu).
    Renvoie la position (relative) du premier feu du comparateur, None
    si jamais, plus la trace complete (contrat B-2)."""
    c = DigitCounter(n_digits)
    trace = []
    for j in range(k_redex + 2, len(tokens)):
        tid = tokens[j][0]
        kind = 'var' if tid >= 4 else ('app' if tid == bd.APP else 'lam')
        ev = c.step(kind) if kind != 'lam' else \
            {"carries": [], "fired": False,
             "digits": tuple(c.digits)}
        trace.append({"j_rel": j - (k_redex + 2), "kind": kind,
                      "carries": ev["carries"], "fired": ev["fired"],
                      "digits": ev["digits"]})
        if ev["fired"]:
            return {"pos": j - (k_redex + 2), "trace": trace}
    return {"pos": None, "trace": trace}
