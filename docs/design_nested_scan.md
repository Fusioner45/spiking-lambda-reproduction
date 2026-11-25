# Design note: from the living cube to nested SCANs (v3) and the
# multiplexing (Item 3)

Status: proposal, not yet implemented. This note sets the architecture
for the next two chantiers and turns them into session-sized milestones.
The living cube (v1+v2) is merged and green: slot patterns are composed
from real emissions (source copies + phase-ring shifts with observed
carries) and read back through STDP recall. One symbolic piece remains:
the KEEP decrement (-1 on kept body tokens), applied channel by channel
by the meta-controller, exactly as the paper's own Python assembles its
output events (Section 2.11). v3 removes it; Item 3 then replaces the
per-occurrence argument copy by a single temporal chain.

## 1. What v3 must add

The decrement is not an operation on tokens: it is an anchoring fact.
The body of the redex used to hang under the redex lambda (first token
at depth d_lam + 1); after the reduction it hangs at d_lam. A re-scan
that starts the depth counter at d_lam (instead of d_lam + 1) emits
every kept token one level shallower without ever applying a "-1" to
any token. Same fact for the free-variable index: the environment loses
one level, so the free port emits n - 1. The decrement dissolves into
the anchoring of the scan.

While scanning, the counter must track the current depth through the
tree structure of the emitted stream:

* LAM emitted: pushes an open level, counter +1 for the following
  tokens.
* APP emitted: pushes an open level (no depth change for its children).
* When a level closes, the counter returns to the level's opening
  depth.

Level closing is detected by a balance integrator per open level: VAR
+1, APP -1, LAM 0; the level closes when its integrator crosses +1
(cascade: a closed child adds +1 to the parent level). This is exactly
the paper's INTG_BODY (Section 2.5) instantiated once per open level --
which is what "nested SCANs" means in this reproduction: SCAN provides
the sequential emission, a stack of INTGs provides the depth bookkeeping.

For the binder channels of a kept VAR: the stack records each open
level's kind and new depth; a VAR bound to a binder inside the body
reads its binder's new depth off the stack (the (n+1)-th LAM from the
top); a VAR bound outside (b < d_lam, not on the stack) keeps its
source BIND channels unchanged. Free vars keep the reserved (7,7) code
and emit the decremented index on the free channels.

Two structural facts lock the design:

* Balance is invariant under substitution. In prefix form every
  well-formed subterm has a net balance of +1 (N_VAR - N_APP = +1),
  exactly the contribution of the bound variable it replaces -- so the
  output stream (kept body tokens and inserted argument copies
  interleaved) preserves the nesting structure, and a single pass of
  the INTG stack needs no exception routing for the insertions. This
  is why the skipped redex-bound VARs contribute +1 in `rescan_body`.
* Calibration reuses Finding n.8. The outer levels of the stack stay
  held under threshold while the inner subterms are traversed -- the
  exact regime where the paper's tau_m = 300 ms integrator drifts.
  Calibrate the stack directly at tau_m >= 1000 ms with
  W_CNT = 1/epsilon(tau_m, 1) (validated for the envelope fix, session
  14 bis), not at the paper's 300 ms.

## 2. Open design question (to settle at implementation time)

Where does the scan read its input from?

* (a) Re-emitter: the scan walks the kept body tokens (source stream)
  and re-emits them at the anchored depths. Inserted arguments break
  the balance bookkeeping: the output stream interleaves re-emitted
  body tokens and argument copies, so the per-level integrators see a
  mixed stream. Handling: argument copies participate in the balance
  like any emitted token (a VAR copy +1, an APP copy -1), which works
  but couples the scan to the insertion schedule.
* (b) Output-stream scan: the scan walks the assembled output stream
  (Section 2.10.3 events, already ordered) and its counter is a
  verifier, not a generator. Cheaper, but then the depths are already
  decided symbolically -- this weakens what v3 is for.

Recommendation: (a) for the body re-scan, with the argument-insertion
schedule owned by the same topographic sort the paper uses. Settle with
a differential bench: the composed cube (v2) must remain exactly equal.

## 3. Milestones

