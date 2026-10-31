# Theory

Mathematical foundations of module composition. Every theorem stated here is
machine-checked in `lean/` (build with `cd lean && lake exe cache get && lake build`),
and every algorithm has a Python mirror in `src/nca/` that is tested against
the Lean model's behavior.

## 1. Types and contracts

Semantic types `Ty` are abstract, with decidable equality and a sequence
former: `seq : Ty → Ty`, recognized by a partial inverse `elem?` with
`elem? u = some t ↔ u = seq t` (`NCA.SeqTypes`). In Python, type ids are
strings and `seq[t]` is the sequence type (`nca.abi.seq_type`).

A **contract** is a list of input types and one output type. Modules are known
to the system only through their contracts; two values are compatible exactly
when their types are equal.

A **plan** is a composition graph:

| Plan | Meaning |
|---|---|
| `given t` | a task input of type `t` |
| `apply c ps` | contract `c` applied to the outputs of sub-plans `ps` |
| `map a body src` | `body` run on each element (of type `a`) of the sequence `src` produces; inside `body` the element is the only input |

**Well-typedness** `WellTyped lib avail p t` (`lean/NCA/Contract.lean`): `p` uses
only installed contracts `lib` and available inputs `avail`, and produces `t`.

| Rule | Premises | Conclusion |
|---|---|---|
| given | `t ∈ avail` | `given t : t` |
| apply | `c ∈ lib`, `ps : c.inputs` pointwise | `apply c ps : c.output` |
| map | `body : e` under inputs `[a]`, `src : seq a` | `map a body src : seq e` |

**Theorem (monotonicity, `WellTyped.mono`).** If `lib ⊆ lib'`, every plan
well-typed under `lib` is well-typed under `lib'`. Installing modules never
invalidates an existing valid composition.

## 2. Planning

`plan lib avail n t` (`lean/NCA/Planner.lean`, `nca.planner.plan`) searches
backward from the goal with depth bound `n`:

1. If `t ∈ avail`, return `given t`.
2. Otherwise try contracts in installation order; the first `c` with
   `c.output = t` whose inputs are all plannable at depth `n - 1` wins.
3. Otherwise, if `t = seq e`, try each candidate element type `a` (elements of
   sequence types that are available or produced by some contract, in that
   order); succeed when `e` is plannable from `[a]` and `seq a` from `avail`.

**Derivability** `Derivable lib avail n t` is the specification: a composition
of depth at most `n` exists (for `map`, with `a` a candidate element type).

**Theorem (soundness, `plan_sound`).** `plan lib avail n t = some p` implies
`WellTyped lib avail p t`.

**Theorem (completeness, `plan_complete`).** `Derivable lib avail n t` implies
`plan lib avail n t` succeeds.

## 3. Routing stability

The add-and-freeze protocol requires that installing a module does not
change how already solved tasks are solved.

**Theorem (instability, `plan_not_stable`).** The plain planner is not stable.
With `need1 : [x] → g`, `from2 : [y] → g`, input `y`, the planner routes `g`
through `from2`; installing `make1 : [y] → x` makes the higher-priority
`need1` applicable and the route changes, although the old route remains valid.

**Generation-layered planning** `planStable` (`lean/NCA/Routing.lean`,
`nca.planner.plan_stable`): plan with the first `k` installed contracts, for
the smallest `k = 0, 1, …, |lib|` that succeeds.

**Theorem (`planStable_sound`, `planStable_complete`).** Layered planning is
sound and complete in the same sense as `plan`.

**Theorem (stability, `planStable_append`).** If `planStable lib avail n t`
succeeds, then `planStable (lib ++ extra) avail n t = planStable lib avail n t`
for every `extra`.

Cost: at most `|lib| + 1` planner runs per goal; results can be cached per
installation generation.

## 4. Compositional reliability

Let an execution consist of finitely many invocations `i`, invocation `i`
failing on an event `fail i` with `μ(fail i) ≤ εᵢ`, and suppose the
**propagation hypothesis**: if no invocation fails, the result is correct
(`⋂ᵢ (fail i)ᶜ ⊆ correct`). Exact modules (parsers, arithmetic) have
`εᵢ = 0`. (`lean/NCA/Reliability.lean`.)

**Theorem (union bound, `composition_error_le_sum`).** For any measure,
`μ(correctᶜ) ≤ Σᵢ εᵢ`.

**Theorem (independent product bound, `composition_success_ge_prod`).** If μ
is a probability measure and the failure events are independent,
`μ(correct) ≥ Πᵢ (1 − εᵢ)`.

Use as falsifiable predictions:

- The union bound holds for every measure, including the empirical
  measure of a test set. Measured accuracy below `1 − Σ (in-situ failure rates)`
  therefore refutes the propagation hypothesis: some failure is not
  attributed to any module.
- Accuracy below the product bound indicates positively correlated failures.
- Failure rates must be measured **in situ**, on the inputs a module
  actually receives inside the composition. Rates measured on the module's
  own training distribution are not the `εᵢ` of the theorem when the
  upstream modules shift that distribution.

## 5. Algorithms of the handwritten-arithmetic pipeline

**Segmentation** (`nca.modules.segmenter`). Ink columns (intensity > 0.1) are
grouped into runs; runs separated by fewer than 2 blank columns merge. Each
run is cropped and translated so that its center of ink mass is at the center
of a 28×28 canvas, the MNIST normalization convention.

**Symbol fusion** (`nca.modules.symbols.SymbolFuser`). With operator
distribution `q` over `{+, −, ×, none}` and digit distribution `p`:
`P(op) = q_op`, `P(d) = q_none · p_d`. The result is a probability
distribution over the 13 symbols whenever `p` and `q` are.

**MAP parsing** (`ExpressionParser`). The grammar `digit (op digit)*` fixes the
class of each position. Under independent per-position distributions the
probability of a token string factorizes, so the most probable well-formed
expression is the per-position argmax restricted to the position's class.
Even-length sequences have no parse.

**Evaluation** (`Evaluator`). `×` binds tighter than `+` and `−`; terms are
accumulated left to right.
