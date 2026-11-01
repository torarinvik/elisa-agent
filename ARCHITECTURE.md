# Architecture

How the theory in THEORY.md is realized in code. Each section of THEORY.md is
proved in `lean/NCA/` and, where implemented, mirrored in `src/nca/`; the
Python mirrors are tested against the behavior of the Lean model. The second
part records implementation details that the theory leaves open.

Build and check the proofs with `cd lean && lake exe cache get && lake build`;
run the Python tests with `uv run pytest`.

## Map

| THEORY.md | Lean (`lean/NCA/`) | Python (`src/nca/`) |
|---|---|---|
| §1 Types and contracts | `Contract` | `abi`, `registry` |
| §2 Planning | `Planner`, `Check` | `planner.plan`, `router.infer` |
| §3 Routing stability | `Routing` | `planner.plan_stable` |
| §4 Compositional reliability | `Reliability` | |
| §5 Reliability under distribution shift | `Shift` | `pipeline` |
| §6 Handwritten-arithmetic pipeline | | `modules.segmenter`, `modules.symbols`, `modules.digit_recognizer`, `modules.operator_recognizer` |
| §7 Measuring accumulation | `Routing` | `accumulation` |
| §8 Explicit route upgrades | `Upgrade` | `router.Router`, `router.sign_test` |
| §9 Module substitution | `Substitution` | `substitution` |
| §10 Complementarity | | `complementarity` |
| §11 Evaluation methodology | | `expressions`, `stats` |
| §12 Lazy loading and discovery | `Loading`, `Pruning`, `Eviction` | `loader`, `planner.plan_stable_indexed`, `scaling` |
| §13 Efficiency | `Cost`, `MinCost`, `Pareto` | `optimize`, `efficiency`, `workspace` |
| §14 Kernel-mediated requests | `Request`, `Cascade`, `Demand`, `Continuation` | `kernel`, `runtime`, `modules.refinement`, `cascade` |
| §15 Normalization against shift | `Normalize` | `modules.normalizer`, `baseline` |
| §16 Knowing when to be unsure | `Selective`, `Demand`, `Practice` | `ladder`, `selective`, `practice` |
| §17 Calibration under shift | `Calibration` | `certify` |
| §18 Noisy Boolean formulas | `Certificate` | `logic`, `formulas`, `modules.words` |
| §19 Error detection by the format | `Detection` | `logic`, `formulas` |
| §20 Higher-order experts, budgets | `Slots`, `Continuation` | `modules.combinators`, `optimize`, `kernel` |
| §21 Decoding by the format | `Decoding` | `formulas.decode`, `native.decoding` |
| §22 Abstaining early | `Detection` | `selective` (`floors`), `ladder` |
| §23 Efficient decoding | `Banding` | `native.decoding` (exact passes only) |
| §24 When the prior is wrong | `Misspecification` | not implemented |
| §25 Climbing order and stopping | `Stopping` | `ladder.stopping_rule` |
| §26 Composing cascades | `Composition` | not implemented |
| §27 Priors as experts | `Product` | not implemented |

## Native kernels

`src/nca/native/` holds optional kernels written in Elisa and built as CPython
extensions with `python -m nca.native` (needs `elisac-stage1`). Each has a
NumPy reference that gives the same results within rounding and is used when
the kernel is not built or `NCA_NATIVE=0`. `decoding.elisa` runs the exact
passes of §21.4 in linear space with per-row rescaling (THEORY §23.7).

## 1. Types and contracts

Type ids are strings and `seq[t]` is the sequence type (`nca.abi.seq_type`).

## 5. Reliability under distribution shift

`nca.pipeline` reports, per recognizer, the excess of in-situ over offline
failure rate: the lower bound on induced shift of `shift_ge_gap`.

## 6. Algorithms of the handwritten-arithmetic pipeline

**Segmentation** (`nca.modules.segmenter`). Ink columns (intensity > 0.1) are
grouped into runs; runs separated by fewer than 4 blank columns merge (the
gap was chosen on the `validation` split, where 4 minimizes segmentation
failures for 2, 8 and 32 operands; results in sections before §15 were
measured with a gap of 2, which split broken strokes more often). Each
run is cropped and translated so that its center of ink mass is at the center
of a 28×28 canvas, the MNIST normalization convention.

