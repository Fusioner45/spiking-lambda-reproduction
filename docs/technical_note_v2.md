# Technical Note v2: living working-memory cube, neural rescan, and temporal multiplexing in an independent spiking-lambda reduction

Follow-up to our first technical note on the independent reproduction of
arXiv:2611.23182v1. This note covers the extensions built on top of the
reproduction: the living working-memory cube, the neural rescan with the
ordinal BIND bus, and a temporal-multiplexing write architecture. All
mechanisms are validated by differential banks against symbolic references,
on the same engine, at bit-exact learned-weight equality.

Repository: https://github.com/Fusioner45/spiking-lambda-reproduction
(MIT, continuous integration, 20 validation banks).

To keep the scientific bookkeeping clean, the results below are sorted into
three categories: **Reproduction** (behaviors matching the paper's
mechanisms and parameters), **Corrections** (defects of the published model
identified experimentally, and recalibrated variants), and **Extensions**
(architectures we added beyond the paper). We do not attribute our own
additions to the paper.

## 1. Reproduction and identified discrepancies

The reproduction covers the seven circuits of Section 2 (det, balance
counter, theta-gamma binding, phase ring, STDP copy, persist/gate/scan) and
the Algorithm 1 orchestration, in pure Python with a bit-faithful C core for
the hot path. The calibration reproduces the paper's epsilon values to four
digits, five step counts match the paper's Table 3 exactly, and the closed
loop reduces PLUS 2 3 to Church 5 in exactly 6 steps. The first note
documents the findings; the repository README tracks the current status.

Corrections measured since the first note:

* **Balance-counter envelope (finding 8, extended).** The paper's balance
  counter uses tau_m = 300 ms and its envelope is limited: on a term of
  9 applied to 8 the counter fails (the loop refuses to compute a wrong
  result and stops). A recalibrated variant with tau_m >= 1000 ms extends
  the envelope: 16+16 reduces to Church 32 with exact traces. Both
  parameterizations remain runnable: 300 ms is the default (fidelity), the
  recalibrated value is opt-in per loop. On very wide bodies the residual
  horizontal drift is measured and monotone with size (about 5 percent at
  39 tokens, 10 percent at 69, 18 percent at 149 on the x^n shape).
* **Free-variable index.** The published encoding binds free variables to
  a reserved phase code and drops their index. The fix combines the
  reserved code with two index channels in the slot encoding, is
  collision-free up to depth 62, and is validated circuit-level under
  10 percent phase noise.

## 2. Living working-memory cube (Extension)

The next reduction's token cube is written slot by slot by the STDP copy
circuits and read back through recall dynamics: the tokens consumed by the
next step come out of the copy memories, not out of a symbolic
re-encoding. Each slot stores 7 phase channels (the 4 paper channels, a
type channel, and 2 free-index channels) -- an extension of the paper's
encoding, which carries the type on distinct populations and drops the
free-variable index.

Corruption is detected at readout (a muted channel stops the loop). An
interruption test goes further: after k steps, the cube is rebuilt from
the captured STDP weights alone (no symbolic state), the term is read back
from the memories, and the reduction continues. The continuation trace and
the final normal form are identical to the uninterrupted reference. The
cube memories alone carry the full state needed to resume.

Status: the neural write path closes the loop bit-exactly for CLOSED terms
(pure combinators, Church numerals, complete reductions). Terms with
variables bound outside the redex keep a meta-controller free-index
decrement (the scan cannot see binders above the body), so the state is
closed-complete, hybrid on external free-variable indices.

## 3. Neural rescan and ordinal BIND bus (Extension)

The KEEP decrement of Section 2.10.3 is realized by a neural rescan: one
balance-counter instance per open level (tau_m = 1000 ms), the counter
anchored at the redex lambda's depth (the anchoring IS the decrement: no
minus-one rule is applied anywhere), and the binder depths read by an
ordinal wave: a chain descends the level stack, active gate-read neurons
answer once, closed ones relay without answering, and the (n+1)-th answer
in ordinal order is the binder.

Two limit regimes are measured:

* Depth scaling. The wave budget grows linearly with the chain length
  (about 1.8 ms per level). With the nominal 12 ms slot the ordinal read
  holds to depth 6; beyond it the outermost response falls out of the slot
  and the read returns None (detectable, not silent). With the slot scaled
  to the linear budget, reads are exact to depth 64 with a
  depth-independent margin (4.3 to 4.4 ms at depths 8, 16, 32 and 64).
* 100 consecutive binder reads of a stable level: all exact, and the
  closed gates stay muted against the analytic re-pinning bound (max
  membrane potential at wave arrival -0.363 versus the -0.46 bound; zero
  firings over the whole series).

## 4. Temporal multiplexing (Extension, an alternative to Section 2.10.2)

