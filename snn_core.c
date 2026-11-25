/* snn_core.c — coeur moteur spiking en C plat (item 4 du lab).
   Miroir BIT-FIDELE de snn_engine.py : pour l'egalite spike-a-spike au
   pas pres, la repartition des courants reproduit le BUCKETING du
   Python — un bucket (dst, tau_syn) par paire, cree a la premiere
   arrivee, decaye chaque pas, courant du neurone = somme des buckets
   dans l'ordre d'insertion des taus (ordre du dict Python). Les listes
   de sorties et d'arrivees respectent l'ordre d'append du Python.
   CUBA-LIF solution exacte, E_L=0, V_th=1, V_reset=0, refractaire soft.
   Decroissance d'un bucket inexistant = 0*k = 0 exact : decayre tous les
   slots est equivalent au Python qui ne decayre que les buckets existants. */

#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <stdio.h>
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

#define MAX_TAU 64

typedef struct { int dst, tau_idx, delay; double w; } Syn;
typedef struct { double v, k_m, t, ref_until, t_ref; } Neuron;

typedef struct {
    double dt;
    int n_neur, cap_neur, n_syn, cap_syn;
    Neuron *neur; Syn *syn;
    double *I, *vmax; int vmax_cap;
    double *bucket;                       /* n_neur * MAX_TAU */
    int *tau_count;                       /* par dst */
    int *tau_order;                       /* n_neur * MAX_TAU */
    int cap_I;                            /* neurones couverts par I/bucket */
    int tau_val[MAX_TAU];                 /* tau (ms) par idx */
    double k_tau[MAX_TAU];                /* exp(-dt/tau) par tau */
    int n_tau;
    int out_cap, *out_cnt, *out_capa, **out_data;
    int n_steps_alloc;
    int *arr_cnt, **arr_data, *arr_capa;
    int k_step;
    int *sp_step, *sp_idx; int n_sp, sp_step_cap, sp_idx_cap;
} Net;

static void die_oom(void) {
    fprintf(stderr, "snn_core: out of memory\n");
    exit(1);
}

static void *xgrow(void *p, int *cap, int need, size_t elem) {
    if (need <= *cap) return p;
    int c = *cap ? *cap * 2 : 64;
    while (c < need) c *= 2;
    p = realloc(p, (size_t)c * elem);
    if (!p) die_oom();
    *cap = c;
    return p;
}

EXPORT Net *snn_create(double dt, int n_steps_alloc) {
    Net *net = calloc(1, sizeof(Net));
    net->dt = dt;
    net->n_steps_alloc = n_steps_alloc;
    net->out_cap = 4096;
    net->out_cnt = calloc((size_t)net->out_cap, sizeof(int));
    net->out_capa = calloc((size_t)net->out_cap, sizeof(int));
    net->out_data = calloc((size_t)net->out_cap, sizeof(int *));
    net->arr_cnt = calloc((size_t)(n_steps_alloc + 128), sizeof(int));
    net->arr_capa = calloc((size_t)(n_steps_alloc + 128), sizeof(int));
    net->arr_data = calloc((size_t)(n_steps_alloc + 128), sizeof(int *));
    return net;
}

EXPORT int snn_add_neuron(Net *net, double tau_m, double t_ref) {
    net->neur = xgrow(net->neur, &net->cap_neur, net->n_neur + 1, sizeof(Neuron));
    Neuron *n = &net->neur[net->n_neur];
    n->v = 0.0; n->k_m = exp(-net->dt / tau_m);
    n->t = 0.0; n->ref_until = -1.0; n->t_ref = t_ref;
    net->vmax = xgrow(net->vmax, &net->vmax_cap, net->n_neur + 1, sizeof(double));
    net->vmax[net->n_neur] = 0.0;
    return net->n_neur++;
}