* v3a (1 session): executable specification + first circuit. DONE.
  The spec `rescan_body` (event semantics) is validated (60 kept tokens
  exact against the KEEP rules), and the neural INTG stack
  (`rescan_circuit.py`, one LIF integrator per open level,
  tau_m = 1000 ms / W_CNT = 1/epsilon(tau_m, 1)) is validated
  token-by-token against the spec on the 8-term battery: 64 kept
  tokens exact. Simultaneous level closures (several integrators
  crossing +1 on the same slot, e.g. APP f (APP x y)) sum correctly:
  each stack neuron projects independently, up to 6 closures observed
  on one slot. Remaining honest boundary: the gating (which INTG
  receives the pulses) is carried by selective port injection, same
  status as the paper's Section 2.11 injections; neural synaptic
  gating is v3b.
* v3b (1 session): neural free-index port and binder stack readout;
  wire the re-scan into `compose_cube` behind a flag; differential
  against v2 canal by canal; 16 banks stay green.
  * v3b-1 DONE: the cut-off is now carried by the neuron dynamics
    themselves -- global VAR/APP ports feed every INTG, and a closed
    level enters a long post-discharge refractory period (t_ref
    covering the rest of the scan) that makes it deaf to further
    pulses. Every INTG fires at most once (bank-verified); the global
    mode reproduces the selective-mode traces exactly on the full
    battery (16 steps / 64 tokens). Remaining honest boundary: the
    wiring (which INTG is connected to the global ports) still happens
    at push time, same status as Section 2.11 initialization.
  * v3b-2 DONE: binder readout off the live stack. read_binder(n)
    returns the anchored depth of the (n+1)-th active LAM from the
    stack top, or None (muted stack) when the binder is outside the
    body or the variable is free -- the free detection is automatic
    (no stack LAM can cover it). Validated on the full battery in both
    gating modes: 15 internal binders read off the stack, 5
    outside-body, 4 free. Design lesson: the binder read happens
    BETWEEN the emission of the token and the closures it triggers --
    the last token of a body closes the whole stack on the same slot,
    so reading after feed() would see an empty stack.
  * Open question for v3b-3: the physical BIND bus with the
    inhibition chain (each active LAM projects its anchored depth and
    inhibits the LAM levels below it; the discharge frees the bus for
    the enclosing LAM). Design difficulty documented: when the top is
    cut, a serial inhibition chain stops propagating (two emitters on
    the bus) -- parallel inhibition or a tokenized read sequence is
    needed.
  * v3b-3 DONE: the bus was implemented as the ORDINAL WAVE readout
    (the alternative route, avoiding the two-emitter problem
    entirely): each LAM level carries a PERSIST (Section 2.9 bistable,
    armed at push), a GATE-read and a pos on a LAM-to-LAM wave chain
    that descends the stack from the top regardless of state (closed
    levels relay the wave but do not answer). A read injects a wave at
    the top; active GATEs answer once, closed ones stay mute, and the
    (n+1)-th answer in ordinal order is the binder. Calibrated
    asymptotically (tonic measured over 500 ms, wave jump +0.78,
    GATE tau_m=30). Two root causes fixed on the way (session 24):
    the deepest gate of a 4-LAM chain answers at ~t0+8.8 ms, past an
    8 ms slot (SLOT_MS 8 -> 12), and closed gates accumulated the
    wave's query pulses (+0.78 per VAR slot; a one-shot close HALT
    only protected the first wave) -- fixed by re-pinning the gate
    HALT at every wave. Remaining meta-controlled rule: the free-index
    port (emitting n-1 on channels 5-6) is future work.