Fusion, parsing and the recognizers are parameterized by an operator
vocabulary: arithmetic (`+ − ×`, value type `int.v1`) and comparison
(`< > =`, value type `bool.v1`) use separate module ids and semantic types,
so installing one family cannot satisfy or alter the other's contracts.

## 7. Measuring accumulation

The add-and-freeze runner (`nca.accumulation`) checks the stability theorem
on real modules. For each task in a fixed suite, before and after installing
new modules, it records coverage (whether `planStable` finds a route),
whether the route is unchanged, accuracy, and the number of individual
answers that changed. Weight fingerprints (SHA-256 of each learned module's
parameters) verify that installation modified no existing module.

The `conflict` scenario reproduces `plan_not_stable` with learned modules. A
symbol classifier consuming `glyph.embedding.v1` is installed before the symbol
fuser but is dormant: no module produces its input type. Installing a glyph
encoder activates it. `plan` then routes every glyph through the classifier,
because it precedes the fuser in installation order, and previously correct
answers change; `planStable` keeps the original route.

## 9. Module substitution

`Registry.replace` refuses a substitute whose contract differs from the
original's (§9).

## 12. Lazy loading and scalable discovery

`ExpertStore.prepare(route)` implements the route-aware transition: the kernel
calls it before executing a route; it evicts only experts outside the route
(least recently used first), loads the missing ones, and pins the route's
experts until the next `prepare`. `tests/test_loader.py` reproduces the case
where least-recently-used eviction is not optimal (16 loads against the
optimal 11).

## 13. Efficiency

Each manifest declares its cost per invocation (`Manifest.cost`); the
workspace counts what a run spends (`Workspace.spent`).

`planMin` and `planPareto` are tested against exhaustive enumeration of all
searchable plans.

## 14. Kernel-mediated requests and refinement

**Continuations.** In `nca.runtime` a module's `invoke` may return a
generator: each yielded `Request` (of any type) is resolved at once, with the
requester added to the chain, so `resolve_avoids` and `RequestChain.length_le`
still apply, and the resolved value is sent back into the generator until it
returns its output. Demand-driven evaluation is unaffected: a continuation is
just a module.

**Relevance gates.** Requests are resolved lazily (`nca.runtime`). A module
may define `relevant(index, provisional)`, judging from the provisional values
of all its inputs whether input `index` can affect its result. An irrelevant
pending request is settled with the requester's provisional answer and
recorded as skipped; requests consumed without a declaration, mapped, or
returned are always resolved. `SymbolFuser` declares the digit reading
irrelevant on glyphs the operator recognizer judges to be operators. That gate
is not sound (a digit misjudged as an operator is skipped); `nca.cascade`
measures its cost as the answers that differ between gated and ungated
refinement.

**Demand.** In `nca.runtime` a consumer may declare `demand(index, demand)`;
arguments and `map` elements with empty demand are not evaluated, so neither
their modules nor the requests raised there run. `ExpressionParser` reads
digit entries at even positions, operator entries at odd ones, and nothing of
an even-length sequence; `SymbolFuser` reads its digit input only when digit
entries are demanded. Hence the digit recognizer never runs on operator
positions.

## 15. Normalization against shift

**Normalizer** (`nca.modules.normalizer.GlyphNormalizer`, contract
`GLYPH → NORMALIZED_GLYPH`). It scales the ink bounding box to 20 pixels,
centers it, then thickens or thins strokes (3×3 max or min, at most three
steps) until the ink fraction is in `[0.10, 0.21]`. This undoes size changes
and most stroke-width changes; it does not undo rotation or endpoint noise.
Recognizers trained with `--normalized` consume `NORMALIZED_GLYPH`, so the
planner routes glyphs through the normalizer; they are trained on the normal
style only.

## 16. Knowing when to be unsure