EXPORT int snn_connect(Net *net, int src, int dst, double w,
                       int delay_steps, int tau_ms) {
    /* indices invalides : REFUS sonore (-1, le wrapper leve) — avant, un
       dst hors neurones ecrivait hors du tampon bucket au run, un delai
       negatif n'etait jamais delivre (cle negative), un tau <= 0
       divisait par zero (session 44) */
    if (src < 0 || dst < 0 || dst >= net->n_neur) return -1;
    if (delay_steps < 0 || tau_ms <= 0) return -1;
    if (src >= net->out_cap) {
        /* port source au-dela de la capacite : les tables de sorties
           croissent (comme le dict Python ; avant : synapse creee mais
           JAMAIS declenchee, -1 ignore par le wrapper) */
        int c = net->out_cap ? net->out_cap : 64;
        while (c <= src) c *= 2;
        net->out_cnt = realloc(net->out_cnt, (size_t)c * sizeof(int));
        net->out_capa = realloc(net->out_capa, (size_t)c * sizeof(int));
        net->out_data = realloc(net->out_data, (size_t)c * sizeof(int *));
        if (!net->out_cnt || !net->out_capa || !net->out_data) die_oom();
        memset(net->out_cnt + net->out_cap, 0,
               (size_t)(c - net->out_cap) * sizeof(int));
        memset(net->out_capa + net->out_cap, 0,
               (size_t)(c - net->out_cap) * sizeof(int));
        memset(net->out_data + net->out_cap, 0,
               (size_t)(c - net->out_cap) * sizeof(int *));
        net->out_cap = c;
    }
    net->syn = xgrow(net->syn, &net->cap_syn, net->n_syn + 1, sizeof(Syn));
    Syn *s = &net->syn[net->n_syn];
    /* registre des taus : idx a la premiere rencontre */
    int tau_idx = -1;
    for (int i = 0; i < net->n_tau; i++)
        if (net->tau_val[i] == tau_ms) { tau_idx = i; break; }
    if (tau_idx == -1) {
        if (net->n_tau >= MAX_TAU) return -1;   /* registre plein */
        tau_idx = net->n_tau++;
        net->tau_val[tau_idx] = tau_ms;
        net->k_tau[tau_idx] = exp(-net->dt / (double)tau_ms);
    }
    s->dst = dst; s->tau_idx = tau_idx; s->delay = delay_steps; s->w = w;
    int si = net->n_syn++;
    net->out_data[src] = xgrow(net->out_data[src], &net->out_capa[src],
                               net->out_cnt[src] + 1, sizeof(int));
    net->out_data[src][net->out_cnt[src]++] = si;
    return si;
}

/* Horizon a la demande (session 44) : les arrivees sont indexees par le
   pas ABSOLU. Avant, snn_run s'arretait en silence a n_steps_alloc et
   arr_push ignorait les arrivees au-dela : un reseau C simulait au plus
   n_steps_alloc pas (10 s par defaut) sans le dire — le compteur
   positionnel renvoyait None sur le corps de 599 tokens du profil au
   lieu de 598. Comme le dict d'arrivees du Python : aucune limite. */
static void ensure_steps(Net *net, int idx) {
    if (idx < net->n_steps_alloc + 128) return;
    int c = net->n_steps_alloc > 0 ? net->n_steps_alloc : 256;
    while (c + 128 <= idx) c *= 2;
    size_t old = (size_t)net->n_steps_alloc + 128, neu = (size_t)c + 128;
    net->arr_cnt = realloc(net->arr_cnt, neu * sizeof(int));
    net->arr_capa = realloc(net->arr_capa, neu * sizeof(int));
    net->arr_data = realloc(net->arr_data, neu * sizeof(int *));
    if (!net->arr_cnt || !net->arr_capa || !net->arr_data) die_oom();
    memset(net->arr_cnt + old, 0, (neu - old) * sizeof(int));
    memset(net->arr_capa + old, 0, (neu - old) * sizeof(int));
    memset(net->arr_data + old, 0, (neu - old) * sizeof(int *));
    net->n_steps_alloc = c;
}

static void arr_push(Net *net, int step, int syn) {
    if (step < 0) return;                /* cle negative : jamais delivree */
    ensure_steps(net, step);
    net->arr_data[step] = xgrow(net->arr_data[step], &net->arr_capa[step],
                                net->arr_cnt[step] + 1, sizeof(int));
    net->arr_data[step][net->arr_cnt[step]++] = syn;
}

static void inject(Net *net, int src, int step) {
    /* source inconnue : aucune sortie (comme le dict Python) — avant,
       lecture hors du tampon out_cnt */
    if (src < 0 || src >= net->out_cap) return;
    for (int i = 0; i < net->out_cnt[src]; i++)
        arr_push(net, step + net->syn[net->out_data[src][i]].delay,
                 net->out_data[src][i]);
}

