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
| §23 Efficient decoding | `Banding` | `formulas.decode_banded`, `formulas.Split` (references), `native.decoding` (exact passes) |
| §24 When the prior is wrong | `Misspecification` | not implemented |
| §25 Climbing order and stopping | `Stopping` | `ladder.stopping_rule` |
| §26 Composing cascades | `Composition` | not implemented |
| §27 Priors as experts | `Product` | not implemented |

## Theorems

Each numbered theorem of THEORY.md and its formal statement in `lean/NCA/`.

| THEORY.md | Lean name | File |
|---|---|---|
| 1.1 | `WellTyped.mono` | `Contract` |
| 2.1 | `plan_sound` | `Planner` |
| 2.2 | `plan_complete` | `Planner` |
| 2.3 | `infer_iff` | `Check` |
| 3.1 | `plan_not_stable` | `Routing` |
| 3.2 | `planStable_sound` | `Routing` |
| 3.2 | `planStable_complete` | `Routing` |
| 3.3 | `planStable_append` | `Routing` |
| 4.1 | `composition_error_le_sum` | `Reliability` |
| 4.2 | `composition_success_ge_prod` | `Reliability` |
| 5.1 | `composition_error_le_shifted` | `Shift` |
| 5.2 | `offline_rate_insufficient` | `Shift` |
| 5.3 | `shift_ge_gap` | `Shift` |
| 8.1 | `route_sound` | `Upgrade` |
| 8.2 | `upgrade_valid` | `Upgrade` |
| 8.3 | `upgrade_target` | `Upgrade` |
| 8.4 | `upgrade_local` | `Upgrade` |
| 8.5 | `upgrade_rollback` | `Upgrade` |
| 8.6 | `route_append` | `Upgrade` |
| 8.7 | `PinsValid.append` | `Upgrade` |
| 9.1 | `substitution_change_le` | `Substitution` |
| 9.2 | `accuracy_transfer` | `Substitution` |
| 9.3 | `substitution_accuracy_ge` | `Substitution` |
| 12.1 | `WellTyped.contracts_subset` | `Loading` |
| 12.2 | `route_contracts_append` | `Loading` |
| 12.3 | `plan_derivable` | `Loading` |
| 12.4 | `Derivable.mono` | `Loading` |
| 12.4 | `plan_mono` | `Loading` |
| 12.5 | `plan_prefix_mono` | `Loading` |
| 12.6 | `planIdx_eq` | `Loading` |
| 12.7 | `planPruned_eq` | `Pruning` |
| 12.8 | `derivable_closure` | `Pruning` |
| 12.9 | `closure_oracle_sound` | `Pruning` |
| 12.10 | `load_lower_bound` | `Eviction` |
| 12.11 | `routeAware_load` | `Eviction` |
| 12.11 | `routeAware_optimal` | `Eviction` |
| 12.12 | `routeAware_switch` | `Eviction` |
| 12.13 | `routeAware_repeat` | `Eviction` |
| 13.1 | `Plan.cost_le_pow` | `Cost` |
| 13.2 | `Plan.cost_linear` | `Cost` |
| 13.3 | `route_cost_append` | `Cost` |
| 13.4 | `planMin_sound` | `MinCost` |
| 13.5 | `planMin_optimal` | `MinCost` |
| 13.6 | `front_cover` | `Pareto` |
| 13.7 | `planPareto_sound` | `Pareto` |
| 13.8 | `planPareto_cover` | `Pareto` |
| 13.9 | `planPareto_within` | `Pareto` |
| 14.1 | `resolve_sound` | `Request` |
| 14.2 | `resolve_avoids` | `Request` |
| 14.3 | `RequestChain.length_le` | `Request` |
| 14.4 | `cascade_error_eq` | `Cascade` |
| 14.5 | `cascade_le_fallback` | `Cascade` |
| 14.6 | `cascade_expected_cost` | `Cascade` |
| 14.7 | `gated_error_le` | `Cascade` |
| 14.8 | `gated_error_eq_of_sound` | `Cascade` |
| 14.9 | `gated_expected_cost` | `Cascade` |
| 14.10 | `DemandSound.comp` | `Demand` |
| 14.11 | `DemandSound.pair` | `Demand` |
| 14.12 | `DemandSound.map` | `Demand` |
| 14.13 | `DemandSound.exact` | `Demand` |
| 14.14 | `Safe.run` | `Continuation` |
| 14.15 | `Safe.bind` | `Continuation` |
| 14.16 | `Depth.run_le` | `Continuation` |
| 14.17 | `Depth.bind` | `Continuation` |
| 15.1 | `ShiftBound.map` | `Normalize` |
| 15.2 | `shift_le_of_invariant_on` | `Normalize` |
| 15.3 | `shift_zero_of_invariant` | `Normalize` |
| 16.1 | `selective_risk_le` | `Selective` |
| 16.2 | `threshold_optimal` | `Selective` |
| 16.3 | `bound_ge_floor` | `Selective` |
| 16.3 | `length_limit` | `Selective` |
| 16.4 | `restricted_risk_le` | `Selective` |
| 16.5 | `queued_value` | `Practice` |
| 16.6 | `unqueued_errors` | `Practice` |
| 16.7 | `queued_captures` | `Practice` |
| 16.8 | `proportional_value` | `Practice` |
| 17.1 | `selective_risk_le_excess` | `Calibration` |
| 17.2 | `shift_ratio_le` | `Calibration` |
| 17.3 | `horvitz_thompson` | `Calibration` |
| 17.4 | `inflated_answered_mono` | `Calibration` |
| 17.6 | `audit_budget_obstruction` | `Calibration` |
| 17.5 | `fixed_sequence_le` | `Calibration` |
| 18.1 | `grouped_risk_le` | `Certificate` |
| 18.2 | `certificate_error_le` | `Certificate` |
| 18.2 | `certificate_error_le_support` | `Certificate` |
| 18.3 | `cert_sound` | `Certificate` |
| 18.4 | `bestCert_valid` | `Certificate` |
| 18.4 | `bestCert_le` | `Certificate` |
| 18.5 | `bestCert_le_full` | `Certificate` |
| 18.6 | `code_prefix` | `Certificate` |
| 18.7 | `alternating_cert_leaves` | `Certificate` |
| 19.1 | `code_sum` | `Detection` |
| 19.2 | `code_no_single_change` | `Detection` |
| 19.3 | `detected_error_le` | `Detection` |
| 19.4 | `joint_le_restricted` | `Detection` |
| 19.5 | `two_occur_le_half` | `Detection` |
| 19.6 | `two_occur_le_pairs` | `Detection` |
| 20.1 | `HTyped.mono` | `Slots` |
| 20.2 | `embed_wellTyped` | `Slots` |
| 20.3 | `HPlan.cost_le_pow` | `Slots` |
| 20.4 | `HPlan.cost_mono` | `Slots` |
| 20.5 | `serve_sound` | `Continuation` |
| 20.6 | `serve_spent` | `Continuation` |
| 20.7 | `Prog.runB_le` | `Continuation` |
| 21.1 | `await_code` | `Decoding` |
| 21.2 | `code_accepted` | `Decoding` |
| 21.3 | `accepts_iff_codes` | `Decoding` |
| 21.4 | `dpSum_eq` | `Decoding` |
| 21.5 | `dpMax_ge` | `Decoding` |
| 21.6 | `dpMax_attained` | `Decoding` |
| 21.7 | `exact_risk_le_union` | `Decoding` |
| 21.7 | `one_sub_prod_le_sum` | `Decoding` |
| 22.1 | `detection_account_mono` | `Detection` |
| 23.1 | `tail_le_esym` | `Banding` |
| 23.2 | `factorial_mul_esym_le` | `Banding` |
| 23.3 | `outside_le_tail` | `Banding` |
| 23.4 | `sum_sub_le_diff` | `Banding` |
| 23.5 | `banded_risk_le` | `Banding` |
| 23.6 | `banded_risk_slack` | `Banding` |
| 23.7 | `dpSum_append` | `Banding` |
| 23.8 | `dpMax_append` | `Banding` |
| 23.9 | `sum_pair_dist` | `Banding` |
| 23.10 | `stitch_attains` | `Banding` |
| 23.13 | `selective_risk_le_approx`, `threshold_stable` | `Selective` |
| 23.12 | `revision_cache_eq` | `Selective` |
| 23.11 | `priority_allocation_sum`, `priority_allocation_nonneg` | `Selective` |
| 24.1 | `reweighted_odds` | `Misspecification` |
| 24.2 | `reweighted_risk_le` | `Misspecification` |
| 24.3 | `reweighted_risk_le_mul` | `Misspecification` |
| 24.4 | `dominated_risk_le` | `Misspecification` |
| 24.5 | `adversarial_prior` | `Misspecification` |
| 25.1 | `cost_ge_of_ratio` | `Stopping` |
| 25.2 | `pairs_ge_count` | `Stopping` |
| 25.3 | `lookahead_stop_optimal` | `Stopping` |
| 25.4 | `lookahead_continue_better` | `Stopping` |
| 26.1 | `fallback_cost_eq` | `Composition` |
| 26.2 | `fallback_cost_conditional` | `Composition` |
| 26.3 | `fallback_cost_sub_independent` | `Composition` |
| 26.4 | `fallback_cost_ge_independent` | `Composition` |
| 26.5 | `chain_error_eq` | `Composition` |
| 26.6 | `chain_cost_eq` | `Composition` |
| 26.7 | `split_error_eq` | `Composition` |
| 26.8 | `argmin_within` | `Composition` |
| 26.9 | `some_deviates_le` | `Composition` |
| 27.1 | `pdpSum_eq` | `Product` |
| 27.2 | `pdpMax_ge` | `Product` |
| 27.3 | `pdpMax_attained` | `Product` |
| 27.4 | `pdpSum_unit` | `Product` |