* v3c DONE (1 session): `compose_cube` drives the real RescanStack
  over the kept body tokens behind the `neural` flag (production
  default via `orchestrate.neural_keep=True`): self comes from the
  anchored counter (the anchor IS the KEEP decrement -- no -1 rule
  applied anywhere) and bind from the ordinal BIND bus. The
  channel-level KEEP rules (body_slot) remain only as the symbolic
  reference of the differential, like the re-encoding. EXCEPTION kept
  honest: the free-index -1 stays in the meta-controller (free
  indices count lambdas above the body, invisible to the scan -- the
  same status as the authors' Section 2.11); the neural free port is
  the next milestone. Differential v2: the neural composition matches
  the re-encoding canal by canal on the trap cases, and the closed
  loop (living_cube) composes through the neural path with the
  per-step filet assert.

## 4. From v3 to Item 3 (multiplexing)

With v3 in place, the substitution cost argument becomes mechanical:
today each bound occurrence triggers a full copy of the argument
(n_bound x l_arg theta-cycle copies, Section 2.8 per token). The paper's
the Section 2.10.2 scheme creates one nested-SCAN chain per occurrence
(O(n_bound) chains, staggered delays); our alternative replaces that
cost with a single temporal chain `pos_arg` of length
l_arg, and every bound occurrence taps it through time addressing from
GATE_BOUND. The composed-cube infrastructure makes the claim testable:
slot patterns for all destinations come from one chain of copies, and
the topographic invariance proof (order of output events independent of
the interleaving of taps) is stated over measured spike times instead of
symbolic assembly.

Milestones: m1, single chain write with per-occurrence taps into the
cube slots (same recall readout as v1); m2, the invariance proof as a
differential bench (taps in all orders, slot contents identical); m3,
complexity measurement n_bound x l_arg -> l_arg on the scale family.

m1/m2/m3 DONE (session 25). `cube_multiplex.py`: the chain is ONE
sequence of shared theta windows (one per argument token, 6 cycles
each) during which ALL tap banks learn their ring-routed pattern in
parallel — emission cost l_arg windows instead of n_bound x l_arg
(`count_emissions`); the memory (one STDP bank per destination slot)
is unchanged by construction (slots are addresses). The tap routing
raw -> shifted is carried by the real ring (the same `arg_slot` /
`ring_shift` the composition uses); the gating (which tap listens in
which window) remains meta-controller (Section 5 boundary). m1
differential: tapped banks' weights are BIT-EXACT against direct v1
writes and the readout is faithful, on both engines (py and C); m2:
weights AND recall spike times are invariant under 4 tap orders
(2 random permutations), per slot, canal by canal; m3: measured
emission gains 1.9x (x^2) to 6.1x (x^8, Church-8) on the
(\x. x^n) (numeral k) family. The multiplexed write is the production
default (`orchestrate.multiplexed=True`); the closed loops run it
end-to-end with the per-step filet assert.

Latent bug found and fixed on the way (probe, not review): CopyC
(snn_core.py) scheduled learn/recall events at ABSOLUTE steps from
zero and its recall read the WHOLE spike log since creation -- the
"C recall" was actually reading the learn-phase spikes, which only
worked because the content coincides. `CopyC` now tracks its own
clock (_k), schedules relative to it, and reads only the recall
window's spikes; a n_steps_alloc parameter was added (the chain needs
l_arg x 720 steps of event capacity).

m4 DONE (same session, formal cost comparison requested by the user):
`run_multiplex.py` measures both modes on the (n_bound, l_arg) family
at bit-exact output/weight equality: simulated theta cycles (the
headline: 1.0x at n_bound=1, up to 6.1x at n_bound=8), literal SRC
events (mux = sequential + the chain's raw emission; the routing
relays are counted literally and decomposed -- in a physical
realization they are the same spikes arriving through gates, so the
neural GATE_BOUND milestone would remove that term), DST spikes
(measured, not forced: the taps run warm through the chain while the
direct banks start fresh; final weights identical), resources
(banks/memory unchanged by construction), and engine wall-clock
reported SEPARATELY as overhead (the harness serializes the
biologically-parallel banks, so mux wall-clock is higher in our sim
-- never mixed with simulated time). Gating/composition are shared
preconditions excluded from the copy delta (object identity
asserted); the fixed prep cost of the multiplexing is measured
separately (microseconds). Metric definitions and counting windows
are documented in the module docstring. The m4 protocol itself caught
a real semantics gap: the taps originally received their pattern in
EVERY window (weights unchanged by clamping, but the SRC flow was
inflated and the time-addressing violated) -- the per-window gating
is now explicit (each tap carries its window), matching the
GATE_BOUND role.

## 5. Honest boundaries throughout