EXPORT void snn_inject(Net *net, int src, int step) { inject(net, src, step); }

static void log_spike(Net *net, int step, int idx) {
    net->sp_step = xgrow(net->sp_step, &net->sp_step_cap, net->n_sp + 1, sizeof(int));
    net->sp_idx = xgrow(net->sp_idx, &net->sp_idx_cap, net->n_sp + 1, sizeof(int));
    net->sp_step[net->n_sp] = step;
    net->sp_idx[net->n_sp] = idx;
    net->n_sp++;
}

EXPORT int snn_k_step(Net *net) { return net->k_step; }
void snn_alloc_I(Net *net);
void snn_grow_I(Net *net);

EXPORT void snn_run(Net *net, int n_steps) {
    if (!net->I) snn_alloc_I(net);
    else if (net->cap_I < net->cap_neur) snn_grow_I(net);
    for (int s = 0; s < n_steps; s++, net->k_step++) {
        int st = net->k_step;
        ensure_steps(net, st);
        /* decay des buckets existants (ordre dst puis tau d'insertion ;
           un bucket a zero decaye reste a zero exactement) */
        for (int d = 0; d < net->n_neur; d++)
            for (int j = 0; j < net->tau_count[d]; j++) {
                int t = net->tau_order[d * MAX_TAU + j];
                net->bucket[d * MAX_TAU + t] *= net->k_tau[t];
            }
        /* arrivees de ce pas, dans l'ordre d'append (comme le Python) */
        for (int i = 0; i < net->arr_cnt[st]; i++) {
            int si = net->arr_data[st][i];
            Syn *sy = &net->syn[si];
            int d = sy->dst, t = sy->tau_idx;
            int seen = 0;
            for (int j = 0; j < net->tau_count[d]; j++)
                if (net->tau_order[d * MAX_TAU + j] == t) { seen = 1; break; }
            if (!seen)
                net->tau_order[d * MAX_TAU + net->tau_count[d]++] = t;
            net->bucket[d * MAX_TAU + t] += sy->w;
        }
        net->arr_cnt[st] = 0;
        /* courants : somme des buckets dans l'ordre d'insertion des taus */
        memset(net->I, 0, (size_t)net->n_neur * sizeof(double));
        for (int d = 0; d < net->n_neur; d++) {
            double acc = 0.0;
            for (int j = 0; j < net->tau_count[d]; j++)
                acc += net->bucket[d * MAX_TAU + net->tau_order[d * MAX_TAU + j]];
            net->I[d] = acc;
        }
        /* neurones */
        for (int i = 0; i < net->n_neur; i++) {
            Neuron *n = &net->neur[i];
            int refrac = n->t < n->ref_until;
            double v_new = n->v * n->k_m + net->I[i] * (1.0 - n->k_m);
            int spiked = 0;
            if (refrac) {
                n->v = v_new < 1.0 ? v_new : 1.0;
            } else if (v_new >= 1.0) {
                n->v = 0.0;
                n->ref_until = n->t + n->t_ref;
                spiked = 1;
            } else {
                n->v = v_new;
            }
            n->t += net->dt;
            if (n->v > net->vmax[i]) net->vmax[i] = n->v;
            if (spiked) { log_spike(net, st, i); inject(net, i, st); }
        }
    }
}

EXPORT void snn_reset(Net *net) {
    net->k_step = 0;
    net->n_sp = 0;
    /* bucket (et I) sont alloues au premier snn_run — un reset AVANT
       tout run ne doit pas memset un pointeur NULL (revue externe :
       access violation). Les champs deja alloues sont remis a zero. */
    if (net->bucket) {
        memset(net->bucket, 0, (size_t)net->n_neur * MAX_TAU * sizeof(double));
    }
    for (int i = 0; i < net->n_neur; i++) {
        net->neur[i].v = 0.0;
        net->neur[i].t = 0.0;
        net->neur[i].ref_until = -1.0;
        net->vmax[i] = 0.0;
    }
    /* ordre des buckets remis a zero : un reset = un reseau NEUF (l'ordre
       d'insertion des taus fixe l'ordre de sommation des courants ; il
       restait celui du run precedent) */
    if (net->tau_count)
        memset(net->tau_count, 0, (size_t)net->cap_I * sizeof(int));
    for (int st = 0; st < net->n_steps_alloc + 128; st++) net->arr_cnt[st] = 0;
}

