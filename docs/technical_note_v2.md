# Technical Note v2: living working-memory cube, neural rescan, and temporal multiplexing in an independent spiking-lambda reduction

Follow-up to our first technical note on the independent reproduction of
arXiv:2611.23182v1. This note covers the extensions built on top of the
reproduction: the living working-memory cube, the neural rescan with the
ordinal BIND bus, and a temporal-multiplexing write architecture. All
mechanisms are validated by differential banks against symbolic references,
at bit-exact learned-weight equality; each bench states which components
are compared.

Repository: https://github.com/Fusioner45/spiking-lambda-reproduction
(MIT, continuous integration, 23 validation benchmarks).

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
  counter uses tau_m = 300 ms and its envelope is limited: on PLUS 9 8
  (Church numerals 9 and 8) the counter fails (the loop refuses to
  compute a wrong result and stops). A recalibrated variant with
  tau_m >= 1000 ms extends the envelope: 16+16 reduces to Church 32 with
  exact traces. Both parameterizations remain runnable: 300 ms is the
  default (fidelity), the recalibrated value is opt-in per loop. The
  falsifiable form of the envelope is a critical length L_max: the body
  length beyond which the residual horizontal drift makes the counter's
  discharge wrong. The measured drift trajectory comes first: on the
  x^n shape (a body of n nested occurrences of x) at tau_m = 1000 ms,
  the 39-token body already discharges two slots early (the measured
  length is 37 instead of 39), with the error growing monotonically
  (10 percent at 69, 18 percent at 149). The drift is trajectory-shape
  dependent (the x^n body drives the counter to its worst-case dive,
  while the 65-token argument of mult 5 5 discharges exactly). L_max
  itself, the first body length whose discharge is wrong, is bracketed
  but not pinned on this shape: the x^8 body (15 tokens) discharges
  exactly in the copy benchmarks at tau_m = 1000 ms, and the 39-token
  body is already wrong, so L_max lies between those measured points.
  This bracket is an empirical interval on the tested shape, not a
  general bound over arbitrary term shapes. The tau_m = 300 default has
  the same structure with a much shorter L_max: on the PLUS family, 8+8
  stays inside the envelope and 9+8 crosses it, and the loop refuses
  the crossed case instead of computing a wrong result.
* **Positional balance counter (proposed amendment, spec and spiking circuit validated).**
  The same balance can be held exactly on the paper's own two-digit
  phase-grid mechanics (Section 2.7, extended to reverse stepping) with
  signed carries and a Section 2.6 coincidence comparator for the
  discharge: exact on the worst-case family (3 to 149 tokens) where the
  analog counter lands 2 to 27 slots early, and on every reduction step
  of the battery, and the spiking circuit of this design is validated
  slot by slot against the spec on both engines. In the closed loop,
  the segmentation is exact at the paper's parameters: PLUS 9 8 and
  PLUS 16 16 compute (the cases the analog counter refuses or misses),
  and mult 5 5 runs to completion (Church 25) with exact segmentation
  on 83-token terms.
* **Free-variable index.** The published encoding binds free variables to
  a reserved phase code and drops their index. The fix combines the
  reserved code with two index channels in the slot encoding, is
  collision-free up to depth 62 (the 8 x 8 = 64 phase pairs include the
  depth-63 code (7,7), which is reserved for free variables, so usable
  depths run 0 to 62), and is validated circuit-level under
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
recall; the reduction then continues. Tested scope: a matrix of
interruption points, terms and engines: k in {1, 2, 3} on 2 I
(Church 2 applied to the identity) and k in {2, 4} on PLUS 2 3. The
closed-term matrix contains nine cases across the Python and C engines;
the open term `(\\x. x y) ((\\z. z) w)` adds one case on each engine,
for eleven cases in total. The k = 3 case resumes at the last step,
where the read-back term is already the normal form. On every case the
read-back term equals the symbolic term, and the resumed trace and final
normal form equal the uninterrupted reference.

The open-term cases rely on the A-bis convention fix: `to_debruijn`
honors the stable `_fN` level suffixes emitted by `from_debruijn`, so a
free variable keeps its identity when a reduction reorders it. This
fix replaces the earlier strict expected failures described in the first
version of this note. The rebuild-from-weights conclusion is therefore
tested on the listed closed and open cases; the architecture remains
closed-complete in the operational sense defined below, while open terms
retain the documented hybrid free-index update. This demonstrates a
rebuild-from-weights protocol: the weights alone carry everything
required to reconstruct the term and continue. It does not demonstrate
restoring the complete
dynamical state (potentials, traces, refractories), which is a distinct
and stronger claim we do not make.

Status (closed-complete, operational definition). Architecturally, for
closed terms the neural memory cube is intended to carry the complete
state required for continuation and reduction, and the interruption and
resume experiment above is a first operational demonstration of this on
the tested configuration. For terms containing free variables whose
indices depend on binders outside the scanned body, the index update
remains meta-controlled (the scan cannot see binders above the body), so
the neural path is complete on closed terms and hybrid exactly there.

