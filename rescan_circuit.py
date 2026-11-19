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

Frontiere honnete (v3b-1) : l'injection est GLOBALE — un port VAR et un
port APP pour tous les INTG, connectes au push — et la COUPURE d'un
niveau ferme est portee par la dynamique du neurone lui-meme : au
discharge, l'INTG entre en refractaire long (t_ref couvrant le reste du
scan) et devient sourd a tout pulse suivant (chaque INTG decharge donc
au plus UNE fois — le banc le verifie). Le gating synaptique complet
PERSIST/GATE (la proposition §2.9 : la porte tenue par le PERSIST du
niveau, coupee par le discharge) demande des niveaux pre-creees avec
warmup ou des poids dynamiques : le tonique PERSIST->GATE du papier
monte en tau_syn=20 ms (2,5 slots), trop lent pour nos niveaux
dynamiques de 1-2 slots — question ouverte pour la v3b-2.

Dimensionnement du refractaire : t_ref = slot_ms x (max_tokens + 2)
compte DEPUIS le discharge — un niveau ferme au slot 0 reste sourd
jusqu'a la fin du scan + 2 slots de marge : le pire cas est couvre par
construction, pas de reveil possible avant la fin du parcours.

v3b-2 : la lecture du binder (canal BIND) lit l'ETAT de la pile —
les niveaux actifs, dont les fermetures sont les discharges reels du
circuit — via read_binder(n) : le (n+1)-ieme LAM depuis le sommet a sa
profondeur d'ancrage, None si la pile n'a pas assez de LAM (binder hors
du corps, ou variable libre). Le bus physique a inhibition (chaque LAM
actif projette sa profondeur et inhibe les niveaux LAM sous lui ; le
discharge libere la main au LAM englobant — design propose par
l'utilisateur) est le mecanisme neural cible : sa difficulte de design
(probleme des deux emetteurs quand l'inhibition en chaine se coupe)
est documentee dans docs/design_nested_scan.md pour la v3b-3.
"""

import snn_engine as se

SLOT_MS = 8.0
DT = 0.1

PV_GLOBAL, PA_GLOBAL = 100, 101            # ports VAR/APP globaux (v3b-1)


class RescanStack:
    """Pile d'INTG LIF pour le re-scan du corps du redex.

    gating='selective' (v3a) : ports par niveau, injection selective.
    gating='global' (v3b-1) : ports globaux, tous les INTG connectes au
    push, coupure par refractaire long au discharge."""

    def __init__(self, d_lam, tau_m=1000.0, slot_ms=SLOT_MS, dt=DT,
                 net_factory=None, gating="global", max_tokens=64):
        self.d_lam = d_lam
        self.slot_ms = slot_ms
        self.dt = dt
        self.tau_m = tau_m
        self.gating = gating
        self.max_tokens = max_tokens
        self.eps = se.measure_epsilon(tau_m, 1.0, dt)
        self.w_cnt = 1.0 / self.eps          # eq. (8) : 1 pulse = 1 unite
        self.net = (net_factory or se.Network)(dt)
        self.levels = []                     # niveaux ouverts (la pile)
        self.all = []                        # tous les niveaux crees
        self.slot = 0
        self.last_closures = 0               # nb de fermetures du dernier slot
        self._push("BODY")                   # le corps lui-meme

    def _add_intg(self):
        t_ref = 0.1
        if self.gating == "global":
            # refractaire long : au discharge, le neurone devient sourd
            # jusqu'a la fin du scan (slot_ms par token + marge, mesure
            # depuis le discharge : le pire cas — fermeture au slot 0 —
            # reste sourd jusqu'a la fin + 2 slots)
            t_ref = self.slot_ms * (self.max_tokens + 2)
        if isinstance(self.net, se.Network):
            return self.net.add(se.Neuron(tau_m=self.tau_m, t_ref=t_ref,
                                          dt=self.net.dt))
        return self.net.add(self.tau_m, t_ref)

    def _push(self, kind):
        k = len(self.all)
        lv = {"kind": kind, "depth": None, "intg": self._add_intg(),
              "pv": 100 + 2 * k, "pa": 101 + 2 * k, "active": True,
              "closes": 0}
        if self.gating == "global":
            self.net.connect(PV_GLOBAL, lv["intg"], +self.w_cnt,
                             delay_ms=0.5, tau_syn=1.0)
            self.net.connect(PA_GLOBAL, lv["intg"], -self.w_cnt,
                             delay_ms=0.5, tau_syn=1.0)
        else:
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

    def feed(self, kind, binder_n=None):
        """Traite un token (kind : 'LAM', 'APP', 'VAR' ou 'SKIP') au slot
        courant. Renvoie (cur, b) : la profondeur d'emission du token
        (self_new), et — si binder_n est passe (pour un VAR) — la
        profondeur d'ancrage du (binder_n+1)-ieme LAM actif, lue ENTRE
        l'emission et les fermetures que ce token declenche (le dernier
        token d'un corps ferme toute la pile au meme slot : la lecture
        apres feed() lirait une pile vide). b=None : binder hors corps
        ou variable libre."""
        cur = self._cur()
        t0 = self.slot * self.slot_ms
        if kind == "LAM":
            lv = self._push("LAM")           # 0 partout, compteur +1 apres
            lv["depth"] = cur
        elif kind == "APP":
            if self.gating == "global":
                lv = self._push("APP")       # connecte AVANT le pulse :
                lv["depth"] = cur            # il recoit son -1 initial
                self.net.inject_spike(PA_GLOBAL, t0)
            else:
                for lv in self.levels:       # -1 a tous les niveaux ouverts
                    self.net.inject_spike(lv["pa"], t0)
                lv = self._push("APP")       # son INTG demarre a -W
                lv["depth"] = cur
                self.net.inject_spike(lv["pa"], t0)
        else:                                # VAR ou SKIP : +1 partout
            if self.gating == "global":
                self.net.inject_spike(PV_GLOBAL, t0)
            else:
                for lv in self.levels:
                    self.net.inject_spike(lv["pv"], t0)
        # lecture du binder : l'etat de la pile APRES l'emission du token,
        # AVANT les fermetures qu'il declenche
        b = self.read_binder(binder_n) if binder_n is not None else None
        # simuler exactement un slot ; toute decharge d'un niveau OUVERT =
        # fermeture (les decharges des niveaux deja fermes ne doivent pas
        # exister : le refractaire long rend le niveau sourd — le banc
        # le verifie avec lv["closes"])
        by_intg = {lv["intg"]: lv for lv in self.all}
        closed = []
        for _tms, idx in self.net.bulk_run(int(round(self.slot_ms / self.dt))):
            lv = by_intg[idx]
            lv["closes"] += 1
            if lv in self.levels:
                closed.append(lv)
        for lv in closed:                    # sommation des simultanees
            lv["active"] = False
            self.levels.remove(lv)
        self.last_closures = len(closed)
        self.slot += 1
        return cur, b

    def open_lams(self):
        """Profondeur courante selon l'etat de la pile (lecture circuit)."""
        return self._cur()

    def read_binder(self, n):
        """Lecture v3b-2 du canal BIND depuis l'etat de la pile : la
        profondeur d'ancrage du (n+1)-ieme LAM ACTIF depuis le sommet
        (n = 0 : le lieur le plus proche), ou None si la pile compte
        moins de n+1 LAM actifs — binder hors du corps, ou variable
        libre (la detection des libres est automatique : aucun LAM de
        la pile ne peut les couvrir). Les fermetures de la pile sont
        les discharges reels du circuit : un binder qui a ferme n'est
        plus lisible (et un lieur ne ferme jamais avant sa variable :
        preuve structurelle, le binder englobe le token)."""
        lam_seen = 0
        for lv in reversed(self.levels):
            if lv["kind"] == "LAM":
                if lam_seen == n:
                    return lv["depth"]
                lam_seen += 1
        return None