**Implementation** (`nca.ladder`, `nca.selective`). The controller is
generic over experts. A *ladder* for a contract is every installed module
with that contract whose output is a distribution, ordered by declared cost,
and each rung has its own temperature fitted on held-out labeled data by
negative log-likelihood. `SecondLook` wraps any such expert into a costlier
one with the same contract that averages its readings of several views, and
joins ladders like any other expert. `refine` reads every item on the bottom
rung and, while the summed risk `1 − max p` exceeds `δ`, moves the riskiest
item up one rung, using its latest reading. If no rung remains, the system
abstains. (Keeping the least risky of an item's readings instead would bias
the bound downward: in a trial the mean bound fell below the observed error,
voiding `selective_risk_le`.)

`nca.selective` applies the controller to a planned route ending in
single-input consumers over a `map`. What it reads comes from module
declarations, not from the task:

- **Which elements:** the map consumer's `demand`.
- **Which inputs of each element:** the map body's `demand`.
- **Which experts:** the ladders for the body's input contracts.
- **Segmentation:** if the map's source offers `alternatives` (the segmenter
  offers its runs, then merges of adjacent runs, narrowest gap first), a
  candidate the consumer would read nothing of is skipped without being read.
  The parser declares that it reads nothing of an even-length sequence, so
  this repairs split glyphs. On the test split 11% of 63-glyph expressions
  had one extra glyph (broken strokes; the validation half has almost none).

The arithmetic library installs cheap, expensive and (optionally) stronger
digit recognizers, the operator recognizer, and second looks (four one-pixel
shifts) of all but the cheapest. The stronger recognizer (`--arch wide
--augment`: a wider network trained six epochs on randomly rotated, shifted
and rescaled digits) reaches 99.19% on MNIST at about 10× the expensive
recognizer's compute.

**Practice** (`nca.practice`). Practice is offline. A copy of the recognizer
is fine-tuned on the queued glyphs mixed with 10,000 replayed MNIST training
digits, so the normal style is not forgotten. The new version is adopted only
if it beats the current one by a one-sided sign test on `validation`
expressions of both styles (§8). Training on the system's own unverified
answers is excluded, since it reinforces errors.

**Decision demand.** A map body declares `decides(index, demand)`. Readings are
computed only where decision-demanded; unread inputs are passed as `None`. A
randomized test checks that the parse is unchanged.

**Decision classes.** A map body declares `decision_classes(index, demand)`;
the controller computes the restricted risk from them.

## 18. A second domain: noisy Boolean formulas

### 18.8 Experts

| Module | Contract | Notes |
|---|---|---|
| tokenizer | text → sequence of noisy words | splits on spaces |
| edit reader | noisy word → word distribution | `p(w) ∝ exp(−d(x, w))`, with `d` the edit distance counting adjacent transpositions; symbolic, no training |
| character reader | noisy word → word distribution | a small network on one-hot characters, trained on the noisy words of training formulas at the calibration noise level, with a quarter of the connectives `xor` so that it knows every word |
| formula evaluator | sequence of word distributions → truth value | parses the most probable words; declares the certificate of §18.5 |

The two readers share a contract, so they form one ladder, cheapest first,
exactly as the digit readers do. The map body applies a reader directly to
each word. In arithmetic a fuser combines two readings per glyph. The
refinement adapter accepts both shapes, and a certificate is declared on
readings the consumer reads directly.

## 20. Higher-order experts and budgeted requests

**Budgets.** The runtime counts invocations against a budget in cost units
and, when a budget is set, allows repeats in the request chain; that is
`serve` (§20.6).

## 21. Decoding by the format

**Decoding interface.** The certificate needs the calibrated distribution of
the arity decision, not only its risk. The controller passes the consumer a
calibrated distribution for any grouped decision it names, alongside the risk
(§21.6).

## 25. Which word to climb, and when to stop

`nca.ladder.stopping_rule` estimates `P(A | s)` by binning calibration states
(§25.3).

## 26. Composing cascades

`Fallback.assess` evaluates a candidate chain on the audit restricted to the
inputs that reach it (§26.4).

## 27. Priors as experts

**Prior experts (planned).** The selective controller routes one sequence of
readings into a single-input consumer. A prior expert is a second input, so
the consumer's other arguments must be passed through `solve` (§27.3).