**Church lists in the closed loop (`run_lists.py`).** The battery's
terms are numerals and combinator families. Lists add nested binders:
with `nil = \c n. n` and `cons h t = \h t c n. c h (t c n)` written in
line, each cons carries four binders and each numeral two, so kept
bodies reach binders at depth 7 and beyond. The closed loop with
positional segmentation reduces `append [1,2] [3]` (87 tokens) in 18
reductions to a normal form that reads back as [1,2,3], `append [1,2,3]
[4]` (113 tokens) in 22 reductions to [1,2,3,4], `map succ [1,2]`
(82 tokens) in 26 reductions to [2,3] (its normal form keeps two
vacuous binders in head position, ignored at readout), and `reverse
[1,2,3]` (90 tokens) in 27 reductions to [3,2,1]. The trace and
the normal form equal the symbolic oracle at every step on both
engines, and the same reductions run with the living cube: slot
patterns composed with the channel-level KEEP reference, written by
the multiplexed chain, read back from the memories. This is symbolic
calculation on structured terms, of the same nature as the numeral
battery.

The terms exposed a convention defect of this implementation, recorded
here as such. The topographic assembly applies the KEEP decrement to
each kept body variable by comparing the binder's address with the
redex lambda's depth, and our comparison used the binder's fine phase
alone. A variable bound inside the body by a binder at depth 7 mod 8
was decremented as if it were free, and a binder at depth 8 or more
was decremented as if it sat above the redex. The name reconstruction
then read the resulting index of -1 as the outermost binder without
complaint; the loop's oracle check stopped the reduction at the fifth
step of `append [1,2] [3]`, so no wrong normal form was produced. The
defect was first observed on the same append written with the cons
already applied (`cons h t = \c n. c h (t c n)`, 69 tokens, 12
reductions), where the old rule is wrong from the second reduction:
two kept variables lose one index each (index 1 read as 0) because
their binder sits at address 7, whose fine phase is the reserved code
of free variables. The redex lambda is at depth 0 at that step, so
only this first case is exercised there. At that step the
channel-level composition equals the oracle's re-encoding on all 63
slots and the neural re-scan refuses the body: the symbolic assembly
was the only faulty component, and the bank pins this diagnosis. The
comparison now uses the full binder address and the free flag, the
reconstruction refuses negative indices, and the bank pins both cases
with minimal terms and lists which demos trigger them. The repository
holds three definitions of the binding truth (closed loop, phase-ring
bank, free-variable bank); they agree at every reduction of the demos.
The analog counter refuses the 87-token term at its
first step at tau_m = 300 ms (a 45-token argument) and at its second
step at tau_m = 1000 ms (a 55-token body): the finding-8 envelope,
measured here on a list.

## 3. Neural rescan and ordinal BIND bus (Extension)

The KEEP decrement of Section 2.10.3 is realized by a neural rescan: one
balance-counter instance per open level (tau_m = 1000 ms), the counter
anchored at the redex lambda's depth (the anchoring IS the decrement: no
minus-one rule is applied anywhere), and the binder depths read by an
ordinal wave: a chain descends the level stack, active gate-read neurons
answer once, closed ones relay without answering, and the (n+1)-th answer
in ordinal order is the binder (for de Bruijn index n).

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
global ports to 1000 and 1001, well above the indices the level neurons
can reach in the tested depth range. The nominal benches (depths <= 5) could
never have observed this; the discovery came from scaling the depth, not
from a content differential. We record it as an addressing constraint:
the flat address plan shared between the global buses and the
depth-indexed level channels must be partitioned.

**Envelope on structured bodies (measured, `run_lists.py`).** The
reads above are validated on the battery's terms, whose bodies are
short and hold few binders. On the body of the fifth reduction of
`append [1,2] [3]` (38 tokens, 11 binders) the neural re-scan leaves
its envelope in two independent ways. With the nominal 12 ms slot the
ordinal wave is late: the response of the lowest binder lands in the
next slot, the ordinal of one read is shifted, and the circuit raises
on the following slot (its out-of-wave firing assertion), so the result
is refused rather than wrong. Independently of the wave, the analog
INTG stack closes the outer levels one token early: the depth read for
the last body token is d_lam instead of d_lam + 1, with the wave
disabled and at both tested slot lengths (12 and 24.8 ms). This is the
finding-8 drift acting on the rescan stack; scaling tau_m with the slot
does not restore exactness (the same last-token error remains at
tau_m = 2067 ms with a 24.8 ms slot). Sizing the slot to the wave
budget (24.8 ms) clears the first wall only. The 43-token body of the
second reduction of the same append in the two-binder encoding is
refused at the nominal slot as well. The list demos therefore
compose the cube on the channel-level KEEP reference; a positional
counter per level, built from the Section 2.7 mechanics validated in
the positional balance counter, is the natural candidate for the second
wall and is not implemented.

## 4. Temporal multiplexing (Extension, an alternative to Section 2.10.2)