EXPORT int snn_n_spikes(Net *net) { return net->n_sp; }
EXPORT void snn_spike(Net *net, int i, int *step, int *idx) {
    if (i < 0 || i >= net->n_sp) { *step = -1; *idx = -1; return; }
    *step = net->sp_step[i]; *idx = net->sp_idx[i];
}
EXPORT double snn_v(Net *net, int i) {
    if (i < 0 || i >= net->n_neur) return NAN;   /* indice invalide : visible */
    return net->neur[i].v;
}
EXPORT double snn_vmax(Net *net, int i) {
    if (i < 0 || i >= net->n_neur) return NAN;
    return net->vmax[i];
}
EXPORT void snn_alloc_I(Net *net) {
    int cap = net->cap_neur ? net->cap_neur : 16;
    net->I = calloc((size_t)cap, sizeof(double));
    net->bucket = calloc((size_t)cap * MAX_TAU, sizeof(double));
    net->tau_count = calloc((size_t)cap, sizeof(int));
    net->tau_order = calloc((size_t)cap * MAX_TAU, sizeof(int));
    if (!net->I || !net->bucket || !net->tau_count || !net->tau_order)
        die_oom();
    net->cap_I = cap;
}

/* Neurones ajoutes APRES un premier run ( pile construite au fil du
   scan) : les courants/buckets couvraient seulement la capacite du
   premier pas — au-dela, ecriture hors tampon. Les lignes existantes
   sont conservees (courants en cours), les nouvelles sont nulles. */
EXPORT void snn_grow_I(Net *net) {
    int cap = net->cap_neur ? net->cap_neur : 16, old = net->cap_I;
    if (cap <= old) return;
    double *I = calloc((size_t)cap, sizeof(double));
    double *bucket = calloc((size_t)cap * MAX_TAU, sizeof(double));
    int *tau_count = calloc((size_t)cap, sizeof(int));
    int *tau_order = calloc((size_t)cap * MAX_TAU, sizeof(int));
    if (!I || !bucket || !tau_count || !tau_order) die_oom();
    memcpy(I, net->I, (size_t)old * sizeof(double));
    memcpy(bucket, net->bucket, (size_t)old * MAX_TAU * sizeof(double));
    memcpy(tau_count, net->tau_count, (size_t)old * sizeof(int));
    memcpy(tau_order, net->tau_order, (size_t)old * MAX_TAU * sizeof(int));
    free(net->I); free(net->bucket); free(net->tau_count); free(net->tau_order);
    net->I = I; net->bucket = bucket; net->tau_count = tau_count;
    net->tau_order = tau_order;
    net->cap_I = cap;
}

/* ---- banc de copie STDP one-shot (§2.8) : N paires plastiques ----
   Replication BIT-FIDELE de copy_stdp.CopyBench : N neurones DST
   (tau_m=10, t_ref=2), synapses diagonales plastiques w[k] mutables,
   traces pre/post (tau 12 ms), A+=1.2 LTP-only, w_max=8, tonique
   I_theta sur tous les DST pendant l'apprentissage. Ordre du pas
   identique au Python : decay g/traces -> arrivees -> pre programmE ->
   neurones -> delta W au spike post (trace pre d'AVANT l'increment du
   pas) -> trace_post=1 (apres) -> trace_pre=1 (pre, en dernier). */

typedef struct {
    double *w, *g, *tpre, *tpost, *v, *ref_until, *t;
    double i_theta, k_tr, k_syn, k_m, dt;
    int n;
    int *pre_cnt, **pre_data, *pre_capa;
    int *ar_cnt, **ar_data, *ar_capa;
    int k_step, n_steps_alloc;
    int *sp_step, *sp_k; int n_sp, sp_step_cap, sp_k_cap;
} Copy;