## Native kernels

`src/nca/native/` holds optional kernels written in Elisa and built as CPython
extensions with `python -m nca.native` (needs `elisac-stage1`). Each has a
NumPy reference that gives the same results within rounding and is used when
the kernel is not built or `NCA_NATIVE=0`. `decoding.elisa` runs the exact
passes of §21.4 in linear space with per-row rescaling (THEORY §23.7).
It also exports `advance`, `retreat`, `scores` and `trace`, the banded cursor of §23.4
(`trace` reads the decoded sequence off the max tables, `Split.best`):
`formulas.Split` keeps the forward and backward tables in NumPy arrays and the
kernel recomputes rows in place through `mutable view[f64]` parameters, which
borrow the arrays' writable buffers. With the kernel built, the sum tables are
linear rows of total 1 with per-row log scales (`forward_scale`,
`backward_scale`); without it, `Split` keeps them in log space.

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

## 23. Incremental risk allocation

`ladder.allocate_risk` distributes a current sequence risk over nonnegative
priorities (Theorem 23.11). It rescales priorities before summing to avoid
overflow and uses uniform weights when all priorities are zero.
`FormulaEvaluator.corrected` uses this allocation with its posterior marginal
risks. `certificate_session` creates a cursor and priorities owned by one solve;
`element_certificate` creates that session through an optional generic hook.
The correction account updates changed cursor rows and refreshes marginal
priorities every `isqrt(m)` changed rows. The current sequence risk and
within-certificate risks are recomputed each call. The raw answer decode and
per-word distribution preparation still run in full; making those incremental
and moving their hot loops to Elisa remains necessary.

