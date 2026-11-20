# Technical Note v2: living working-memory cube, neural rescan, and temporal multiplexing in an independent spiking-lambda reduction

Follow-up to our first technical note on the independent reproduction of
arXiv:2611.23182v1. This note covers the extensions built on top of the
reproduction: the living working-memory cube, the neural rescan with the
ordinal BIND bus, and a temporal-multiplexing write architecture. All
mechanisms are validated by differential banks against symbolic references,
at bit-exact learned-weight equality; each bench states which components
are compared.

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

The foreground result of this note is the interruption and resume
protocol: after k reduction steps, the working-memory cube is rebuilt
from the captured STDP weights alone (no symbolic state of the term is
kept), the term is read back from the memories, and the reduction
continues with the same trace and the same final normal form as the
uninterrupted reference. Section 2 gives the exact protocol and its
tested scope.

Corrections measured since the first note:

* **Balance-counter envelope (finding 8, extended).** The paper's balance
  counter uses tau_m = 300 ms and its envelope is limited: on a term of
  9 applied to 8 the counter fails (the loop refuses to compute a wrong
  result and stops). A recalibrated variant with tau_m >= 1000 ms extends
  the envelope: 16+16 reduces to Church 32 with exact traces. Both
  parameterizations remain runnable: 300 ms is the default (fidelity), the
  recalibrated value is opt-in per loop. The falsifiable form of the
  envelope is a critical length L_max: the body length beyond which the
  residual horizontal drift makes the counter's discharge wrong. The
  measured drift trajectory comes first: on the x^n shape at
  tau_m = 1000 ms, the 39-token body already discharges two slots early
  (the measured length is 37 instead of 39), with the error growing
  monotonically (10 percent at 69, 18 percent at 149). The drift is
  trajectory-shape dependent (the x^n body drives the counter to its
  worst-case dive, while the 65-token argument of mult 5 5 discharges
  exactly). L_max itself, the first body length whose discharge is
  wrong, is bracketed but not pinned on this shape: the x^8 body
  (15 tokens) discharges exactly in the copy benchmarks at
  tau_m = 1000 ms, and the 39-token body is already wrong, so L_max
  lies between those measured points. The tau_m = 300 default has the
  same structure with a much shorter L_max: on the PLUS family, 8+8
  stays inside the envelope and 9+8 crosses it, and the loop refuses
  the crossed case instead of computing a wrong result.
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
type channel, and 2 free-index channels), an extension of the paper's
encoding, which carries the type on distinct populations and drops the
free-variable index. Each channel is a one-hot code over 8 phase values,
so the 56-bit figure for a slot is the logical one-hot encoding width,
not a physical memory word.

Corruption is detected at readout (a muted channel stops the loop). The
interruption and resume test goes further, with the protocol made
explicit. Saved at interruption: the learned STDP weights of the cube
banks alone; no symbolic state of the term is kept. Rebuilt at resume:
the cube network is re-created fresh (membrane potentials, synaptic
traces and refractory timers are re-initialized, not restored), the
weights are reloaded, and the term is read back from the memories by
recall; the reduction then continues. Tested scope: one interruption
point (k=2), one term (2 I), one engine (Python); the scope is small and
stated. The resumed trace and the final normal form are identical to the
uninterrupted reference. This demonstrates a rebuild-from-weights
protocol: the weights alone carry everything required to reconstruct the
term and continue. It does not demonstrate restoring the complete
dynamical state (potentials, traces, refractories), which is a distinct
and stronger claim we do not make.

Status (closed-complete, operational definition). For closed terms, the
neural memory cube carries the complete state required for continuation
and reduction. For terms containing free variables whose indices depend
on binders outside the scanned body, the index update remains
meta-controlled (the scan cannot see binders above the body), so the
neural path is complete on closed terms and hybrid exactly there.

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
  to the linear budget, reads are exact on the tested configurations up
  to depth 64, with a depth-independent margin (4.3 to 4.4 ms at depths
  8, 16, 32 and 64).
* 100 consecutive binder reads of a stable level: all exact, and the
  closed gates stay muted. The muteness criterion is that a gate's
  membrane potential never crosses its firing threshold (+1.0). The
  three values at play have distinct roles. The leak-free reference is
  the instantaneous algebraic sum: at wave arrival the pinned weight
  holds the potential near -1.24, and the largest query pulse adds
  +0.78, so with no decay at all the peak would be -0.46. The measured
  peak over the whole series is -0.363, slightly higher (less negative)
  than the leak-free sum because the inhibition and the pulse act over
  a few milliseconds rather than instantaneously. Both sit far below
  the firing threshold, and the margin that matters is the measured
  one: 1.0 - (-0.363) = 1.363. The exact relation is: leak-free
  reference (-0.46) < measured peak (-0.363) < firing threshold (+1.0).
  Zero firings are observed over the whole series.

**Failure discovered during stress testing (an addressing constraint).**
The depth-scaled bench exposed a port collision that the nominal benches
could not see: the two global bus ports (variable and application
signalling) sat at indices 100 and 101, and from depth 25 the per-level
gate neurons reach those same indices (the 25th lambda's gate is index
100), so every global bus pulse struck the deep levels directly and the
whole stack closed on the first read at depth 32. The fix moves the
global ports to 1000 and 1001. The nominal benches (depths <= 5) could
never have observed this; the discovery came from scaling the depth, not
from a content differential. We record it as an addressing constraint:
the flat address plan shared between the global buses and the
depth-indexed level channels must be partitioned.

## 4. Temporal multiplexing (Extension, an alternative to Section 2.10.2)

