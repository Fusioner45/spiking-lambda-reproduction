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
    needed. The free-index port (emitting n-1 on channels 5-6) and the
    compose_cube integration behind a flag ride with it.
* v3c (1 session): remove `body_slot`'s channel-level KEEP rule from
  the meta-controller; the decrement is now fully neural. The boundary
  note moves to "output ordering only" (the paper's own boundary).

## 4. From v3 to Item 3 (multiplexing)

With v3 in place, the substitution cost argument becomes mechanical:
today each bound occurrence triggers a full copy of the argument
(n_bound x l_arg theta-cycle copies, Section 2.8 per token). The paper's
Section 4.5 replaces this by a single temporal chain `pos_arg` of length
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

## 5. Honest boundaries throughout

After v3: the meta-controller owns output ordering only (same as the
paper's Section 2.11). After Item 3: it owns the initial cube and the
halt check. Noise behavior of the neural binder stack is out of scope
for v3 (Finding n.9 tracks it separately).
