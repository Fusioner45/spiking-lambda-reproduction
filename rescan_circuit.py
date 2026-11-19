# -*- coding: utf-8 -*-
"""v3a : la pile d'INTG du re-scan neural (cf. docs/design_nested_scan.md
et la specification executable rescan_body dans cube_write.py).

Un neurone INTG par niveau ouvert (BODY, chaque LAM, chaque APP),
calibre comme INTG_BODY (§2.5) avec le fix du finding n°8 :
    tau_m = 1000 ms, W_CNT = 1/epsilon(tau_m, 1)   (1 pulse = 1 unite)
Les niveaux externes restent sous le seuil pendant toute la traversee
des sous-termes internes — le regime ou les 300 ms du papier derivent ;
1000 ms est la compensation de fuite validee (session 14 bis).

Semantique (miroir exact de rescan_body) :
  - chaque token emis contribue a TOUS les niveaux ouverts :
    VAR/SKIP -> +W_CNT, APP -> -W_CNT, LAM -> 0 (et l'APP pousse un
    niveau dont l'INTG demarre lui-meme a -W_CNT : il est le premier
    token de son sous-arbre) ;
  - un niveau FERME quand son INTG decharge (spike LIF) ; les
    fermetures simultanees du meme slot se SOMMENT — chaque neurone de
    la pile projette independamment vers le compteur, jamais un
    « -1 par slot actif » (edge case APP f (APP x y) : trois niveaux
    ferment sur le dernier token) ;
  - la profondeur courante = d_lam + nombre de LAM ouverts : le
    compteur est ANCRE a d_lam, le decrement KEEP est l'ancrage.

Frontiere honnete : le gating (quels INTG recoivent les pulses) est
porte par l'injection selective par ports, meme statut que les
injections §2.11 du papier ; le gating synaptique neural est la v3b.
"""

import snn_engine as se

SLOT_MS = 8.0
DT = 0.1


class RescanStack:
    """Pile d'INTG LIF pour le re-scan du corps du redex."""

    def __init__(self, d_lam, tau_m=1000.0, slot_ms=SLOT_MS, dt=DT,
                 net_factory=None):
        self.d_lam = d_lam
        self.slot_ms = slot_ms
        self.dt = dt
        self.tau_m = tau_m
        self.eps = se.measure_epsilon(tau_m, 1.0, dt)
        self.w_cnt = 1.0 / self.eps          # eq. (8) : 1 pulse = 1 unite
        self.net = (net_factory or se.Network)(dt)
        self.levels = []                     # niveaux ouverts (la pile)
        self.all = []                        # tous les niveaux crees
        self.slot = 0
        self.last_closures = 0               # nb de fermetures du dernier slot
        self._push("BODY")                   # le corps lui-meme

    def _add_intg(self):
        if isinstance(self.net, se.Network):
            return self.net.add(se.Neuron(tau_m=self.tau_m, t_ref=0.1,
                                          dt=self.net.dt))
        return self.net.add(self.tau_m, 0.1)

    def _push(self, kind):
        k = len(self.all)
        lv = {"kind": kind, "depth": None, "intg": self._add_intg(),
              "pv": 100 + 2 * k, "pa": 101 + 2 * k, "active": True}
        self.net.connect(lv["pv"], lv["intg"], +self.w_cnt,
                         delay_ms=0.5, tau_syn=1.0)
        self.net.connect(lv["pa"], lv["intg"], -self.w_cnt,
                         delay_ms=0.5, tau_syn=1.0)
        self.levels.append(lv)
        self.all.append(lv)
        return lv

    def _cur(self):
        return self.d_lam + sum(1 for lv in self.levels
                                if lv["kind"] == "LAM")

    def feed(self, kind):
        """Traite un token (kind : 'LAM', 'APP', 'VAR' ou 'SKIP') au slot
        courant. Renvoie la profondeur d'emission du token (self_new) ;
        les fermetures de niveaux déclenchées par ce token sont
        appliquées à la fin du slot."""
        cur = self._cur()
        t0 = self.slot * self.slot_ms
        if kind == "LAM":
            lv = self._push("LAM")           # 0 partout, compteur +1 apres
            lv["depth"] = cur
        elif kind == "APP":
            for lv in self.levels:           # -1 a tous les niveaux ouverts
                self.net.inject_spike(lv["pa"], t0)
            lv = self._push("APP")           # son INTG demarre a -W
            lv["depth"] = cur
            self.net.inject_spike(lv["pa"], t0)
        else:                                # VAR ou SKIP : +1 partout
            for lv in self.levels:
                self.net.inject_spike(lv["pv"], t0)
        # simuler exactement un slot ; les decharges = fermetures
        closed = []
        for _tms, idx in self.net.bulk_run(int(round(self.slot_ms / self.dt))):
            for lv in self.levels:
                if lv["intg"] == idx:
                    closed.append(lv)
        for lv in closed:                    # sommation des simultanees
            lv["active"] = False
            self.levels.remove(lv)
        self.last_closures = len(closed)
        self.slot += 1
        return cur

    def open_lams(self):
        """Profondeur courante selon l'etat de la pile (lecture circuit)."""
        return self._cur()
