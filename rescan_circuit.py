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

v3b-3 : le bus BIND PHYSIQUE par lecture ordinale (piste 2, §2.7 et
§2.9-2.10 assembles) — design propose par l'utilisateur. Chaque niveau
LAM porte : un PERSIST (bistable §2.9, arme au push), un GATE-read
(tonique PERSIST->GATE + pulse de l'onde) et un pos de la chaine de
propagation de l'onde (§2.10 : la chaine descend la pile du sommet vers
la base INDEPENDAMMENT des etats — les niveaux fermes laissent passer
l'onde sans repondre). Une lecture lance une onde au sommet : chaque
LAM actif repond (1 spike), les fermes sont muets, et le comptage PAR
RANG ORDINAL des reponses (meme convention que l'anneau §2.7)
selectionne le (n+1)-ieme = le lieur de VAR(n).

Calibrage du AND (voir calibrate_w_pg) : GATE tau_m=30 / t_ref=2.0 ;
tonique calibre ASYMPTOTIQUEMENT sur 500 ms (le piege de la session 21 :
un transitoire court sous-estime la limite — la somme des queues du
train PERSIST depasse 1.00 vers le slot 40) -> V_peak_inf = 0.80 ;
pulse d'onde +0.78 depuis le creux (fire garanti a ~1.18 sur un GATE
recharge d'1 slot : le cas des 2 VAR consecutifs). SLOT_MS=12 : budget
temporel de l'onde (session 24) — avec 4 LAM sur la chaine (actifs +
fermes qui relayent), le GATE le plus bas repond a ~t0+8.8 ms : le
V_pic=0.97 « mi-force » du slot 15 etait la phase montante TRONQUEE par
la fin du slot a 8 ms, pas un EPSP insuffisant.

Muette des GATE fermes (sessions 22-24) : le HALT du PERSIST + du GATE
(poids verrouille -1.3/epsilon(30,1), le signe perdu en s22 retabli)
est INJECTE A LA FIN DU SLOT de fermeture : les niveaux qui ferment au
meme slot que le VAR repondent encore a l'onde (l'etat d'emission est
lu, lecon de la v3b-2), muets des le slot suivant. MAIS le HALT
one-shot ne protegeait que la PREMIERE onde : le pos ferme relaye
l'onde a chaque slot VAR (+0.78 de w_query sur son propre GATE) et
tau_m=30 ne decaye qu'a ~0.67 par slot — le V des fermes s'accumulait
au-dela du seuil des la 2e onde et polluait l'ordinal en tete de
chaine (slot 16 : b=3 au lieu de 1). Fix session 24 : RE-PINNING du
gh a chaque onde pour tous les niveaux fermes (le MEME poids) — V a
l'arrivee du pulse <= -0.46, muets en permanence.
"""

import snn_engine as se

SLOT_MS = 12.0
DT = 0.1

PV_GLOBAL, PA_GLOBAL = 100, 101            # ports VAR/APP globaux (v3b-1)

_W_PG_CACHE = None                         # calibrage global du tonique


def calibrate_w_pg():
    """Calibration ASYMPTOTIQUE du tonique PERSIST -> GATE-read.

    LE PIEGE qui a coute la session 21 : mesurer V_max sur un
    transitoire court (100-200 ms) sous-estime la valeur limite — avec
    tau_m=30, la somme des queues exponentielles du train PERSIST
    (periode ~2 ms) converge vers son asymptote en ~200 ms (~25 slots),
    et l'asymptote mesurait > 1.00 : le GATE arme depuis 40 slots
    franchissait le seuil SANS onde et cassait le comptage ordinal.

    Le fix : simuler 500 ms SANS onde (60+ slots, regime etabli) et
    fixer W_tonic pour que le PIC asymptotique soit V_peak_inf = 0.80
    (marge 0.20 au seuil, garantie meme sur des termes tres longs).
    Renvoie (w_pg, v_min_inf) : le creux asymptotique sert a calibrer
    W_query (une impulsion d'onde depuis le creux doit porter V >= 1.25
    — fire garanti). Mesure une fois, puis cache."""
    global _W_PG_CACHE
    if _W_PG_CACHE is not None:
        return _W_PG_CACHE
    w = 1.2
    v_min_inf = None
    for _try in range(8):
        net = se.Network(DT)
        trig = 100
        p = net.add(se.Neuron(tau_m=10.0, t_ref=2.0, dt=DT))
        g = net.add(se.Neuron(tau_m=30.0, t_ref=1.0, dt=DT))
        net.connect(trig, p, 9.0, delay_ms=0.2, tau_syn=2.0)
        net.connect(p, p, 9.0, delay_ms=0.1, tau_syn=2.0)
        net.connect(p, g, w, delay_ms=0.5, tau_syn=2.0)
        net.inject_spike(trig, 0.2)
        vmax = vmin = None
        for k in range(int(500.0 / DT)):       # 500 ms : l'asymptote
            net.step()
            if k * DT > 250.0:                 # regime etabli (2e moitie)
                v = net.neurons[g].v
                vmax = v if vmax is None else max(vmax, v)
                vmin = v if vmin is None else min(vmin, v)
        if vmax <= 0.80:
            break
        w *= 0.80 / vmax
    _W_PG_CACHE = (w, vmin)
    return w, vmin


class RescanStack:
    """Pile d'INTG LIF pour le re-scan du corps du redex.

    gating='selective' (v3a) : ports par niveau, injection selective.
    gating='global' (v3b-1) : ports globaux, tous les INTG connectes au
    push, coupure par refractaire long au discharge."""

    def __init__(self, d_lam, tau_m=1000.0, slot_ms=SLOT_MS, dt=DT,
                 net_factory=None, gating="global", max_tokens=64,
                 binder_bus=True):
        self.d_lam = d_lam
        self.slot_ms = slot_ms
        self.dt = dt
        self.tau_m = tau_m
        self.gating = gating
        self.max_tokens = max_tokens
        self.binder_bus = binder_bus         # v3b-3 : bus BIND par onde
        self.eps = se.measure_epsilon(tau_m, 1.0, dt)
        self.w_cnt = 1.0 / self.eps          # eq. (8) : 1 pulse = 1 unite
        self.net = (net_factory or se.Network)(dt)
        self.levels = []                     # niveaux ouverts (la pile)
        self.all = []                        # tous les niveaux crees
        self.slot = 0
        self.last_closures = 0               # nb de fermetures du dernier slot
        if binder_bus:
            self.w_pg, v_min_inf = calibrate_w_pg()   # asymptotique (500 ms)
            # le saut d'onde = 0.78 : un GATE non arme (V=0) atteint 0.78
            # (aucun faux tir), un GATE recharge 1 slot depuis le reset
            # post-spike d'une lecture consecutive (V~0.40) atteint
            # 0.40+0.78=1.18 >= 1 (tir garanti meme sur VAR consecutifs),
            # un GATE etabli (V~0.80) atteint 1.58
            self.w_query = 0.78 / se.measure_epsilon(30.0, 1.0, dt)
            # HALT du GATE dimensionne pour abaisser V <= -0.5 depuis le
            # pire cas (tonique etabli 0.80) : il faut une chute >= 1.3
            # — sinon la queue synaptique residuelle du PERSIST peut
            # maintenir V+0.78 >= 1.0 au slot suivant. NEGATIF : la
            # session 22 a perdu le signe en passant du litteral -30 au
            # poids calcule (+38 = surcharge -> les GATE des lieurs
            # fermes restent a V~0.85 et tirent spontanement)
            self.w_halt_gate = -1.30 / se.measure_epsilon(30.0, 1.0, dt)
            self.last_lam_pos = None         # tete de la chaine de lieurs
            self.last_lam_pos_pq = None      # son port d'injection d'onde
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
        if self.binder_bus:
            # v3b-3 : la chaine de l'onde ne relie QUE les lieurs (LAM ->
            # LAM) — les APP n'ont ni GATE ni pos, l'onde les SAUTE :
            # avec les APP dans la chaine, chaque etage coute ~1.8 ms
            # (delay + latence de franchissement) et les 4 APP d'un corps
            # comme plus 2 3 faisaient deborder la reponse hors du slot
            if kind == "LAM":
                pos = self._add_neuron(5.0, 1.0)
                lv["pos"] = pos
                lv["pq"] = 503 + 4 * k        # port d'injection de l'onde
                self.net.connect(lv["pq"], pos, 9.0, delay_ms=0.2,
                                 tau_syn=1.0)
                if self.last_lam_pos is not None:
                    # l'onde descend vers le lieur cree avant lui (les
                    # fermes restent sur la chaine : muets, l'onde passe)
                    self.net.connect(pos, self.last_lam_pos, 9.0,
                                     delay_ms=1.0, tau_syn=1.0)
                self.last_lam_pos = pos
                self.last_lam_pos_pq = lv["pq"]
                # le lieur : PERSIST (bistable §2.9) + GATE-read (tau_m=30 :
                # lisse les trains du PERSIST — ratio creux/pic 0.93 ;
                # t_ref=2.0 ms < SLOT : peut tirer sur 2 VAR consecutifs)
                pv_idx = self._add_neuron(10.0, 2.0)
                g_idx = self._add_neuron(30.0, 2.0)
                lv["persist"], lv["gate"] = pv_idx, g_idx
                # les familles de ports a stride 4 : sans collision entre
                # elles (le 3k decale d'1 faisait egaler pa_arm(k) et
                # pq(k-1) : chaque armement frappait le pos du lieur
                # precedent -> cascade de faux fires)
                lv["ph"], lv["pa_arm"] = 501 + 4 * k, 500 + 4 * k
                lv["gh"] = 502 + 4 * k        # HALT direct du GATE
                self.net.connect(pv_idx, pv_idx, 9.0, delay_ms=0.1,
                                 tau_syn=2.0)          # auto-entretien (§2.9)
                self.net.connect(lv["pa_arm"], pv_idx, 9.0, delay_ms=0.2,
                                 tau_syn=2.0)          # armement au push
                self.net.connect(lv["ph"], pv_idx, -15.0, delay_ms=0.1,
                                 tau_syn=1.0)          # HALT du PERSIST
                self.net.connect(lv["gh"], g_idx, self.w_halt_gate,
                                 delay_ms=0.1, tau_syn=1.0)
                self.net.connect(pv_idx, g_idx, self.w_pg, delay_ms=0.5,
                                 tau_syn=2.0)          # tonique (mesure)
                self.net.connect(pos, g_idx, self.w_query, delay_ms=0.5,
                                 tau_syn=1.0)          # pulse de l'onde
        self.levels.append(lv)
        self.all.append(lv)
        return lv

    def _add_neuron(self, tau_m, t_ref):
        if isinstance(self.net, se.Network):
            return self.net.add(se.Neuron(tau_m=tau_m, t_ref=t_ref,
                                          dt=self.net.dt))
        return self.net.add(tau_m, t_ref)

    def _cur(self):
        return self.d_lam + sum(1 for lv in self.levels
                                if lv["kind"] == "LAM")

    def feed(self, kind, binder_n=None):
        """Traite un token (kind : 'LAM', 'APP', 'VAR' ou 'SKIP') au slot
        courant. Renvoie (cur, b) : la profondeur d'emission du token
        (self_new), et — si binder_n est passe (pour un VAR) — la
        profondeur du (binder_n+1)-ieme LAM actif lue par l'ONDE
        ordinale du bus BIND (v3b-3) : l'onde part du sommet et descend
        la chaine ; les niveaux actifs repondent (1 spike chacun), les
        fermes sont muets (PERSIST HALTE) ; la (n+1)-ieme reponse est le
        lieur. b=None : moins de n+1 reponses (binder hors corps ou
        variable libre — detection automatique)."""
        cur = self._cur()
        t0 = self.slot * self.slot_ms
        if kind == "LAM":
            lv = self._push("LAM")           # 0 partout, compteur +1 apres
            lv["depth"] = cur
            if self.binder_bus:              # armer le PERSIST du lieur
                self.net.inject_spike(lv["pa_arm"], t0)
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
        # v3b-3 : l'onde de lecture part du lieur le plus interne (le
        # dernier LAM cree — les fermes restent sur la chaine mais muets),
        # DANS le slot du token. Sans lieur du tout dans le corps : pile
        # muette d'office (b=None : variable libre).
        responses = []
        t_query = t0 + 0.6 if binder_n is not None else None
        if binder_n is not None and self.last_lam_pos_pq is not None:
            self.net.inject_spike(self.last_lam_pos_pq, t_query)
            # re-pinning des GATE fermes a CHAQUE onde : leur pos relaye
            # l'onde et leur delivre w_query (+0.78) a chaque slot VAR —
            # le HALT one-shot de fermeture ne protegeait que la 1re onde
            # (tau_m=30 ne decaye qu'a ~0.67 par slot : le V des fermes
            # s'accumule au-dela du seuil des la 2e). Le MEME poids gh
            # (verrouille) les remet sous le seuil avant l'arrivee du
            # pulse ; les niveaux qui vont fermer DANS ce slot restent
            # dans self.levels a ce stade (etat d'emission, lecon v3b-2)
            # et ne sont pas touches.
            for lv in self.all:
                if lv["kind"] == "LAM" and lv not in self.levels:
                    self.net.inject_spike(lv["gh"], t_query)
        # simuler le slot PAS A PAS : les discharges des INTG ferment les
        # niveaux ; le HALT de leur PERSIST est INJECTE A LA FIN DU SLOT
        # (delai de propagation : les lectures du slot voient l'etat
        # d'emission — lecon de la v3b-2) ; les niveaux fermes sont muets
        # des le slot suivant. Le refractaire long garantit au plus une
        # decharge par INTG (le banc le verifie avec lv["closes"]).
        t_halt = t0 + self.slot_ms - 0.1
        by_intg = {lv["intg"]: lv for lv in self.all}
        gate_by_idx = {lv["gate"]: lv for lv in self.all if "gate" in lv}
        label_by_idx = {}
        if self.binder_bus:
            for lv in self.all:
                tag = "%s@%s" % (lv["kind"], lv["depth"])
                if "persist" in lv:
                    label_by_idx[lv["persist"]] = "PERS:" + tag
                    label_by_idx[lv["gate"]] = "GATE:" + tag
                if "pos" in lv:
                    label_by_idx[lv["pos"]] = "POS:" + tag
        closed = []
        slot_spikes = []
        # instrumentation anti-boucle : par GATE (ACTIF ET FERME — les
        # tirs spontanes des fermes corrompent l'ordinal), V juste
        # avant l'onde, V pic du slot, spiked — consomme par le banc
        # en cas d'echec (une impression, arret propre, aucune boucle)
        gate_probe = {lv["gate"]: {"depth": lv["depth"],
                                   "active": lv["active"],
                                   "v_wave": None, "v_peak": None,
                                   "spiked": False}
                      for lv in self.all if "gate" in lv} \
            if (self.binder_bus and binder_n is not None) else {}
        for _ in range(int(round(self.slot_ms / self.dt))):
            spikes = self.net.step()
            t = self.net.k_step * self.dt
            if gate_probe:
                for g_idx_p, rec in gate_probe.items():
                    v = self.net.neurons[g_idx_p].v
                    rec["v_peak"] = v if rec["v_peak"] is None \
                        else max(rec["v_peak"], v)
                    if t >= t_query - 0.2 and rec["v_wave"] is None:
                        rec["v_wave"] = v
            for idx in spikes:
                lv = by_intg.get(idx)
                if lv is not None:
                    lv["closes"] += 1
                    slot_spikes.append((t, "INTG:%s@%s" % (lv["kind"], lv["depth"])))
                    if lv in self.levels:
                        closed.append(lv)
                        if self.binder_bus and "ph" in lv:
                            # HALT du PERSIST (la source du tonique) ET du
                            # GATE lui-meme (effet immediat) — tous deux a
                            # la fin du slot (delaie de propagation)
                            self.net.inject_spike(lv["ph"], t_halt)
                            self.net.inject_spike(lv["gh"], t_halt)
                if self.binder_bus and idx in label_by_idx:
                    slot_spikes.append((t, label_by_idx[idx]))
                if self.binder_bus and idx in gate_by_idx:
                    bad = gate_by_idx[idx]
                    if binder_n is None:
                        raise AssertionError(
                            "faux fire du GATE-read hors onde (t=%.1f, "
                            "niveau %s depth=%s, armee=%s)" %
                            (t, bad["kind"], bad["depth"], bad["active"]))
                    # fenetre de comptage STRICTE : a partir de
                    # l'injection de l'onde uniquement — un fire
                    # pre-onde (tonique frôlant le seuil) est ignore,
                    # jamais compté dans l'ordinal
                    if t >= t_query:
                        responses.append((t, gate_by_idx[idx]))
                if idx in gate_probe:
                    gate_probe[idx]["spiked"] = True
        self.last_gate_vs = [(g_idx_p, rec["depth"], rec["active"],
                              rec["v_wave"], rec["v_peak"], rec["spiked"])
                             for g_idx_p, rec in gate_probe.items()]
        self.last_slot_spikes = slot_spikes
        for lv in closed:                    # sommation des simultanees
            lv["active"] = False
            self.levels.remove(lv)
        self.last_closures = len(closed)
        self.last_responses = [(t, lv["kind"], lv["depth"])
                               for t, lv in responses]
        self.slot += 1
        # comptage PAR RANG ORDINAL des reponses (§2.7) : la (n+1)-ieme
        b = None
        if binder_n is not None:
            if len(responses) > binder_n:
                b = responses[binder_n][1]["depth"]
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