The paper's Section 2.10.2 creates one nested-SCAN chain per bound
variable occurrence (O(n_bound) chains, staggered delays). We implement an
alternative: ONE temporal chain shared by all occurrences, every
destination bank learning its ring-routed pattern during the shared
windows, with per-tap gates selecting the learning window. The learned
weights are bit-exact against the per-occurrence write on both engines,
and invariant under the tap creation order.

The formal cost comparison measures both modes at bit-exact output and
final-weight equality, with the costs sorted into three categories. The
metrics that matter for a physical reading are the simulated theta
cycles, the synaptic operations (emissions and post-synaptic fan-in) and
the projection-table footprint:

| Cost category | What is counted | Sequential | Multiplexed |
| --- | --- | --- | --- |
| Dynamic | simulated theta cycles | n_slots x 6 | (n_direct + l_arg) x 6 |
| Dynamic | SRC events | n_slots x 42 | (n_direct + l_arg + n_arg) x 42 |
| Dynamic | DST spikes | measured, identical | measured, identical |
| Structural | post-synaptic fan-in per destination bank (max) | 42 | 42 (each tapped bank receives only its own window) |
| Structural | post-synaptic fan-in, total | n_slots x 42 | n_slots x 42 (n_arg x 42 of them delivered by the chain) |
| Structural | neurons, synapses | unchanged | unchanged (+1 chain emitter) |

Fan-in, measured on the family (n_bound=8, l_arg=19, n_slots=47): 1974
post-synaptic events in both modes; the chain delivers 1680 of them
(n_arg=40, 40 x 42) and the direct banks receive theirs as in the
sequential mode. Per-bank fan-in is 42 events in both modes: the
multiplexed chain does not inflate it.

Two short caveats. The multiplexed mode's SRC events include the routing
relays (materialized as re-scheduled events in our harness); in a
physical realization they would be the same spikes arriving through
gates. The wall-clock is engine overhead of our serialized Python
harness (the biologically parallel banks run one by one, so it is
higher), it is never summed with the simulated cycles, and it is not a
cost metric here.

## 5. Neural GATE_BOUND (Extension, preliminary)

The window selection itself is then moved into neurons: every tap receives
every window through its routed projection tables (wiring laid down at
creation from the ring-composed patterns), and a LIF gate per tap
(Section 2.9 mechanics: arm current during its own window) selects what is
learned. The SRC events drop to the theoretical minimum (the chain's raw
emission only): the routing relays of the previous table become wiring,
counted as a resource (n_arg x l_arg x 7 routing-table entries). The
cost trade-off is measured on both sides: the event-based mode pays the
routing in emissions, the wired mode pays it in fan-in and wiring, at
identical final weights and recall. Measured on the two harness
families: (n_occ=2, l_arg=7, 14 taps) gives 294 SRC events (the raw
chain emission, 7 x 6 x 7), 686 routing-table entries and 4116 delivered
post-synaptic events (14 taps x 7 windows x 42); (n_occ=4, l_arg=11,
44 taps) gives 462 SRC events, 3388 routing-table entries and 20328
delivered events (44 x 11 x 42). The per-tap fan-in rises from 42 (own
window only) to l_arg x 42 (every window delivered by the diffuser).

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
multi-bit presentations, with independent noise draws. At 40 trials on
the first battery term, the vote eliminates the false bindings at
5 percent noise (6/40 at k=1 to 0/40 at k=7) and halves them at
10 percent (11/40 to 5/40) with a structural residual (positions one bit
away from the lambda re-fire often). Misses stay at zero everywhere: the
noise only adds bits, a true coincidence fires in every presentation,
and the majority cannot lose one. The cost is k times the presentation
duration.

The critical term (a free variable inside the body, presented to the
circuit) was then re-measured at the widened scale, with the same
majority-vote protocol and independent noise draws: 100 trials PER
SEED, three seeds, so 300 trials per cell. False-binding trials per
seed:

| Noise | k | Seed 3000 | Seed 4000 | Seed 5000 | Total |
| --- | --- | --- | --- | --- | --- |
| 5 percent | 1 | 0/100 | 0/100 | 0/100 | 0/300 |
| 5 percent | 7 | 0/100 | 0/100 | 0/100 | 0/300 |
| 10 percent | 1 | 2/100 | 0/100 | 1/100 | 3/300 |
| 10 percent | 7 | 0/100 | 0/100 | 0/100 | 0/300 |

All three false-binding trials at k=1 under 10 percent noise mark the
free variable (the rare marking also seen at 40 trials, 1/40 at k=1,
crushed from k=3); at k=7 the vote crushes them at both noise levels,
0/300 with zero misses. The two batteries do not contradict each other:
the 10 percent residual is term-dependent. On the first battery term it
concentrates on positions one bit away from a lambda, which re-fire
often enough to clear the majority; on the critical term the only false
bindings observed are free-variable markings, which are rare per draw
and do not survive k=7 independent draws. The zero counts carry
rule-of-three bounds, not guarantees: 0/100 bounds a per-seed rate at
about 3 percent, and 0/300 bounds it at about 1 percent. A 1000-trial
multi-seed study is future work.

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
  grows with the body length even at tau_m = 1000 ms (the discharge is
  exact at 15 tokens and wrong at 39, so L_max lies between those
  measured points on this shape); a shape-aware or recurrent fix is
  open.
* The noise mitigation statistics (a 40-trial majority sweep, plus
  3 seeds x 100 trials = 300 trials on the critical term) are
  intermediate; a 1000-trial multi-seed study is future work.

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
