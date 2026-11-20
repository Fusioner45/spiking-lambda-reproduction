# Design note: a positional balance counter (chantier B)

Status: spec designed and validated differentially (`run_balance.py`);
the spiking circuit is B-2, future work.

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

## Open problems

* The reverse-step circuit: a cyclic digit state driven from both
  directions without ghost transitions (the Section 2.9 gating
  mechanics are the candidate tool).
* The comparator's timing: the coincidence window must span the digit
  settling after a carry chain, not just one slot.
* The C port of the new circuit (both-engine differential as usual).
