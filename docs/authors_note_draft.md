# Technical note: independent reproduction of arXiv:2611.23182v1

**Status:** draft for the authors of *Fully Spiking Neural Implementation
of λ-Calculus β-Reduction via Biologically Documented Mechanisms*
(Lazovskiy, Kazantsev, Stasenko, arXiv:2611.23182v1, November 2026).
Everything below was produced by an independent reimplementation; no code
from the authors was available.

## 1. Reference implementation and validation

We reimplemented the complete closed-loop pipeline on simulated LIF
neurons: redex detection (Jeffress delay lines with a WTA latch), subterm
segmentation (INTG_BODY), argument-mode signalling, theta-gamma variable
binding, the phase-ring shift, theta-cycle STDP token copying, and the
PERSIST/GATE/SCAN orchestration of Algorithm 1. A symbolic evaluator
serves as the oracle; every reduction step of the closed loop is checked
against it. The engine follows Section 2.3: exact exponential CUBA-LIF
update, exponential PSCs, axonal delays, and calibrated weights.

The calibration procedure reproduces your measured values exactly:

| ε (mV per unit weight) | paper | ours |
|---|---|---|
| ε(2, 1) | 0.263 | 0.262805516115 |
| ε(10, 2) | 0.137 | 0.137123421277 |
| ε(300, 1) | 0.00344 | 0.003436597478 |

The closed loop normalises the same terms in the same number of reduction
steps as a full normal-order evaluator:

| Term | steps (ours) | steps (paper, §3.2) |
|---|---|---|
| PLUS 1 1 | 6 | 6 |
| MULT 2 2 | 7 | 7 |
| MULT 2 3 | 7 | 7 |
| PRED 3 | 11 | 11 |
| if true (2 I) ω | 8 | 8 |

For `2 I` the reduction trace is 10 → 8 → 5 → 2 tokens (Section 4 below).
A C core of the engine is bit-faithful to the Python engine: identical
calibration values (difference 0.0), identical DET spikes on `2 I`
(single spike at 9.10 ms, 105 INH spikes, K = 0), and identical STDP
weights after learning (difference 0.0). On chains of nested identities
the C core runs the closed loop 3.1x to 9.5x faster than the Python
engine (14 to 449 tokens, 4 to 149 reduction steps).

## 2. Free variables: circuit-level reproduction and a fix (Section 3.3)

Section 3.3 reports that free variables are misclassified when the redex
lambda sits at depth 0. We reproduce this at circuit level: with
BIND = (0, 0) for free variables, the bound-to-redex mask of Section 2.6
marks every free variable of the body as bound. On `(\x. x y) z` the
circuit returns BOUND = [x, y] where only x is bound.

**Fix.** Reserve the phase code (7, 7) for free variables and cap the
useful nesting depth at 62 (your own validation goes up to 25 lambdas).
No extra neurons are needed. A depth-d lookup can then never collide
with (7, 7), which we verified by enumeration over depths 0 to 62. At
circuit level the mask becomes exact on all five open terms we tested,
and closed terms behave identically to the original encoding.

Under 10 % uniform noise on the depth channels, free variables are
protected by the reserved code (0 false bindings in 80 trials), and
adding the FREE_F inhibition described below removes even the residual
p² per free variable.

## 3. INTG_BODY: discharge drift on long subterms (Section 2.5)

The τ_m = 300 ms balance counter accumulates a decayed sum, so its
discharge time matches the true balance only while the decayed negative
residue is small. On `MULT 5 5`, once intermediate terms reach 80 tokens,
the discharge of the argument integrator fires at slot 31 where the true
balance first reaches +1 at slot 65. Both our Python and C engines agree
on this behaviour, so it is a property of the circuit as specified, not
of a particular implementation. Your validation envelope (random terms
of 3 to 14 tokens) stays within the region where the drift is negligible.

