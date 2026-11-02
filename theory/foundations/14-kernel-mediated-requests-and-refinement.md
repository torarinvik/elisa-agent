# 14. Kernel-mediated requests and refinement

Modules never invoke one another. A module may return a `Request` instead of
its output, delegating that output to the kernel: "produce a value of this type
from these inputs, without me". The kernel plans the request over the
installed modules minus every module in the current request chain, executes it
under the same budget, records it in the workspace, and uses its result as the
requester's output.

| Theorem | Statement |
|---|---|
| 14.1 | a resolved request is a well-typed plan producing the requested type from the request's inputs |
| 14.2 | it never invokes a module in the request chain |
| 14.3 | every chain of nested requests is at most as long as the number of installed modules, whatever the budget |

Termination follows from freshness: each new requester is a module of a plan
resolved with the chain excluded, so the chain has no repeats and is bounded
by the library.

**Confidence-triggered refinement.** A cheap module answers when confident
(event `C`) and otherwise requests refinement, served by a fallback. With
`W₁`, `W₂` the cheap and fallback error events, the composite errs exactly on
`(C ∩ W₁) ∪ (Cᶜ ∩ W₂)`.

| Theorem | Statement |
|---|---|
| 14.4 | `P(error) = P(C ∩ W₁) + P(Cᶜ ∩ W₂)` |
| 14.5 | if `P(C ∩ W₁) ≤ P(C ∩ W₂)` (confidence is selective), the composite is at least as accurate as the fallback alone |
| 14.6 | expected cost is `κ₁ + κ₂ · P(Cᶜ)` |

The fallback can itself be a refining module, so the two-stage results compose
into chains of any depth. Refinement spends expensive computation only on the
fraction of inputs where the cheap module is unsure: cost tracks the input's
difficulty, not its size alone.

**Relevance gating.** A request is worth resolving only if its result can
change the answer. Let `R` be the event that the requester's output influences
the final answer: off `R`, the answer is wrong after refinement exactly when it
is wrong without it (`E_r ∩ Rᶜ = E_u ∩ Rᶜ`). A gate `G` predicts relevance, and
gated refinement resolves requests only on `Cᶜ ∩ G`.

| Theorem | Statement |
|---|---|
| 14.7 | `P(error, gated) ≤ P(error, ungated) + P(Cᶜ ∩ Gᶜ ∩ R)`: gating costs at most the relevant requests it skips |
| 14.8 | if the gate is sound (`R ⊆ G`), gated and ungated refinement err exactly equally |
| 14.9 | gated refinement costs `κ₁ + κ₂ · P(Cᶜ ∩ G)` |

Requests are therefore resolved lazily: a pending request is decided when
its value is consumed. The *consumer* supplies the gate, since only the reader
knows what it reads. A gate judged from provisional values is in general not
sound, and its cost is the extra term of Theorem 14.7.

**Demand-driven evaluation (a sound gate).** Soundness is easy to obtain when
the gate comes from what a consumer provably reads rather than from what a
value looks like. A *readable* type pairs values `V` with demands `D` and, for
each demand, an agreement relation `v ≈_d v'` ("`v` and `v'` look the same to a
reader with demand `d`"). A module `f : V → W` with demand map `δ : D_W → D_V`
is *demand-sound* when `v ≈_{δ d} v'` implies `f v ≈_d f v'`: whatever the
module's input differs in outside `δ d` cannot be seen in its output under `d`
.

| Theorem | Statement |
|---|---|
| 14.10 | demand-sound modules compose: `g ∘ f` is sound with `δ_f ∘ δ_g` |
| 14.11 | modules on a pair are sound when each component's demand is |
| 14.12 | `map f` is sound on lists with per-element demand `(i, n) ↦ δ (d i n)` |
| 14.13 | at a top demand under which agreement is equality, agreeing inputs give equal answers |

So inputs whose demand is empty can be replaced by anything, in particular
never computed, and the answer is unchanged. Skipping the requests raised for
them is therefore a sound gate: by Theorem 14.8, gated and
ungated refinement err exactly equally.

**Positive rescaling and decision demand.** Suppose a fuser presents scores
`qᵢ = s · pᵢ` for a family of alternatives, where `s > 0` is independent of
`i`. **Theorem 14.18.** Any maximizer of `p` is also a maximizer of `q`,
and conversely. A consumer choosing only within that family can therefore ignore the input that
sets `s`, provided the fuser and consumer use the same tie rule. This argument
requires strictly positive `s`: at zero all scaled scores tie and the original
winner need not be selected. In finite precision, even positive scaling can
round distinct scores to the same value, so the real-number result alone does
not justify dropping the ordering information. If a risk account uses the
original ordering, every downstream decision based on the scaled scores must
receive and use that same ordering as well.

**Continuation requests.** Delegation replaces the requester's output; an
expert that needs a sub-result and then keeps computing is instead a program
over questions:
`Prog := pure a | ask q (k : A q → Prog)`, composed by `bind`. The kernel is a
handler `h q : Option (A q)` (no route is `none`); `run h p` returns the result
and the number of requests made. Each question `q` has a specification
`R q a`, and `Safe R post p` holds when `p` meets `post` whatever correct
answers it receives.

| Theorem | Statement |
|---|---|
| 14.14 | a handler returning only correct answers gives results meeting `post` |
| 14.15 | a sequence is safe when the first program establishes what the continuation needs |
| 14.16 | a program of question depth `n` makes at most `n` requests on any run |
| 14.17 | depths add under `bind` |

Continuations are needed when the sub-result has a different type from the
output, which delegation cannot express (for example, splitting a value and
requesting each part).

[Theory index](../THEORY.md)