`Distribution.revision(i)` identifies the item's rung within one refinement
run. The run fixes observations and calibration, so the rung identifies both.
The selective adapter preserves these revisions when mapping elements to
refined items. Plain distribution callbacks remain supported without revisions.

The correction session consumes distribution revisions to update calibrated
rows and invalidate within-group risk entries only for revised items. Cached
within-group risks are indexed by item and decoded arity, since a different
word's refinement may change the item's decoded arity. Distribution callbacks
without revision support recompute every row and invalidate every risk entry.
The raw answer decode and conversion of readings remain full passes.

The session also owns an independent raw-reading cursor for choosing the
answer's words. It compares raw rows, updates only changed arity masses, and
uses `Split.best` (native Elisa `trace` when available). The calibrated cursor
still computes the risk of that selected sequence, which need not maximize
the calibrated posterior. Both cursors remain scoped to one solve.

The optional native decoding module also exports `certificate`: the least-risk
certificate recurrence over parsed prefix trees, including right-child tie
preference. `FormulaEvaluator.evaluated` marshals opcodes and child indices to
Elisa; `evaluated_reference` remains the Python recurrence and fallback when
the native module or this export is absent. This implements the existing
certificate soundness and minimum-weight results (18.3–18.5).

`formulas.parse` uses native `parse_tree` for arities 0–2. It returns the
same child lists as `parse_reference`, with invalid inputs returning `None`.
The Elisa parser maintains an explicit parent stack, avoiding recursion depth
limits. Other arities and installations without the export use the reference.
The native result has two child slots per node; Python currently rebuilds
lists before certificate selection marshals them back into native arrays.

For the correction account, `certificate_words` combines parsing and
certificate selection inside Elisa. Invalid prefix words return an empty
result, which the account rejects. Child arrays remain native and are passed
as borrowed slices. The Python child-list route remains the fallback when
this export is absent. Existing format and certificate theorems cover the
composition; neither decoding weights nor certificate tie rules change.