EXPORT Copy *cp_create(int n, double i_theta, double dt, int n_steps_alloc) {
    Copy *c = calloc(1, sizeof(Copy));
    c->n = n; c->i_theta = i_theta; c->dt = dt;
    c->n_steps_alloc = n_steps_alloc;
    c->w = calloc((size_t)n, sizeof(double));
    c->g = calloc((size_t)n, sizeof(double));
    c->tpre = calloc((size_t)n, sizeof(double));
    c->tpost = calloc((size_t)n, sizeof(double));
    c->v = calloc((size_t)n, sizeof(double));
    c->ref_until = calloc((size_t)n, sizeof(double));
    c->t = calloc((size_t)n, sizeof(double));
    for (int k = 0; k < n; k++) c->w[k] = 3.5;          /* W_0 (§2.8) */
    c->k_tr = exp(-dt / 12.0);
    c->k_syn = exp(-dt / 2.0);
    c->k_m = exp(-dt / 10.0);
    int nb = n_steps_alloc + 128;
    c->pre_cnt = calloc((size_t)nb, sizeof(int));
    c->pre_data = calloc((size_t)nb, sizeof(int *));
    c->pre_capa = calloc((size_t)nb, sizeof(int));
    c->ar_cnt = calloc((size_t)nb, sizeof(int));
    c->ar_data = calloc((size_t)nb, sizeof(int *));
    c->ar_capa = calloc((size_t)nb, sizeof(int));
    return c;
}

/* horizon a la demande du banc de copie (meme defaut que le reseau :
   cp_run s'arretait en silence a n_steps_alloc, et cp_push ecrivait
   SANS CONTROLE hors des tampons pour un spike programme au-dela) */
static void cp_ensure(Copy *c, int idx) {
    if (idx < c->n_steps_alloc + 128) return;
    int n = c->n_steps_alloc > 0 ? c->n_steps_alloc : 256;
    while (n + 128 <= idx) n *= 2;
    size_t old = (size_t)c->n_steps_alloc + 128, neu = (size_t)n + 128;
    c->pre_cnt = realloc(c->pre_cnt, neu * sizeof(int));
    c->pre_capa = realloc(c->pre_capa, neu * sizeof(int));
    c->pre_data = realloc(c->pre_data, neu * sizeof(int *));
    c->ar_cnt = realloc(c->ar_cnt, neu * sizeof(int));
    c->ar_capa = realloc(c->ar_capa, neu * sizeof(int));
    c->ar_data = realloc(c->ar_data, neu * sizeof(int *));
    if (!c->pre_cnt || !c->pre_capa || !c->pre_data ||
        !c->ar_cnt || !c->ar_capa || !c->ar_data) die_oom();
    memset(c->pre_cnt + old, 0, (neu - old) * sizeof(int));
    memset(c->pre_capa + old, 0, (neu - old) * sizeof(int));
    memset(c->pre_data + old, 0, (neu - old) * sizeof(int *));
    memset(c->ar_cnt + old, 0, (neu - old) * sizeof(int));
    memset(c->ar_capa + old, 0, (neu - old) * sizeof(int));
    memset(c->ar_data + old, 0, (neu - old) * sizeof(int *));
    c->n_steps_alloc = n;
}

/* which = 0 : spikes pre programmes ; 1 : arrivees. Les pointeurs des
   tableaux sont relus APRES la croissance (realloc peut les deplacer). */
static void cp_push(Copy *c, int which, int step, int k) {
    if (step < 0) return;
    cp_ensure(c, step);
    int **data = which ? c->ar_data : c->pre_data;
    int *capa = which ? c->ar_capa : c->pre_capa;
    int *cnt = which ? c->ar_cnt : c->pre_cnt;
    data[step] = xgrow(data[step], &capa[step], cnt[step] + 1, sizeof(int));
    data[step][cnt[step]++] = k;
}

EXPORT void cp_schedule_src(Copy *c, int k, int step) {
    if (k < 0 || k >= c->n) return;
    cp_push(c, 0, step, k);
}