The paper's Section 2.10.2 creates one nested-SCAN chain per bound
variable occurrence (O(n_bound) chains, staggered delays). We implement an
alternative: ONE temporal chain shared by all occurrences, every
destination bank learning its ring-routed pattern during the shared
windows, with per-tap gates selecting the learning window. The learned
weights are bit-exact against the per-occurrence write on both engines,
and invariant under the tap creation order.

The formal cost comparison measures both modes at bit-exact output and
final-weight equality, with the costs sorted into three categories.
Here n_direct is the number of destination slots written directly (the
kept body slots, not derived from the argument), n_arg = n_bound x l_arg
is the number of argument-derived destination banks across all
occurrences, n_slots = n_direct + n_arg, and l_arg is the argument
length in tokens. The metrics that matter for a physical reading are the
simulated theta cycles, the synaptic operations (emissions and
post-synaptic fan-in) and the projection-table footprint:

| Cost category | What is counted | Sequential | Multiplexed |
| --- | --- | --- | --- |
| Dynamic | simulated theta cycles | n_slots x 6 | (n_direct + l_arg) x 6 |
| Dynamic | SRC events | n_slots x 42 | (n_direct + l_arg + n_arg) x 42 |
| Dynamic | DST spikes | measured, identical | measured, identical |
| Structural | post-synaptic fan-in per destination bank (max) | 42 | 42 (own window only) |
| Structural | post-synaptic fan-in, total | n_slots x 42 | n_slots x 42 (n_arg x 42 via the chain) |
| Structural | neurons, synapses | unchanged | unchanged (+1 chain emitter) |

Fan-in, measured on the family (n_bound=8, l_arg=5, n_slots=47): 1974
post-synaptic events in both modes; the chain delivers 1680 of them
(n_arg=40, 40 x 42) and the direct banks receive theirs as in the
sequential mode. Per-bank fan-in is 42 events in both modes: the
multiplexed chain does not inflate it.

Two short caveats. The multiplexed mode's SRC events include the routing
relays (materialized as re-scheduled events in our harness); in a
physical realization they would be the same spikes arriving through
gates. Wall-clock runtime reflects the overhead of our serialized Python
harness (the biologically parallel banks are stepped sequentially), is
never summed with the simulated cycles, and is not treated as a hardware
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
families: (n_occ=2, l_arg=7, so n_arg = 14 taps) gives 294 SRC events
(the raw chain emission, 7 x 6 x 7), 686 routing-table entries and 4116
delivered post-synaptic events (14 taps x 7 windows x 42); (n_occ=4,
l_arg=11, so n_arg = 44 taps) gives 462 SRC events, 3388 routing-table
entries and 20328 delivered events (44 x 11 x 42). The per-tap fan-in
rises from 42 (own window only) to l_arg x 42 (every window delivered
by the diffuser).

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
the iteration term (\f. \x. f (f (f x))) (\x. x y), the vote eliminates
the false bindings at
5 percent noise (6/40 at k=1 to 0/40 at k=7) and halves them at
10 percent (11/40 to 5/40) with a structural residual (positions one bit
away from the lambda re-fire often). Misses stay at zero everywhere: the
noise only adds bits, a true coincidence fires in every presentation,
and the majority cannot lose one. The cost is k times the presentation
duration.

The critical free-variable term (\f. f (g f)) h (a free variable inside
the body, presented to the circuit) was then re-measured at the widened
scale, with the same majority-vote protocol and independent noise
draws: 100 trials per seed, three seeds, so 300 trials per cell. One
trial is one majority vote over k noisy presentations, each
presentation's noise drawn independently; a trial counts as a
false-binding trial when the voted mask binds any non-truth position,
and as a miss when it loses any true position. The seeds control the
noise generator only; the circuit itself is deterministic.
False-binding trials per seed:

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
the 10 percent residual is term-dependent. On the iteration term it
concentrates on positions one bit away from a lambda, which re-fire
often enough to clear the majority; on the critical free-variable term
the only false bindings observed are free-variable markings, which are
rare per draw and do not survive k=7 independent draws. The zero counts
carry rule-of-three bounds, not guarantees (3/n is the 95 percent
one-sided upper bound after n zero-count trials): 0/100 bounds a
per-seed rate at about 3 percent, and 0/300 bounds it at about
1 percent. A 1000-trial multi-seed study is future work.

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
* The neural re-scan on structured bodies: on a 38-token body with 11
  binders the ordinal wave exceeds the nominal slot and the analog INTG
  stack closes the outer levels one token early, at both tested slot
  lengths. Both are detected. The list demos compose the cube on the
  channel-level KEEP reference; a positional counter per level is open.
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
measured in three cost categories. Church lists (append, map, reverse)
are reduced in the closed
loop with positional segmentation and with the living cube on the KEEP
reference; the convention defect they exposed in the assembly is
recorded and pinned, with its diagnosis measured on the term of the
first observation. The limits are documented rather than
hidden, and the experiments that contradicted our own assumptions (the
falsifiable envelope, the concurrency verdict, the Section 2.10.2
attribution correction) are kept in the record.