Section 2.5 motivates τ_m = 300 ms by the oculomotor line attractor
(Seung 1996), whose recurrent excitation nearly cancels membrane decay;
the paper then writes that the slow τ_m "performs the same role". A
sweep of τ_m shows that simply increasing it recovers the line-attractor
behaviour: for the same 65-token argument, τ_m = 1000 ms and above
discharge exactly at the true slot (τ_m = 3000, 10000, 30000 and 100000
ms all give the same result). The recalibration is analytic, as in your
paper (W_CNT = 1/ε(τ_m, 1)). With τ_m = 1000 ms the closed loop
normalises `MULT 5 5` to Church 25 in 13 steps (83 tokens maximum), which
the τ_m = 300 ms integrator cannot complete.

## 4. Noise on the binding circuit (Section 3.2, block 9)

We ran a Monte-Carlo analysis of the theta-gamma binding circuit under
uniform noise on the phase channels (inactive bits activated with
probability p, active bits preserved, as in Section 3.2). Over 40 trials
per noise level on a term with three bound variables, one variable bound
to a different lambda, and one free variable:

| Noise | exact mask | misses | free variables marked | false bindings |
|---|---|---|---|---|
| 0 % | 40/40 | 0 | 0 | 0 |
| 5 % | 35/40 | 0 | 0 | 5 |
| 10 % | 29/40 | 0 | 0 | 11 |

Three properties hold at every noise level: truly bound variables are
never missed, free variables are never marked (thanks to the reserved
code of Section 2 combined with a FREE_F inhibition pulse on the
integrator), and false bindings stay confined to variables whose phase
differs from the redex lambda by one bit in one channel. The failure
mode is a spurious bit on the lambda's SELF pattern (or on the
variable's BIND pattern) that completes a coincidence. A naive one-hot
WTA decode of the noisy channels removes the false bindings but misses
75 to 92 percent of true bindings (the WTA drops the true bit), so we
did not adopt it; majority voting over repeated presentations or a
hysteresis mechanism look more promising. Since block 9 of your paper
uses one trial per term, we thought a per-variable failure-mode analysis
would be useful for a v2.

## 5. Implementation clarifications and errata

* **Refractory behaviour.** A hard refractory period (membrane potential
  frozen during t_ref) kills every self-sustaining circuit in the paper:
  INH (Section 2.4), PERSIST (Section 2.9) and ARG_MODE (Section 2.5.1)
  all rely on a recurrent EPSP arriving during their own refractory
  period. We use a soft refractory rule (V keeps integrating, capped at
  V_th, spikes blocked) and suggest stating it explicitly in a v2.
* **Effective SCAN delay.** Section 2.10.1 states d = SLOT = 8 ms with an
  actual inter-spike interval of ~4.9 ms. These are incompatible (ISI ≥
  delay). With d = 4 ms we measure an ISI of 4.81 ms, which matches your
  ~4.9 ms and the phase ring of Section 2.7. The text of Section 2.10.1
  likely means d = 4 ms.
* **Theta drive of the copy circuit.** With I_θ = 0.5 the tonic potential
  converges to V = I = 0.5 under your own equation (2), and the W_0 EPSP
  is 3.5 × ε(10,2) = 0.48, so V peaks at 0.98 < 1 and the learning LTP
  cannot trigger as published (Section 2.8 states EPSP ≈ 0.78 and
  V ≈ 0.25). Note that 0.78 corresponds to W ≈ 5.7, which is the weight
  after one or two LTP cycles, so the text probably describes a later
  cycle. We set I_θ = 0.75, the centre of the selectivity window
  (1 − W_0·ε, 1) = (0.52, 1.0), and learning saturates the active
  weights at w_max exactly.
* **Equation (13).** "1.5 × 0.263 = 0.21" evaluates to 0.39. The intended
  SCAN increment of +0.21 corresponds to W_GATE ≈ 0.8.
* **Reduction trace of 2 I.** Our closed loop gives 10 → 8 → 5 → 2 tokens.
  The λx-level intermediate after the first step is λx. (I (I x)), which
  has 8 tokens; the 7 in Section 3.1 may be a typo. The figure files
  (fig1_redex.png, fig2_intg.png, fig3_Ycomb.png, fig4_persist.png) are
  missing from the PDF and HTML of v1, which prevented a figure-level
  cross-check.

## Reference implementation

A self-contained Python implementation (standard library only) plus the
bit-faithful C core, with one validation script per circuit and per
block above, is available with this note. [REPO LINK]

## Contact

[YOUR NAME], [affiliation, email]
