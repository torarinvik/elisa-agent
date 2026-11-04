# Architecture

How the theory indexed in [THEORY.md](THEORY.md) is realized in code. Each chapter is
proved in `lean/NCA/` and, where implemented, mirrored in `src/nca/`; the
Python mirrors are tested against the behavior of the Lean model. The second
part records implementation details that the theory leaves open.

Build and check the proofs with `cd lean && lake exe cache get && lake build`;
run the Python tests with `uv run pytest`.

## Map

| THEORY.md | Lean (`lean/NCA/`) | Python (`src/nca/`) |
|---|---|---|
| [§1 Types and contracts](theory/foundations/01-types-and-contracts.md) | `Contract`, `Terms` | `abi`, `registry` |
| [§2 Planning](theory/foundations/02-planning.md) | `Planner`, `Check`, `Terms`, `Unification`, `PatternSearch` | `planner.plan`, `router.infer` |
| [§3 Routing stability](theory/foundations/03-routing-stability.md) | `Routing` | `planner.plan_stable` |
| [§4 Compositional reliability](theory/reliability/04-compositional-reliability.md) | `Reliability` | |
| [§5 Reliability under distribution shift](theory/reliability/05-reliability-under-distribution-shift.md) | `Shift` | `nca_arithmetic.pipeline` |
| [§6 Handwritten-arithmetic pipeline](theory/studies/06-algorithms-of-the-handwritten-arithmetic-pipeline.md) | | `nca_arithmetic.segmenter`, `nca_arithmetic.symbols`, `nca_arithmetic.digit_recognizer`, `nca_arithmetic.operator_recognizer` |
| [§7 Measuring accumulation](theory/studies/07-measuring-accumulation.md) | `Routing` | `nca_arithmetic.accumulation` |
| [§8 Explicit route upgrades](theory/evidence/08-explicit-route-upgrades.md) | `Upgrade` | `router.Router`, `router.sign_test` |
| [§9 Module substitution](theory/evidence/09-module-substitution.md) | `Substitution` | `nca_arithmetic.substitution` |
| [§10 Complementarity](theory/studies/10-complementarity.md) | | `nca_arithmetic.complementarity` |
| [§11 Evaluation methodology](theory/studies/11-evaluation-methodology.md) | | `nca_arithmetic.expressions`, `stats` |
| [§12 Lazy loading and discovery](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `Loading`, `Pruning`, `Eliminators`, `Eviction` | `loader`, `index`, `planner.plan_stable_indexed`, `registry`, `kernel`, `nca_arithmetic.scaling` |
| [§13 Efficiency](theory/foundations/13-efficiency.md) | `Cost`, `MinCost`, `Pareto` | `optimize`, `nca_arithmetic.efficiency`, `workspace` |
| [§14 Kernel-mediated requests](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `Request`, `Cascade`, `Demand`, `Continuation` | `kernel`, `runtime`, `modules.refinement`, `nca_arithmetic.cascade` |
| [§15 Normalization against shift](theory/reliability/15-normalization-against-shift.md) | `Normalize` | `nca_arithmetic.normalizer`, `nca_arithmetic.baseline` |
| [§16 Knowing when to be unsure](theory/reliability/16-knowing-when-to-be-unsure.md) | `Selective`, `Demand`, `Practice` | `ladder`, `selective`, `nca_arithmetic.practice` |
| [§17 Calibration under shift](theory/reliability/17-calibration-under-distribution-shift.md) | `Calibration` | `nca_arithmetic.certify` |
| [§18 Noisy Boolean formulas](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `Certificate` | `prefix`, `modules.edit`, `nca_boolean.logic`, `nca_boolean.formulas`, `nca_boolean.words` |
| [§19 Error detection by the format](theory/decoding/19-error-detection-by-the-format.md) | `Detection` | `prefix`, `shares`, `nca_boolean.logic`, `nca_boolean.formulas` |
| [§20 Higher-order experts, budgets](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `Slots`, `Continuation`, `Relevance` | `modules.combinators`, `optimize`, `kernel`, `runtime` |
| [§21 Decoding by the format](theory/decoding/21-decoding-by-the-format.md) | `Decoding` | `decoding.decode`, `prefix.PrefixEvaluator` (`decode`), `native.decoding` |
| [§22 Abstaining early](theory/reliability/22-abstaining-early.md) | `Detection` | `selective` (`floors`), `prefix.PrefixEvaluator.floor`, `ladder` |
| [§23 Efficient decoding](theory/decoding/23-efficient-decoding.md) | `Banding` | `decoding.decode_banded`, `decoding.Split` (references), `native.decoding` (exact passes) |
| [§24 When the prior is wrong](theory/decoding/24-when-the-prior-is-wrong.md) | `Misspecification` | not implemented |
| [§25 Climbing order and stopping](theory/reliability/25-which-word-to-climb-and-when-to-stop.md) | `Stopping` | `ladder.stopping_rule` |
| [§26 Composing cascades](theory/reliability/26-composing-cascades.md) | `Composition` | not implemented |
| [§27 Priors as experts](theory/decoding/27-priors-as-experts.md) | `Product`, `Decoding` | `priors.ArityPrior`, `priors.select_prior`, `nca_boolean.words`, `nca_boolean.logic` |
| [§28 Packages as experts](theory/foundations/28-packages-as-experts.md) | `Package`, `Loaders` | `objects`, `objects.loaders`, `packages`, `cache` |
| [§29 Types as objects](theory/foundations/29-types-as-objects.md) | `Refinement` | `objects.Constructor`, `packages.Upcast`, `domains.*.types` |
| [§30 Selection by evidence](theory/evidence/30-selection-by-evidence.md) | `Selection`, `Calibration` | `evidence` |
| [§31 Composing uncertainty](theory/reliability/31-composing-uncertainty.md) | `Risk`, `Pareto` | `evidence.route_risk`, `evidence.error_bound`, `evidence.rates`, `evidence.route_bound`, `packages.charge`, `optimize.plan_pareto` |
| [§32 Trust](theory/evidence/32-trust.md) | `Trust`, `Spot` | `evidence.trust`, `objects.Attestation.signature`, `evidence.Issuers`, `cache.ResultCache` (checks), `evidence.purity` |
| [§33 Per-input risk on any route](theory/reliability/33-per-input-risk.md) | `Selective`, `Risk` | `runtime.RiskLedger`, `ladder.Calibrated`, `evidence.answer_within`, `evidence.exact_by`, `evidence.refine_within`, `modules.refinement.Escalating` |
| [§34 Compiled routes](theory/foundations/34-compiled-routes.md) | `Batch` | `compile.compile_route`, `compile.NotCompilable`, `evidence.refine_batch`, `loader.LazyExpert.invoke_batch` |
| [§35 Calibration audits](theory/reliability/35-calibration-audits.md) | `Audit` | `evidence.Audit`, `evidence.audit`, `evidence.recalibrate` |
| [§36 Acquiring experts](theory/evidence/36-acquisition.md) | `Acquire` | `evidence.hotspots`, `evidence.acquire`, `evidence.Acquisition` |
| [§37 Calibration by groups of inputs](theory/reliability/37-grouped-calibration.md) | `Grouped` | `evidence.grouped.Grouped`, `evidence.grouped.fit_groups` |
| [§38 In-situ audits](theory/reliability/38-in-situ-audits.md) | `Sampling` | `runtime.Invocation`, `RiskLedger.invocations`, `evidence.sample_invocations`, `evidence.audit_invocations`, `Escalating.answering` |
| [§39 Answering over alternatives](theory/reliability/39-alternatives.md) | `Alternatives` | `evidence.alternatives.answer_over_alternatives`, `evidence.alternatives.Choice`, `evidence.alternatives.Tabled`, `evidence.alternatives.fit_table` |
| [§40 Audits by agreement](theory/reliability/40-agreement-audits.md) | `Agreement` | `evidence.cross_audit` |
| [§41 Verification](theory/reliability/41-verification.md) | `Verification` | `evidence.verification.answer_verified`, `evidence.verification.verified_bound`, `evidence.verification.verifier_rates` |

`prefix.PrefixEvaluator` reads per-position distributions over any
`RankedVocabulary` as a prefix term and evaluates it with semantics the domain
supplies; it carries the certificate, detection, correction and prior accounts
and their floors, so any domain whose answers are terms over a ranked alphabet
gets them by supplying its vocabulary, its semantics and, optionally, its
short-circuit rule. `nca_boolean.words.FormulaEvaluator` is the Boolean
instance. `nca_standard_experts.edit.EditDistanceReader` reads noisy strings against any
vocabulary. Formula data generation lives in `nca_boolean.formulas`; counter
decoding and incremental bands live in `decoding`; weighted automata and prior
selection live in `priors`. Numerical kernels remain in `native/decoding.elisa`,
with Python reference implementations for validation and fallback.

`decoding.cursors` implements the incremental `Split` and `CertifiedSplit`
tables; the `decoding` package retains whole-sequence passes, band selection,
shared backend selection and the public cursor exports. `prefix.vocabulary`
owns ranked vocabulary declarations and readout helpers; the `prefix` package
retains correction state, evaluation and its public vocabulary exports. Each
package initializes shared definitions before loading its implementation module.

## Development and optional packages

Install and test the independent core with `uv sync --extra trust`,
`.venv/bin/python -m pytest -q`, and
`NCA_NATIVE=0 .venv/bin/python -m pytest -q`. Build core kernels with
`uv run python -m nca.native`. Numerical libraries are declared infrastructure
dependencies; task-specific dependencies belong to their own distributions.

Expert checkouts may live anywhere outside this repository. Install an optional
collection into a chosen environment with
`uv pip install --python <environment-python> -e <package-checkout>`.
Before local distributions are published, pass the core and any generic expert
library checkouts explicitly to the same command. Their READMEs describe this
setup using developer-selected variables, not prescribed checkout paths.
The current entry-point boundary is sufficient for discovery; a dedicated
package-manager interface is future work.

## Layout

`src/nca/` is the generic core: the ABI, planners, index, kernel, runtime,
loader, ladders and selective refinement, statistics, decoding over ranked
alphabets, priors, prefix-term evaluation and its accounts (`prefix`,
`shares`), measured costs (`cost`), generic model interpreters and training
mechanisms, and core native kernels. Ready-made expert implementations are outside this repository. Nothing
in it names a task, a data set, or a domain type.

Expert implementations live in independent repositories outside this checkout.
Current optional distributions are `nca-arithmetic` (`nca_arithmetic`),
`nca-boolean` (`nca_boolean`), and the reusable `nca-standard-experts`
(`nca_standard_experts`) library. Each owns its source, tests, dependencies,
entry-point contribution and any package-specific native kernels. These are
research examples, not a core catalog. Checkout locations are chosen by each
developer and are never embedded in runtime code or distribution metadata.

The core declares no expert entry points and depends on no expert distribution.
Its source and tests import only core interfaces and declared infrastructure
libraries; `tests/test_layout.py` checks this boundary. Task packages can depend
on public generic expert libraries, but task domains never import each other.
Packages share semantic types by identical constructor contents, without
importing another domain's definitions. The generic learned-model interpreter
and training mechanisms remain core infrastructure, without preinstalled tasks.

The examples below refer to optional packages and require their installation.
They are not part of the core's tests or installation requirements.

## Theorems

Numbered theorems in the theory chapters and their formal statements in `lean/NCA/`.

### Guarantee status and proof debt

The mappings below identify formal statements, not end-to-end verification of
their Python implementations. In particular, the recent execution and memory
lemmas are supporting special cases. None closes the following key obligations.
Tests provide empirical evidence; they do not discharge universal statements.

| Relied-on guarantee | Status | Evidence and remaining obligation |
|---|---|---|
| Serialized in-memory artifact identity | Model proved; empirically linked | `Artifacts.run_retains`, `admitted_read_stable` and `run_read_identity` model checked decoding and non-overwriting hash-map admission for arbitrary codecs, digests, policies and operation interleavings. Python/Lean differential tests cover 512 operations, including real and colliding digests. Immutable bytes, lock linearization and codec/runtime fidelity are trusted library boundaries; decoded views are independently tested. |
| Artifact persistence, DAG validation and runtime fidelity | Open | The identity model does not prove filesystem atomicity, the dependency/index validation algorithm, JSON implementation correctness or loaded-expert behavior. `Execution/DependencyWalk` proves decreasing visit/emit work and absence of an infinite machine run under acyclic weights, exact per-step task accounting and preservation of dependency order when a fresh ready vertex is appended. `objects.Store.walk` and `flatten` use a shared explicit work stack; 1,024 DAGs with fixed topological order, mixed object kinds and duplicate edges match the recursive reference and decode each reached node once. The full DFS readiness/reachability argument, admission/runtime fidelity and byte-memory bounds are not mechanized. Save/reopen, collision, malformed schema and concurrent duplicate-admission tests provide empirical coverage only. |
| Native arithmetic implements the reference account | Open end-to-end | Differential tests include subnormal allocation and extreme temperatures. Builds require strict FP; compiler lowering, gradual underflow and external mathematical routines remain trusted. Exact-real lemmas and passing numerical tests do not prove arbitrary compiled floating-point execution. |
| Deterministic state threading under replay | Open | Process tests cover supplied deterministic experts. Model transitions, nested execution and replay; expert determinism and immutable payloads remain trusted assumptions. |
| Authority only narrows; every mediated operation is declared and granted | Open | Effect-scope tests cover runtime and compiled callbacks. Prove the full nested, batched, deferred and generator execution model. Cooperative gateways are trusted; arbitrary expert code is not isolated. |
| Failed transitions preserve state, memory and ledgers | Open; not currently satisfied | Process cursors retain the committed state, but execution can retain charges and memory writes. Joint transaction semantics are required before claiming failure atomicity. |
| Exact durable recall and bounded capacity | Open | `memoryInsert_recall`, `memoryInsert_preserves` and `memory_capacity` model a functional map and arithmetic admission. Model serialization, hash validation, concurrent transactions and persistent accounting; SQLite durability and hash collision resistance are trusted backend assumptions. |
| Append cursors survive eviction and reopening | Model proved; finite-linked | `cursorAppend_valid`, `cursorErase_valid` and `cursor_after_eviction` model a retained high-water mark, independent of live records. `memory.sqlite.MemoryStore` schema 2 updates that mark in the same transaction as admission; removal never decreases it. `tests/test_memory_cursors.py` exhausts 256 four-operation append/evict/reopen/duplicate traces against the model and injects transaction failure. SQLite isolation, crash durability and serialization remain trusted, not proved. Schema-1 migration requires a caller-certified upper bound covering deleted positions; it cannot be reconstructed from surviving records. These cursors support durable enumeration; statistical allocation and refusal replay use the separate history mechanism below. |
| Pinned routes and rejected updates preserve behavior | Open | Routing and publication lemmas cover abstract snapshots. Tests exercise old snapshots and rejected updates. Prove actual graph traversal, version pinning and publication; immutable expert implementations and resettable replay callbacks remain trusted. |
| Every affected route is replayed | Open | Tests cover arguments, maps, slots and reverse-index rebuilding. Model the real dependency traversal and reverse index, including shared nodes; opaque implementations must remain pinned. |
| Zero-loss admission preserves retained successes | Open end-to-end | `retained_zero_losses` proves the finite Boolean-list special case. Link attestation merging, record decoding, actual execution, scoring, both comparisons and atomic publication to that proposition. Scorer correctness is supplied by the caller. |
| Sampled admission remains sound under adaptive updates | Proved except the sampling step; empirically checked | `zeroLoss_miss`, `decisionLevel_total`, `allocate_fresh` and `sampledGate_sound` prove the sample size, the budget over unboundedly many decisions, that no case informs two decisions and the union over decisions and routes. That fresh i.i.d. cases give miss probability `(1-ℓ)^m` given the history is the stated sampling hypothesis, not proved in Lean; whether real retained pools are i.i.d. samples of a route's operating distribution is trusted. Tests name each theorem; the Python allocator is not differentially linked to `allocate`. |
| Regional corrections preserve behavior outside their region | Open end-to-end | Existing regional tests and mathematical special cases do not verify the implementation and router error jointly for arbitrary contributed experts. |
| Stable bounded plasticity | Proved for the default regulator; empirically linked | `smooth_unit`, `smooth_step`, `hysteresis_gap` and `reopen_after_settle` prove bounds, per-step movement and no flapping; `retention.plasticity` matches `Reliability/PlasticityReplay.lean` exactly over rationals on 64 generated trajectories. Other regulators are checked only for staying in [0, 1]. `retention.signals` derives inputs from runtime ledgers, audits and dependents; `meanSignal_unit`, `dependentStability_unit` and `dependentStability_mono` prove them in range. Signal quality depends on expert calibration, which audits check. |
| Safe consolidation | Proved; empirically checked | `published_only_if_admitted` and `allocate_skips_drawn` prove that a consolidated piece is published only through the gate and that training on drawn cases keeps later gate cases fresh; `retention.consolidation.consolidate` enforces the freshness rule. Distiller quality is the caller's; the gate checks it. |
| Bounded retained evidence and safe eviction | Proved; empirically checked | `evict_keeps_protected` and `withdraw_fresh` prove that ordinary eviction keeps protected records and that withdrawal keeps later draws fresh; `MemoryStore.remove` refuses parents. SQLite deletion durability is a trusted backend assumption. Forced deletions are assumed independent of the estimated loss. |
| Safe migration | Open; not implemented | Shared-representation migration, and its composition with updates, consolidation and eviction, is not established. |
| Bounded connectors through a hub | Proved; empirically checked | `hubConnectors_card`, `hub_routes`, `direct_connectors_lower`, `hubConnectors_mono` and `hub_route_risk` prove 2N connectors, two-step routes, the N(N−1) pairwise lower bound, locality and additive route risk; `tests/test_hub.py` checks planning through a hub. |
| Hub learned by attachment | Proved; empirically checked | `attached_risk` and `attachment_depth_risk` bound a type's hub risk by its fit risk plus its partner's, and by `dε` at depth `d`; `tests/test_hub_learning.py` checks `learning.hub.attach`. The sampling bound for each fit is not formalized. |
| Hub migration by a bridge | Proved; empirically checked | `bridged_keeps`, `bridged_routes`, `bridged_card` and `bridged_route_risk` prove that bridging keeps both versions' routes, joins them in three steps with at most two new connectors and adds the bridge's risk; `tests/test_hub_learning.py` checks a bridged plan. |
| Refined pieces in general slots | Proved; empirically checked | `slot_risk_transfer` bounds a consumer's risk on refined inputs by `c` times its measured rate under a density-ratio certificate, and `slot_risk_unbounded` shows no rate transfers without one; `route_risk(shift=…)` charges `min(1, c · rate)` and returns `None` without a certificate, checked by `tests/test_slot_risk.py`. Obtaining certificates from data is not addressed. |
| Containment and complete effect attribution | Open | Permission checks are cooperative. There is no OS-isolation guarantee or complete transactional audit of arbitrary expert effects. |
| Stored artifacts survive core reorganization | Model proved; empirically linked | `resolveLoader_relocate`, `resolveLoader_perm`, `resolveLoader_unrelated` and `resolveLoader_conflict` prove that resolution of stored identifiers is order-free, unaffected by other identifiers' registrations, refuses conflicts and follows injective code moves. `objects.loaders.location` matches `Execution/LoaderReplay.lean` on 256 generated registries; legacy import-path entries are registered aliases. Entry-point metadata parsing and each factory's fidelity to its identifier are trusted. |
| Unreachable goals become typed acquisition sub-goals | Proved; empirically checked | `gap_iff` characterizes single-connector repairs of unary routes exactly and `horn_gap_iff` single-expert repairs with any number of inputs; `planner.gaps` confirms every candidate by planning with a stand-in, and `Kernel(acquire=…)` serves an unservable request through an acquired connector, checked by `tests/test_gaps.py` against the planner over every type pair. `repair_complete` and `repair_sound` characterize repairs with `k` allowed connectors; `planner.gaps.fewest_missing` is checked minimal against brute force. The 0-1 search itself is not formalized, experts with several inputs are approximated in the search and confirmed by the planner, and media (invented intermediate types) are proved not to change reachability (`founded_keeps`, `founded_medium`); whether growing one is worth its requests is measured, not proved. |
| Acquired connectors are certified before use | Proved; empirically checked | `acquisition_sound` with `zeroLoss_miss` bounds the probability of admitting any connector erring above `ε` by `δ` across all requests; `retention.acquisition.CertifiedAcquirer` implements the test and `tests/test_certified_acquisition.py` checks admissions, refusals and the false-admission rate. Independence of fresh cases is assumed, not established. |
| Impossible deterministic contracts can be screened before fitting | Proved under stated semantic and sampling hypotheses; finite-linked | `contradictory_pairs_errors` proves that disjoint incompatible pairs force distinct errors; `contradiction_screen_risk` gives `binom(n,r) εʳ` under a joint-error bound on the original cases. Fresh conditional IID sampling implies that hypothesis but is not formalized here. `retention.screening.FeasibilityScreen` keeps all unmatched observations, checks disjoint pair certificates and uses exact rational thresholds. `unmatched_append`/`unmatched_remove` preserve unmatched independence; `maximal_pairs_half` bounds any endpoint-covered alternative matching by twice the returned pair count. All 1,024 ordered five-vertex graphs are checked against brute-force maximum matching. Callback purity, key bucketing, traversal fidelity and certificate validation remain executable boundaries; `CertifiedAcquirer` reuses passing prefixes for training and retains fresh final certification. `tests/test_acquisition_screening.py` exhausts small samples and predictors and exactly enumerates a false-discard experiment. Key equivalence and separation soundness for the actual agreement rule are caller assumptions; passing is inconclusive, stochastic/hidden-state predictors are outside the guarantee. Optional persisted reuse is governed by the following row. The family budget uses the same telescoping union bound as `acquisition_sound`, separately from admission confidence. |
| Durable scoped acquisition refusals | Model proved; empirically linked | `durable_refusal_risk` bounds replayed false refusals by the original rejection events over any finite subset of non-reused spending indices. `retention.history.AcquisitionHistory` commits nonce-bearing reservations through `MemoryBackend.append_position` before sampling, and `CertifiedAcquirer` uses their indices for both screening and admission. Only screened impossibility is cached; keys include the full contract, caller-versioned semantic context, tolerance and both confidence budgets. The incremental index is bounded and checks retained references; misses and eviction cause fresh reservations. Tests cover restart reuse, changed scope, interrupted sampling, eviction, bounded-index misses, full storage and duplicate tickets. Conditional sampling, semantic scope identity, trusted history writers, nonce freshness and backend durability are assumptions; all tests in one confidence family must share a non-rewinding backend. Planner callback avoidance and storing learned implementations remain open. |
| Depth-independent risk by redundancy | Proved; empirically checked | `vote_correct` and `vote_risk` bound a majority over disjoint routes by `e_t` of their risks under independent failures; `evidence.redundancy` plans disjoint routes, votes and computes the bound, checked by `tests/test_redundancy.py` against exact enumeration and simulation. Independence is assumed, not established. |
| Staged training with fresh certification | Proved under the existing sampling hypothesis; finite-linked | `staged_acquisition_sound` specializes the nested confidence union bound to declared training stages and early stopping. `CertifiedAcquirer(stages=…)` splits each request level conservatively with `family_audit_alpha`, fits bounded training prefixes and tests each frozen candidate on new cases. Failed-test cases can train later candidates, never certify them; retained cases are capped by `train`. Default acquisition has one stage. `tests/test_staged_acquisition.py` checks unseen-case memorizer refusal, reuse without double charging, early/later acceptance, contract matching, stage validation and exact-rational budget bounds over all subsets of up to eight stages. Conditional IID sampling, candidate immutability and the existing floating-point sample-size implementation remain trusted boundaries. No learning-rate or universal efficiency claim is made. |
| Supplied acquisition priorities preserve valid candidates | Model proved; finite-linked | `acquisition_order_valid` proves that permutation preserves candidate validity. `planner.gaps.gaps(priority=…)` stably sorts already-confirmed candidates with finite scores, and `repair(priority=…)` uses that order in its single-gap search without pruning; `Kernel(priority=…, arity=…)` exposes it to mediated acquisition requests. Multi-step fewest-missing paths retain their order. `acquisition_swap_difference` and `acquisition_swap` prove the local expected-cost exchange criterion for fixed independent success chances and costs; supplied estimates need not satisfy those assumptions. `tests/test_acquisition_priority.py` checks candidate preservation, tie order, complete refusal traversal, nonfinite-score rejection, preferred repair, kernel-mediated multi-input acquisition and exact rational exchange costs. Python sorting and scorer purity remain trusted. The learned success-frequency scorer lives only in the benchmark; calibrated semantic prediction, context transfer and performance guarantees for adaptive scores remain open. |
| Majority risk without independent failures | Proved under marginal-risk and measurability hypotheses; finite-linked | `vote_omit_forces`, `dependent_vote_risk` and `dependent_majority_bound` prove that omitting r indices leaves at least t−r failures, then bound the remaining count by Markov without independence. `evidence.redundancy.dependent_vote_risk` minimizes the resulting bounds by omitting the largest marginals; exact rational evaluation and upward float conversion prevent numerical understatement. The independent `vote_risk` now uses the same conservative numerical discipline and both reject invalid probabilities. Tests enumerate dependent two-atom joint laws, all omitted-subset bounds for small risk vectors, exact independent products and subnormal underflow. Sorting, probability inputs and runtime failure semantics remain trusted; measured marginals need separate coverage guarantees outside an exactly enumerated distribution. No reliability amplification or risk-targeted acquisition is claimed from dependence alone. |
| Acquire toward a jointly certified vote target | Proved under stated fresh-case hypotheses; empirically linked | `ensemble_miss` applies the zero-loss bound to the entire vote error, including abstention; `ensemble_search_sound` reuses the staged confidence union bound, without any route-independence hypothesis. `retention.ensembles.EnsembleSearch` asks a supplied route acquirer up to declared counts and returns the first vote passing a fresh test. `retention.certification.zero_loss_test` is shared with `CertifiedAcquirer`; bounded retention, early stopping, insufficient draws and exception-time label accounting are tested. Exhaustive small Boolean histories link its admission to `earlyTest_admits`. Tests distinguish abstention from a unanimous None payload and cover stopping, common-mode refusal, unavailable/wrong-output routes and durable confidence continuation. Conditional IID sampling, truthful agreement, typed route/runtime fidelity, fixed expert/resolver behavior and backend durability remain assumptions; no saved-certificate restoration or learned proposal policy is proved. Refusal is not cached as impossibility. |
| Counterexamples inform later acquisition | Conditional progress proved; transport empirically linked | `EnsembleSearch(feedback=…)` emits one `VoteFailure` after a scored rejection, including the last stage; admission, insufficient data and execution/scoring exceptions emit no counterexample. The handler receives the failed vote, case and drawn count and may inform later proposals or searches. It cannot make old draws fresh; `ensemble_search_sound` still requires new conditional IID certification cases and fixed candidate behavior. `feedback_repair_progress` and `feedback_chain_bound` prove strict error-count progress only when the supplied learner removes the reported error without new errors. Tests check callback order, first-failure selection within a batch, no admission-data leakage, exception accounting, new draw identifiers and exhaustive finite-set progress. The benchmark supplies domain-specific simulator labels outside the core and audits regressions; inference of intermediate supervision, monotonicity of arbitrary fitters and persistent feedback retention remain open. |
| Whole-candidate revision from endpoint feedback | Proved conditionally; empirically linked | `EnsembleSearch.revise` requests a fresh nonempty candidate family within each declared cap and supplies earlier closed-test failures. Repeated caps support same-size revisions. Both growth and revision use one `_search` path and the existing `ensemble_search_sound` confidence allocation; no old implementation is mutated or automatically published. `keyCorrection_outside` and `endpoint_correction_errors` prove pointwise preservation for a supplied injective key and truthful endpoint label, linked to the existing `learning.discovery.Corrected` interpreter by exhaustive finite tests. These hypotheses are not inferred for arbitrary features or noisy targets. Tests cover curriculum order, candidate caps, immutable incumbents and configurable export/kernel planning depth. `install`, `install_scopes` and `Kernel` now expose planning fuel separately from execution budget. Export result-cache identities include planning/execution configuration while artifact bindings remain stable; binding-level purity refutations still disable caching. Generic `cache_identity` overrides are tested against different routes selected at different fuel values. The benchmark uses the existing correction learner through an exported public interface, with no new intermediate supervision; initial pretraining remains supervised. Unrestricted repair-feature discovery, certificate persistence and automatic publication remain open. |
| Remaining foundation guarantees | Open | Adaptive label efficiency, compression, shape-parametric refinement, semantic planning, arbitrary-policy preservation and distributed consistency require their own mechanism-level proofs and scaling curves. Existing numbered lemmas alone do not close these obligations. |

Supplied-feature endpoint repair (§31.12) now optionally retains a bounded
successful prefix from a rejected test (`EnsembleSearch.retain_controls`).
`propose_corrections(preserve_successes=True)` forbids corrections that break
observed incumbent successes. `keyCorrection_protected` proves this finite
guarantee; `fiber_correction_errors` proves global preservation only under
truth-constant fibers. Exhaustive finite fitting tests and scored-prefix tests
link the mechanisms. Controls are selected training data, never fresh audit
data. The nuisance-variation benchmark demonstrates generalization using
supplied positional features; retaining controls saved no labels and increased
CPU in this experiment. Learning new features and global fiber sufficiency,
adaptive control retention and certified candidate publication remain open.

`learning.features.compose_features` (§36.59–60) constructs compatible
feature trees breadth-first, retaining distinct paths and cycles through
caller-supplied depth and candidate bounds. It inspects metadata only and uses
the existing `Decoded` interpreter for contract/effect/cost composition. The
`featureClosure_iff` theorem proves bounded endpoint reachability in the
untruncated relation model; finite graph tests compare actual path enumeration,
including capped prefixes, and test that search invokes no expert. The relation
model assumes faithful contract matching and does not identify implementations
sharing a type. The repair benchmark learns a useful chain from supplied parts,
but does not invent primitives or prove useful features exist in an arbitrary
installed library.

The §36.60 extension admits any positive number of ordered inputs on ground
slot-free transformations. `AppliedFeature` evaluates each branch separately,
forwards the shared external inputs and slot fillings, and adds branch costs,
effects and slot-call declarations. Search gives each tree one leftmost deepest
child pivot; bounded prefixes may omit useful trees. `featureTreeClosure_iff`
proves bounded root-type reachability from all rule antecedents, not just one
edge; exhaustive finite-rule tests compare actual tree sets, duplicates and
prefix order, while repeated-type tests exercise binary/ternary positions and
slot forwarding. Pivot uniqueness is justified mathematically and finite-tested,
not proved for the Python implementation. Higher-order/polymorphic transformation
search and practical large-library enumeration remain open; no universal
learning gain is claimed.

Multi-input applications now participate in shared graph retention (§36.61).
`nca/application@1` restores a head and ordered feature bindings, including
repeated references. `AppliedFeature` recomputes contract/effect/cost/call
metadata; the normal primitive loader checks it against the declaration.
`featureApplication_reloaded_eq` proves conditional function equality for
arbitrary heterogeneous argument positions, not executable codec fidelity.
Round-trip tests cover nested trees, a shared head, repeated slot branches,
lazy unique-component loading, argument-order identity and malformed binding
positions. Retained sharing saves implementation storage, not branch executions.
The benchmark fits a fully supervised head and freshly certifies reopened graphs;
it establishes parameter reuse on one task, not hidden-state restoration,
certificate persistence or transfer to new distributions.

Feature enumeration now uses lazy rule-position buckets and per-height branch
type indices (§36.62). Buckets retain library order, repeated entries and
argument positions. Rules are read incrementally so an early capped prefix
does not build the unread suffix. `feature_index_filter` proves ordered
flattening unchanged when excluded entries produce no candidates. The full
Python index construction and recursive search remain finite-linked: tests
compare exact trees and prefixes with the pre-index full-scan reference in
`benchmarks/feature_search.py`, alongside exhaustive bounded closure checks.
The benchmark measures manifest reads, CPU and incremental traced allocations;
it makes no expert invocations or label requests. Indices trade memory for
less incompatible scanning and do not reduce compatible-tree combinatorics.
No learned prioritization, semantic pruning or universal speedup is asserted.

`compose_features(index_entries=…)` (§36.63) now bounds prefetched rule-position
entries for unqueried types. None preserves broad prefetch; zero caches only
completed queried buckets. Finite budgets prefetch a contiguous whole-rule
prefix; lookup combines its matches with a filtered suffix of cached contract
headers. `feature_demand_index_eq` proves faithful completed-cache lookup, and
`feature_demand_prefix_filter` proves ordered prefix/suffix recombination.
Neither proves Python index construction or a total byte bound. Headers,
completed queried buckets and returned models are outside the prefetch budget.
Finite exhaustive differential tests cover zero, finite and unbounded budgets,
including capped prefixes and unread library suffixes. CPU and allocation passes
disable diagnostic read-counter increments; reads are counted separately.
Measurements show a memory/CPU tradeoff as queried-type diversity grows, so
the existing broad policy remains the default. Repeated header scans, complete
resource accounting and useful candidate prioritization remain open.

Compact repeated lookup now optionally packs the unprefetched suffix into
integer hash/rule-position/input-position records (§36.64). The Elisa
`native/records.elisa` kernel selects equal-column rows in order; Python then
checks full type identifiers, so hash collisions never define equality.
Packing happens only after headers are complete and a new query needs the
unprefetched suffix; early stopped and fully prefetched searches avoid it.
`feature_coarse_filter` proves exact rechecking removes arbitrary coarse
false positives when no exact match is omitted. Exhaustive integer-table
tests, invalid shapes, signed extremes, forced hash collisions and existing
ordered-prefix comparisons link the implementation. The compiler, buffer ABI,
stable hash equality and faithful packing remain trusted boundaries. Packing
adds allocation and may slow small searches. NCA_NATIVE=0 retains the Python
path; no universal speedup or total-memory bound follows. The current local
Stage1 snapshot and compiler checkout both identify f69873914 and compile the
new kernel successfully; no compiler change was needed.

`compose_features(priority=…)` (§36.65) optionally scores eligible ground,
positive-arity, slot-free transformations once per entry and stably sorts
highest first. Nonfinite scores fail; default None preserves lazy library
order. Opt-in ranking inspects the eligible library and changes capped prefixes,
so scorer work is caller-owned and must use training/history only. It does not
invent transformations or calibrate semantic scores. `feature_priority_closure`
proves bounded root-type closure invariant under a rule permutation; Python
sorting and full program enumeration are not formally verified. Tests check
exact ranked order, stable ties, ineligible filtering, once-per-entry scoring,
uncapped family equality and nonfinite rejection. The benchmark learns an
empirical predictability score from a separate task and charges its labels and
fits before transfer to related relabelings. Wider search and learned ranking
serve the same tasks in that family; arbitrary-task transfer, adversarial score
quality and universal compute or label savings remain open.

`EnsembleSearch.retain_training` (§31.13) exposes a bounded prefix of already
charged draws only after a scored rejection, including unscored final-batch
cases. It reuses the shared `zero_loss_test` retention path. The explicit
`VoteFailure.training` may overlap the first failure and controls, so consumers
choose one evidence source or deduplicate draw identifiers. Defaults retain
nothing. `retained_feedback_account` proves no additional label identifiers
and transfers disjointness from drawn to retained evidence; tests check actual
batch tails, caps, label/evaluation counts and no admission/incomplete-test
leakage. Identifier freshness does not prove conditional IID sampling. An
endpoint-only experiment fits existing projection/threshold learners from
this feedback, without supplied feature directions or intermediate labels.
Both scored controls and drawn prefixes learn successfully; drawn prefixes
did not save validation labels. Generalization remains independently tested,
not a consequence of the retention theorem.

`store_acquired_models` now retains exact `Corrected` runtimes (§31.14) through
the same shared graph traversal as other learned models. The stable
`nca/correction@1` interpreter restores two content-bound children, a canonical
structural correction table and explicit overhead cost. It rejects duplicate
decoded keys and recomputes metadata; constructor validation rejects mismatched
external signatures and invalid costs. Tests cover table-order identity, tuple
keys/labels, present None values, unseen-key fallback, immutable snapshots,
malformed metadata and exhaustive small lookup tables. `correction_reloaded_eq`
proves function equality conditional on faithful children and lookup, not codec,
filesystem or executable fidelity. Binding resolution now refuses exports
whose nondefault execution configuration would change on default installation.
Exact `Export` nodes are now retained with their execution settings as described
below; opaque bindings still refuse configuration changes. Saved model
parameters contain no admission certificate. The restart benchmark freshly certifies each reopened model and
measures parameter reuse against forgetful retraining.

Configured acquired composites (§36.66) retain their actual ordered member graph,
export position, planning fuel, execution budget and manifest-length parameter.
`learning.export_objects` rebuilds exports from retained member bindings rather
than reinstalling their original composites with defaults. Their primitive
wrappers declare internal risk accounting. `configuredExport_reloaded_eq` in
`Planning/FeatureClosure` proves interpretation equality conditional on identical
settings and faithful semantic member descriptors; tests exercise real planning,
refusal and save/reopen. Mutable expert state, opaque binding fidelity and
filesystem atomicity remain outside this guarantee.

Every open row requires a mechanism-level theorem, explicit assumptions and
executable differential or theorem-linked property tests before it is treated
as proved. Interleavings between mechanisms are an additional obligation, not
an inference from their separate tests.

| THEORY.md | Lean name | File |
|---|---|---|
| [1.1](theory/foundations/01-types-and-contracts.md) | `WellTyped.mono` | `Contract` |
| [1.2](theory/foundations/01-types-and-contracts.md) | `WellTyped.subst` | `Terms` |
| [2.1](theory/foundations/02-planning.md) | `plan_sound` | `Planner` |
| [2.1](theory/foundations/02-planning.md) | `planShallow_sound` | `Routing` |
| [2.2](theory/foundations/02-planning.md) | `zero_fuel_nonempty_inputs` | `Planner` |
| [2.2](theory/foundations/02-planning.md) | `traverse_singleton` | `Planner` |
| [2.2](theory/foundations/02-planning.md) | `zero_fuel_map_children` | `Planner` |
| [2.2](theory/foundations/02-planning.md) | `renVar_ne_external`, `renVar_injective` | `PatternSearch` |
| [2.2](theory/foundations/02-planning.md) | `subst_ground` | `PatternSearch` |
| [2.2](theory/foundations/02-planning.md) | `HTypedSlots.has_filling` | `Slots` |
| [2.2](theory/foundations/02-planning.md) | `plan_complete` | `Planner` |
| [2.3](theory/foundations/02-planning.md) | `infer_iff` | `Check` |
| [2.4](theory/foundations/02-planning.md) | `Contract.subst_determined` | `Terms` |
| [2.5](theory/foundations/02-planning.md) | `InstanceOf.subst`, `answer_sound` | `Terms` |
| [2.6](theory/foundations/02-planning.md) | `Term.subst_app_ne` | `Terms` |
| [2.7](theory/foundations/02-planning.md) | `mgu_exists` | `Unification` |
| [2.8](theory/foundations/02-planning.md) | `unifies_eqSubst`, `isMGU_append` | `Unification` |
| [2.9](theory/foundations/02-planning.md) | `Skel.sound`, `Skel.complete`, `Skel.most_general` | `PatternSearch` |
| [2.10](theory/foundations/02-planning.md) | `SeqMGU.isMGU`, `SeqMGU.exists` | `PatternSearch` |
| [3.1](theory/foundations/03-routing-stability.md) | `plan_not_stable` | `Routing` |
| [3.2](theory/foundations/03-routing-stability.md) | `planStable_sound` | `Routing` |
| [3.2](theory/foundations/03-routing-stability.md) | `planStable_complete` | `Routing` |
| [3.2](theory/foundations/03-routing-stability.md) | `planShallow_complete`, `planShallowStable_sound`, `planShallowStable_complete` | `Routing` |
| [3.3](theory/foundations/03-routing-stability.md) | `planStable_append` | `Routing` |
| [3.3](theory/foundations/03-routing-stability.md) | `planShallowStable_append` | `Routing` |
| [4.1](theory/reliability/04-compositional-reliability.md) | `composition_error_le_sum` | `Reliability` |
| [4.2](theory/reliability/04-compositional-reliability.md) | `composition_success_ge_prod` | `Reliability` |
| [5.1](theory/reliability/05-reliability-under-distribution-shift.md) | `composition_error_le_shifted` | `Shift` |
| [5.2](theory/reliability/05-reliability-under-distribution-shift.md) | `offline_rate_insufficient` | `Shift` |
| [5.3](theory/reliability/05-reliability-under-distribution-shift.md) | `shift_ge_gap` | `Shift` |
| [8.1](theory/evidence/08-explicit-route-upgrades.md) | `route_sound` | `Upgrade` |
| [8.2](theory/evidence/08-explicit-route-upgrades.md) | `upgrade_valid` | `Upgrade` |
| [8.3](theory/evidence/08-explicit-route-upgrades.md) | `upgrade_target` | `Upgrade` |
| [8.4](theory/evidence/08-explicit-route-upgrades.md) | `upgrade_local` | `Upgrade` |
| [8.5](theory/evidence/08-explicit-route-upgrades.md) | `upgrade_rollback` | `Upgrade` |
| [8.6](theory/evidence/08-explicit-route-upgrades.md) | `route_append` | `Upgrade` |
| [8.7](theory/evidence/08-explicit-route-upgrades.md) | `PinsValid.append` | `Upgrade` |
| [9.1](theory/evidence/09-module-substitution.md) | `substitution_change_le` | `Substitution` |
| [9.2](theory/evidence/09-module-substitution.md) | `accuracy_transfer` | `Substitution` |
| [9.3](theory/evidence/09-module-substitution.md) | `substitution_accuracy_ge` | `Substitution` |
| [11](theory/studies/11-evaluation-methodology.md) | `paired_zip_length` | `Calibration` |
| [12.1](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `WellTyped.contracts_subset` | `Loading` |
| [12.2](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `route_contracts_append` | `Loading` |
| [12.3](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `plan_derivable` | `Loading` |
| [12.4](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `Derivable.mono` | `Loading` |
| [12.4](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `plan_mono` | `Loading` |
| [12.5](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `plan_prefix_mono` | `Loading` |
| [12.6](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `planIdx_eq` | `Loading` |
| [12.7](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `planPruned_eq` | `Pruning` |
| [12.8](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `derivable_closure` | `Pruning` |
| [12.9](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `closure_oracle_sound` | `Pruning` |
| [12.10](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `load_lower_bound` | `Eviction` |
| [12.11](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `routeAware_load` | `Eviction` |
| [12.11](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `routeAware_optimal` | `Eviction` |
| [12.12](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `routeAware_switch` | `Eviction` |
| [12.13](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `routeAware_repeat` | `Eviction` |
| [12.15](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `demanded_missing_le` | `Eviction` |
| [12.16](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `pinned_next_fits` | `Eviction` |
| [12.17](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `derivable_seq_source` | `Pruning` |
| [12.18](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `plan_prefix_append` | `Loading` |
| [12.19](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `HTyped.eclosure`, `ECl.trans` | `Eliminators` |
| [12.20](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `HTyped.seq_source` | `Eliminators` |
| [12.21](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `planDepth_eq` | `DepthPruning` |
| [12.22](theory/foundations/12-lazy-loading-and-scalable-discovery.md) | `derivable_within` | `DepthPruning` |
| [13.1](theory/foundations/13-efficiency.md) | `Plan.cost_le_pow` | `Cost` |
| [13.2](theory/foundations/13-efficiency.md) | `Plan.cost_linear` | `Cost` |
| [13.3](theory/foundations/13-efficiency.md) | `route_cost_append` | `Cost` |
| [13.4](theory/foundations/13-efficiency.md) | `planMin_sound` | `MinCost` |
| [13.5](theory/foundations/13-efficiency.md) | `planMin_optimal` | `MinCost` |
| [13.6](theory/foundations/13-efficiency.md) | `front_cover` | `Pareto` |
| [13.7](theory/foundations/13-efficiency.md) | `planPareto_sound` | `Pareto` |
| [13.8](theory/foundations/13-efficiency.md) | `planPareto_cover` | `Pareto` |
| [13.9](theory/foundations/13-efficiency.md) | `planPareto_within` | `Pareto` |
| [14.1](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `resolve_sound` | `Request` |
| [14.2](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `resolve_avoids` | `Request` |
| [14.3](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `RequestChain.length_le` | `Request` |
| [14.4](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `cascade_error_eq` | `Cascade` |
| [14.5](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `cascade_le_fallback` | `Cascade` |
| [14.6](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `cascade_expected_cost` | `Cascade` |
| [14.7](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `gated_error_le` | `Cascade` |
| [14.8](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `gated_error_eq_of_sound` | `Cascade` |
| [14.9](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `gated_expected_cost` | `Cascade` |
| [14.10](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `DemandSound.comp` | `Demand` |
| [14.11](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `DemandSound.pair` | `Demand` |
| [14.12](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `DemandSound.map` | `Demand` |
| [14.13](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `DemandSound.exact` | `Demand` |
| [14.14](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `Safe.run` | `Continuation` |
| [14.15](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `Safe.bind` | `Continuation` |
| [14.16](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `Depth.run_le` | `Continuation` |
| [14.17](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `Depth.bind` | `Continuation` |
| [14.18](theory/foundations/14-kernel-mediated-requests-and-refinement.md) | `positive_scale_preserves_maximum`, `zero_scale_collapses_order` | `Demand` |
| [15.1](theory/reliability/15-normalization-against-shift.md) | `ShiftBound.map` | `Normalize` |
| [15.2](theory/reliability/15-normalization-against-shift.md) | `shift_le_of_invariant_on` | `Normalize` |
| [15.3](theory/reliability/15-normalization-against-shift.md) | `shift_zero_of_invariant` | `Normalize` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `selective_risk_le`, `selective_risk_le_available`, `upper_fold_ge` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `positive_alternative_risk` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `positive_observation_floor` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `observation_weight_sum_positive` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `collapsed_pair_cannot_choose_both` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `original_value_distinguishes` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `monotone_normalized_rank`, `batched_monotone_normalized_rank`, `ranked_tie_keeps_first`, `integer_shift_preserves_order`, `rowwise_shift_order`, `exp_shift_ratio`, `ranked_restriction_ext`, `calibration_subset_membership`, `calibration_subset_empty`, `calibration_matrix_restriction_ext`, `grouped_normalization`, `batched_group_mass_ext`, `batched_group_risk_bounds`, `calibrated_difference_rescale`, `grouped_negative_log_likelihood` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `asymmetric_group_risk` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `grouped_selection_risk_difference` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `unsigned_bitpattern_order` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `average_calibrated_difference` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `singleton_target_normalizer` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `target_maximum_unit_weight` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `calibration_relabel_normalization` | `Selective` |
| [16.1](theory/reliability/16-knowing-when-to-be-unsure.md) | `positive_target_group_nonempty` | `Selective` |
| [16.2](theory/reliability/16-knowing-when-to-be-unsure.md) | `threshold_optimal` | `Selective` |
| [16.3](theory/reliability/16-knowing-when-to-be-unsure.md) | `bound_ge_floor` | `Selective` |
| [16.3](theory/reliability/16-knowing-when-to-be-unsure.md) | `length_limit` | `Selective` |
| [16.4](theory/reliability/16-knowing-when-to-be-unsure.md) | `restricted_risk_le`, `zero_total_no_positive_entry`, `risk_scale_invariant` | `Selective` |
| [16.5](theory/reliability/16-knowing-when-to-be-unsure.md) | `queued_value` | `Practice` |
| [16.6](theory/reliability/16-knowing-when-to-be-unsure.md) | `unqueued_errors` | `Practice` |
| [16.7](theory/reliability/16-knowing-when-to-be-unsure.md) | `queued_captures` | `Practice` |
| [16.8](theory/reliability/16-knowing-when-to-be-unsure.md) | `proportional_value` | `Practice` |
| [17.1](theory/reliability/17-calibration-under-distribution-shift.md) | `selective_risk_le_excess` | `Calibration` |
| [17.2](theory/reliability/17-calibration-under-distribution-shift.md) | `shift_ratio_le` | `Calibration` |
| [17.3](theory/reliability/17-calibration-under-distribution-shift.md) | `horvitz_thompson` | `Calibration` |
| [17.4](theory/reliability/17-calibration-under-distribution-shift.md) | `inflated_answered_mono` | `Calibration` |
| [17.8](theory/reliability/17-calibration-under-distribution-shift.md) | `threshold_trace_prefix` | `Calibration` |
| [17.9](theory/reliability/17-calibration-under-distribution-shift.md) | `audit_family_le` | `Calibration` |
| [17.7](theory/reliability/17-calibration-under-distribution-shift.md) | `audit_rejection_of_completion` | `Calibration` |
| [17.6](theory/reliability/17-calibration-under-distribution-shift.md) | `audit_budget_obstruction` | `Calibration` |
| [17.6](theory/reliability/17-calibration-under-distribution-shift.md) | `audit_cdf_upper_refutes`, `audit_cdf_lower_proves` | `Calibration` |
| [17.5](theory/reliability/17-calibration-under-distribution-shift.md) | `fixed_sequence_le` | `Calibration` |
| [18.1](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `grouped_risk_le` | `Certificate` |
| [18.1](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `risk_as_alternative_mass` | `Selective` |
| [18.1](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `osa_symmetric` | `Edit` |
| [18.1](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `osa_empty_left`, `osa_empty_right` | `Edit` |
| [18.1](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `osa_self` | `Edit` |
| [18.2](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `certificate_error_le` | `Certificate` |
| [18.2](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `certificate_error_le_support` | `Certificate` |
| [18.3](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `cert_sound` | `Certificate` |
| [18.4](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `bestCert_valid` | `Certificate` |
| [18.4](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `bestCert_le` | `Certificate` |
| [18.5](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `bestCert_le_full` | `Certificate` |
| [18.6](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `code_prefix` | `Certificate` |
| [18.7](theory/studies/18-a-second-domain-noisy-boolean-formulas.md) | `alternating_cert_leaves` | `Certificate` |
| [19.1](theory/decoding/19-error-detection-by-the-format.md) | `code_sum` | `Detection` |
| [19.2](theory/decoding/19-error-detection-by-the-format.md) | `code_no_single_change` | `Detection` |
| [19.3](theory/decoding/19-error-detection-by-the-format.md) | `detected_error_le` | `Detection` |
| [19.4](theory/decoding/19-error-detection-by-the-format.md) | `joint_le_restricted` | `Detection` |
| [19.5](theory/decoding/19-error-detection-by-the-format.md) | `two_occur_le_half` | `Detection` |
| [19.6](theory/decoding/19-error-detection-by-the-format.md) | `two_occur_le_pairs` | `Detection` |
| [19.6](theory/decoding/19-error-detection-by-the-format.md) | `pair_share_prefix_suffix_upper` | `Detection` |
| [19.6](theory/decoding/19-error-detection-by-the-format.md) | `detection_share_combine_upper` | `Detection` |
| [20.1](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `HTyped.mono` | `Slots` |
| [20.2](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `embed_wellTyped` | `Slots` |
| [20.3](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `HPlan.cost_le_pow` | `Slots` |
| [20.4](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `HPlan.cost_mono` | `Slots` |
| [20.5](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `serve_sound` | `Continuation` |
| [20.6](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `serve_spent` | `Continuation` |
| [20.7](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `Prog.runB_le` | `Continuation` |
| [20.8](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `choice_cost_le` | `Slots` |
| [20.9](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `PTyped.erase`, `WellTyped.positional` | `Relevance` |
| [20.10](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `PPlan.uses_apply`, `PPlan.given_not_relevant`, `PTyped.uses_lt` | `Relevance` |
| [20.11](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `gap_iff`, `gap_complete`, `gap_sound` | `Planning/Gaps` |
| [20.12](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `repair_complete`, `repair_sound` | `Planning/Gaps` |
| [20.13](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `founded_keeps`, `founded_medium` | `Planning/Gaps` |
| [20.14](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `acquisition_sound` (with `zeroLoss_miss`), `earlyTest_admits`, `earlyTest_reads` | `Reliability/SampledGate` |
| [20.16](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `contradictory_pairs_errors`, `contradiction_screen_risk` | `Reliability/Screening` |
| [20.20](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `unmatched_append`, `unmatched_remove`, `maximal_pairs_half` | `Reliability/Screening` |
| [20.17](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `durable_refusal_risk` | `Reliability/Screening` |
| [20.18](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `staged_acquisition_sound` | `Reliability/SampledGate` |
| [20.19](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `acquisition_order_valid`, `acquisition_swap_difference`, `acquisition_swap` | `Planning/Acquisition` |
| [43.6](theory/foundations/43-episodic-memory.md) | `cursorAppend_valid`, `cursorErase_valid`, `cursor_after_eviction` | `Execution/Memory` |
| [20.15](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `horn_gap_iff`, `horn_gap_complete`, `horn_gap_sound` | `Planning/Horn` |
| [21.1](theory/decoding/21-decoding-by-the-format.md) | `await_code` | `Decoding` |
| [21.2](theory/decoding/21-decoding-by-the-format.md) | `code_accepted` | `Decoding` |
| [21.3](theory/decoding/21-decoding-by-the-format.md) | `accepts_iff_codes` | `Decoding` |
| [21.3](theory/decoding/21-decoding-by-the-format.md) | `await_balance`, `accepted_arity_sum`, `accepted_arity_lt_length` | `Decoding` |
| [21.4](theory/decoding/21-decoding-by-the-format.md) | `dpSum_eq` | `Decoding` |
| [21.5](theory/decoding/21-decoding-by-the-format.md) | `dpMax_ge` | `Decoding` |
| [21.6](theory/decoding/21-decoding-by-the-format.md) | `dpMax_attained`, `tiedChoice_eq_min`, `tiedChoice_comm`, `arity_exceeds_state_bound`, `completion_transition_bound`, `counter_growth_bound`, `foldl_await_zero_nonempty` | `Decoding` |
| [21.7](theory/decoding/21-decoding-by-the-format.md) | `exact_risk_le_union` | `Decoding` |
| [21.7](theory/decoding/21-decoding-by-the-format.md) | `one_sub_prod_le_sum` | `Decoding` |
| [22.1](theory/reliability/22-abstaining-early.md) | `detection_account_mono` | `Detection` |
| [22.3](theory/reliability/22-abstaining-early.md) | `lower_fold_le` | `Selective` |
| [22.4](theory/reliability/22-abstaining-early.md) | `committed_continuation_preferred` | `Stopping` |
| [22.4](theory/reliability/22-abstaining-early.md) | `firstStoppingState_append` | `Stopping` |
| [22.4](theory/reliability/22-abstaining-early.md) | `positive_target_preserves_order` | `Stopping` |
| [23.1](theory/decoding/23-efficient-decoding.md) | `tail_le_esym` | `Banding` |
| [23.2](theory/decoding/23-efficient-decoding.md) | `factorial_mul_esym_le` | `Banding` |
| [23.3](theory/decoding/23-efficient-decoding.md) | `outside_le_tail`, `diff_le_reference_length`, `tail_above_length`, `tail_row_scale`, `row_mass_partition`, `anchored_exp_mass`, `rowFactor_normalizes`, `tail_le_row_factors`, `row_summary_append` | `Banding` |
| [23.3](theory/decoding/23-efficient-decoding.md) | `bandPolynomial_recurrence`, `bandPolynomial_threshold_suffix`, `threshold_search_step`, `threshold_search_shrinks`, `searchGap_i64`, `threshold_search_adjacent` | `BandSearch` |
| [23.4](theory/decoding/23-efficient-decoding.md) | `sum_sub_le_diff`, `sum_sub_le_diff_bounded`, `band_covers_interval`, `ragged_band_storage_covers` | `Banding` |
| [23.4](theory/decoding/23-efficient-decoding.md) | `sum_filter_support`, `max_filter_support`, `support_shift_bounds`, `split_support_intersection`, `trace_predecessor_monotone`, `trace_successor_monotone`, `ordered_arity_exceeds_envelope`, `scoredChoice_comm`, `scoredChoice_assoc` | `Decoding` |
| [23.5](theory/decoding/23-efficient-decoding.md) | `banded_risk_le` | `Banding` |
| [23.6](theory/decoding/23-efficient-decoding.md) | `banded_risk_slack` | `Banding` |
| [23.7](theory/decoding/23-efficient-decoding.md) | `dpSum_append` | `Banding` |
| [23.8](theory/decoding/23-efficient-decoding.md) | `dpMax_append` | `Banding` |
| [23.9](theory/decoding/23-efficient-decoding.md) | `sum_pair_dist` | `Banding` |
| [23.10](theory/decoding/23-efficient-decoding.md) | `stitch_attains` | `Banding` |
| [23.15](theory/decoding/23-efficient-decoding.md) | `cache_lookup_correct`, `cache_evict_sound`, `cache_store_sound` | `Selective` |
| [23.14](theory/decoding/23-efficient-decoding.md) | `sum_row_shift`, `row_shift_order` | `Selective` |
| [23.13](theory/decoding/23-efficient-decoding.md) | `selective_risk_le_approx`, `threshold_stable` | `Selective` |
| [23.12](theory/decoding/23-efficient-decoding.md) | `revision_cache_eq` | `Selective` |
| [23.11](theory/decoding/23-efficient-decoding.md) | `priority_allocation_sum`, `priority_allocation_nonneg`, `priority_allocation_cover` | `Selective` |
| [24.1](theory/decoding/24-when-the-prior-is-wrong.md) | `reweighted_odds` | `Misspecification` |
| [24.2](theory/decoding/24-when-the-prior-is-wrong.md) | `reweighted_risk_le` | `Misspecification` |
| [24.3](theory/decoding/24-when-the-prior-is-wrong.md) | `reweighted_risk_le_mul` | `Misspecification` |
| [24.4](theory/decoding/24-when-the-prior-is-wrong.md) | `dominated_risk_le` | `Misspecification` |
| [24.5](theory/decoding/24-when-the-prior-is-wrong.md) | `adversarial_prior` | `Misspecification` |
| [25.1](theory/reliability/25-which-word-to-climb-and-when-to-stop.md) | `cost_ge_of_ratio` | `Stopping` |
| [25.1](theory/reliability/25-which-word-to-climb-and-when-to-stop.md) | `fractional_ratio_bound_strict` | `Stopping` |
| [25.1](theory/reliability/25-which-word-to-climb-and-when-to-stop.md) | `selective_risk_le_selected` | `Selective` |
| [25.1](theory/reliability/25-which-word-to-climb-and-when-to-stop.md) | `charge_cost_ratio_order` | `Stopping` |
| [25.2](theory/reliability/25-which-word-to-climb-and-when-to-stop.md) | `pairs_ge_count` | `Stopping` |
| [25.3](theory/reliability/25-which-word-to-climb-and-when-to-stop.md) | `lookahead_stop_optimal` | `Stopping` |
| [25.4](theory/reliability/25-which-word-to-climb-and-when-to-stop.md) | `lookahead_continue_better` | `Stopping` |
| [25.4](theory/reliability/25-which-word-to-climb-and-when-to-stop.md) | `split_bin_gain_nonneg` | `Stopping` |
| [25.5](theory/reliability/25-which-word-to-climb-and-when-to-stop.md) | `single_climb_account` | `Stopping` |
| [26.1](theory/reliability/26-composing-cascades.md) | `fallback_cost_eq` | `Composition` |
| [26.2](theory/reliability/26-composing-cascades.md) | `fallback_cost_conditional` | `Composition` |
| [26.3](theory/reliability/26-composing-cascades.md) | `fallback_cost_sub_independent` | `Composition` |
| [26.4](theory/reliability/26-composing-cascades.md) | `fallback_cost_ge_independent` | `Composition` |
| [26.5](theory/reliability/26-composing-cascades.md) | `chain_error_eq` | `Composition` |
| [26.6](theory/reliability/26-composing-cascades.md) | `chain_cost_eq` | `Composition` |
| [26.7](theory/reliability/26-composing-cascades.md) | `split_error_eq` | `Composition` |
| [26.8](theory/reliability/26-composing-cascades.md) | `argmin_within` | `Composition` |
| [26.9](theory/reliability/26-composing-cascades.md) | `some_deviates_le` | `Composition` |
| [27.1](theory/decoding/27-priors-as-experts.md) | `pdpSum_eq` | `Product` |
| [27.2](theory/decoding/27-priors-as-experts.md) | `pdpMax_ge` | `Product` |
| [27.3](theory/decoding/27-priors-as-experts.md) | `pdpMax_attained` | `Product` |
| [27.4](theory/decoding/27-priors-as-experts.md) | `pdpSum_unit` | `Product` |
| [27.5](theory/decoding/27-priors-as-experts.md) | `complete_shape_length` | `Decoding` |
| [27.6](theory/decoding/27-priors-as-experts.md) | `prior_support_sum`, `prior_support_max`, `prior_step_zero_outside`, `prior_prune_zero_readings`, `pdpSum_zero_row`, `pdpMax_zero_row`, `partitionCompose_zero_left` | `Product` |
| [27.7](theory/decoding/27-priors-as-experts.md) | `bounded_shape_length`, `complete_shape_bounded` | `Decoding` |
| [27.8](theory/decoding/27-priors-as-experts.md) | `prior_evidence_identity` | `Product` |
| [27.9](theory/decoding/27-priors-as-experts.md) | `prior_selection_regret`, `prior_selection_half_gap` | `Product` |
| [27.10](theory/decoding/27-priors-as-experts.md) | `clipped_evidence_bounds`, `clipped_error_bound_mono` (concentration not formalized) | `Product` |
| [27.11](theory/decoding/27-priors-as-experts.md) | `selected_audit_failure_le` (conditional finite mixture) | `Product` |
| [27.12](theory/decoding/27-priors-as-experts.md) | `partial_evidence_bounds` (bounded range for optional scores) | `Product` |
| [27.15](theory/decoding/27-priors-as-experts.md) | `prior_empty`, `prior_empty_normalized` | `Product` |
| [27.16](theory/decoding/27-priors-as-experts.md) | `risk_from_other_mass`, `partition_risk_common_factor`, `prior_common_factors`, `equal_positive_mass_increases`, `two_sum_residual_identity`, `compensated_evidence_step` | `Product` |
| [27.17](theory/decoding/27-priors-as-experts.md) | `partitionCompose_assoc`, `partitionCompose_identity`, `partitionCompose_nonneg` | `Product` |
| [27.18](theory/decoding/27-priors-as-experts.md) | `partitionBoundary_total`, `partitionBoundary_nonneg`, `partitionBoundary_assoc`, `partitionBoundary_identity` | `Product` |
| [27.19](theory/decoding/27-priors-as-experts.md) | `partition_prefix_reuse` | `Product` |
| [28.1](theory/foundations/28-packages-as-experts.md) | `Pkg.flattenList_append` | `Package` |
| [28.2](theory/foundations/28-packages-as-experts.md) | `install_stable` | `Package` |
| [28.3](theory/foundations/28-packages-as-experts.md) | `WellTyped.inline` (via `WellTyped.instantiate`, `lookupArg_typed`) | `Package` |
| [28.4](theory/foundations/28-packages-as-experts.md) | `cache_lookup_correct`, `cache_store_sound`, `cache_evict_sound` | `Selective` |
| [28.5](theory/foundations/28-packages-as-experts.md) | `Artifacts.run_retains`, `Artifacts.admitted_read_stable`, `Artifacts.run_read_identity` | `Execution/Artifacts` |
| [29.4](theory/foundations/29-types-as-objects.md) | `hubConnectors_card`, `hub_routes`, `direct_connectors_lower`, `hubConnectors_mono`, `hub_route_risk` | `Types/Hub` |
| [29.5](theory/foundations/29-types-as-objects.md) | `attached_risk`, `attachment_depth_risk` | `Types/Hub` |
| [29.6](theory/foundations/29-types-as-objects.md) | `bridged_keeps`, `bridged_routes`, `bridged_card`, `bridged_route_risk` | `Types/Hub` |
| [29.7](theory/foundations/29-types-as-objects.md) | `slot_risk_transfer`, `slot_risk_unbounded` | `Types/SlotRisk` |
| [28.6](theory/foundations/28-packages-as-experts.md) | `resolveLoader_perm`, `resolveLoader_unrelated`, `resolveLoader_conflict`, `resolveLoader_relocate` | `Execution/Loaders` |
| [28.7](theory/foundations/28-packages-as-experts.md) | `dependency_expand_decreases`, `dependency_step_decreases`, `dependency_no_infinite_run`, `dependency_expand_account`, `dependency_pop_account`, `dependency_append_order` | `Execution/DependencyWalk` |
| [29.1](theory/foundations/29-types-as-objects.md) | `WellTypedSub.coerce` | `Refinement` |
| [29.2](theory/foundations/29-types-as-objects.md) | `Plan.eval_erase` | `Refinement` |
| [29.3](theory/foundations/29-types-as-objects.md) | `planShallowStable_append` (for the stability half) | `Routing` |
| [30.1](theory/evidence/30-selection-by-evidence.md) | `audit_family_le` (the union bound; the sign test's validity is assumed) | `Calibration` |
| [30.2](theory/evidence/30-selection-by-evidence.md) | `plan_rename`, `planShallow_rename`, `planShallowStable_rename`, `WellTyped.rename` | `Selection` |
| [31.1](theory/reliability/31-composing-uncertainty.md) | `risk_le_expected_failures` | `Risk` |
| [31.2](theory/reliability/31-composing-uncertainty.md) | `expected_failures_eq`, `risk_le_charges` | `Risk` |
| [31.4](theory/reliability/31-composing-uncertainty.md) | `audit_family_le` with `risk_le_charges` | `Calibration`, `Risk` |
| [31.5](theory/reliability/31-composing-uncertainty.md) | `risk_le_charges` on relevant counts, with `DemandSound.exact` | `Risk`, `Demand` |
| [31.6](theory/reliability/31-composing-uncertainty.md) | `vote_correct`, `vote_fails_subset`, `vote_risk` | `Reliability/Vote` |
| [31.7](theory/reliability/31-composing-uncertainty.md) | `vote_omit_forces`, `dependent_vote_risk`, `dependent_majority_bound` | `Reliability/DependentVote` |
| [31.8](theory/reliability/31-composing-uncertainty.md) | `ensemble_miss`, `ensemble_search_sound` (using `staged_acquisition_sound`) | `Reliability/Ensemble` |
| [31.9](theory/reliability/31-composing-uncertainty.md) | `feedback_repair_progress`, `feedback_chain_bound` (fresh admission uses `ensemble_search_sound`) | `Reliability/RepairFeedback` |
| [31.10](theory/reliability/31-composing-uncertainty.md) | `keyCorrection_outside`, `endpoint_correction_errors` | `Reliability/RepairFeedback` |
| [31.11](theory/reliability/31-composing-uncertainty.md) | `keyCorrection_protected`, `fiber_correction_errors` | `Reliability/RepairFeedback` |
| [31.12](theory/reliability/31-composing-uncertainty.md) | `retained_feedback_account` | `Reliability/RepairFeedback` |
| [31.13](theory/reliability/31-composing-uncertainty.md) | `correction_reloaded_eq` | `Reliability/RepairFeedback` |
| [36.59](theory/evidence/36-interface-acquisition.md) | `featureClosure_iff` | `Planning/FeatureClosure` |
| [36.60](theory/evidence/36-interface-acquisition.md) | `featureTreeClosure_iff` | `Planning/FeatureClosure` |
| [36.61](theory/evidence/36-interface-acquisition.md) | `featureApplication_reloaded_eq` | `Planning/FeatureClosure` |
| [36.62](theory/evidence/36-interface-acquisition.md) | `feature_index_filter` | `Planning/FeatureClosure` |
| [36.63](theory/evidence/36-interface-acquisition.md) | `feature_demand_index_eq`, `feature_demand_prefix_filter` | `Planning/FeatureClosure` |
| [36.64](theory/evidence/36-interface-acquisition.md) | `feature_coarse_filter` | `Planning/FeatureClosure` |
| [36.65](theory/evidence/36-interface-acquisition.md) | `feature_priority_closure` | `Planning/FeatureClosure` |
| [32.1](theory/evidence/32-trust.md) | `decision_isolated` (via `filter_append_unaccepted`) | `Trust` |
| [32.2](theory/evidence/32-trust.md) | `undetected_le_exp` | `Spot` |
| [33.1](theory/reliability/33-per-input-risk.md) | `risk_le_expected_failures` on the conditional distribution | `Risk` |
| [33.2](theory/reliability/33-per-input-risk.md) | `selective_risk_le` with the ledger total as bound | `Selective` |
| [33.4](theory/reliability/33-per-input-risk.md) | `selective_risk_le` on the final execution | `Selective` |
| [33.5](theory/reliability/33-per-input-risk.md) | `inside_ledger_no_cache`, `inside_replay_charge`, `erased_accounting_underreports` | `Reliability/Selective` |
| [33.6](theory/reliability/33-per-input-risk.md) | `ledger_fold_upper` | `Reliability/Selective` |
| [34.2](theory/foundations/34-compiled-routes.md) | `batch_flatten`, `batch_sound_flatten` | `Batch` |
| [34.3](theory/foundations/34-compiled-routes.md) | `cache_lookup_correct` with Theorem 34.1's induction | `Selective` |
| [34.4](theory/foundations/34-compiled-routes.md) | `selective_risk_le` on each row's final evaluation | `Selective` |
| [35.1](theory/reliability/35-calibration-audits.md) | `count_tail_le`, `audit_tail_le` | `Audit` |
| [36.1](theory/evidence/36-acquisition.md) | `split_test_le` | `Acquire` |
| [37.1](theory/reliability/37-grouped-calibration.md) | `grouped_calibrated` | `Grouped` |
| [38.1](theory/reliability/38-in-situ-audits.md) | `sampled_calibrated` | `Sampling` |
| [39.1](theory/reliability/39-alternatives.md) | `alternatives_le`, `alternatives_lower` | `Alternatives` |
| [40.1](theory/reliability/40-agreement-audits.md) | `disagreement_le` with `audit_tail_le` | `Agreement`, `Audit` |
| [41.1](theory/reliability/41-verification.md) | `verified_le` | `Verification` |
| [43.1](theory/foundations/43-episodic-memory.md) | `zeroLoss_miss`, `decisionLevel_total`, `allocate_fresh`, `sampledGate_sound` | `Reliability/SampledGate` |
| [43.2](theory/foundations/43-episodic-memory.md) | `smooth_unit`, `smooth_step`, `hysteresis_gap`, `reopen_after_settle` | `Reliability/Plasticity` |
| [43.3](theory/foundations/43-episodic-memory.md) | `meanSignal_unit`, `dependentStability_unit`, `dependentStability_mono` | `Reliability/Plasticity` |
| [43.4](theory/foundations/43-episodic-memory.md) | `published_only_if_admitted`, `allocate_skips_drawn` | `Reliability/SampledGate` |
| [43.5](theory/foundations/43-episodic-memory.md) | `evict_keeps_protected`, `withdraw_fresh` | `Reliability/SampledGate` |

## Native kernels

`src/nca/native/` holds optional kernels written in Elisa and built as CPython
extensions with `python -m nca.native` (needs `elisac-stage1`). Each has a
NumPy reference that gives the same results within rounding and is used when
the kernel is not built or `NCA_NATIVE=0`. Kernels that only a domain needs
live in that independent package. Build any installed package's kernels with
`python -m nca.native --package <import-namespace>`; the builder has no package catalog. `decoding.elisa` runs the exact
passes of §21.4 in linear space with per-row rescaling (THEORY §23.7).
Its implementation is grouped under `native/decoding_parts/` into weights,
partitions, priors, cursors, decisions and calibration. The entry file uses
Elisa's relative `include` mechanism and retains the Python export declaration.
Include fragments use `.elisa.inc`; the generic builder discovers `.elisa`
entry files, and distributions ship the fragments alongside them.
The builder passes `-fstrict-fp`: conservative sums, compensated arithmetic and
subnormal divisions rely on strict operation semantics. Default reciprocal
relaxation can overflow an intermediate even when the original quotient is
finite; the reference-equivalence tests include these boundary cases.
It also exports `advance_ragged_log`, `retreat_ragged_log`, `scores_ragged_log`
and `trace_ragged`, the banded cursor of §23.4
(`trace_ragged` reads the decoded sequence off the max tables, `Split.best`, and
returns no sequence when the maximum is unreachable):
`decoding.Split` keeps the forward and backward tables in NumPy arrays and the
kernel recomputes rows in place through `mutable view[f64]` parameters, which
borrow the arrays' writable buffers. Cursors copy input weights into row-major
storage so native calls can borrow a flat view without copying the matrix.
The cursor keeps its mapped arities read-only and caches their ordering;
`scores_ragged_with_order` and `trace_ragged_with_order` require a true flag
to mean the supplied arities are nondecreasing. Their compatibility entry
points determine ordering independently. `trace_ragged_indexed` additionally
requires a permutation of the original indices sorted by their arities; the
cursor constructs that permutation lazily for unordered alphabets and retains
it across band rebuilds, which do not change the arities or row count.
Sum and max tables use log weights in
both the native kernel and the NumPy fallback, retaining finite path weights
that would underflow even with per-row linear rescaling.
Both paths reject non-finite results of finite log-weight additions during
sweeps and split scoring; a rejected climb does not replace its row.
Cursor bands also exclude states beyond the configured alphabet's prefix
reachability bound (`counter_growth_bound` in `NCA.Decoding`).
The nonincremental band pass uses Elisa's `banded_format` with rolling sum
and maximum rows and a traceback table. Its NumPy fallback bounds path sums
before using an unchecked finite-range fast path (`log_weight_sum_bound` in
`NCA.Decoding`). Both restrict states to the requested band.
`Split` validates row dimensions, word indices and band bounds before native
calls; an absent positive-weight path yields an empty trace.
The prefix parser uses Elisa's general-arity `parse_tree_generic` when
available, with an iterative Python fallback; both reject noninteger arities.
`accepted_clamp_length_iff` and `accepted_clamp_length_eq` in `NCA.Decoding`
prove that clamping nonnegative arities to the sequence length preserves format
acceptance and leaves every accepted sequence unchanged.

`stats.elisa` computes the Poisson-binomial count recurrence (§21.8) in place;
`bernoulliStep_zero` and `bernoulliStep_succ` in `NCA.Decoding` state its steps.
`bernoulli_split_mass` states the exact-arithmetic normalization identity.
`bernoulli_step_upper` establishes monotonicity of one nonnegative update;
`poisson_binomial_upper_bound` uses upward-rounded operations in `stats.elisa`
or its Python fallback for excess p-values, under IEEE 754 assumptions.
The conservative Clopper–Pearson bisection uses a homogeneous-event Elisa
recurrence without materializing repeated probabilities; the Python path
remains the reference when the kernel is unavailable.
For low thresholds it tracks the tail directly; `bernoulli_tail_step_upper`
states the corresponding monotonicity step.
Exact zero- and one-probability events are removed before choosing a count
range; `certain_success_threshold` states the threshold adjustment.
`format_upper_bound` rounds displayed bounds upward in decimal as well.
The pair-premise audit supplies `pair_risk_upper` as input to that excess-tail
bound. Its Elisa kernel accumulates pair products with an upward-rounded
prefix (`pair_prefix_step_upper`); the fallback sums upper-rounded shares.
The separate distant-pair diagnostic uses `pair_gap_sum` to accumulate only
eligible pairs without subtraction; `pair_gap_sum_nonneg` states nonnegativity
in exact arithmetic. This diagnostic is not an outward-rounded bound.
`bernoulliStep_impossible` justifies skipping zero-probability events.
`bernoulliStep_certain_zero` and `bernoulliStep_certain_succ` justify combining
the shifts for events with probability one.
`bernoulli_count_le_length` establishes the upper limit of the count's support.
The caller promotes reduced-precision probabilities before computing their
complements, avoiding loss of probability mass from independent rounding.

## 1. Types and contracts

`abi.types` owns type terms, canonical syntax and substitution/matching/unification
operations. The `abi` package owns contracts, manifests and message/demand
envelopes and re-exports the type definitions and cached functions. There is one
shared parser/cache and one class identity per type-term constructor.

A type id is the canonical text of a type term (`nca.abi.TypeId`): a constructor
name, either the `sha256:` reference of a constructor object (§29) or a
textual name with its namespace and version, optionally applied to bracketed,
comma-separated argument types, as in `seq[image.rgb.v1]`; `?a` is a type
variable. Manifests carry type ids as text, so they stay plain data for any
language. `parse_type` and `format_type` convert between text and terms
(`Var`, `App`), `substitute` applies a substitution, and `seq_type` and
`elem_type` build and take apart sequence types. A `Contract` rejects types that
are malformed or not in canonical form. `Contract.variables` and
`Contract.free` are its type variables and those absent from its output
(THEORY §2.2). `Contract.producing(goal)` matches the output
against a ground goal and returns the binding of the one instance producing it;
`Contract.instance` substitutes a binding. The planners (`planner`, and
`optimize.plan_min` and `plan_pareto`) record that binding in `Apply.binding`,
and `Apply.contract` is the applied instance, which `router.infer` checks and
the runtime uses for message types. `planner.terms` owns `Given`, `Apply`,
`Map`, their `Plan` union and structural input/output inspection. The `planner`
package retains search and re-exports those model definitions without wrappers.
`index.ProducerIndex` keeps polymorphic producers
apart from those indexed by exact output type and merges both in installation
order; its forward closure counts every type a polymorphic producer has an
instance for as reachable, so pruning stays sound.
For generic outputs, candidate lookup uses matching constructor and arity or
a variable output; the head-mismatch theorem (§2.2) justifies this filter.
Both cost planners use the same ordered producer index when enumerating
candidate instances; free-variable instances are expanded after lookup.

A contract with free variables is applied by pattern search (`planner._solutions`):
its inputs are solved as pattern goals with `abi.unify`, which follows the
steps of the proof of Theorem 2.7 (decomposition, the occurs check, variable
elimination) and returns a most general unifier as a triangular binding, renaming each candidate contract's variables apart and
backtracking over earlier inputs' alternatives. Applications are kept open
(`_Open`) until the answer substitution is known, then closed with their
bindings and slots; a candidate that leaves a variable undetermined is skipped
as ambiguous. Ground sub-goals go through the memoized planner, pattern goals
are not memoized, and pruning by the forward closure ignores inputs with
variables.
Before expanding a nested candidate, `_solutions` rejects any ground slot
that cannot be filled at the candidate's remaining depth, including slots
made ground by output unification.

`NCA.Skel` (`lean/NCA/Planning/PatternSearch.lean`) models a plan skeleton and its
equations, with each node's variables renamed by its path, as
`index.rename_apart` does with fresh tags. Each input pattern the search
unifies with a candidate's output is one equation of `Skel.eqs`, solved in
search order with the bindings found so far applied, as in `SeqMGU`.

Ground producers are also pruned by depth (THEORY §12, Theorems
12.21–12.22): `ProducerIndex.depths(available, limit)` gives each type's
least level in `NCA.Within`, computed by rounds of the closure's
propagation and cached per available types and library prefix, and a
producer is skipped when a non-sequence input's level exceeds the fuel
left for its arguments. It returns `None`, and nothing is pruned by depth,
when a contract's output is a bare variable.

`map` candidates are pruned by the same closure oracle
(`ProducerIndex.may_derive`, THEORY §12): an element `a` is tried only if the
body goal may be derived from `[a]`. `ProducerIndex.sources` finds a superset of
those elements by searching backward from the body goal through producers'
inputs, so a sequence goal visits only candidates that can lead to its element
type instead of every element type in the library. Candidate lists are cached
per available types and library prefix. `ProducerIndex.seq_elements` is the
source oracle of Theorems 12.17 and 12.20: the closure of the elements of the
sequence types in the closure of the available types. A sequence goal whose
element is neither a sequence type nor in it is rejected before any
candidate is tried. When a polymorphic producer may output a sequence
(`ProducerIndex.polymorphic_sequences`), the elements the oracle admits are
also `map` candidates, after the enumerated ones; when it admits every type,
the planner solves the pattern goal `seq[?a]` for them instead (THEORY §2.2).

Contracts whose output is a bare variable, such as the eliminators `Case` and
`Fold`, enter the closure through their contributions (Theorem 12.19):
`ProducerIndex.reachable` matches their input patterns against the closure,
adds what each binding determines, including the closure of a slot's inputs,
and repeats to a fixed point. A slot whose inputs are already in the closure
adds nothing, so only bindings that reach new types cost a nested closure.
`ProducerIndex.total` reports when a contribution is unconstrained and the
closure prunes nothing. The planner tries such a contract for a ground goal
only if `ProducerIndex.may_produce` accepts it: a sequence type, a type in the
closure, or one a polymorphic producer covers.

`NCA.ECl` (`lean/NCA/Planning/Eliminators.lean`) models this closure over plans of
`HPlan`s whose experts are instances of installed slot contracts or of the
`map` family, which stands for the planner's built-in `map`. Its rules are
the cases of `ProducerIndex._open_contributions`; the index computes a
superset of it, since it ignores slots of contracts with constructor outputs
and counts every type a polymorphic producer covers, and it reports the
closure total where the model would still bound it.

Pattern goals take their candidates from `ProducerIndex.pattern_candidates`:
modules indexed by the root constructor and arity of their output
(Theorem 2.6), plus those whose output is a variable, keeping a monomorphic
contract only if it fires in the closure of the available types.

`optimize.plan_min` and `plan_pareto` cost a contract with free variables at
each instance `planner.free_bindings` returns, the instances pattern search
determines, and take `map` elements from `planner.map_candidates`, which adds
the sources of sequences that polymorphic producers make (THEORY §13).
After a binding has one valid closed argument plan, duplicate solutions for
that binding need not be closed again; failed closures do not suppress later
solutions for the same binding.
Pattern search renames the input and output types it needs, retaining fresh
names for slot-only variables for later closure without constructing a full
renamed contract at each search node. It passes the renamed terms directly to
unification instead of formatting and reparsing them.
Generated variable identities pair a source name with a unique scope and
are distinct from user-provided textual names.
At the last search depth, pattern search skips contracts with inputs before
renaming them, since no input can be solved at depth zero.
For free-variable instances, ground inputs are checked before expanding the
remaining pattern inputs; a failed ground check cannot be repaired by a later
substitution. The check also applies when earlier inputs make a later one
ground, without discarding alternative earlier bindings.

The index persists. `ProducerIndex.append` indexes a newly installed module
after the others, and every cached result (closures, candidate sets, plans in
`ProducerIndex.memo`, stable routes in `ProducerIndex.routes`) is keyed by a
library prefix, so it stays valid (THEORY §12, Theorem 12.18). A stable route
found earlier is returned without search, since installation never changes it
(Theorem 3.3); a goal that had no route is planned again. `ProducerIndex.replace`
swaps an implementation under the same contract and drops cached plans.
`ProducerIndex.without` removes modules, keeping every result cached for the
prefix before the first removed one, the routes planned within it, and the
goals known to have no route. The `Registry` keeps an index of its modules up
to date (`Registry.index`) this way. The `Kernel` keeps one index per set of
modules excluded by a request chain, each derived from the index of the whole
library. `Module`, the protocol every expert
implements, is part of the ABI (`nca.abi`).

Values of the core type constructors (THEORY §20.7) have fixed
representations, so experts by different authors agree on them: `seq[a]` is
a sequence, `pair[a,b]` a pair, `unit` is `()`, and `either[l,r]` is an
`abi.Choice` carrying the alternative's index and value.
`modules.combinators.Case` and `Fold` are the polymorphic eliminators of
choices and sequences.

A goal no route reaches is a capability gap (THEORY §20.9).
`planner.gaps.gaps` lists the unary contracts `A → B` whose installation
would complete a route, with `A` producible from the inputs and `B` consumed
toward the goal, each confirmed by planning with a stand-in expert.
`planner.gaps.fewest_missing` finds a route needing the fewest missing
connectors by a 0-1 breadth-first search over types, avoiding refused ones,
and `planner.gaps.repair` requests them in turn from a supplied acquirer,
searching again after each refusal (§20.9, Theorem 20.12).
`kernel.Kernel(acquire=…, missing=…)` does so for a request it cannot serve,
appending the acquired experts and serving the request through them.
`benchmarks/gaps.py` compares these with random acquisition.
`gaps(arity=n)` also lists experts with up to `n` inputs, each a set of
producible types (Theorem 20.15), and `repair(arity=n)` requests them, fewest
inputs first; `CertifiedAcquirer` tests such experts on input tuples.
`benchmarks/combining.py` measures acquisition of experts that combine two
inputs.
With `media`, `repair` invents an intermediate type for an unreachable goal no
existing medium reaches: `planner.gaps.medium` founds a content-addressed
constructor on the goal with identity `Founder` connectors, and
`planner.gaps.grow` asks the acquirer to connect each listed type into it
until a pass adds none. An acquirer may return companions with the requested
expert, such as the decoder learned with an encoder. `benchmarks/media.py`
compares repair with and without media over a sequence of tasks.
`retention.acquisition.CertifiedAcquirer` (Theorem 20.14) wraps any fitter
and case sampler as an acquirer: request `k` fits on training cases and is
admitted only after zero errors on `required_cases(ε, decision_level(δ, k))`
fresh cases, drawn in doubling batches and stopping at the first
disagreement (`earlyTest_admits`, `earlyTest_reads`), and admitted experts
report `ε` through `rate` for
`evidence.route_risk`. `benchmarks/certified_acquisition.py` compares
memorizing and generalizing fitters with and without certification.

Available inputs are addressed by position where types do not tell them
apart (THEORY §20.8): `planner.Given` carries an optional `position`, the
runtime binds slot and request inputs as an ordered list, and
`router.infer` checks that a position holds the named type. `NCA.PPlan`
(`lean/NCA/Execution/Relevance.lean`) models positional plans. `abi.Contract.relevant`
lists, per slot, the inputs every filling must use; `Fold` declares both
inputs of its step. `planner.uses` computes the positions a plan reads, and
`router.infer` rejects a filling that misses a relevant one. The planner and
the cost planners carry a set of required positions with every sub-goal:
an input meets it only if it is the one required, an application divides it
among its arguments (`planner.assignments`, spread-out divisions first), and
a `map` passes it to its source. `plan`, `plan_min` and `plan_pareto` accept
a requirement on the task's own inputs.

## 5. Reliability under distribution shift

`nca_arithmetic.pipeline` reports, per recognizer, the excess of in-situ over offline
failure rate: the lower bound on induced shift of `shift_ge_gap`.

## 6. Algorithms of the handwritten-arithmetic pipeline

**Segmentation** (`nca_arithmetic.segmenter`). Ink columns (intensity > 0.1) are
grouped into runs; runs separated by fewer than 4 blank columns merge (the
gap was chosen on the `validation` split, where 4 minimizes segmentation
failures for 2, 8 and 32 operands; results in sections before §15 were
measured with a gap of 2, which split broken strokes more often). Each
run is cropped and translated so that its center of ink mass is at the center
of a 28×28 canvas, the MNIST normalization convention.

Fusion, parsing and the recognizers are parameterized by an operator
vocabulary: arithmetic (`+ − ×`, value type `types.INTEGER`) and comparison
(`< > =`, value type `types.BOOLEAN`) use separate module ids and semantic types,
so installing one family cannot satisfy or alter the other's contracts.

## 7. Measuring accumulation

The add-and-freeze runner (`nca_arithmetic.accumulation`) checks the stability theorem
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

`ExpertStore.prepare(route)` implements the route-aware transition when called
explicitly before executing a route; it evicts only experts outside the route
(least recently used first), loads the missing ones, and pins the route's
experts until the next `prepare`. `tests/test_loader.py` reproduces the case
where least-recently-used eviction is not optimal (16 loads against the
optimal 11). Theorem 12.14 maps to `oversized_route_infeasible` in `Eviction`;
all lazy experts in a prepared route must belong to that store, ensuring their
later invocations use the same resident set. A lazy expert's manifest and
owning store cannot be reassigned after construction. Route preparation is not
automatic in `Kernel` or `execute`.
Preparation scans route experts iteratively, so its scan does not depend on
Python's recursion limit. Other planning and execution paths may still recurse.
Lazy wrappers can expose demand and relevance callbacks without loading their
implementations. Callers must provide rules consistent with the implementations;
preparing the whole route eagerly still loads all its lazy experts, including
ones that demand-driven execution might skip.
With `prepare(route, eager=False)`, the store pins the same route but loads its
experts on invocation; the entire declared route must still fit its budget.
Previously resident experts outside the route remain evictable. Additional
dynamic requests can fail if pinned experts leave insufficient room.
Pinned references reserve their expert definitions even before loading, and the
budget cannot be reduced below the declared size of a pinned route.
`prepare` rejects an oversized declared working set before changing pins or
residency. The bound uses declared expert sizes, not measured process memory.
Other loading failures can still leave partial store changes. Prior resident
pins survive only while their original owners remain resident; prior deferred
pins are restored if their references have not been claimed. For the resident
case, `surviving_pins_maximal` in `Eviction` characterizes the largest resident
subset of the old pins.

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
is not sound (a digit misjudged as an operator is skipped); `nca_arithmetic.cascade`
measures its cost as the answers that differ between gated and ungated
refinement.

**Demand.** In `nca.runtime` a consumer may declare `demand(index, demand)`;
arguments and `map` elements with empty demand are not evaluated, so neither
their modules nor the requests raised there run. `ExpressionParser` reads
digit entries at even positions, operator entries at odd ones, and nothing of
an even-length sequence; `SymbolFuser` reads its digit input only when digit
entries are demanded. Hence the digit recognizer never runs on operator
positions. In selective solving, `SymbolFuser` passes original per-field
weight ordering to `ExpressionParser`, which uses it for digit and operator
choices; other consumers retain numerical readings unless they explicitly
support the same handoff. The parser batches ranked digit and operator
choices through the Elisa row-argmax kernel when available.

## 15. Normalization against shift

**Normalizer** (`nca_arithmetic.normalizer.GlyphNormalizer`, contract
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

**Practice** (`nca_arithmetic.practice`). Practice is offline. A copy of the recognizer
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

The edit reader's integer recurrence is specified by `osaTable` in
`NCA/Edit.lean` (§18.1). Lean proves empty-prefix values, zero self-distance,
the max-length upper bound, and distinctness of three cyclic row slots.
Elisa `native/edit.elisa` uses those three rows and batches one input against
borrowed slices of the encoded vocabulary. The Python boundary supplies
Unicode code points rather than UTF-8 bytes; it performs no normalization.
The integer distances feed the existing Torch tensor and softmax operations,
so the learned/calibrated reader interface and declared costs are unchanged.
`modules.edit._edit_distance_reference` retains the full-table reference; missing native
exports fall back to Python. The compiled loop's agreement with the model is
tested, not a theorem about the generated binary.

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
(§21.6). The optional log-distribution interface retains finite group masses
that underflow in numerical probabilities; native Elisa grouping has a PyTorch
fallback. Adapters preserve this interface and its revision identity. A
custom rung overriding probability distributions must also provide a matching
log distribution to retain underflowed masses; otherwise the adapter logs the
numerical probabilities. The linear-space format decoder falls back to an
Elisa log-space decoder when weights or forward contributions underflow or
linear weights or backward scaling overflow, or to the NumPy
reference when the native kernel is unavailable; banded correction checks an
exact partition if its risk rounds to zero, which can require more work. If a
rung lacks labels needed to fit a requested restricted decision,
the account is unavailable rather than treated as a finite bound; refinement
can try higher rungs and abstains if none supplies a usable account.

## 25. Which word to climb, and when to stop

`nca.refinement.policies` contains refinement state, climb-priority helpers, stopping
policies and certification routines. `nca.ladder` re-exports the public names
and uses the same priority-function objects. `ladder.rungs` implements
calibrated observations and temperature fitting; `engine` owns the refinement
loop and result, `budgets` owns conservative sums and risk allocation, and
`attestations` owns calibration serialization and calibrated expert adapters.
`nca.ladder` retains decision/readout helpers, shared native backend selection
and public exports. Implementation modules load after these shared definitions;
calls through the public API retain the same backend and scoring overrides.

`nca.ladder.refine` accepts an optional generic climb-priority callback; its
default ranks by charge, while `charge_per_cost` is an experimental heuristic
using the next invocation's declared cost (§25.1). `solve`, `solve_many`, and
`solve_stops` pass the chosen callback to the controller.

`nca.ladder.stopping_rule` estimates `P(A | s)` by binning calibration states
(§25.3). Its optional open-charge feature also bins by the fraction of the
current bound assigned to items that can still climb (§25.4). When the
account is unavailable, it bins open charge relative to the target instead.
`nca.selective.solve_stops` evaluates pure policies on a shared deterministic
refinement path, preserving each selected state's readings and cost (§22.4).

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
`prefix.PrefixEvaluator.corrected` uses this allocation with its posterior marginal
risks. `certificate_session` creates a cursor and priorities owned by one solve;
`element_certificate` creates that session through an optional generic hook.
State is reset when its evaluator, decoder mode, or input length changes.
Each certificate resolves its prior once for both answer selection and risk.
Selective solving creates a per-solve consumer session and holds each resolved
prior fixed across refinement and final answer production.
Refinement rejects invalid item indices, nonfinite or negative certificate
charges, and nonfinite total charges before comparing a bound with a target.
It rounds non-binary64 charges upward on conversion, then sums the binary64
values with upward-rounded additions, assuming IEEE 754
binary64 round-to-nearest arithmetic and gradual underflow. Lean proves the
real-number accumulator principle, not the floating-point implementation or
the conservativeness of the charges themselves.
The built-in additive floor and the formula evaluator's non-detection floors
convert and sum fixed charges downward under the same arithmetic assumptions.
Detection-based and other custom floors retain their own obligations.
Pairwise detection shares use Elisa prefix and suffix sums with upward-rounded
products; Markov halves and within-group additions also round upward. Lean
checks the real-number ordering, not the floating-point code or the individual
risk estimates. Detection floors have not yet been numerically enclosed.
The correction account also rounds each share and within-group risk addition
upward; `combined_allocation_cover` checks how these charges preserve the
coverage of the allocated bound in real arithmetic. Binary floating-point
inputs no wider than binary64 convert exactly before the Elisa addition;
other within-group inputs are converted upward first.
The correction account updates changed cursor rows and refreshes marginal
priorities every `isqrt(m)` changed rows or when the prior changes. Sequence
and within-certificate risks are reused only while their relevant inputs
remain unchanged. The raw answer cursor reuses its trace on unchanged
readings; changed readings still require incremental decoding and per-word
distribution preparation. Elisa's `changed_rows` compares contiguous binary64
snapshots in row order without a temporary comparison matrix; other layouts use
NumPy with the same unequal-value semantics.

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

The Boolean domain's own native module, `nca_boolean.kernels`, exports
`certificate`: the least-risk certificate recurrence over parsed prefix trees,
including right-child tie preference. Its opcodes are the formula vocabulary,
so it lives with the domain, not in the core kernels. `FormulaEvaluator.evaluated`
marshals opcodes and child indices to Elisa; `evaluated_reference` remains the
Python recurrence and fallback when the module is absent. This implements the
existing certificate soundness and minimum-weight results (18.3–18.5).

`decoding.parse` uses the core's native `parse_tree_generic`, or `parse_tree`
for arities 0–2. It returns the same child lists as `parse_reference`, with
invalid inputs returning `None`. The Elisa parsers maintain an explicit parent
stack, avoiding recursion depth limits. The certificate and correction
accounts parse with it and then select the certificate, so parsing stays
generic and only the selection is domain code. `valid_prefix` checks the
format automaton without building the tree; `guardedPrefix_correct` in
`NCA.Decoding` proves that the corresponding guarded natural-number validator
accepts exactly the automaton's completed runs. This does not prove the Elisa
implementation or its machine-integer arithmetic; its guard keeps the counter
within the remaining input length before addition.

`native.decoding.grouped_masses` sums finite nonnegative row entries into
caller-declared class groups, indexed by each class's position in the
vocabulary's arity order (`RankedVocabulary.class_groups`), so arities need
not be consecutive. `prefix.arity_masses` uses it to prepare raw
arity masses for stateless, prior, exact-cursor and banded decoding; the
Python grouped sums remain the fallback. No calibration or normalization is
applied by grouping. `grouped_mass_sum` and `grouped_mass_nonneg` in
`NCA/Selective.lean` prove preservation of total mass and nonnegativity over
real numbers (§18.3). The native loop uses compensated additions in class
order, matching the runtime's Python float tuples in tested comparisons;
NumPy scalar sums may round differently. This is not a formal floating-point
error bound.

`native.decoding.grouped_argmax` performs row-wise selection within supplied
class groups. `PrefixEvaluator.symbols` uses it after arity decoding; group ids
and scores are arguments, so the kernel is independent of the vocabulary.
Strict score comparison preserves the first class on ties, matching the
reference restricted argmax of §21.5. The Python loop remains the fallback.

Native grouped selection reuses the current `answer_readings` snapshot when
running inside a correction session. That snapshot is copied from the input
after changed rows have updated the cursor, so later caller mutation cannot
alter cached observations. Stateless word selection still prepares its own
score array. No extra observation/calibration cache assumption is needed.

`ladder.allocate_risk` dispatches ordinary binary64-compatible priorities to
native `risk_shares_checked`, which validates them while finding the largest
priority. Other numeric representations retain Python validation. The Elisa
loop rescales by the largest priority and uses compensated summation; all-zero
priorities get uniform weights. A downward-rounded sum and upward shortfall
adjustment ensure the returned shares cover the supplied binary64 bound under
the documented floating-point assumptions. The Python path remains the
fallback. Both implement Theorem 23.11;
small floating-point differences in charges can affect refinement tie order.

The correction account uses `priors.sequence_log_weight` to score the
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
and returns the original tensor dtype.
CPU temperature fitting can use Elisa `calibration_loss_grid_stable`, which
evaluates the same 120 candidate temperatures, supports arbitrary grouped
labels, and rescales overflowing mean losses using row maxima cached across
affected temperatures. A row whose target is a singleton uses a direct target
calculation; full and target-group normalizers add unit mass directly at their
respective maxima, including ties. Older builds can use
`calibration_loss_grid` when all its candidate losses are finite.
Calibration accepts signed and unsigned integer label tensors; labels are
converted to signed 64-bit indices and checked against the observation width.
For CPU held-out data, `calibration_subset` finds included rows and their
group labels in input order; unsupported metadata uses the PyTorch reference.
Rungs cache at most 128 absent restricted-calibration results, invalidating
them on recalibration or held-out label replacement. A weak reference avoids
retaining old label tensors. As with fitted temperatures, callers must not
mutate snapshot tensors in place. The derived cache is discarded during
serialization and rebuilt on demand, including when loading a rung serialized
before the cache fields existed.
For a wide class space and a small selected set, it scans the selected classes
instead of allocating a lookup proportional to the full width. The selected
matrix gathers row and class indices together, avoiding an intermediate copy
of all columns in the included rows. Other shapes retain the lookup path.
The native path is used for up to 2,048 logits in ungrouped fits and 16,384
in grouped fits; larger fits use PyTorch based on local timing measurements.
Other devices, gradient-bearing inputs, unsupported layouts and unavailable
kernels also use PyTorch. These are routing thresholds, not model-size limits;
floating-point rounding can change a near-tied winner.
The reference fit reuses row shifts across temperatures. If native grid
losses are unusable or an ordinary reference mean overflows, it computes the
mean from individually scaled row gaps and normalizers of observed target
groups. Unused empty entries do not participate; targeting one is rejected.
Reading, risk, and distribution paths require positive finite temperatures
for both ordinary and ranked observations. `temperature_rank` proves the
real-arithmetic ordering effect of the temperature's sign.
On CPU, Elisa `observation_logs_into` validates weights and writes floored
logarithms into caller-owned storage; older native builds and the reference
implementation remain supported.
Integer logits are shifted relative to the selected classes before conversion
to floating point. On CPU, Elisa `shifted_integer_logits_into` writes the
shifted values into a caller-owned array; other devices and missing kernels
use the reference path. Integer inputs return ordinary probabilities in the
default floating dtype, and log probabilities in binary64 where supported.
Readings, grouped distributions and log distributions accept leading batch
dimensions and normalize each final-dimension row independently; integer batches can use
Elisa `shifted_integer_rows_into`. Small CPU binary64 batches without
gradients can use Elisa `scaled_logit_rows_into`; larger batches retain the
tensor path based on local timings. Grouped CPU batches can use Elisa
`calibrated_group_rows_into`; larger inputs use the tensor path. `Rung.risk`
remains per item; `Rung.risk_batch` handles numerical readings over leading
batch dimensions, returning binary64 risks. It uses Elisa
`calibrated_risk_rows_into` for supported CPU inputs up to 65,536 selected
logits and the tensor path otherwise; this is a routing heuristic, not a model
limit. Unrestricted native batches use implicit singleton groups rather than
materializing class metadata. MPS risk batches return on CPU because MPS lacks
binary64. Callers may supply original binary64 ordering weights to
`risk_batch` when consumers use that same ranking; otherwise it selects from
the numerical reading. Ordering weights must have a floating-point dtype;
reading and ordering inputs are mutually exclusive.
Reused readings can also use boolean or integer representations; class
selection preserves integer ordering before a potentially lossy conversion,
both per item and in batches. Supported CPU batches of 64-bit integer
readings use Elisa `calibrated_integer_risk_rows_into`; other configurations
retain the tensor selection path.
Standalone decision risk accepts finite nonnegative unnormalized weights with
positive total mass in the decision. Its Elisa path checks and sums the weights, rescaling
when the total overflows; PyTorch supplies the fallback.
Integer inputs are ranked before conversion to floating point, though their
subsequent masses and ratios can still round.
Both return the smallest positive binary64 value if positive outside mass
would otherwise yield zero, without claiming a general upward error bound.
For a large temperature, scaled differences that overflow before division
are computed by scaling each finite operand first, in both Elisa and PyTorch.
The PyTorch path promotes lower-precision logits when the temperature is
outside their dtype's finite normal range.
MPS promotes half-precision inputs to float32 when sufficient; temperatures
outside float32's finite normal range use CPU binary64 intermediates. Log distributions
from MPS observations are returned as CPU binary64 tensors, and a risk
recovery requiring binary64 also copies its selected values to CPU.
For MPS log distributions, sparse selections from inputs of at least 16 MB
are gathered on the device before transfer; smaller or denser inputs are
copied first. This routing threshold is a local performance heuristic.
Calibrated decisions reject NaN or positive-infinite log weights and selected
groups with zero total mass; negative infinity is valid for individual
zero-mass entries. The fallback checks the maximum on the host, which entails
a device synchronization for accelerator tensors.
PyTorch remains the fallback for gradients, other devices, nonpartitioned
groups and missing kernels. Double intermediates may differ from PyTorch's
float32 arithmetic by rounding, requiring outcome checks on full runs.

The native calibration group-id and class-index arrays are cached by the
immutable decision key and marked read-only. Each metadata cache retains at most
128 recently used decisions; this bounds entries rather than bytes. Evicted
metadata is recomputed; group IDs are expanded by Elisa when available.
Normalization of immutable built-in decision tuples is cached by identity;
mutable groups are copied and validated on every use. The metadata contains
only decision structure; calibration
temperatures and observation values remain current. The revision-cache
invariants (23.12, 23.15) apply to this deterministic metadata. Within a
refinement run, risk and distribution caches retain only each item’s current
rung; climbing discards that item’s obsolete entries. Missing-calibration
results are cached separately for risk and distribution queries on that rung.
A single cached entry uses a pair and expands to a dictionary only when needed. For a default account with immutable decisions, a climb replaces only that
item’s charge (25.5), while the bound is still summed in the original order.
Mutable decisions are rechecked at every step. Experts and calibration
parameters must remain fixed for the run. Gradient-bearing
observations continue through PyTorch and retain differentiability.

`Rung.risk` dispatches to native `calibrated_risk_for_reading_checked` for supported
CPU observations and partitioned groups, selecting and charging in one call. It chooses the group containing the
class selected from the ranked weights or numerical reading, rather than
choosing the group with greatest total mass. Full-class risk uses singleton groups.
Reused readings must match the observation's shape; selected entries are
checked for finite nonnegative values, but their provenance is the caller's
responsibility. Restricted all-zero readings retain first-class tie behavior.
With an older native kernel, reused readings take the validated fallback.
It sums the other groups' weights directly instead of subtracting the chosen
probability from one. The PyTorch risk path uses the same formulation. Decision groups must be a
nonempty partition of distinct nonnegative class indices; overlapping and
repeated classes are rejected.
PyTorch remains the fallback under the same device/gradient restrictions as
grouped distribution. When finite alternative logits underflow, both paths
recover their aggregate in log space and retain a positive binary64 sentinel
if it remains unrepresentable. This is not an outward-rounding guarantee.
`Rung.observe` converts probabilities to binary64 and floors zero at the
smallest positive representable value before taking logs. For array and list
outputs, an Elisa kernel validates weights and computes the logarithms;
CPU fallback uses scalar `math.log` on the same binary64 values. MPS tensor
outputs are copied to CPU before binary64 conversion because MPS lacks that
dtype. Other non-CPU tensor outputs use the PyTorch fallback, whose logarithms
can round differently. Representing logarithms in binary64 can collapse distinct
weights into a tie, so it does not always preserve the original weight order.
`Rung.observe_ranked` retains a separate immutable weight snapshot for exact
binary64 class ordering. `Rung.risk` can use that ordering to select its group;
numeric readings may still tie, so the consumer must use the same ranked
choice. `ranked_argmax_checked` validates selected weights in Elisa; older
kernels use the validated Python fallback. For larger restrictions,
`ranked_argmax_indices_checked` also validates indices and gathers weights in
Elisa; sparse restrictions retain the existing path. If unselected weights
cannot be converted to binary64, selection gathers only the selected weights.
Immutable built-in integer tuples cache read-only index arrays by identity,
with at most 128 entries, not a byte limit. Mutable inputs are copied and
validated on each call. The selective controller propagates ranked readings
to consumers and fusers that explicitly support the handoff.
Positive unnormalized weights are accepted; neither validation nor smoothing
is a calibration guarantee. Native double arithmetic can change rounding.

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
entire checking budget. `nca_boolean.logic.shifted` skips candidate fit/check evaluations
when even that bound exceeds the target. The uncontrolled evaluation remains
unchanged, and feasible audit budgets use the existing fixed-sequence test.
The Lean obstruction theorem covers the zero-error power inequality; the
binomial bound's monotonicity in errors is used as its standard statistical
property, not newly formalized here.

For feasible audit budgets, `nca_boolean.logic.shifted` computes checking outcomes lazily
in the fit-half-determined order. It stops at the first rejected candidate
and chooses maximum coverage only among the accepted prefix. Fit-half
candidate evaluation remains complete, and the order never changes in
response to checking labels. This implements §17.5's existing stopping rule.

Checking calls to `nca_boolean.logic.outcomes` pass `reject_above` and `alpha`. After a
new error, the runner tests the optimistic bound that credits every checking
example as answered. If even it fails, the routine returns partial counts,
which are used only to reject that candidate. Accepted candidates still
consume the full checking sample; fit and evaluation calls remain complete.
Theorem 17.7 proves rejection under the supplied monotonicity premises;
binomial-bound monotonicity itself is not newly formalized here.

`refine(..., observe=...)` optionally exposes every evaluated state, including
initial and terminal states. Outer reading lists are independent; observers
must treat tensors as read-only. This is the basis for shared-target inference
under Theorem 17.8. Audit fitting uses the hook through `solve_many`. A future client
should retain only selected target snapshots, rather than every trace state.
Target-dependent floors/stopping must not be mixed into shared-path selection.

`selective.solve_many` runs to the strictest requested target and retains at
most one first-qualifying reading snapshot per distinct target. It reconstructs
each answer through the same consumer chain, preserving the cost and bound
of that policy's stopping state. Exhausted targets use the final state.
`solve` shares the internal preparation/rendering path; its floor/stop options
remain available. Multi-target calls exclude those options and require
deterministic consumers. Audit fitting uses this API to share thresholds for each input.

`nca_boolean.logic.outcomes_many` accumulates fit-half answer/error counts from
`solve_many` for all inflation thresholds. These counts determine the same
candidate order as independent solves. Checking lazily computes one shared
path per visited sample and retains only its answer/error flags. Candidates
still consume those flags in the predetermined order and stop on irreversible
rejection; checking labels do not influence the fit trajectory or ordering.
When the first candidate's fit coverage cannot certify even with zero errors,
checking starts with that candidate alone and switches to sharing only after
it passes. The fit-based choice changes computation, not the statistical test.

`decoding.CertifiedSplit` manages a fixed-reference `Split` band and widens
it until the relative tail and exact-maximum conditions of §23.3 hold.
Its band width uses the configured maximum arity, and its full-coverage
threshold is precomputed from the fixed reference counters.
It and `decode_banded` sum off-reference log masses and tolerated row-mass
excess using Elisa's `tail_mass_summary`, with a NumPy fallback, and compare
scaled tails in log space. The initial tail search uses Elisa's
`initial_band_changes_scaled` when available,
stops at one more than the word count, and reconciles the crossing with the
Python calculation to handle `lgamma` rounding differences.
`band_changes` requires one in-range integer reference-column index per row;
integer array checks run vectorized before native conversion.
If a computed sequence risk rounds to zero, the generic Elisa
`format_partition` separately accumulates selected and alternative paths;
the fallback uses the same recurrence in NumPy. Both reject non-finite
results of adding finite path weights instead of treating them as absent mass.
`pdpSum_zero_row` and `partitionCompose_zero_left` in `NCA.Product` justify
stopping when no reading or partition paths remain. `sum_filter_support` and
`foldl_await_zero_nonempty` in `NCA.Decoding` cover the support restriction and
early completed-state exclusion used by the format partition.
Single-row updates reuse native cursor sweeps; rebuilds preserve the reference.
Its `Banded` result bounds model risk with the requested slack. After a
successful result, `sequence_risk` scores any accepted arity sequence with the
same upper normalizer, even outside the band. `normalizer` and
`climb_normalizer` certify that bound without requiring or tracing a maximum;
the calibrated account uses these while raw answer selection uses `result`
and `climb` (the existing `banded_risk_le`
and `banded_risk_slack` proofs apply). The native `accepted_log_weight` kernel
validates the selected prefix sequence with a pending-subformula counter and
sums its log weights in one pass, without constructing children. It uses the
same remaining-length guard as `valid_prefix` and corresponds to `await` and
`accepts_iff_codes` in `NCA/Decoding.lean`; invalid
sequences return an empty result, distinct from a valid zero-weight sequence.
For wide alphabets, direct indexed lookup or a temporary first-occurrence
table avoids a linear alphabet scan for each selected symbol; duplicate
symbols retain their first column. `accepted_arity_lt_length` bounds table
indices for accepted sequences. Smaller alphabets use direct scanning.
The scorer, format partition, and one-shot banded decoder check flat matrix
dimensions with division and remainder instead of multiplying signed lengths.
`matrix_shape_division` proves the equivalent natural-number relation; it does
not prove the native implementation.
Failed updates invalidate this bound. It validates
probability row mass and arities 0–2; zero accepted mass returns `None`.
The evaluator can opt into this wrapper for raw answer selection. Storage remains full-sized
arrays with restricted active bands, and floating-point enclosure is not
certified by this wrapper.

`logic --premises` reports the §21.8 diagnostic for every reader rung,
including the learned reader whose calibration can fail under noise shift.
It tests fixed-rung readings, not the adaptively selected deployment policy.

`logic --band-slack η` enables certified banding for both the evaluator's raw
answer cursor and calibrated risk cursor. The latter scores the actual selected
arity sequence with `sequence_risk`, regardless of the calibrated maximum.
Revision-invalidated calibrated rows are normalized before updating the band;
exact marginal refreshes still supply allocation priorities. The relative
slack bounds compare accounts at identical readings, not final accounts from
possibly different refinement trajectories.
Positive raw arity rows are normalized before tail accounting; Theorem 23.14
explains the unchanged score ordering. Zero-mass rows fall back to the
existing nondecoded reading behavior. The option defaults to disabled pending
broader timing, tie-choice and deployment-audit comparisons.

`priors.ArityPrior` represents the weighted deterministic automaton of
THEORY §27. Its validated transition, log-edge and log-final arrays are copied
and read-only. Alphabets may contain distinct nonnegative integer arities.
When a label exceeds native signed 64-bit range, native calls use dense
alphabet indices and map decoded labels back to their original integers.
The separate format decoder maps arities too large for a fixed input to an
unreachable sentinel before native conversion (`accepted_arity_lt_length`
in `NCA.Decoding`).
`prior_relabel` in `NCA.Product` proves path-weight preservation for a
relabelling with a left inverse.
Prior path-weight evaluation rejects detected finite-addition loss while
preserving zero mass for forbidden or zero-weight paths. For wide alphabets
and longer paths, it uses sorted search or a compact first-column index when
applicable; short paths avoid building the index.
Reading-sequence and accepted-format scoring use the same local arithmetic
check; invalid syntax and zero-weight sequences retain their distinct results.
For wide alphabets, reading-sequence scoring uses lower-bound search when the
alphabet is sorted; otherwise it indexes first occurrences in the column-count
range and scans for other integer symbols. `ordered_lower_bound_is_first`
checks the mathematical first-occurrence criterion, not the native search.
Rolling prior partitioning checks selected-symbol membership in Elisa using
indexed lookup, binary search for sorted alphabets, or a generic fallback,
retaining the full-normalizer fallback for unsupported symbols.
The selected-path update uses the same lookup strategies, keeping first-column
semantics and processing path weights in their original order.
`sum_excluding_absent` proves the corresponding real-sum identity;
`search_midpoint_bounds` and `ordered_search_excludes_lower`/`_upper` prove
the search's interval and ordering principles, not the native implementation.
Selected symbols are checked as integers before native conversion. When NumPy
infers a non-integer dtype, native symbols are encoded from the original
integers to preserve their identity. `decode`
uses Elisa `decode_prior` for forward sums, maximum
backtracking and backward marginals, with a NumPy reference fallback.
`Decoded` retains the prior so its sequence risks include the edge and final
weights. Its marginal-row check detects invalid normalization but is not a
floating-point accuracy certificate. Weighted decoding also checks material
local log-arithmetic loss, with a magnitude-bounded fast path. On detected marginal or partition failure,
format and weighted-prior decoding and sequence risk can retry with checked shifts;
absolute partitions and incremental cursors retain their original scale. The recurrences
correspond to `pdpSum_eq`, `pdpMax_ge` and `pdpMax_attained` in
`NCA/Product.lean`; the format-only comparison exercises
the unit-prior specialization of §27.4.

The automaton must include any required format restriction: this interface
does not automatically intersect an arbitrary expert with prefix syntax.
The evaluator accepts a generic length-indexed prior provider as described
below. Both implementations use dense position-by-state tables, with
O(length × states × alphabet) work and O(length × states) storage. The Elisa
decoder rolls its maximum-score and backward rows while retaining forward
sums and traceback choices. Tie choices may differ between implementations.

`formulas.complete_prior(length)` constructs and caches the complete-tree
unit-weight prior of §27.4. Theorem 27.5 maps a supported length to its depth;
`CompleteShape` and `complete_shape_length` in `NCA/Decoding.lean` formalize
the shape grammar and its bounds. Construction uses pending height budgets
and a marker for a leaf constant after unary negation. Impossible lengths
return `None`; decoding and posterior calculations use the existing Elisa
weighted-automaton kernel. Exhaustive grammar tests check the transition
construction; the construction itself is not extracted from Lean. This
factory can be supplied through `FormulaEvaluator(prior=complete_prior,
decode=True)`. The evaluator accepts a generic deterministic length-to-prior
provider, uses it for raw answer selection and calibrated sequence risk, and
refuses certificates at unsupported lengths. The alphabet must be
`ARITY_ORDER`, and the prior must include syntax constraints. Native
normalizers refresh prior risk at every account call, while marginal
allocation priorities refresh periodically; the default format
cursor and its revision caches remain unchanged. Prior decoding and format
banding cannot yet be combined. `logic --prior complete` supplies the prior to correction routes, including
selective and shifted-policy audit runs; other accounts remain unchanged.
The CLI rejects combining this prior with banding before loading the reader,
and labels the chosen correction prior. Premise diagnostics still explicitly
report the format-only model. The complete-prior library now installs the
independent prior expert and the slot-consuming evaluator.

The Elisa prior decoder skips states whose current forward log weight is
negative infinity in forward, backward and marginal passes (§27.6,
`prior_support_sum` in `NCA/Product.lean`). The backward table is therefore
valid on forward support, sufficient for all emitted posteriors, rather than
a continuation table for arbitrary starting states. Per-position support
envelopes avoid scanning outside the reachable range. Arrays remain dense;
reused score rows clear only their previous envelopes, and no finite
low-probability state is pruned.

`nca_boolean.words.CompleteTreePrior` exposes the independent contract
`logic.formula.length.v1 → logic.arity.prior.v1`. It delegates supported
lengths to the cached constructor and returns an empty-support automaton
otherwise, retaining the output type without a format fallback. The ordinary
stable planner and runtime can route and execute it independently; the
evaluator can consume its `invoke` method as a prior provider. Direct
evaluation refuses selected shapes outside the supplied prior support.
`PriorFormulaEvaluator` declares a slot from formula length to arity prior,
with one call per invocation. Its `bind_slots` method constructs a per-solve
ordinary evaluator, caching the supplied prior by length. `split_route` binds
consumer slots before asking for certificates or invoking consumers, so risk
and answers use the same filling. Other slotted consumers must provide
`bind_slots`; unsupported bindings are rejected rather than discarded.

Slot fillings execute through the ordinary runtime in fresh workspaces with
a 10,000-invocation budget per call. This does not turn the selective solver
into a general cost-budgeted runtime: `Answer.cost` still counts reader
refinement compute, excluding consumer and auxiliary-slot execution. The
ordinary runtime charges slot and consumer manifests when executing the
whole typed route. The consumer chain still has one ordinary data input per
module; slots add explicitly bound higher-order dependencies.

`ArityPrior.log_weight` uses Elisa `prior_log_weight` to traverse selected
arities, accumulate ordered log edge weights and include the final-state
weight, corresponding to `prior` in `NCA/Product.lean`. Forbidden symbols or
transitions yield negative infinity; an empty sequence retains the start
state's final weight. The Python traversal remains the reference fallback.
`Decoded.log_weight` also uses the native selected-reading reduction, keeping
both position-wise scoring loops out of Python during posterior risk checks.

`formulas.height_prior(height)` constructs the unit-weight automaton of all
unary/binary prefix trees within an edge-height budget (§27.7). It allows
early leaves and unary nodes at any level; pending subtree budgets enforce
termination. `BoundedShape`, `bounded_shape_length` and
`complete_shape_bounded` in `NCA/Decoding.lean` establish the grammar's node
bound and complete-shape inclusion. Exhaustive tests check the Python
transition constructor against an independent grammar; the constructor is
not extracted from Lean. Numerical decoding uses the existing Elisa kernel.
`HeightBoundedPrior(height)` exposes the same typed length-to-prior contract
as the complete expert, with the fixed height encoded in its module ID.
`logic --prior height --prior-height D` installs it into the evaluator slot.
The height is explicit rather than inferred from audit labels; constants use
height zero. The CLI requires a nonnegative height and rejects structural
priors combined with the format-only banding option. Input lengths beyond
the bound's support retain the same automaton, whose decoding returns no
accepted sequence.

`ArityPrior.log_evidence(log_posteriors, log_base)` computes the relative
log evidence of §27.8, using native decoding for both normalizers.
`prior_evidence_identity` in `NCA/Product.lean` proves the finite-sum Bayes
identity under the supplied posterior relation and nonzero normalizers. The
API checks normalized probability rows and posterior/base support, rejects
zero base mass, and returns negative infinity for zero posterior mass. It
does not establish that calibrated reader scores satisfy a shared likelihood
model. Prior selection is explicit rather than automatically installed. `log_normalizer` uses Elisa
`prior_normalizer` for the sum-product pass with two reusable state rows.
Each row records an enclosing interval of reachable states. Reuse clears only
its previous interval, and transitions scan the current interval in ascending
state order. Cells outside the interval stay unreachable, by the support-step
invariant of §27.6 (`prior_step_zero_outside`). Symbol order and the order of
nonzero log additions are preserved. The initial rows still require O(S) space
and initialization; sparse intervals reduce subsequent scans, not automaton size.
`log_evidence` calls it for both arguments. The transition recurrence matches
`pdpSum_eq`; it retains the full decoder as a reference fallback when the
normalizer export is absent. Empty reading arrays follow the decoder
convention of no accepted formula. Readings identical to the base have
evidence exactly zero: `ArityPrior.supports` decides positive mass by
reachability alone, so neither `log_evidence` nor `select_prior` computes a
base normalizer for them, and the native and reference paths agree even when
that normalizer is too large to compute precisely.

`priors.select_prior` sums relative log evidence from unlabeled held-out
reading matrices under length-indexed candidate providers and one shared base
vector. It returns `PriorSelection` with the winning index, all scores and
sample count. Exact ties keep the caller's declared order; without clipping,
unavailable lengths exclude a candidate. Invalid normalizers, incompatible alphabets,
empty inputs, score overflow and no finite-evidence candidate are errors.
`format_prior(length)` exposes the syntax-only counter through the same
automaton interface for comparison.

By default this is empirical maximization of §27.5. An optional finite,
nonnegative `score_error` admits candidates within twice that supplied
total-score error of the best, choosing the first declared candidate.
`PriorSelection` retains the bound. Theorem 27.9 and `prior_selection_regret`
in `NCA/Product.lean` prove a conditional four-error regret bound. The API
does not estimate sampling uncertainty or prove reader likelihood assumptions. It does not install the selected
provider or certify an answering policy. Candidate order and calibration
must be fixed before selection; deployment checking remains separate.

`select_prior(..., score_clip=B, alpha=α)` clips each per-formula score to
[-B,B] and derives the simultaneous total-score error of §27.10. The result
records B, α and the derived error. In bounded mode, a provider returning
`None` receives -B for that observation; provided models with zero base mass
still raise an error. Mixing a manual error with this bound is rejected.
It assumes fixed models/base/B/K/n, IID formulas, and valid candidate base
normalizers wherever a model is supplied. `clipped_evidence_bounds` proves
the clipping range and `prior_selection_regret` proves the conditional
selection step; Hoeffding concentration is not formalized in Lean here.
The bound concerns expected clipped scores, not raw evidence or deployment
error. An answering policy still requires an independent risk audit.

`logic --prior auto --prior-height D` performs bounded selection after
reader calibration. It uses `--prior-fit` validation formulas at
`seed + 10000`, maximum requested depth and deployment noise when shifted.
Calibration labels supply only the common base frequencies; selection reads
texts through the highest reader rung. Candidate order is format, height D,
complete, with fixed `--prior-score-clip` and `--prior-alpha`. The chosen
correction route is then held fixed through audit and evaluation. D must
cover the generator's maximum requested depth plus optional leaf negation.
The default remains format-only; premise diagnostics remain format-only.

The auto-prior route is fixed before `shifted` receives it; checking labels
do not choose a prior. The regression verifies one selection precedes the
audit call even when multiple audit draws are requested. Theorem 27.11 and
`selected_audit_failure_le` express the conditional failure-mixture step.
They do not formalize the data-generation independence assumptions or
upgrade a reused checking split into fresh validation.

`nca.priors` exposes the structural-prior API; its `arithmetic` submodule owns
checked log arithmetic, posterior-risk conversion and score comparisons.
`symbols` handles lossless integer-alphabet encoding, `factories` constructs
cached shape automata, `decoding` computes posterior sequence results, and
`selection` compares held-out evidence. The weighted automaton remains in
`nca.priors`; implementation modules load after its class definition. Existing
imports through `nca.priors` retain their public names and exception classes.
Native backend selection remains shared with the Python reference paths.

`select_prior` owns snapshots of the base vector, alphabet and candidate
order for the batch. A local cache retains each immutable prior model and
base normalizer by candidate index and length; observation normalizers are
still computed for every formula. Large common prior offsets use the same
checked shifted prior for both normalizers, which the cache retains. The cache is discarded when selection
returns, so no cached denominator crosses calibration or selection runs.
Large residual normalizers are rejected before subtraction unless the readings
are identical; this is a diagnostic, not an accumulated-error certificate.
Empty readings are supported when a provider supplies a prior whose start
state has nonzero final weight; its relative log evidence is zero.
Decoded sequence risk uses `expm1` to retain small positive risks when the
selected sequence's log probability is near zero; the stateful evaluator uses
the same calculation. Elisa's prior log-sum uses `log1p` to retain small
alternative weights. These improvements do not by themselves supply a
certified floating-point error bound. Prior-backed and exact format-only risk
use a separate Elisa sum of selected and alternative sequence weights
(Theorem 27.16), with a Python reference path. Banded risk continues to use
its certified normalizer bound and can lose sufficiently small positive risk
to rounding. Format risk over other alphabets retains the previous calculation.
Within a correction session, unchanged revision-tagged readings reuse that
partition risk only for the same selected arities and prior object. Unversioned
readings, changed revisions, and changed distribution sources force
recomputation. Selective adapters carry the source identity through their
wrappers, so revision numbers from unrelated sources are never conflated.
Restricted-risk cache entries are also cleared when the risk callback source
changes; adapters preserve that callback's source identity across calls.
For changed readings, `PartitionCursor` retains prefix summaries and recomputes
from the first changed row or selected arity. The Elisa kernel performs the
numeric update. For sufficiently wide rows that appear sparse, it gathers
finite reading columns once per row and reuses them across source states;
their original order is retained. For nonindexed alphabets, that scan also
records the first selected column, even if its reading weight is zero.
`sum_filter_zero_readings` proves the
corresponding real-arithmetic sum identity, not the floating-point code.
For sufficiently long updates with an indexed alphabet, the selected symbol
is also its column; other alphabets retain the general search.
When both selected and alternative frontiers are empty, the update clears
retained suffix summaries and stops; `zero_frontier_step` gives the
real-arithmetic zero-propagation principle and `zero_frontier_suffix`
extends it over an arbitrary sequence of zero-preserving transitions.
Without the kernel, or when the estimated cache exceeds 64 MiB by
default, the cursor uses the rolling full partition. The limit is configurable;
the estimate includes the immutable alphabet-membership set used by the cache.
When no membership set is retained, a lower-bound check can choose the rolling
path before allocating that set if the numeric cache or its symbol pointers
cannot fit the configured budget.
Selected symbols use the same exact native encoding as the full partition;
changing that encoding invalidates the cached prefix, even if encoded values
match an earlier selection. Unchanged contiguous readings are compared with
the private snapshot before making a new copy; changed readings are copied
before the native update, preserving snapshot ownership.
The cache and its floating-point behavior are not formally verified in Lean.
For widths up to three, Elisa accepts clearly normalized, base-supported
reading snapshots in one pass; ambiguous or invalid rows fall back to NumPy's
full validation, as do wider alphabets and installations without the kernel.
The generic log-weight validation also uses Elisa for contiguous arrays;
noncontiguous arrays and installations without the kernel use NumPy.
When native prior decoding or maximization returns no result, the Python
wrapper checks the native normalizer if available to distinguish zero mass
from arithmetic failure. Maximum selection can retry the latter with checked
common shifts when mass exists. Older native modules without that entry point retain their
existing empty-result behavior.

`FormulaDataset(..., early_leaf=p)` and `formula(..., early_leaf=p)` expose
the structural-shift family in §18.1. The new trailing parameter defaults
to zero; its disabled branch consumes no random draw, preserving historical
seeded samples. `logic --early-leaf p` applies the structural variant to
selection, stopping-rule fit, diagnostics, audit halves and evaluation;
reader calibration remains on complete trees. The descriptive leaf column
is labeled as a maximum, since actual pruned-tree sizes vary.
`prunedLeaves`, `prunedBranches` and `pruned_branches_eq_leaves_sub_one` in
`NCA/Decoding.lean` formalize the algebraic count recurrences and identity;
they do not formalize the RNG's probability law.

The per-selection model cache also remembers declared absence. Bounded
selection penalizes each unavailable observation without discarding earlier
valid scores or excluding the whole batch. `partialEvidenceScore` and
`partial_evidence_bounds` formalize this reward's range (§27.12); no
likelihood interpretation or coverage guarantee is assigned to absence.

`logic --family-alpha A --shift ...` allocates A over the predeclared
`len(depths) * draws * len(targets)` risk-control audits (§17.9). It is
mutually exclusive with per-audit `--alpha`. `stats.family_audit_alpha`
rounds the divided level downward by one representable float for multiple
audits and rejects underflow. The level reaches feasibility checks, fit
ordering, checking rejection and certification. The family count is not
reduced using observed audit results. Default per-audit confidence is
unchanged. `audit_family_le` proves the finite union bound from supplied
individual failure bounds; it does not cover arbitrary later CLI runs.

Prior-aware `prefix.CorrectionState` retains a calibrated log-row snapshot. A
revision-tagged distribution refreshes only invalidated rows, using the same
per-solve revision identity as the format cursor (Theorem 23.12). Unversioned
distributions rebuild all rows and clear revision provenance. Snapshots are
copied before updates so previous arrays remain independent. Prior
risk uses a full decode initially and after each isqrt(n) invalidated rows;
between refreshes, the rolling native normalizer scores the actual selected
sequence. Cached nonnegative priorities allocate that current risk under
Theorem 23.11. Unversioned calls invalidate all rows and therefore retain
full refreshes. Stateless calls remain a full-decode reference.

`ArityPrior.best` uses Elisa `prior_best` for weighted maximum selection
without normalizers or marginals. Prior-aware raw answer selection calls
this path. It retains two maximum rows plus predecessor choices for
traceback. Each maximum row records an enclosing reachable-state interval,
clearing only that row's old interval when it is reused. Source and terminal
scans stay in ascending state order; symbol traversal and strict tie updates
match the full native decoder. The support-pruning maximum identity is
`prior_support_max` in `NCA/Product.lean` (§27.6). Dense predecessor
initialization and storage still cost O(mS). Without the export, the full decoder supplies the reference
fallback. The recurrences correspond to §27.2–27.3; tests cover weighted
priors, uniform ties, empty support, and a guard against full decoding.

`priors.tilt_prior` adds finite per-symbol log factors to an automaton's edge
weights, preserving alphabet, transitions, final weights and start state.
It rejects edge overflow and returns an independent immutable model. The
existing Elisa weighted kernels evaluate it without a new numerical path.
Theorem 27.13 maps to `prior_tilt` and `prior_tilt_ne_zero` in `Product`.
The leaf/binary count identity in Theorem 27.14 maps to
`bounded_shape_leaf_binary_count` in `Decoding` for bounded shapes.
`bounded_leaf_binary_prior` in `Product` connects the count identity to the
tilted automaton weights. `normalized_common_factor` proves finite-weight
cancellation, and `bounded_leaf_binary_posterior` combines these results for
finite sets of bounded shapes.
A caller can predeclare tilted providers in `select_prior`; no catalog or
CLI default changes automatically. Constant feature counts cancel after
conditioning, as tested for unary tilts of complete-skeleton priors.

The native prior decoder returns `PriorDecoded?`, exposed to Python as a
`PriorDecoded | None` record with `log_z`, integer `arities`, and nested
`marginals` rows. The compiler-generated record converter copies owned
arrays before releasing the call arena. `ArityPrior.decode` consumes named
fields; no float-encoded symbols, packed offsets or empty-array absence
sentinel are used for this result. Generated stubs describe the nullable
record directly. Native extensions must be rebuilt after this interface
change. The dynamic-programming recurrences and Python fallback are unchanged.

Numeric Python buffers are borrowed only when the compiler-generated shim
verifies the element format, one-dimensional C-contiguous layout, and C ABI
alignment. Incompatible read-only buffers are copied by the FFI converter;
mutable views require a directly writable aligned buffer and are rejected
otherwise. NumPy contiguity conversion alone does not ensure alignment.
The prior-decoding regression exercises read-only unaligned weights through
maximum, normalizer and full-posterior paths without an application-side copy.

Generated Python annotations accept `Sequence[T] | Buffer` for numeric view
inputs and require `Buffer` for writable views. NumPy arrays therefore satisfy
the input annotations, while lists are rejected statically for writable views.
These protocols do not encode dtype, rank, alignment or write permission;
the native converters enforce those constraints. Python 3.12+ uses the standard
`collections.abc.Buffer`; older typing targets use the official
`typing_extensions` backport without adding a native-module runtime dependency.

Native builds pass the running interpreter as `PYTHON_BIN` and let Elisa resolve
matching headers/configuration rather than guessing a platform-specific
`python-config` path. Installed compiler snapshots freeze and verify their
recorded bootstrap inputs, so development compiler rebuilds cannot invalidate
the consumer's installed toolchain. Source/product and frozen-input integrity
checks remain enabled.

## 28. Packages as experts

`objects.store` implements artifact DAG admission, directory persistence and
mutable name bindings. The `objects` package owns data definitions, canonical
encoding and public exports. Admission serializes once, validates the canonical
round trip, and stores immutable bytes. Existing references accept identical
bytes idempotently and reject differing bytes, including hash collisions.
Reads and attestation lookup decode independent views; callers can edit those
views without changing the stored artifact. A reentrant lock serializes admission
and index publication, while reads capture bytes before decoding. `save` captures
a record snapshot and refuses conflicting existing files. Pickle restoration
requires a fresh instance and rebuilds validated admissions, including legacy
object-valued states. Directory publication is not a multi-file transaction.

`Execution/Artifacts.lean` proves the in-memory retention theorem of §28.8 using
a hash map of byte sequences. The codec and digest are arbitrary functions;
decode/re-encode checks replace a round-trip hypothesis, and collision rejection
replaces a collision-freedom hypothesis for retention within one store.
`tests/test_artifact_identity.py` compares generated operation traces with
`Execution/ArtifactReplay.lean`, instantiating the codec boundary with UTF-8 for
canonical schema-valid fixtures and supplying their digest table. Schema-invalid
inputs, view mutations, persistence conflicts and concurrent duplicates have
separate Python regressions. This is an executable link, not a proof of Python,
JSON, locks, hashing libraries or filesystem behavior.

`objects.loaders` resolves primitive entries (§28.9). Distributions register
factories under the `nca.loaders` entry-point group, naming a stable identifier
(the core's own are `nca/<name>@1`, declared in `pyproject.toml`) or an earlier
import-path entry kept as an alias; the value is the factory's current module
path. `resolve` loads the unique registered location, refuses an identifier
registered at two locations without affecting others, and imports unregistered
`module:attribute` entries directly. Registrations are cached; `refresh` rereads
them after installing distributions. Core primitives store only registered
identifiers, which `tests/test_loaders.py` checks, so learner modules can move
without changing any reference. `Execution/Loaders.lean` proves Theorem 28.6 and
`Execution/LoaderReplay.lean` is its executable differential runner.

`objects` holds the content-addressed object model: `Primitive`, `Composite`
and `Attestation`, each identified by the SHA-256 digest of its canonical
JSON (`canonical`, `digest`). A primitive loads by calling its `entry` with
JSON `arguments` and checks that the loaded manifest equals the declared one;
`weights` carries the digest of the bytes it loads (`file_digest`). `Store`
admits a composite only after its members and only when its declared effects
cover theirs, keeps attestations by subject, and saves one canonical file per
object, rechecking digests on `open`. `Names` maps mutable names to
references. Manifests declare `effects` (`None`: undeclared; empty: pure).

Export identities (§28.3) are `composite.ref#position`, with the numeric export
position also used in the manifest's module id. The planner's producer index
is separate state and contributes nothing to this identity. `export_identity_eq`
in `Execution/Package.lean` proves uniqueness of the abstract reference/index
pair; the formatting and store round trip are regression-tested.

`packages.install(store, ref)` returns the experts a scope sees. Primitives
become `LazyExpert`s carrying their reference as `identity`, one per
reference however many composites share it. Transparent composites expand to
their members in order. An exporting composite becomes one `Export` per
exported contract, whose contract is the export with the composite's
requirements as slots; inside, each requirement is a `Requirement` expert
that calls the filling of the current invocation (a stack, so nested and
recursive invocations are safe), the export's route is planned once by
`plan_stable` over the members and requirements, and requests are resolved
by a `Kernel` over that inner library. Each call executes the route in a
fresh workspace with the `budget` given at installation, so inner provenance
stays private and the outer workspace records one message per export
invocation. `execute` accepts ordered input messages, so exports with
several inputs of one type are supported. The Lean model's inlining
(`WellTyped.inline`) is the correctness argument for this substitution; the
implementation executes the inner route instead of rewriting the outer plan,
which gives the same values because both evaluate the same expert
applications on the same inputs.

`nca_arithmetic.package.arithmetic` is the first real package: the
segmenter, symbol fuser, expression parser and evaluator as members, the
digit and operator glyph readers as requirements, and one export from
expression image to integer. The export shares its inner index with its
kernel (`Kernel(..., index=...)`).

`cache.ResultCache` implements the result cache of §28.5
(`cache_lookup_correct`, `cache_store_sound`; least-recently-used eviction
by `cache_evict_sound`). `execute(..., cache=...)` looks up an application by
the module's `identity` and the `value_digest` of each input when the module
declares empty effects and the application has no slots; inputs without a
canonical encoding (NaN, objects, non-string keys) disable the lookup. A hit
posts the stored value with producer `ref+cache` and charges neither budget.
Only results returned directly are stored, not those obtained through
requests. A sealed export with no requirements is cached as a whole; an
export with requirements takes slots and is not.

`packages.discover(store)` implements §28.6. It reads the `nca.packages`
entry-point group of every installed distribution, sorted by name; each
entry point names a callable that puts a package into the store and returns
its reference, which is bound to the entry point's name in a `Names`. A
name offered twice, a failing contribution, a reference missing from the
store and a name already bound elsewhere are errors. This project's
`pyproject.toml` contributes `nca.arithmetic`
(`nca_arithmetic.package.arithmetic`) and `nca.formulas`
(`nca_boolean.package.formulas`: tokenizer and formula evaluator, with
the word reader as requirement); a domain shipped as its own distribution
declares the same entry point and needs no change to the core.
Installed primitives keep their implementation's `demand` and `relevant`
rules: the lazy expert reads them from the implementation, loading it, the
first time the runtime asks.

`ladder.calibration` states a rung's temperatures (after fitting any listed
decisions) as a `calibration` attestation about the expert's reference, and
`ladder.attested` reads one back into a rung, refusing an attestation about
another identity. Held-out data are not part of the claim.

Selective refinement (`selective`) still requires the producer–map–consumer
route shape, so it does not see through exports; composing refinement across
a composite boundary is the composition problem of §26.

## 29. Types as objects

`objects.Constructor` is a type constructor as a content-addressed object:
name, version, arity, meaning and the references of the constructors it
refines. Its reference is its name in type terms (`Constructor.type`), so
type identifiers may contain `sha256:` constructor names, and the type
grammar admits `:` in names. `Store.put` admits an object only once every
reference it depends on is present (`_requires`): besides members and
subjects, the constructors a constructor refines, which must have equal
arity, and every constructor a primitive's contract or a composite's
exports and requirements mention, applied to exactly its arity. Textual
constructor names remain valid and are their own identity.

`packages.install` turns a constructor into one `packages.Upcast` per
refinement, with the polymorphic contract `S[?a0,…] ⇒ T[?a0,…]`, zero
declared cost and empty effects; it returns its input. Constructors can
therefore be composite members, so a package carries the types it
defines. The planner has no subtyping rule: upcasts are planned like any
adapter, which is Theorem 29.1. Each refinement step on a route uses one
level of planning fuel, so the default `fuel=8` admits chains of about
five steps between a producer and a consumer. Upcasts have no `identity`
and are never cached, since looking up a value would cost more than
returning it.

The Lean evaluator of Theorem 29.2 (`Plan.eval`) is a model: modules are
functions of their arguments' values and a map body reads only its element.
The core defines no value types. Each domain defines the constructors of its own types in its `types` module
(`nca_arithmetic.types`, `nca_boolean.types`); its modules take their
type ids from them, and its package puts them into the store as members, so
installing a package brings its types. `tests/test_layout.py` checks that
every contract of a discovered package names only constructor objects or the
core's `seq`, `pair`, `either` and `unit`. Domains share a type by stating
its constructor with identical contents, which gives it one reference: both
domains state the same `BOOLEAN`, and a test checks that their references
agree.

## 30. Selection by evidence

`evidence.attestations` owns evaluation, purity and exactness claim construction,
issuer-policy checks and stored outcome lookup. The `evidence` package retains
promotion, route bounds, execution checks and audits, and re-exports those claim
helpers. Claim construction is not proof that the reported outcomes are true.

`evidence` implements §30. `benchmark(samples)` identifies a benchmark by
the `cache.value_digest` of its samples. `evaluation(identity, bench,
outcomes, issuer)` is an `evaluation` attestation whose claim holds the
expert's identity, the benchmark and its outcomes as a string of `0` and
`1`; its subject is the stored object the identity names, the composite for
an export (`ref#index`). `outcomes` reads the outcomes that a given set of
issuers attest and refuses disagreeing ones.

`promote(modules, store, bench, issuers, alpha)` goes through the library
in order. For each contract the first expert is the incumbent; every later
expert with the same contract and a trusted evaluation is tested against it
with `router.sign_test` at `stats.family_audit_alpha(alpha, k)`, and the
accepted challenger with the smallest p-value exchanges places with the
incumbent. It returns the new library and a `Promotion` record (wins,
losses, p-value, level) per change. An exchange is a signature-preserving
renaming, so `planShallowStable_rename` gives the effect on routes:
the challenger takes the incumbent's place in each route that used it, and
nothing else changes. Promotion compares experts one contract at a time; a
deployment promoting along several contracts at once divides `alpha` among
them itself.

## 31. Composing uncertainty

`packages.charge(plan, length, unit)` sums `unit` over a route's
invocations: map bodies once per element at `length`, slot fillings by
their declared calls. Exports declare their cost with it; with
`strict=True`, a slot whose expert declares no call counts is an error
instead of being counted once. `evidence.route_risk(plan, rate, length)`
is `charge` with each expert's failure rate as unit (§31.2): an export is
charged its own route, its `Requirement`s nothing (their fillings are
charged through the outer slots), and an `Upcast` nothing. It returns
`None` when an invoked expert has no rate or a slot's call count is
undeclared. `evidence.error_bound` gives a rate as the Clopper–Pearson
upper bound of an evaluation's failures; dividing the confidence budget
among the route's experts, as in the diary experiment, is the caller's
choice. The result is a bound on an expected count and may exceed 1, in
which case it says nothing; it is a probability bound only for in-situ
rates and a `length` that bounds every mapped sequence (Theorems 31.1 and
31.2, `risk_le_charges`).

`optimize.plan_pareto` accepts, besides a mapping from manifest refs to
rates (absent meaning 0, as before), a function from modules to rates in
which `None` leaves the module out (§31.4). `evidence.rates(bounds, length)`
is such a function: rates by identity for experts, `route_risk` of its own
route for an export, 0 for upcasts and requirements. With it the Pareto
planner's error objective is the charge of §31.2 and `cheapest_within(δ)`
plans by cost under a risk target, through packages, with the exactness of
`NCA.planPareto_sound`, `planPareto_cover` and `planPareto_within`.

`evidence.route_bound(plan, store, benches, issuers, beta, length)`
implements §31.5: experts with an accepted `exact` attestation
(`evidence.exact`) are charged 0, and `beta` is split among the others in
proportion to their invocation counts in the route (computed with
`route_risk` and an indicator rate), each bound coming from that expert's
in-situ benchmark in `benches`.

`route_risk(..., relevant=True)` implements §31.6: it propagates demand
from the answer (`None`) through each expert's `decides` rule, or its
`demand` rule, charges a map's body at each element's demand over `length`
elements and its source in full, and charges nothing for an invocation
whose output has empty demand. Exports' routes and slot fillings are
charged in full. An installed `LazyExpert` forwards `demand` but not
`decides`, so packaged experts are charged at their read demand, which is
sound but coarser.

## 32. Trust

`objects.Attestation` has an optional `signature` over `unsigned()`, its
data without the signature; the signature is stored and is part of the
reference. `evidence.trust` keeps a registry of verifiers by scheme (`register`),
so the core depends on no scheme; `ed25519` is registered when the optional
`cryptography` package is installed (the `trust` extra), and
`Ed25519Signer` signs attestations as issuer `ed25519:<public key hex>`.
`verified` checks an attestation's signature against its issuer;
`Trust(keys).accepts` also requires the issuer to be trusted. Stores keep
unverified attestations: storing a claim asserts nothing, and acceptance is
decided where evidence is read. Every `issuers` parameter of `evidence`
takes a `Trust` or, as before, a collection of plain issuer names, which
nothing authenticates and which are meant for local tests and private
deployments.

`ResultCache(check_rate=q, seed=…, refuted=…)` checks purity where it is
read: `sample()` picks a hit with probability q, the runtime then invokes
the expert as on a miss (charging budget) and `check` compares the digests
of the stored and fresh outputs. A mismatch adds the expert's identity to
`refuted`, drops its entries and stops it being cached; `checks` counts
each expert's checks and mismatches, skipping outputs without a canonical
encoding. `evidence.purity` states those counts as a `purity` attestation,
and `evidence.refuted` reports whether an accepted one shows a mismatch, so
a deployment can start a cache with `refuted` filled from others' evidence.

## 33. Per-input risk on any route

Internal-accounting declarations now survive lazy and artifact boundaries
(§33.4). `Primitive.accounts_inside` is content-bound, omitted when false to
preserve ordinary legacy encodings, and copied by `objects.primitive` and
`packages.install` into a read-only `LazyExpert` property. Primitive factories
and direct lazy loaders reject non-Boolean or mismatched declarations before
the implementation is admitted. An internally accounted legacy artifact must
be reissued with that declaration rather than silently losing its protocol.
Tests cover save/reopen, scalar and compiled replay after value-cache warming,
zero and positive reports, malformed declarations, both mismatch directions
and all 32 cache/ledger/accounting/purity/identity Boolean cases without loading.
`inside_ledger_no_cache` and `inside_replay_charge` prove the conditional cache
gate/account model; `erased_accounting_underreports` demonstrates its failure
when the marker is erased. They do not verify full runtime execution or report
calibration. The synthetic benchmark reproduces the former erased boundary as
a reference only. Cooperative reporting, fixed implementations, complete effect
attribution and failure atomicity remain separate obligations.

Ledger reports now require finite nonnegative supported real scalars (§33.5).
Boolean, non-real, negative and nonfinite reports fail before their contribution
is recorded; missing reports retain the existing uncertified behavior. Scalar
conversion rounds upward when needed, including exact rational inputs. Initial
charges are validated too; an infinite initial or overflowed accumulator is an
exhausted upper bound. Positive finite report bounds above one are not clipped.
`native.stats.nonnegative_add_upper` uses strict-FP FastTwoSum residual checking
and advances only downward-rounded sums. The Python fallback follows the same
rule, including when an older optional stats extension lacks the new export.
`ledger_fold_upper` proves the real fold invariant assuming a non-understating
adder and nonnegative inputs. It does not prove compiled IEEE behavior; tests
compare native/fallback additions with exact rational sums across subnormals,
normal/subnormal boundaries, random finite bit patterns and overflow, then exercise
actual interpreted/compiled budget gates. The kernel/IEEE assumptions, truthful
calibration, accumulated overconservatism and transaction safety remain open
boundaries. These checks prevent malformed or rounded-down charges, not false
but numerically well-formed reports from dishonest experts.

`runtime.ledger` owns invocation records, risk charges and the single context
variable shared by interpreted and compiled execution. The `runtime` package
re-exports these definitions; nested execution does not create another ledger
context merely by importing an implementation module.

`execute(..., ledger=RiskLedger(exact))` keeps the per-input charge of
§33. Alongside the read demand the runtime propagates a decision demand
from the answer through each expert's `decides` rule, or its `demand`
rule; each invocation whose decision demand is not empty adds its
`risk(output, *inputs)` report, adds nothing if `exact(module)` holds, and is
otherwise recorded in `uncertified`. The ledger is also the current one in
a context variable, so an `Export` (`accounts_inside`) runs its route on
it and is not served from the result cache while a ledger is kept; its
`Requirement`s and `Upcast`s report 0, and installed experts forward their
implementation's `risk`. `ladder.Calibrated(rung)` is an expert that
outputs a rung's calibrated distribution and reports `1 − max p`.
`evidence.answer_within(plan, inputs, δ, exact)` answers only when the
ledger is certified and at most `δ`, and `evidence.exact_by(store,
issuers)` is an `exact` predicate from accepted exactness attestations.

The ledger's `entries` record each charged invocation's expert, input
values and report. `modules.refinement.Escalating(rungs, module_id)` holds
reporting substitutes with one contract, cheapest first, answers each
distinct input (by `value_digest`) at its level and reports the risk of
the rung at that input's level; `invoke_batch` calls each rung once for
the rows at its level; `refine(*values)` raises that input's level. Levels persist
across calls, so an input once found hard starts higher next time.
`evidence.refine_within` re-executes the route, each time raising the
charged invocation with the largest report whose expert can climb, until
the ledger is within `δ` (answer) or nothing can climb (abstain). Every
round re-executes the whole route; experts other than the escalating ones
are re-invoked unless the result cache serves them.

## 34. Compiled routes

`compile.compile_route(plan, available, demand)` checks that the plan has
no slots (else `NotCompilable`) and returns a function from a batch of
rows, one value per available type, to the answers. Each node is
evaluated for the whole batch: `Given` is resolved per row as in the
runtime; an `Apply` evaluates each argument only for the rows whose
declared demand on it is not empty (the others pass `None`), then calls
the expert's `invoke_batch(*columns)` once, or `invoke` per row if it has
none; a `Map` flattens the elements of every row, with their element
demands, evaluates the body on that one batch and regroups. An output
that is a `Request` or generator raises `NotCompilable`. The compiled
function takes an optional `cache` and an optional list of `ledgers`, one
per row: it propagates decision demand, charges each row through
`runtime.charge` and keys the cache through `runtime.result_key`, the
functions `execute` uses, and invokes the misses of a batch once per
distinct key. An expert with `accounts_inside` is invoked per row with that
row's ledger current. A compiled route records no messages and spends no
budget; `execute` remains the reference semantics. `LazyExpert`
forwards `invoke_batch`, falling back to per-row invocation, and the
arithmetic digit and operator readers batch their forward pass.

`evidence.refine_batch(plan, available, rows, δ, exact, cache)` is
`refine_within` for a batch on the compiled route: each round evaluates
the undecided rows together with fresh ledgers, answers or abstains on
each, and climbs the riskiest climbable entry of every row over `δ`,
making a climb that several rows share once per round. A `cache` serves
the pure invocations a climb did not change.

## 35. Calibration audits

`evidence.audit(reports, failures, independent)` compares an expert's
reports on labeled invocations with its failures and returns an `Audit`
whose `p_value` bounds the chance of that many failures under calibrated
reports: `stats.poisson_binomial_upper_bound` when failures are
independent (Theorem 35.2), otherwise the total report over the failures
(Theorem 35.1). `Audit.refutes(alpha)` tests at level `alpha`.
`evidence.recalibrate(rung, values, labels, subject, issuer, alpha)` fits
a fresh `ladder.Rung` for the rung's expert on the first half of the
labeled values, audits its `Calibrated` reports on the second half, and
returns a calibration attestation about `subject` (read back with
`ladder.attested`) unless that audit refutes the refit. Which invocations
to audit, and how they are labeled, is the caller's choice.

## 36. Acquiring experts

`evidence.hotspots(ledgers)` sums each charged expert's reports over a
batch of ledgers, largest first. `evidence.acquire(incumbent, train,
values, labels, correct, alpha)` calls the domain's `train` on the first
half of the labeled values, requires the challenger to have the
incumbent's contract, scores both on the second half with `correct`, and
runs `promote`'s paired sign test on those outcomes. The `Acquisition`
holds the challenger, both outcome sequences (to attest with `evaluation`
when the experts are stored objects) and the `Promotion`, if any. The
challenger is installed by the caller, after calibrating it with
`recalibrate` on the evaluation half. In the arithmetic domain,
`digit_recognizer.fine_tuned` trains a copy of a network further on
labeled glyphs, and `SymbolRecognizer.fine_tuned` wraps it as a trainer.

## 37. Calibration by groups of inputs

`evidence.grouped.fit_groups(module, group, values, labels)` routes labeled values
by the grouping function `group` and fits one `ladder.Rung` per group
present. `evidence.grouped.Grouped(module, group, rungs)` is an expert with the
module's manifest that reads each input through its group's rung, as
`ladder.Calibrated` does, and reports that rung's risk; an input whose
group has no rung is read uncalibrated and reports `None`. Groups are
audited separately with `evidence.audit`. The grouping is the caller's:
any function of the input, such as a classifier trained to tell audited
inputs from calibration inputs.

## 38. In-situ audits

`runtime.charge` also appends each charged invocation to
`RiskLedger.invocations` as a `runtime.Invocation(expert, values,
output, report)`, where `expert` is the module's `answering(*values)` if
it has one (an `Escalating` expert's rung at the input's current level)
and the module otherwise; both execution paths charge through it.
`evidence.sample_invocations(ledgers, rate, seed, select)` keeps each
invocation of a selected expert with probability `rate`, by seeded coins;
callers pass final ledgers, such as those `refine_batch` returns, so the
sample is of the invocations answers relied on.
`evidence.audit_invocations(invocations, labels, correct)` audits them
once labeled, and their `values` feed `recalibrate` or `fit_groups`.

## 39. Answering over alternatives

A fork is any expert with `candidates(*inputs) -> list[(output, q)]`.
`evidence.alternatives.answer_over_alternatives(plan, available, rows, δ, exact,
cache)` requires exactly one fork outside map bodies. It evaluates the
fork's argument subplans compiled, with one ledger per row (charge `c₀`),
expands each row into one row per candidate, and evaluates the rest of
the route compiled, with the fork replaced by a `Given` of an extra
available input and one ledger per candidate (charge `c`, 1 if
uncertified). Candidates are grouped by their answer's `value_digest`;
the answer with the largest support `Σ q (1 − c)` is returned in a
`Choice` with bound `c₀ + 1 − support` if that is at most `δ`.
`evidence.alternatives.Tabled(module, table, stratum)` makes a fork of an expert
with ranked `alternatives`, giving candidate `k` the bound `table[(s, k)]`
for `s = stratum(*inputs)`, and `evidence.alternatives.fit_table` estimates the
table as per-cell Clopper–Pearson lower bounds at level `β` over the
cells. The arithmetic segmenter's first segmentation cuts each run into
`round(width / PITCH)` glyphs at its faintest columns
(`segmenter.pitched`), separating touching glyphs; its further
`alternatives` are the uncut runs, merges and single splits, without
repeats, and `segmenter.segmentations` gives their column spans.

## 40. Audits by agreement

`evidence.cross_audit(invocations, reference, same, independent)` audits
sampled invocations without labels: it requires `reference` to have the
audited expert's contract and to report risk, invokes it on each
invocation's inputs, counts a failure where `same(output, reference
output)` is false, and runs `audit` with reports `min(1, report +
reference report)`. A refutation means the expert, the reference, or
both are miscalibrated on the sampled inputs.

## 41. Verification

A verifier is any callable `verify(*inputs, answer) -> bool`.
`evidence.verification.answer_verified(plan, available, rows, δ, verify, miss,
false_reject, exact, cache)` runs the compiled route with one ledger per
row, answers nothing for a rejected answer, and otherwise returns a
`Choice` with `evidence.verification.verified_bound(charge, miss, false_reject)`,
the bound of Theorem 41.1 (0 for `miss == 0`, 1 for a charge of 1 or an
uncertified ledger), answering if it is at most `δ`.
`evidence.verification.verifier_rates(accepted, correct, β)` gives Clopper–Pearson
upper bounds on the miss and false-rejection rates at level `β / 2`
each.
The arithmetic domain's `components.ComponentSegmenter` segments by
8-connected components of ink, merging components whose column spans
mostly overlap and cropping each glyph by its own pixels; it has the
segmenter's contract and serves routes meant to fail differently.

## Proposal search for new decompositions (§36.3)

`discovery.discover` gives a proposer only the training half of labeled input
rows. It freezes proposals (experts plus optional new constructor objects),
checks their external contracts, and tests each on the held-out half at
`alpha / count`. The accepted proposal with the lowest p-value is returned
without installation or risk claims. Internal compositions are unrestricted.
`NCA.proposal_budget_le` in `Reliability/Acquire.lean` proves the budget-sum
step; test validity and split independence remain premises of `split_test_le`.

`discovery.discover_packages` lets the training callback store learned primitive
or composite objects and return references. It freezes the references, installs
them into a candidate scope, and tests every export matching the incumbent's
contract. Each matching export counts toward the family budget. The chosen
`Proposal.package` and expert identity identify what to reinstall from a saved
store; no active library or name is changed. Constructors remain in the store,
and external weights remain the loader's responsibility. Selection evidence is
not persisted by this API. `reloaded_outcomes_eq` in `Reliability/Acquire.lean`
proves Proposition 36.3 conditional on executable equivalence; store/reload
behavior for a trained two-stage package is regression-tested.

`discovery.propose_decoders` (§36.4) learns a modal lookup decoder for each
supplied feature expert and returns `Decoded` proposals. It derives decoder
contracts from feature output and incumbent output types. Inputs, slots and
relevance must match the incumbent; feature call counts and effects are
preserved, with the explicitly supplied decoder cost added. Hashable keys and
labels use Python equality; training-order ties and unseen-key fallback are
deterministic. These proposals have no persistent object identity or risk
certificate. `modal_decoder_optimal` proves empirical optimality conditional
on per-key maximal counts. Tests exhaustively compare a small fitted table
with all alternatives and exercise held-out selection, unseen keys and slots.

`discovery.joint_features` (§36.5) enumerates feature subsets in increasing size
and input order, bounded explicitly by `max_size` and `limit`. `JointFeature`
constructs left-associated structural product interfaces, calling both components
on the same inputs and fillings in order. Declared feature costs plus `pair_cost`
add, as do known affine slot calls; expected counts fall back to worst-case
counts per component. Missing counts or effects remain unknown. Feeding these
features to `propose_decoders` searches decompositions not supplied as complete
interfaces. `joint_decoder_simulates` proves exact prediction preservation for
a decoder projecting one component; held-out improvement remains empirical.

`discovery.train_tree` (§36.6) learns a breadth-first conditional feature tree
with an explicit total-node budget, scoring categorical splits by child modal
successes. Zero-gain splits are allowed to expose interactions; a feature is
removed from the remaining choices on each path. `FeatureTree.invoke` evaluates
only visited nodes and falls back at unseen keys. Manifest costs and known slot
calls conservatively sum features used anywhere in the tree, adding the supplied
whole-tree overhead bound; effects are their union or unknown. Features with
negative/nonfinite costs or worst-case call counts are rejected. Training
precomputes feature keys and assumes stable feature behavior. The tree is an
in-memory proposal, without a persisted identity or risk certificate.
`modal_refinement_le` proves the finite modal-refinement inequality conditional
on per-child maximal counts. Tests cover conditional calls, interactions,
node limits, unseen keys, higher-order contracts and conservative metadata.

`train_tree(lookahead=..., lookahead_budget=...)` (§36.7) ranks splits by
projected modal successes, then projected declared feature cost, then feature
order. The default one-step horizon now also prefers lower feature cost in
accuracy ties. Deeper horizons require an explicit state-expansion budget.
Projection memoizes subset/remaining-feature/horizon states, stops at a modal
leaf when work is exhausted, and reports `projection_states` and
`projection_exhausted` on the returned tree. These are search diagnostics, not
risk claims. Projection does not solve global allocation of the final node
budget. `lookahead_score_mono` proves only complete attainable-score set
inclusion; Python search correctness, exhaustion, costs and actual conditional
calls are regression-tested. Accuracy-only `discover` does not promote an
equally accurate candidate solely for saving execution cost.

`discovery.factor_tree` (§36.8) derives a `Constructor` from a trained tree's
node label counts, modal tie choices and target type. Records are canonicalized,
deduplicated and sorted to assign stable codes. `TreeStateEncoder` returns the
reached node's code; a separate decoder returns its chosen label. The resulting
`Proposal` includes the generated constructor and an ordinary `Decoded` expert.
Every stopping node is represented, including internal fallback states. Labels
are currently JSON scalars; unsupported labels fail explicitly, and no repr-based
identity is used. Counts are empirical records, not calibrated probabilities.
`state_factorization_eq` proves prediction preservation conditional on decoding
each node code correctly. Tests verify prediction equality, stable type identity,
distinct count profiles, type-object store round trips and planner composition.
The tree/features must remain fixed; executable persistence is not implemented
by this factory. Encoding and decoding costs are explicit caller declarations.

`Primitive.dependencies` (§28.7) records ordered executable scope references.
The canonical encoding omits empty dependencies, keeping old primitive references
unchanged. Store admission checks dependency presence, executable kind and
effect coverage; `walk` follows all declared object dependencies. `install`
resolves each dependency scope before the factory runs, shares primitive lazy
wrappers, and passes the scopes as the factory's reserved `dependencies` keyword.
Factories must retain rather than invoke them while loading. Lazy prerequisites
conservatively include all primitives reachable through the declared scopes;
`route_experts` includes this closure so preparing a lazy route checks and pins
its required declared bytes before loading. Existing composite visibility is
unchanged. `dependency_rank_acyclic` proves acyclicity from strictly decreasing
admission ranks; Python admission, shared loads, effect checks and byte budgets
are regression-tested. Store reload also checks that decoded contents retain
the digest of the saved object, including optional-field canonicalization.

`discovery.decoder_object` (§36.9) snapshots a learned finite head's contract,
scalar table, fallback and cost into a `Primitive` interpreted by `_load_decoder`.
Canonical key ordering makes identity independent of table insertion order.
Unsupported key/label values fail explicitly. Constructor dependencies are
admitted by the ordinary store, and loading uses the ordinary lazy lifecycle.
`state_factorization_eq` supplies the conditional prediction-preservation
argument; scalar codec fidelity, snapshot behavior and reload are tested.
This persists model data for a generic runtime, not a built-in expert catalog.

`tree_objects.tree_object` (§36.10) snapshots a learned tree's ordered node
records and explicit dependency/export bindings. Bindings must match trained
feature identities and manifests. `load_tree` reconstructs the generic model
without invoking feature implementations; backward edges and invalid export
positions are rejected. Interpreter residency ids derive from model contents
and dependency references. Scalar keys/labels are supported; the existing
conditional state-factorization and ranked-dependency proofs supply the abstract
preservation/acyclicity arguments, while codec behavior is regression-tested.

`value_codec` (§36.11) preserves finite JSON scalars and recursively tagged
tuples in learned decoder and tree artifacts. Scalar wire data stays unchanged;
unknown records, unsupported values and nonfinite numbers fail explicitly.
`pair_codec_roundtrip` proves the componentwise pair special case conditional
on faithful component codecs; Python structural encoding is regression-tested.
Joint feature keys and tuple labels can now be persisted through normal loading.
The empirical-state constructor factory still requires scalar labels.

`discovery.propose_corrections` (§36.12) groups training invocations by supplied
feature keys, fitting constant-label corrections only when modal target counts
strictly exceed incumbent successes in that region. Empty corrections are
omitted. `Corrected` consults its feature and otherwise delegates to the unchanged
incumbent, including unseen keys. Contracts, effects and conservative slot/cost
bounds are composed generically. `residual_successes_le` proves training-count
dominance; held-out improvement is evaluated by the existing discovery split.
These are in-memory learned proposals, without persisted identity or calibration.

`learning.numeric.propose_partition` (§36.13) learns an observed-value boundary
and modal decoder from training data over a supplied finite-float measurement.
`PartitionEncoder` generates a constructor describing the source type, boundary
and code convention. A sorted sweep updates left/right label counts without
splitting equal observations; modal scans depend on label cardinality. The
result is an ordinary encoder/head proposal, with independent selection through
`discover`. `threshold_score_le` proves finite-maximum dominance conditional on
candidate membership; the Python sweep is checked against exhaustive boundaries.
This is threshold-family representation learning, not arbitrary raw-feature
invention. The learned encoder is currently an in-memory model.

`learning.numeric.propose_regions` (§36.14) greedily refines the best impure
interval using the shared `_best_split` sweep, up to an explicit region budget.
`RegionsEncoder` derives a constructor from sorted learned boundaries and uses
binary search for region codes. Pure or constant-valued intervals stop refining.
`modal_refinement_le` supplies the nonnegative local training-gain inequality;
the greedy search policy is not formally verified or globally optimal. Tests
cover region budgets, training-score monotonicity and duplicate observations.

`train_tree(refine=...)` (§36.15) optionally asks a supplied trainer for new
features on each unresolved node's training subset. Contracts and cost/call
bounds are validated as for initial features. Acquired features and their
cached keys are scoped to that subtree; already queued siblings cannot see
them. Pure nodes or insufficient remaining node budget skip acquisition.
Projection uses only fitted features. `split_test_le` supplies the conditional
training/evaluation argument; callback isolation and scoping are tested.
This supports local learned interfaces without registering any task in core.

`numeric_objects.encoder_object` (§36.16) retains learned threshold/region
parameters with a verified measurement scope binding and a model-derived
residency identifier. Generated constructors must precede artifact admission.
`store_numeric_tree` retains acquired numeric encoders, reconstructs their lazy
modules, and snapshots the tree against those artifact bindings. Existing
content-identified features use the same generic `packages.resolve_binding`
check as `tree_objects`. The factories reconstruct contracts, costs and effects
from the measurement and parameters; ordinary primitive loading checks metadata.
`state_factorization_eq` supplies the conditional executable-equivalence
composition argument. Parameter fidelity and complete acquired-tree reload are
regression-tested; external feature code/weight fidelity remains an assumption.

`learning.interfaces.propose_adapter` (§36.17) pairs source/teacher outputs on
training rows, fits a categorical `source-type → teacher-type` decoder, and
proposes source/adapter/consumer composition for the external contract. Exact
types remain distinct. Selection uses existing independent end-to-end outcomes;
the teacher is absent from inference. `Decoded` checks unary-head composition
and unions effects, while `fit_decoder` shares modal fitting across learners.
`adapter_composition_eq` proves consumer agreement conditional on perfect
alignment; finite-data alignment is not a universal equivalence proof.
New `decoder_object` artifacts derive residency ids from model contents; their
loader defaults preserve legacy saved-head compatibility. Coexistence, effects,
typed planner composition and absence of held-out teacher calls are tested.

`propose_adapter(fit=...)` (§36.18) accepts a fitter obeying `AdapterFitter`;
its returned contract must exactly match the requested bridge. The default
categorical fitter is unchanged. `affine_learning.fit_affine` is a continuous
scalar instance using centered least squares, rejecting unrepresentable
statistics/predictions and using a mean target for constant inputs. The generic
runtime and `affine_object` store only parameters and contracts, without a
teacher implementation. `affine_slope_optimal` proves the ideal real quadratic
minimum from a normal equation, not Python numerical fidelity or global
alignment. Tests cover fresh inputs, persistence, numeric limits and contracts.

`vector_learning.fit_vector_affine` (§36.19) implements the same fitter protocol
for finite tuple vectors of independently inferred input/output dimensions.
`vector_affine_object` stores the fitted matrix and nominal contract without
training-teacher dependencies. NumPy's native least-squares backend supplies a
minimum-norm solution for rank-deficient data; independent task selection is
still required. `vector_adapter_composition_eq` proves conditional downstream
agreement from exact coordinatewise alignment, not solver correctness.

`learning.projections.propose_projections` (§36.20) learns budgeted centroid-pair
projection directions from supplied tuple-vector measurements and opaque training
targets. Each direction feeds the generic scalar partition learner, proposing
two generated constructors plus an encoder/head route for independent selection.
The current proposals are in-memory; no persistence or unrestricted nonlinear
feature search is implied. `projection_prototype_gap` proves the finite-real
prototype separation identity, with no floating-point or generalization claim.

`PolynomialEncoder` and `propose_polynomial_partitions` (§36.21) extend this
search to caller-selected degrees. A combinatorial term count is checked before
basis enumeration; each lift has a generated constructor and delegates learning
to the same projection/partition mechanism. The current artifacts are in-memory.
`symmetric_interaction_gap` is an expressivity witness for a nonlinear coordinate
with coincident original centroids, not an accuracy or extrapolation guarantee.

Numeric partition/region fitting and projection acquisition accept an optional
`place_boundary(lower, upper)` policy (§36.22). The result must remain within
`(lower, upper]`, preserving training splits; only the fitted float is retained
by existing encoder artifacts. `midpoint_boundary` is an opt-in policy with an
upper-edge fallback for float rounding. `gap_boundary_preserves` proves the real
comparison invariant and `midpoint_inside_gap` the exact real midpoint bound.

Projection acquisition's `reuse_observations=True` (§36.23) snapshots finite
training tuples per row and uses the shared `_partition_from_ordered` fitter
across candidate directions. Reuse requires known empty effects, no slots and
caller-assumed determinism/stability. Proposed routes retain original measurement
modules and inference metadata; no training cache enters runtime or artifacts.
`training_projection_fusion` proves the pure list identity, not executable purity.

`native/polynomial.elisa` (§36.24) evaluates the lift's packed coordinate-index
terms in multiplication order. `PolynomialEncoder` keeps the Python interpreter
as its fallback and shares input/output validation across paths. Offsets and
indices are checked before native buffer access. `ordered_product_fold` proves
the real fold/product identity; bitwise float, FFI and failure correspondence
are regression-tested rather than formally verified. Build with the ordinary
native builder; `NCA_NATIVE=0` selects the reference path.

`numeric_objects.store_encoder_chain` (§36.25) retains fitted polynomial,
projection and scalar-partition stages as separate parameter artifacts linked
to the verified original measurement reference/export. It reconstructs each
predecessor before rebinding the next stage without mutating trained objects.
`store_numeric_tree` uses the same chain serializer; ordinary composites can
export the final encoder with a separately stored decoder. Installs remain lazy.
`restored_chain_eq` proves conditional composition fidelity for endomorphism
lists, not executable factories or heterogeneous typed serialization.

`learning.regional.propose_regional_experts` (§36.26) spends an explicit region
budget where incumbent training errors concentrate. A supplied proposer trains
arbitrary contract-preserving experts on complete regional training subsets.
`RegionalExpert` gates the specialist and delegates other inputs to the incumbent;
constructor declarations propagate, while inference costs, slots and effects
include all possible stages conservatively. These proposals remain in memory.
`regional_preserves_complement` proves pure-function output preservation outside
the selected region, not effectful-execution or generalization guarantees.

`propose_failure_partitions` (§36.27) fits `fit_partition_encoder` to auxiliary
incumbent failure indicators, then delegates regional task training to
`propose_regional_experts`. The numeric fitter returns only a generated routing
encoder, so auxiliary labels never masquerade as the task's output type.
Measurement and region budgets are explicit; constant error signals yield no
proposal from this family. `failure_partition_covers` proves training coverage
conditional on exact alignment, without asserting learned or held-out coverage.

`fit_regions_encoder` (§36.28) shares interval-refinement parameters with the
existing task-head fitter. `propose_failure_partitions(routing_regions=...)`
can acquire multi-interval routers; binary defaults preserve the original path.
An optional pure `tie_break` scores read-only label histograms only after modal
accuracy. `purity_tiebreak` supplies weighted child purity without label semantics.
`binary_modal_split_le` proves the binary empirical split bound, not greedy
lookahead optimality or executable/native verification.

`regional_objects.regional_object` (§36.29) stores a structural routing key,
explicit dispatch overhead and three verified dependency bindings. Store fitted
components first, rebuild the regional runtime from their installed versions,
then snapshot its wiring. The factory checks scope positions and reconstructs
contracts/costs/effects; the resulting identity includes key and dependencies.
`discover_packages` can select these stored experts directly. Installation stays
lazy. `regional_reloaded_eq` proves conditional pure-function agreement with
unchanged key, not key-codec, factory, effectful-execution or provenance fidelity.

`RegionalPolicy` (§36.30) generalizes single-region dispatch to a mapping of keys
to experts, evaluating its feature once. `RegionalExpert` preserves the single-key
interface over that runtime. Acquisition's opt-in `max_combinations` adds a
bounded Cartesian prefix across nonempty selected regional families, alongside
single candidates. `policy_object` retains ordered keys and verified dependency
bindings; existing single-key artifacts keep their factory/data format.
`regional_policy_missing` proves pure missing-key fallback, not empirical gains
or exhaustive combination search. Conservative metadata includes every branch.

Regional acquisition and composition (§§36.26–36.55) are described in the
[regional acquisition chapter](theory/evidence/36-regional-acquisition.md).
Interface alignment (§§36.56–36.58) continues in the
[alignment acquisition chapter](theory/evidence/36-interface-acquisition.md).
`_ranked_combinations` enumerates a bounded best-first Cartesian frontier after
regional alternatives are scored on training rows. Ranking maximizes summed
training successes, then minimizes summed declared cost, with deterministic
position ties. The frontier avoids materializing the product; upfront scoring
still visits all alternatives on their regional samples. `regional_training_maxima`
proves the conditional summed-score bound, not heap correctness or generalization.

Combination search includes an incumbent fallback per region (§36.32), scored
from existing training outcomes with zero incremental wiring cost. Fallback
keys are omitted from `RegionalPolicy`, so existing parameter artifacts retain
partial compositions directly. Baseline/single assignments are skipped with a
finite pop allowance before emitting bounded joint candidates. `regional_fallback_score`
proves the one-alternative empirical maximum identity, not generalization or
best-first enumeration. Omitted experts contribute no policy dependency or cost.

The optional `RegionalRefiner` hook (§36.33) receives the best regional training
seed only when errors remain. `max_refinements` bounds calls per regional search
(per measurement in failure-partition search); callbacks own internal budgets.
Direct alternatives remain available, and seed constructor declarations propagate
into refined proposals. Existing regional runtimes support nested results.
`nested_refinement_scope` proves the pure shared-fallback intersection identity,
not automatic discovery of a refiner or held-out improvement.

`acquisition_objects.store_acquired_model` (§36.34) traverses supported learned
runtimes in iterative postorder, memoizes shared objects and reconstructs parent
wiring from retained children. Regional policies, compositions, numeric encoders
and fitted categorical/scalar/vector heads use parameter artifacts. Other types
(including unknown subclasses) remain opaque and require verified original
bindings. Per-node sizes are caller declarations. `load_composition` reifies
fixed feature/head wiring; `decoded_reloaded_eq` proves conditional pure
composition fidelity, not executable serialization or mutable-state equivalence.


`learning.regional.propose_failure_partitions` (§36.35) optionally accepts a
training-only `routing_signal(row, prediction, target)`. Its opaque labels fit
the router, while specialists receive original targets. The default remains
binary failure routing; no-error samples produce no proposals. The callback is
not part of retained inference graphs. `auxiliary_feedback_separation` proves
only the ordered two-observation threshold identity.

`router.sign_probability` (§36.36) retains paired binomial tails as exact
fractions. `sign_test` compares before float conversion, and `discover` uses
exact tails for multiplicity-adjusted acceptance and ranking. Reported trial
p-values remain floats and may be zero. `reciprocal_evidence_order` proves only
the positive-denominator reciprocal ordering used by the all-win special case.

`propose_failure_partitions` (§36.37) can screen an explicit bounded measurement
prefix before specialist acquisition. Fitted routers rank by training modal
signal accuracy, with stable ties; only `max_measurements` receive specialist
training. `max_measurement_candidates=None` preserves prefix allocation.
`router_score_selection` proves the two-score comparison special case only.

`learning.projections.fit_projection_encoders` (§36.38) exposes the same
centroid-pair fitting used by `propose_projections` without a task decoder.
Auxiliary categories train directions; regional trainers keep original targets.
Each returned encoder exposes its constructor for proposal propagation and
existing numeric graph retention. `feedback_group_invariance` proves only
filter equality when opaque category membership is unchanged.

`learning.regional.MeasurementProposer` (§36.39) receives training rows, opaque
feedback and remaining candidate slots. `propose_failure_partitions` appends a
bounded prefix of its measurement proposals, validates external signatures and
propagates their constructors through router screening and specialist acquisition.
It never retains the training callback. `measurement_prefix_bound` proves only
the retained-list length bound, not callback computation or model correctness.

`learning.interfaces.propose_heads` (§36.40) derives a unary head contract per
candidate representation, observes training inputs and requests a bounded head
family through `HeadProposer`. It validates exact head contracts and emits fixed
`Decoded` compositions with feature/head constructors. Existing graph retention
supports known heads; unknown experts remain opaque bindings.
`head_fiber_consistency` proves only the necessary equal-feature target condition.

`learning.projections.fit_regression_projection` (§36.41) fits centered vector
observations against continuous training feedback, returning an ordinary
`ProjectionEncoder` or no candidate for an exactly zero direction. It retains
no teacher or targets. Existing head/measurement acquisition and numeric graph
retention can consume its generated interface. `orthogonal_residual_square`
proves only the scalar orthogonal residual identity, not the NumPy solver.

`fit_polynomial_regression_features` (§36.42) grows complete polynomial lifts
while fitted projection/offset residuals exceed a supplied training tolerance.
It emits feature proposals with lift/projection constructors, stops before term
budget overflow, and leaves head fitting and whole-task selection separate.
`nested_fit_comparison` proves only conditional optimizer comparison, not a
floating-point or maximum-residual monotonicity result.

Polynomial regression growth's optional `reuse_observations` (§36.43) captures
pure deterministic source outputs once, using `PolynomialEncoder.encode` and
shared `_regression_direction` fitting for each degree. Fitted models retain
original dependencies, not snapshots. `training_snapshot_map_eq` proves only
conditional mapped-observation equality; runtime equivalence is regression tested.

`learning.interfaces.FeatureRefiner` (§36.44) extends `propose_heads` with
training-error-driven representation proposals. A bounded queue shares one total
feature budget; a separate call budget limits refinement. Best training heads
use success/cost/stable-order ranking, and no-head families can bootstrap with a
None seed. `feature_admission_bound` proves the natural-number admission bound,
not callback runtime, training fitness or generalization.

`learning.interfaces.propose_joint_refinements` (§36.45) screens bounded companion
features by empirical modal label improvement, emitting ranked `JointFeature`
proposals with both constructor sets. It can implement a `FeatureRefiner` without
specializing generic search to a task. `joint_key_refines_seed` proves the key
partition implication; `binary_modal_split_le` supplies a restricted score result.
Structural products are retained by the acquired-model graph path (§36.46).

`acquisition_objects.load_joint` (§36.46) reconstructs exact ordered child exports
with explicit `JointFeature.pair_cost`. The graph visitor recognizes the exact
runtime type, preserving sharing and opaque external bindings. `joint_reloaded_eq`
proves conditional ordered-pair functional equality, not executable serialization.

`propose_joint_refinements` (§36.47) can score bounded companion subsets across
non-improving intermediate pairs. Companion/depth/scored-subset/output budgets
are explicit; original features are observed once per row and their products
remain ordinary persistable `JointFeature` graphs. `modal_refinement_dominates`
proves the conditional finite child-score comparison, not search completeness.

`learning.interfaces.fit_categorical_partition` (§36.48) learns a key-to-code
`Decoder` inside a `Decoded` feature, returning its generated constructor. It
can feed `propose_heads` and existing graph retention without a new runtime.
`grouped_modal_dominates` proves the finite summed-count condition only, not
executable fitting, category-renaming invariance or cross-task sufficiency.

`learning.projections.fit_prototype_encoder` (§36.49) fits category centroids as a
generated vector partition. `PrototypeEncoder` uses finite Euclidean distances
and stable first-center ties, without retaining categories. The numeric encoder
factories and acquired-model graph visitor retain its parameters and constructor.
`prototype_left_of_midpoint` proves only the one-dimensional two-center case.

`fit_prototype_encoder` (§36.50) optionally fits bounded per-category multiple
centers through deterministic farthest-first seeds and Lloyd updates. Total
center budgets fail explicitly; `PrototypeEncoder` and its factory format remain
unchanged. `two_point_mean_minimizes` proves only the two-scalar update case.

`native/prototypes.elisa` (§36.51) accelerates interval-separated nearest-center
inference over packed fitted centers. `PrototypeEncoder` falls back to existing
`_prototype_distances` for uncertain/overflow/empty-dimensional cases. Native
and fallback assignments are regression-tested; the float enclosure assumptions
are not formally verified. `prototype_interval_choice` proves only abstract
interval ordering. CPython's reference uses its shared vector norm implementation
([source](https://github.com/python/cpython/blob/3.12/Modules/mathmodule.c));
platform/compiler/libm fidelity remains an assumption.

`learning.projections.fit_prototype_features` (§36.52) grows per-category prototype
allowances while modal training errors remain above a supplied budget. Complete
allocation bounds stop resource overflow before fitting; all fitted encoders
remain proposals for head acquisition and independent selection.
`zero_failed_observations` proves only the zero-error Boolean sample special case.

`fit_prototype_features(allocate_by_errors=True)` (§36.53) increments a single
eligible category's reserved allowance using modal training-error counts and
stable ties. All fitted feature proposals still require independent head/task
selection. `single_allowance_increment` proves only the finite reservation sum
identity, not greedy allocation quality or numerical fitting.

`fit_prototype_features(max_allocation_trials=...)` (§36.54) adds bounded
alternative allocation search, deduplicating allowance signatures and scoring
all fitted models before independent selection. It preserves greedy defaults.
`incremented_allowance_distinct` proves only that a one-slot increment changes a
state, not correctness or completeness of the priority frontier.

`acquisition_objects.store_acquired_models` (§36.55) retains chosen models and
representations as ordered public bindings with one shared traversal memo. The
single-root API delegates to it. `packages.install_scopes` installs related roots
with a shared primitive memo; `install` delegates for one scope. This avoids
conflicting wrappers in one residency pool without weakening collision checks.
Reinstalled representations can feed new head
acquisition through ordinary contracts/invocations, preserving expert opacity.
`retained_root_outputs_eq` proves only conditional ordered output equality.

`learning.interfaces.propose_adapters` (§36.56) searches a bounded compatible
source/teacher/consumer family through public contracts and paired training
invocations, emitting completed routes and constructor declarations. It reuses
`propose_adapter`; teacher implementations are absent from retained inference
closures. `adapter_consumer_family_eq` proves conditional family agreement only,
not learned alignment quality or end-to-end task correctness.

`learning.interfaces.fit_interface_bridge` (§36.57) exposes alignment independently
of a consumer. `propose_adapters(share_alignment=True)` shares one fitted bridge
per compatible source/teacher pair while retaining completed-route budgets.
Multi-root retention/installation preserves the shared artifact and optional
public bridge root. `shared_alignment_observation_bound` proves only the external
paired-observation count inequality, not speed or executable model equivalence.

`propose_adapters(fitters=...)` (§36.58) searches explicit ordered bridge-fitting
families, keeping sharing local to each entry and bounding completed routes.
The singular fitter remains the default. `adapter_family_contains_route` proves
only mapped-family membership for a present adapter, not prefix coverage,
provider success or generalization.

## Working state and streams

[§42](theory/foundations/42-working-state.md) defines state-threaded ordinary
routes. `runtime.Process` keeps the last completed state message and executes
each event with `execute`, sharing provenance, cache, resolver and risk ledger.
Its implementation is in `runtime.process`; the `runtime` package owns the
interpreter and re-exports the cursor. Process dispatch uses the public
`runtime.execute` binding.
The external contract places state first and returns the same contributor-defined
type. Callers supply a well-typed route; no route is selected merely because its
output matches the state type. `stream` is lazy and bounded by caller steps;
budgets apply per transition. `Execution/State.lean` proves conditional invariant
preservation and failed-transition cursor preservation for immutable states.
Mutable payloads and external effects are not rolled back or contained. Workspace
history remains linear; this provides no durable or bounded episodic memory.

`effects.effect_scope` establishes optional host grants; nested scopes intersect.
`runtime` and `compile` admit declared effects before callbacks and use
`effects.effect_call` to install each callback's declaration. Requests preserve
the requester's authority across deferred resolution and continuation resumption.
Contributor-owned resource gateways call `effects.require_effect` before acting.
`Execution/Effects.lean` proves finite-set attenuation and conditional gateway
refusal (§42.4). These checks do not intercept arbitrary host-language effects;
untrusted implementations still need an OS/process isolation boundary.

## Episodic record storage

[§43](theory/foundations/43-episodic-memory.md) maps to `memory.MemoryRecord` and
`memory.MemoryStore`, with abstract exact-recall/lookup-preservation proofs in
`Execution/Memory.lean`. Replay and guarded catalogs accept the structural
`memory.MemoryBackend` interface, independent of storage implementation.
`memory.records` owns canonical records; `memory.sqlite.MemoryStore` implements
the default backend and remains exported as `memory.MemoryStore`. Alternative
backends are host-supplied and must meet the same identity, provenance,
permission, append-atomicity, capacity and enumeration obligations. The protocol
does not enforce these semantics or certify a backend. The following storage
details describe the SQLite implementation.

The host provisions a dedicated SQLite database and
supplies read/write effect identifiers. Appends and indexed reads use the
permission gateway; canonical records carry opaque bytes, type, producer, time,
reported confidence, parents and optional same-type supersession. One writer
transaction validates parents, enforces persistent logical-byte capacity and
inserts an immutable record. WAL mode is required and synchronous commits use
FULL mode. Reopening preserves references; duplicate appends
are idempotent. Reads verify content digests. Quota excludes SQLite physical
storage overhead. There is no eviction, semantic retrieval strategy or bundled
memory expert; external packages provide codecs, recall and consolidation.
`MemoryStore.scan` provides bounded append-order reference pages for external
index rebuilding. Its cursor survives reopen; concurrent appends get higher
positions in the same serialized transaction. The position index is physical
storage overhead, outside the logical record-byte quota.
The artifact `objects.Store` retains its expert/type DAG semantics and eager
whole-directory reopen. Episodic traffic uses an indexed transactional backend
to support bounded reads and atomic cross-handle capacity admission without
loading every experience into the artifact store.

## Retained replay admission

[§43.4](theory/foundations/43-episodic-memory.md) extends existing evaluation
attestations with ordered durable `records` references. `evidence.evaluation`
checks benchmark identity, alignment and distinctness; `evidence.trusted` is the
shared issuer/signature policy used by existing evidence and `retention.replay_gate`.
The replay gate unions compatible baselines per route, rejecting conflicting
outcomes and counting each route/record pair once. It freezes these baselines,
checks a total case budget and scores
supplied proposed route versions on those records. Each route has its own loss
count; wins elsewhere cannot compensate. Missing/corrupt evidence and invalid
claims raise errors. `Execution/Memory.lean` proves the zero-loss retained-success
special case, not population generalization after adaptive replay. The caller
must include every affected route, control evaluator resources/effects and commit
only on whole-family acceptance. No route or memory update is performed by the
gate. Existing artifact serialization preserves the retained reference bindings.

`retention.sampled.SampledGate` implements sampled admission (§43.7). It shares
`retention.baselines` with the exact gate to validate and merge trusted
evaluations, shuffles each added batch once with a seed fixed at construction,
and keeps a cursor per route. `decide` numbers decisions as they draw cases,
spends `decision_level(δ, k)` split over the affected routes, draws
`required_cases(ε, level)` unused cases per route, retires them before
evaluating, and replays only drawn baseline successes; zero losses admit. A
route without enough unused cases refuses the decision without drawing or
spending budget, and `add` appends newly retained cases behind every cursor.
`Reliability/SampledGate.lean` proves the accounting of Theorem 43.1;
`benchmarks/sampled_gate.py` compares it with exact replay.
`RouteCatalog.replace`, `replan` and the router accept the gate through
`ReplayContext.sampler`. In sampled mode the catalog requires zero losses,
checks that the sampler holds evidence for every affected anchor, and counts a
drawn case as lost when the proposed plan fails where the original baseline or
the current plan succeeds; the current plan runs only when needed.
`GuardedUpdate.sampled` then carries the decision and the exact gates are empty.

`retention.plasticity.PlasticityField` keeps a plasticity and an open flag per
caller-chosen key (§43.8). `observe(key, surprise, stability)` applies a
pluggable regulator (default `Smoothing(rate)`), rejects values outside [0, 1]
and applies hysteresis between `close_at` and `open_at`; `allocate(budget)`
divides attempts over open keys by largest remainder in proportion to
plasticity; `settle(key)` closes a key after the gate admits a change for it.
Arithmetic is generic, which lets `tests/test_plasticity.py` compare it exactly
with `Reliability/PlasticityReplay.lean` over rationals.
`benchmarks/plasticity.py` compares budget allocation with uniform and oracle
policies under random shifts.

`retention.signals` computes those inputs (§43.9). `surprise(ledgers, key,
audits=...)` averages reported risks of charged invocations per key, where
`key` maps an `Invocation` to an expert identity and optionally an input
region, and sets a key to one when its audit refutes calibration.
`stability(catalog, module)` is `d / (d + half)` over
`RouteCatalog.dependents(module)`, and `observe` feeds a window to a field.
`benchmarks/ledger_signals.py` runs region experts through `execute` with
silent and honest shifts.

`retention.consolidation.consolidate(catalog, piece, distill, training, ...)`
implements §43.10. `record` rewrites each training route's plan with a
forwarding recorder in place of the piece and runs it on decoded training
records, collecting the piece's inputs and outputs; the distiller turns these
into a candidate with the same contract, which `RouteCatalog.replace` gates on
every dependent route. With a sampler, training records still listed by
`SampledGate.unused` for an affected route are refused. An admitted
consolidation reports the replaced piece as retired when no protected route
uses it. `benchmarks/consolidation.py` consolidates accumulated patch chains.

`MemoryStore.remove` deletes one record and frees its charge, refusing records
named as parents through a `memory_parents` index that older stores backfill
when opened; positions continue from the largest used. `retention.eviction`
implements §43.11: `protected` collects records named by a catalog's retained
evaluations, unused sampled cases and caller-pending records; `candidates`
orders drawn sampled cases first, then unprotected records in append order;
`evict` removes requested records until enough bytes are freed, keeps
protected ones unless `forced`, withdraws every removed case from the sampler
(`SampledGate.withdraw`) and, when forced, reports routes that lost unused
cases or retained-evaluation records. `benchmarks/eviction.py` runs a long
stream in a store of fixed capacity.

Hub types (§29.4) need no kernel support beyond ordinary planning: a
contributor-chosen constructor serves as the shared medium, and each
contributor installs an encoder into it and a decoder out of it.
`tests/test_hub.py` checks two-step routes, route stability when a contributor
joins and additive route risk; `Types/Hub.lean` proves Theorem 29.4; and
`benchmarks/shared_medium.py` compares hub and pairwise connector growth with
translators fit by `learning.discovery.fit_decoder`.
`learning.hub.attach` learns a hub without hub labels (§29.5): it maps a
partner member's paired values through that member's encoder and fits the new
type's encoder and decoder with a supplied fitter. The same benchmark compares
attaching to the founder, the predecessor or a random member.
Hub migration (§29.6) is one more attachment: the new hub attaches to the old
through the old founder, and the planner composes across versions;
`benchmarks/hub_migration.py` compares this bridge with re-attaching every
old member.

A consumer fed refined values through an upcast is charged by `route_risk`
with its rate taken in situ unless a `shift` certificate is passed (§29.7):
`evidence.shifted` rewrites the plan so each expert fed through upcasts is
charged `min(1, c · rate)` for the certificate of the types it actually
receives, and the risk is `None` where none exists. `benchmarks/slot_risk.py`
compares the in-situ and certified charges.

`retention.routes.RouteCatalog` generalizes pinned routes to immutable multi-root
snapshots (§43.5). Its reverse index covers explicit arguments, maps and slots;
`replace` rewrites contract-equal expert versions, requires evidence for every
affected anchor and executes actual current/proposed plans using each registered
codec/scorer. It applies both original-baseline and current-outcome replay checks.
Only complete acceptance returns the prepared replacement catalog; refusal returns
the old catalog unchanged. Metadata is snapshotted as canonical bytes, and public
route maps are read-only. `Execution/Memory.lean` proves abstract refusal identity
and conditional invariant preservation; it does not verify dependency traversal
or Python immutability. Opaque experts/resolvers stay pinned; changed internals
need a new outer expert. This API does not guard arbitrary manual `Router.upgrade`
calls. Existing snapshots retain their actual expert references. Active manifests are checked against stored snapshots, refusing in-place metadata
changes. Exact unchanged route objects reuse validated dependency sets; every rewritten
root is type-checked. Catalog copying/index rebuilding remains linear and is
included in update measurements.

`Router(catalog=...)` or `Router.protect` activates protected dispatch (§43.6).
Bindings use available-input signatures and goals; unknown signatures return no
route. Explicit binding choices resolve ambiguity without excluding other catalog
roots from expert-update replay. Existing legacy pins must be represented by the
same plan objects before activation. Protected legacy pin views are read-only.

`Router.upgrade` and `rollback` require `ReplayContext` after activation and use
`RouteCatalog.replan`, which preserves external signatures while allowing new
internal wiring. `ReplayRejected` carries the complete refused result;
`last_update` exposes the last completed check. `replace_experts` publishes the
existing catalog-wide replacement result into the same router snapshot. A
nonblocking mutation lock rejects reentrancy/concurrent mutation, and dispatch
captures one state reference without waiting for replay. Refusal changes only
its diagnostic receipt, not the catalog. `Execution/Memory.lean` proves abstract
no-fallback dispatch and refusal lookup preservation, not Python concurrency.
Unprotected routing remains an explicit research compatibility mode; supplying
replay context to it is an error rather than silently skipping the gate.

Router replay narrows effects to the memory-read effect plus `ReplayContext.effects`;
the host must already grant them. Live irreversible actions must not be opted
into replay. Plan-only catalog snapshots share frozen attestation bytes and their
anchor index; selected assertions are parsed in original family order. Public
`retained` views remain independent decoded objects. Root copying/index rebuilding
still depends on total catalog size.
