# Design note: a positional balance counter (chantier B)

Status: spec, spiking circuit AND closed-loop integration designed
and validated differentially (`run_balance.py`, both engines).

## The measured defect of the analog counter

The paper's balance counter (Section 2.5) is one slow LIF neuron
integrating +W_CNT per VAR and -W_CNT per APP, with
W_CNT = 1/epsilon(tau_m, 1). Its membrane potential lags the true
balance because every past contribution decays by the membrane time
constant. On the worst-case body shape (the x^n chain: prefix
APP^(n-1) VAR^n, the balance dives to -n and climbs back to +1 on the
last token), the negative APP pulls decay while the balance sits deep,
so the potential climbs ABOVE the true balance during the recovery and
crosses the firing threshold before the balance does.

Measured at tau_m = 1000 ms (the recalibrated variant), on the x^20
body of 39 tokens: at slot 37 the true balance is -1 while the
potential is +1.495; the discharge lands two slots early. The error
grows with the dive depth times the span: -7 slots at 69 tokens, -27
at 149. Raising tau_m cannot fix this: the loss is
exp(-span / tau_m), so exactness would need tau_m to grow with the
term size, which is not a constant parameter.

## The design: digits instead of potentials

The paper's own Section 2.7 already holds arithmetic exactly on a
two-digit phase grid (fine phases plus coarse carry, grid 1000/1000):
the information lives in cyclic PHASES, not in decaying potentials. We
apply the same idea to the balance counter:

* **Digits.** The balance is held as signed base-8 digits (two's
  complement, k digits; k = 3 covers sigma in [-128, 127], beyond the
  deepest measured dive of -74). Each digit is a cyclic state with 8
  values, advanced by one step per VAR (+1) or APP (-1).
* **Signed carries.** Crossing 7 -> 0 emits a +1 carry to the next
  digit; crossing 0 -> 7 emits a -1 carry. Carries propagate upward
  and are discrete: no analog quantity crosses the digit boundary.
* **Comparator.** The discharge (eq. 7: the balance reaches +1 for the
  first time) is a coincidence test in the Section 2.6 sense:
  (fine digit == 1) AND (every higher digit == 0). During a dive past
  -8 the fine digit also passes through 1 (sigma = -7 reads
  d0 = 1, d1 = 7), and the higher-digit condition rejects exactly
  those states. The first fire latches (the Section 2.5.1 ARG_MODE).

No analog quantity accumulates across the span: the per-window error
is bounded by construction and the carries report it exactly. The
discharge position is exact wherever the analog counter drifts:
measured on the same family, the spec is exact at 3, 15, 39, 69 and
149 tokens while the analog counter lands at 3, 15, 37, 62 and 122.

The exactness claim is differential and binary: on every reduction
step of the validation battery (113 cases: plus, mult, pred,
conditionnal structure, combinator terms, an open term) and on the
stress family, the spec's discharge position equals the semantic
truth (`body_end_pos`), and the digit value equals the direct balance
at every step.

## The one new mechanical element, stated honestly

The paper's ring only advances: shifts are +sh, phases step one way.
The balance counter must also step BACKWARD (each APP is a -1 step).
Reverse stepping is the single new mechanical element of this design;
it is a documented extension of the Section 2.7 mechanics, not a
re-attribution of anything in the paper. The comparator reuses the
Section 2.6 coincidence mechanics; the latch reuses Section 2.5.1.

## The event contract for the circuit (B-2)

`balance_digits.run_counter` emits, per body token, the event trace
the spiking circuit must reproduce spike by spike: the digit steps
(VAR/APP/LAM pass), the signed carry events per digit, and the
comparator fire. Measured contract on the x^20 body: 39 steps, 5
upward and 5 downward carries, exactly one comparator fire at step 38
with digits (1, 0, 0). The bench asserts these counts.

## The circuit (B-2, validated)

`balance_circuit.py` implements the spec with the paper's primitives:

* **Digits.** 8 one-hot PERSIST neurons per digit (Section 2.9:
  tau_m = 10, t_ref = 2, recurrent 9, ~483 Hz measured, ignition
  >= 1.0, HALT -15 extinction). Exactly one active; the state holds
  between tokens with no decay (the information lives in WHO fires,
  not in an integrated potential).
* **Transitions.** 8 T+ and 8 T- neurons per digit (tau_m = 10) read
  the current state through the P's FAST spike trains (tau_syn = 2,
  V_ss = 0.97 x weight, smooth) and fire on the VAR/APP broadcast
  pulse (+0.74 over the 0.78 train): train alone < 1, train + pulse
  > 1. Fire -> HALT the current P, ignite the neighbor.
* **Carries.** Only the wrap neurons (T+[7], T-[0]) re-arm the next
  digit's broadcast: the higher digits step ONLY on carries (the
  paper's own coarse-register rule). Feeding the broadcast to the
  higher digits' wrap neurons directly lets them fire on every token
  (measured: the comparator accumulates and fires at slot 8 instead
  of 14): the restriction is load-bearing.
* **Comparator.** No analog sum: the comparator fires on the T+[0]
  spike (the VAR 0->1 transition of the fine digit, the only path to
  sigma = +1) UNLESS inhibited by any non-zero state of the higher
  digits (the 14 P of d1.P[1..7], d2.P[1..7] inhibit). The false
  T+[0] spikes (sigma -8 -> -7, +8 -> +9) see d1 or d2 non-zero and
  are inhibited; d1 = d2 = 0 offers no inhibition. Exact by
  construction.
* **Timing.** The counter runs its own 25 ms/token clock (a free
  parameter): the fresh P's train reaches 70 percent within one slot,
  the dead P's train tail is gone, and all the analog margins are
  >= 0.14. At the 8 ms token clock the margins close (measured: the
  machine lags one slot, then freezes).
* **Validation.** The differential against the spec is slot-by-slot
  on both engines: digits, carries and the discharge position match
  on x^8, x^20, I I, 2 I and the open term (10 cases). The discharge
  positions are exact where the analog counter drifts by 2 to 27
  slots.

## The closed-loop integration (B-3, validated)

The loop's `balance_counter` mode replaces the analog IntgCircuit for
the segmentation: the positional counter computes l_body and l_arg
(25 ms/token of simulated time, its own clock). The oracle checks of
the loop (l_body == truth, l_arg == truth) pass on every step.
Results at the PAPER'S parameters (tau_m = 300, no recalibration):

* PLUS 2 3: 6 reductions, Church 5 (the paper's trace);
* PLUS 9 8: 6 reductions, Church 17, the case the analog counter
  REFUSES at tau_m = 300 (finding 8's falsifiable envelope);
* PLUS 16 16: 6 reductions, Church 32, the case that needed the
  tau_m >= 1000 recalibration.

The finding-8 limitation is removed at the paper's own parameters.
The mult 5 5 case runs to completion: 13 reductions to Church 25,
both engines, trace and normal form equal to the oracle, with exact
segmentation on terms up to 83 tokens. (An earlier draft of this note
reported a halt at the DET circuit's term span; that attribution was
wrong: a direct probe shows the DET exact up to 1002-token terms, and
the observed halt was the validation harness's own 8-step default.)

## Open problems

* Deeper dives: the k = 3 digits cover [-128, 127]; a wider range is
  a digit-count change, but the carries cascade through the chain
  and their timing budget grows with it.