`native.decoding.grouped_argmax` performs row-wise selection within supplied
class groups. `FormulaEvaluator.words` uses it after arity decoding; group ids
and scores are arguments, so the kernel is independent of the vocabulary.
Strict score comparison preserves the first class on ties, matching the
reference restricted argmax of §21.5. The Python loop remains the fallback.

Native grouped selection reuses the current `answer_readings` snapshot when
running inside a correction session. That snapshot is copied from the input
after changed rows have updated the cursor, so later caller mutation cannot
alter cached observations. Stateless word selection still prepares its own
score array. No extra observation/calibration cache assumption is needed.

`ladder.allocate_risk` validates inputs and dispatches to native `risk_shares`
when available. The Elisa loop rescales by the largest priority and uses
compensated summation; all-zero priorities get uniform weights. The existing
Python `math.fsum` path remains the fallback. Both implement Theorem 23.11;
small floating-point differences in charges can affect refinement tie order.

The correction account uses `formulas.sequence_log_weight` to score the
actual selected arity sequence under calibrated weights (§21.5). The native
reduction preserves position order, and accepts an explicit alphabet.
Unknown symbols have weight zero (log weight minus infinity); incompatible
matrix dimensions are rejected before entering native code. A Python
ordered-sum reference remains available when the export is absent.

Both correction cursors retain the last `Split.climb` return value for their
current normalizer, avoiding a second `scores` call at that same position.
When no row changes, they still obtain a score from the current tables. This
reuses the split result of §23.4 without altering its weights or arithmetic.

`Rung.distribution` can use native `calibrated_groups` for CPU observations
without gradients and partitioned decision groups. The kernel subtracts the
largest logit before exponentiation, sums probabilities by supplied group,
and returns the original tensor dtype. Temperature fitting is unchanged.
PyTorch remains the fallback for gradients, other devices, nonpartitioned
groups and missing kernels. Double intermediates may differ from PyTorch's
float32 arithmetic by rounding, requiring outcome checks on full runs.

The native calibration group-id array is cached by the immutable decision
key and marked read-only. It contains only decision structure; calibration
temperatures and observation values remain current. The revision-cache
invariant (23.12) applies to this deterministic metadata. Gradient-bearing
observations continue through PyTorch and retain differentiability.

`Rung.risk` also dispatches to native `calibrated_risk` for supported CPU
observations and partitioned groups. It chooses the group containing the
highest individual logit, preserving first-class ties, rather than choosing
the group with greatest total mass. Full-class risk uses singleton groups.
PyTorch remains the fallback under the same device/gradient restrictions as
grouped distribution. Native double arithmetic can change final rounding.

The selective certificate adapter caches immutable reading tuples by the
item's revision within one solve. Consumers still receive independent outer
lists, preserving earlier snapshots. Without revision metadata it refreshes
all tuples and clears revision history; returning to revision-aware calls
therefore cannot reuse values from an unversioned callback. This uses the
same revision invariant as calibrated state (Theorem 23.12).

The floor adapter has no distribution/revision argument and independently
converts current readings on each call. It does not share the certificate
adapter's tuple cache. Tests cover mapping fixed item indices back to source
elements, changed readings and snapshot independence. Ruff's `F821` check
rejects undefined names throughout source and tests.

The numerical allowance and threshold-margin results (23.13) specify how a
future certified roundoff envelope would enter selective answering. They do
not supply such an envelope for the kernels and do not change `refine`'s
threshold. Model validity, numerical error certification and empirical
cross-backend agreement remain separate obligations.

Risk-control audits certify the complete executed policy, including its
numerical backend and fixed calibration. Native-kernel changes should be
included in a new audit rather than inheriting certification from a different
backend solely because sampled outputs agree. The existing `logic --shift`
runner can audit the current correction path without a pointwise roundoff
allowance, subject to the sampling assumptions of §17.

`ladder.certification_possible` tests the zero-error upper bound for the
entire checking budget. `logic.shifted` skips candidate fit/check evaluations
when even that bound exceeds the target. The uncontrolled evaluation remains
unchanged, and feasible audit budgets use the existing fixed-sequence test.
The Lean obstruction theorem covers the zero-error power inequality; the
binomial bound's monotonicity in errors is used as its standard statistical
property, not newly formalized here.

For feasible audit budgets, `logic.shifted` computes checking outcomes lazily
in the fit-half-determined order. It stops at the first rejected candidate
and chooses maximum coverage only among the accepted prefix. Fit-half
candidate evaluation remains complete, and the order never changes in
response to checking labels. This implements §17.5's existing stopping rule.