EXPORT void cp_run(Copy *c, int n_steps, int tonic_on) {
    for (int s = 0; s < n_steps; s++, c->k_step++) {
        int st = c->k_step;
        cp_ensure(c, st + 5);          /* avant de capturer pre_data[st] */
        for (int k = 0; k < c->n; k++) {
            c->g[k] *= c->k_syn;
            c->tpre[k] *= c->k_tr;
            c->tpost[k] *= c->k_tr;
        }
        for (int i = 0; i < c->ar_cnt[st]; i++) {
            int k = c->ar_data[st][i];
            c->g[k] += c->w[k];
        }
        c->ar_cnt[st] = 0;
        int npre = c->pre_cnt[st];
        int *prek = c->pre_data[st];
        for (int i = 0; i < npre; i++)
            cp_push(c, 1, st + 5, prek[i]);
        double tonic = tonic_on ? c->i_theta : 0.0;
        for (int k = 0; k < c->n; k++) {
            int refrac = c->t[k] < c->ref_until[k];
            double i = c->g[k] + tonic;
            double v_new = c->v[k] * c->k_m + i * (1.0 - c->k_m);
            int spiked = 0;
            if (refrac) {
                c->v[k] = v_new < 1.0 ? v_new : 1.0;
            } else if (v_new >= 1.0) {
                c->v[k] = 0.0;
                c->ref_until[k] = c->t[k] + 2.0;
                spiked = 1;
            } else {
                c->v[k] = v_new;
            }
            c->t[k] += c->dt;
            if (spiked) {
                double w = c->w[k] + 1.2 * c->tpre[k];
                c->w[k] = w < 8.0 ? w : 8.0;
                c->tpost[k] = 1.0;
                c->sp_step = xgrow(c->sp_step, &c->sp_step_cap,
                                   c->n_sp + 1, sizeof(int));
                c->sp_k = xgrow(c->sp_k, &c->sp_k_cap, c->n_sp + 1, sizeof(int));
                c->sp_step[c->n_sp] = st;
                c->sp_k[c->n_sp] = k;
                c->n_sp++;
            }
        }
        for (int i = 0; i < npre; i++) c->tpre[prek[i]] = 1.0;
    }
}

EXPORT void cp_reset(Copy *c) {
    c->k_step = 0;
    c->n_sp = 0;
    for (int k = 0; k < c->n; k++) {
        c->w[k] = 3.5; c->g[k] = 0.0;
        c->tpre[k] = 0.0; c->tpost[k] = 0.0;
        c->v[k] = 0.0; c->ref_until[k] = -1.0; c->t[k] = 0.0;
    }
    for (int st = 0; st < c->n_steps_alloc + 128; st++) {
        c->pre_cnt[st] = 0; c->ar_cnt[st] = 0;
    }
}

EXPORT double cp_weight(Copy *c, int k) {
    if (k < 0 || k >= c->n) return NAN;   /* indice invalide : visible */
    return c->w[k];
}
EXPORT void cp_set_weight(Copy *c, int k, double w) {
    if (k < 0 || k >= c->n) return;
    c->w[k] = w;
}
EXPORT int cp_n_spikes(Copy *c) { return c->n_sp; }
EXPORT void cp_spike(Copy *c, int i, int *step, int *k) {
    if (i < 0 || i >= c->n_sp) { *step = -1; *k = -1; return; }
    *step = c->sp_step[i]; *k = c->sp_k[i];
}
EXPORT void cp_free(Copy *c) {
    for (int st = 0; st < c->n_steps_alloc + 128; st++) {
        free(c->pre_data[st]); free(c->ar_data[st]);
    }
    free(c->pre_cnt); free(c->pre_data); free(c->pre_capa);
    free(c->ar_cnt); free(c->ar_data); free(c->ar_capa);
    free(c->w); free(c->g); free(c->tpre); free(c->tpost);
    free(c->v); free(c->ref_until); free(c->t);
    free(c->sp_step); free(c->sp_k);
    free(c);
}

EXPORT void snn_free(Net *net) {
    for (int i = 0; i < net->out_cap; i++) free(net->out_data[i]);
    for (int st = 0; st < net->n_steps_alloc + 128; st++) free(net->arr_data[st]);
    free(net->out_cnt); free(net->out_capa); free(net->out_data);
    free(net->arr_cnt); free(net->arr_capa); free(net->arr_data);
    free(net->neur); free(net->syn); free(net->I); free(net->vmax);
    free(net->bucket); free(net->tau_count); free(net->tau_order);
    free(net->sp_step); free(net->sp_idx);
    free(net);
}