The paper's Section 2.10.2 creates one nested-SCAN chain per bound
variable occurrence (O(n_bound) chains, staggered delays). We implement an
alternative: ONE temporal chain shared by all occurrences, every
destination bank learning its ring-routed pattern during the shared
windows, with per-tap gates selecting the learning window. The learned
weights are bit-exact against the per-occurrence write on both engines,
and invariant under the tap creation order.

The formal cost comparison measures both modes at bit-exact output and
final-weight equality, with the costs sorted into three categories:

| Cost category | What is counted | Sequential | Multiplexed |
| --- | --- | --- | --- |
| Dynamic | simulated theta cycles | n_slots x 6 | (n_direct + l_arg) x 6 |
| Dynamic | SRC events | n_slots x 42 | (n_direct + l_arg + n_arg) x 42 |
| Dynamic | DST spikes | measured, identical | measured, identical |
| Structural | neurons, synapses | unchanged | unchanged (+1 chain emitter) |
| Temporal | wall-clock | reported separately | reported separately |

Two honest caveats. First, the multiplexed mode's SRC events include the
routing relays (materialized as re-scheduled events in our harness); in a
physical realization they would be the same spikes arriving through gates.
Second, the simulated cycles are simulation time: the wall-clock is engine
overhead (our Python harness serializes the biologically parallel banks,
so its wall-clock is higher), and the two are never summed.

## 5. Neural GATE_BOUND (Extension, preliminary)

The window selection itself is then moved into neurons: every tap receives
every window through its routed projection tables (wiring laid down at
creation from the ring-composed patterns), and a LIF gate per tap
(Section 2.9 mechanics: arm current during its own window) selects what is
learned. The SRC events drop to the theoretical minimum (the chain's raw
emission only): the routing relays of the previous table become wiring,
counted as a resource (n_arg x l_arg x 7 routing-table entries).

This block is preliminary: the reference implementation is Python-only.
The production write path still uses the event-based multiplexed chain on
both engines; the C port with a per-step gated tonic is future work.

## 6. Ablations and noise robustness

**Ablations.** Disabling one circuit at a time (det, balance counters,
binding, phase ring, rescan; the STDP copy is covered by the in-loop
sabotage): every ablation is caught at the expected cross-check site of
the loop, across three term families (a baseline, a term with an
out-of-body binder, a term with simultaneous closures). The reduction
never computes a silently wrong result: it stops. This establishes the
necessity of each circuit within our architecture and scenarios, not a
universal claim.

**Noise.** The binding circuit's sensitivity to one-bit phase noise
(finding 9) has a measured mitigation: a majority vote over repeated
multi-bit presentations, with independent noise draws. At 5 percent noise
the false bindings are eliminated at k=7 (0/100 trials); at 10 percent
they are halved (about 21-28 per 100 to 9-11 per 100) with a structural
residual (positions one bit away from the lambda re-fire often). The rare
free-variable marking at 10 percent (1/100 at a single presentation) is
crushed from k=3. Misses stay at zero everywhere: the noise only adds
bits, a true coincidence fires in every presentation, and the majority
cannot lose one. The cost is k times the presentation duration. The
zero-count results carry a rule-of-three bound (0/100 gives p_max about 3
percent), not a hard guarantee; a larger multi-seed study is future work.

## 7. Limitations and open problems

* The meta-controller still owns: the initial encoding, the topographic
  output ordering, the halt check, and the free-index decrement. The
  paper's own meta-controller owns the same first items; the quantification
  of what is neural versus symbolic per reduction step is documented in the
  repository.
* The multiplexed mode's routing relays: in the event-based variant they
  are re-scheduled events; the neural GATE_BOUND block moves them to
  wiring, and the C port of that block (with per-step gated tonic and
  tick-order determinism between the gate and the arriving STDP events) is
  future work.
* The ordinal BIND bus: concurrent reads inside one slot are not
  disambiguated by the circuit alone (at zero offset the second read is
  silently absorbed by the refractory; the one-read-per-slot meta contract
  is load-bearing and documented).
* The balance counter's horizontal envelope on the x^n shape: the drift
  grows with the body length even at tau_m = 1000 ms; a shape-aware or
  recurrent fix is open.
* The noise mitigation statistics: 100-trial multi-seed validation is
  intermediate; a 1000-trial study is future work.

## 8. Summary

The reproduction now implements, as spiking circuits: the redex
detection, the subterm segmentation, the binding, the phase-ring shifts,
the STDP copy, the living working-memory cube as the effective state
carrier, the neural rescan with an ordinal BIND bus, and a shared-chain
multiplexed write with a neural gate, each validated differentially at
bit-exact equality against a symbolic reference, with the cost trade-offs
measured in three cost categories. The limits are documented rather than
hidden, and the experiments that contradicted our own assumptions (the
falsifiable envelope, the concurrency verdict, the one-bit attribution
correction) are kept in the record.