After v3: the meta-controller owns output ordering only (same as the
paper's Section 2.11). After Item 3: it owns the initial cube and the
halt check. Noise behavior of the neural binder stack is out of scope
for v3 (Finding n.9 tracks it separately).

Precise status (external review, session 31): the neural state is
CLOSED-COMPLETE -- the write path closes the loop bit-exactly for
closed terms; terms with variables bound outside the redex keep the
meta-controller free-index decrement (the scan cannot see binders
above the body), so the state is hybrid on external free-variable
indices. The GATE_BOUND current follows the chain's emission state;
the tap-to-window assignment remains a meta datum.
Attribution correction (session 31): the paper's nested-SCAN
mechanism is Section 2.10.2 (one pos_arg chain PER bound occurrence,
staggered delays); Section 4.5 is Future directions (System F). The
multiplexing implemented here is an alternative architecture
addressing the per-occurrence cost of the Section 2.10.2 scheme.

## 6. Envelope on structured bodies (session 44, measured)

The reads above are validated on the battery's terms. Church lists
(`run_lists.py`) bring bodies with many nested binders: a cons carries
four, each numeral two. On the body of the fifth reduction of
`append [1,2] [3]` (38 tokens, 11 binder levels created along the
scan) the re-scan leaves its envelope in two independent ways. Both
are detected: neither produces a silently wrong cube, because the
verified path compares the composed patterns with the re-encoding at
every step.

1. Wave budget (nominal slot). The chain counts every binder level
   ever created, closed ones included (they relay the wave without
   answering). At the read of the 20th body token the chain holds 7
   levels and the response of the lowest binder lands 1.3 ms inside
   the NEXT slot. The strict counting window attributes it to that
   next read: the ordinal shifts and the binder read is depth 4 where
   the reference says 3. The circuit then raises on the following
   slot, which carries no wave (its out-of-wave firing assertion).
   This is the stress-bank envelope (about 1.8 ms per stage) reached
   by a real term. The hazard is worth stating: had the following slot
   carried a wave, the late response would have been counted in the
   wrong ordinal and the circuit alone would not have said so; only
   the differential with the re-encoding catches it.
2. INTG drift (both tested slot lengths). With the wave disabled
   (`binder_bus=False`) and the nominal slot, the depth read for the
   last body token is d_lam (2) instead of d_lam + 1 (3): the outer
   levels, BODY included, close one token early. The same error is
   measured at a 24.8 ms slot and with tau_m scaled with the slot
   (2067 ms). This is the finding-8 drift reaching the stack; its
   mechanism is the one the stress bank measures on the stand-alone
   counter and was not re-measured here. Scaling tau_m with the slot
   does not restore exactness: at tau_m = 2067 ms the closure pattern
   changes (one level closes at token 35 where four close at
   tau_m = 1000 ms) and the last-token error remains. A single pulse
   is normalized to exactly the threshold (W_CNT = 1 / epsilon), so
   any change of tau_m moves the single-pulse levels onto the knife
   edge; which levels close late at tau_m = 2067 ms was not isolated.
3. Slot sized to the wave budget. The stress-bank rule (3.8 +
   1.8 (n_lam - 1) + 3 ms, so 24.8 ms here) clears the first wall:
   every binder read of the body is then exact. The second wall
   stays: exactly one of the 72 slots differs from the reference, the
   last body token.

The figures of items 1 to 3 (7 levels on the chain at the 20th token,
the late response 1.3 ms inside the next slot, the read of depth 4
for 3, the closure counts at token 35 for both tau_m values) are
asserted by `run_lists.py` (blocks 6 and 6d).

The body of the second reduction of the same append in the two-binder
encoding (43 tokens; the term on which the assembly defect of
`technical_note_v2.md` Section 2 was first observed) is refused at the
nominal slot too, with the same out-of-wave firing assertion
(`run_lists.py`, block 2b). Which of the two walls it meets first was
not isolated.

Status: the list demos run the living cube on the channel-level KEEP
reference (`neural_keep=False`), which is exact on these bodies (72 of
72 slots equal the oracle re-encoding on the body above). Candidate
for the second wall: a positional counter per level (the mechanics of
`balance_circuit.py`, exact by construction). Candidate for the first:
the slot sized by the binder count, once the second wall is cleared.
Neither is implemented.

Repair along the way: `RescanStack(binder_bus=False)` raised an
`AttributeError` on its first VAR (the chain head was only created
with the bus); the head is now defined in every mode, and block 6 of
`run_lists.py` exercises the bus-less stack.
