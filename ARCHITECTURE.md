# Architecture

Maps the theory indexed in [THEORY.md](THEORY.md) to Lean declarations and core
interfaces. The proof-debt table distinguishes conditional mathematical models
from verified implementation behavior. Mathematical arguments belong in the
topic chapters; predictions and measurements belong in the research diary.

Build and check the proofs with `cd lean && lake exe cache get && lake build`;
run the Python tests with `uv run pytest`.

## Map

| THEORY.md | Lean (`lean/NCA/`) | Python (`src/nca/`) |
|---|---|---|
| [§1 Types and contracts](theory/foundations/01-types-and-contracts.md) | `Contract`, `Terms` | `abi`, `registry` |
| [§2 Planning](theory/foundations/02-planning.md) | `Planner`, `Check`, `Terms`, `Unification`, `PatternSearch` | `planner.plan`, `router.infer` |
| [§2.13 Proposal-only libraries and retained certificates](theory/foundations/02-planning.md#213-proposal-only-libraries-and-retained-certificates) | `Reliability/SampledGate`, `Reliability/Occam` | `retention.ensembles.EnsembleSearch`; external `nca_structural_experts.reuse` and `nca-procedural-families: benchmarks.curriculum_checkpoint` |
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

Capability measurements so far concern the synthetic families recorded in the
diary. Held-out-family generalization, final-answer-only autonomous learning
and sublinear scaling have not yet been established.

| Relied-on guarantee | Status | Evidence and remaining obligation |
|---|---|---|
| Serialized in-memory artifact identity | Model proved; empirically linked | `Artifacts.run_retains`, `admitted_read_stable` and `run_read_identity` model checked decoding and non-overwriting hash-map admission for arbitrary codecs, digests, policies and operation interleavings. Python/Lean differential tests cover 512 operations, including real and colliding digests. Immutable bytes, lock linearization and codec/runtime fidelity are trusted library boundaries; decoded views are independently tested. |
| Artifact persistence, DAG validation and runtime fidelity | Open | Per-file publication now has a complete, non-overwriting transition model (`Artifacts.publicationRun_retains`, `publicationRun_source`), linked by 512 finite traces, concurrent writers, injected failures and subprocess exit. Atomic hard-link semantics are trusted; whole-directory transactions and power-loss durability remain open. The identity model does not prove the dependency/index validation algorithm, JSON implementation correctness or loaded-expert behavior. `Execution/DependencyWalk` proves decreasing visit/emit work and absence of an infinite machine run under acyclic weights, exact per-step task accounting and preservation of dependency order when a fresh ready vertex is appended. `objects.Store.walk` and `flatten` use a shared explicit work stack; 1,024 DAGs with fixed topological order, mixed object kinds and duplicate edges match the recursive reference and decode each reached node once. The full DFS readiness/reachability argument, admission/runtime fidelity and byte-memory bounds are not mechanized. Save/reopen, collision, malformed schema and concurrent duplicate-admission tests provide empirical coverage only. |
| Native arithmetic implements the reference account | Open end-to-end | Differential tests include subnormal allocation and extreme temperatures. Builds require strict FP; compiler lowering, gradual underflow and external mathematical routines remain trusted. Exact-real lemmas and passing numerical tests do not prove arbitrary compiled floating-point execution. |
| Deterministic state threading under replay | Open | Process tests cover supplied deterministic experts. Model transitions, nested execution and replay; expert determinism and immutable payloads remain trusted assumptions. |
| Authority only narrows; every mediated operation is declared and granted | Open | Effect-scope tests cover runtime and compiled callbacks. `effects.invoke_scoped` applies each immediate learning-component invocation's own declaration, including training observations and learned model interpreters. `composed_child_allowance` proves that a composite union gives its child no sibling authority. Scalar/compiled composition tests and finite permission sets link the model to execution. Immediate invocation scopes now also cover evidence evaluation, calibration, retention recording, certification and selective consumers/fusers. Reference risk reports and evidence-demand callbacks use their owners' scopes. Selective per-solve helpers retain their originating expert's declaration without requiring a helper manifest; a supplied helper manifest further narrows that authority. `effectPath_gateway_owner` proves ownership along arbitrary finite callback paths; evaluator/candidate, calibration, reference and delegated-session tests link these paths. Other non-invocation callbacks and returned deferred objects still need audit and complete origin authority. Prove the full nested, batched, deferred and generator execution model. Cooperative gateways are trusted; arbitrary expert code is not isolated. |
| Failed transitions preserve state, memory and ledgers | Open; not currently satisfied | `Execution/Workspace` proves prior bindings survive fresh suffix writes and reverse suffix erasure restores the index; log truncation restores the prefix. `Workspace.post` rejects identifier collisions and makes exact-object reposts idempotent; runtime input admission uses the same gate. Tests exhaust 3,125 post/checkpoint/rollback traces and check input collisions before invocation. Python object identity, immutable payloads, serialized operations and container fidelity remain assumptions. Process cursors retain the committed state, but execution can retain charges and memory writes. Joint transaction semantics are required before claiming failure atomicity. |
| Exact durable recall and bounded capacity | Open | `memoryInsert_recall`, `memoryInsert_preserves` and `memory_capacity` model a functional map and arithmetic admission. Model serialization, hash validation, concurrent transactions and persistent accounting; SQLite durability and hash collision resistance are trusted backend assumptions. |
| Append cursors survive eviction and reopening | Model proved; finite-linked | `cursorAppend_valid`, `cursorErase_valid` and `cursor_after_eviction` model a retained high-water mark, independent of live records. `memory.sqlite.MemoryStore` schema 2 updates that mark in the same transaction as admission; removal never decreases it. `tests/memory/test_memory_cursors.py` exhausts 256 four-operation append/evict/reopen/duplicate traces against the model and injects transaction failure. SQLite isolation, crash durability and serialization remain trusted, not proved. Schema-1 migration requires a caller-certified upper bound covering deleted positions; it cannot be reconstructed from surviving records. These cursors support durable enumeration; statistical allocation and refusal replay use the separate history mechanism below. |
| Pinned routes and rejected updates preserve behavior | Open | Routing and publication lemmas cover abstract snapshots. Tests exercise old snapshots and rejected updates. Prove actual graph traversal, version pinning and publication; immutable expert implementations and resettable replay callbacks remain trusted. |
| Every affected route is replayed | Open | Tests cover arguments, maps, slots and reverse-index rebuilding. Model the real dependency traversal and reverse index, including shared nodes; opaque implementations must remain pinned. |
| Zero-loss admission preserves retained successes | Open end-to-end | `retained_zero_losses` proves the finite Boolean-list special case. Link attestation merging, record decoding, actual execution, scoring, both comparisons and atomic publication to that proposition. Scorer correctness is supplied by the caller. |
| Sampled admission remains sound under adaptive updates | Proved except the sampling step; empirically checked | `zeroLoss_miss`, `decisionLevel_total`, `allocate_fresh` and `sampledGate_sound` prove the sample size, the budget over unboundedly many decisions, that no case informs two decisions and the union over decisions and routes. That fresh i.i.d. cases give miss probability `(1-ℓ)^m` given the history is the stated sampling hypothesis, not proved in Lean; whether real retained pools are i.i.d. samples of a route's operating distribution is trusted. Tests name each theorem; the Python allocator is not differentially linked to `allocate`. |
| Regional corrections preserve behavior outside their region | Open end-to-end | Existing regional tests and mathematical special cases do not verify the implementation and router error jointly for arbitrary contributed experts. |
| Stable bounded plasticity | Proved for the default regulator; empirically linked | `smooth_unit`, `smooth_step`, `hysteresis_gap` and `reopen_after_settle` prove bounds, per-step movement and no flapping; `retention.plasticity` matches `Reliability/PlasticityReplay.lean` exactly over rationals on 64 generated trajectories. Other regulators are checked only for staying in [0, 1]. `retention.signals` derives inputs from runtime ledgers, audits and dependents; `meanSignal_unit`, `dependentStability_unit` and `dependentStability_mono` prove them in range. Signal quality depends on expert calibration, which audits check. |
| Safe consolidation | Proved; empirically checked | `published_only_if_admitted` and `allocate_skips_drawn` prove that a consolidated piece is published only through the gate and that training on drawn cases keeps later gate cases fresh; `retention.consolidation.consolidate` enforces the freshness rule. Distiller quality is the caller's; the gate checks it. |
| Bounded retained evidence and safe eviction | Proved; empirically checked | `evict_keeps_protected` and `withdraw_fresh` prove that ordinary eviction keeps protected records and that withdrawal keeps later draws fresh; `MemoryStore.remove` refuses parents. SQLite deletion durability is a trusted backend assumption. Forced deletions are assumed independent of the estimated loss. |
| Safe migration | Open; not implemented | Shared-representation migration, and its composition with updates, consolidation and eviction, is not established. |
| Bounded connectors through a hub | Proved; empirically checked | `hubConnectors_card`, `hub_routes`, `direct_connectors_lower`, `hubConnectors_mono` and `hub_route_risk` prove 2N connectors, two-step routes, the N(N−1) pairwise lower bound, locality and additive route risk; `tests/planner/test_hub.py` checks planning through a hub. |
| Hub learned by attachment | Proved; empirically checked | `attached_risk` and `attachment_depth_risk` bound a type's hub risk by its fit risk plus its partner's, and by `dε` at depth `d`; `tests/learning/test_hub_learning.py` checks `learning.hub.attach`. The sampling bound for each fit is not formalized. |
| Hub migration by a bridge | Proved; empirically checked | `bridged_keeps`, `bridged_routes`, `bridged_card` and `bridged_route_risk` prove that bridging keeps both versions' routes, joins them in three steps with at most two new connectors and adds the bridge's risk; `tests/learning/test_hub_learning.py` checks a bridged plan. |
| Refined pieces in general slots | Proved; empirically checked | `slot_risk_transfer` bounds a consumer's risk on refined inputs by `c` times its measured rate under a density-ratio certificate, and `slot_risk_unbounded` shows no rate transfers without one; `route_risk(shift=…)` charges `min(1, c · rate)` and returns `None` without a certificate, checked by `tests/evidence/test_slot_risk.py`. Obtaining certificates from data is not addressed. |
| Containment and complete effect attribution | Open | Permission checks are cooperative. There is no OS-isolation guarantee or complete transactional audit of arbitrary expert effects. |
| Stored artifacts survive core reorganization | Model proved; empirically linked | `resolveLoader_relocate`, `resolveLoader_perm`, `resolveLoader_unrelated` and `resolveLoader_conflict` prove that resolution of stored identifiers is order-free, unaffected by other identifiers' registrations, refuses conflicts and follows injective code moves. `objects.loaders.location` matches `Execution/LoaderReplay.lean` on 256 generated registries; legacy import-path entries are registered aliases. Entry-point metadata parsing and each factory's fidelity to its identifier are trusted. |
| Unreachable goals become typed acquisition sub-goals | Proved; empirically checked | `gap_iff` characterizes single-connector repairs of unary routes exactly and `horn_gap_iff` single-expert repairs with any number of inputs; `planner.gaps` confirms every candidate by planning with a stand-in, and `Kernel(acquire=…)` serves an unservable request through an acquired connector, checked by `tests/planner/test_gaps.py` against the planner over every type pair. `repair_complete` and `repair_sound` characterize repairs with `k` allowed connectors; `planner.gaps.fewest_missing` is checked minimal against brute force. The 0-1 search itself is not formalized, experts with several inputs are approximated in the search and confirmed by the planner, and media (invented intermediate types) are proved not to change reachability (`founded_keeps`, `founded_medium`); whether growing one is worth its requests is measured, not proved. |
| Acquired connectors are certified before use | Proved; empirically checked | `acquisition_sound` with `zeroLoss_miss` bounds the probability of admitting any connector erring above `ε` by `δ` across all requests; `retention.acquisition.CertifiedAcquirer` implements the test and `tests/retention/test_certified_acquisition.py` checks admissions, refusals and the false-admission rate. The optional fixed-size path uses `lossTest_admits`, `tolerant_test_miss` and conservative binomial cutoffs. Fresh IID loss laws, coupling and numerical CDF bounds are assumed, not established. |
| Impossible deterministic contracts can be screened before fitting | Proved under stated semantic and sampling hypotheses; finite-linked | `contradictory_pairs_errors` proves that disjoint incompatible pairs force distinct errors; `contradiction_screen_risk` gives `binom(n,r) εʳ` under a joint-error bound on the original cases. Fresh conditional IID sampling implies that hypothesis but is not formalized here. `retention.screening.FeasibilityScreen` keeps all unmatched observations, checks disjoint pair certificates and uses exact rational thresholds. `unmatched_append`/`unmatched_remove` preserve unmatched independence; `maximal_pairs_half` bounds any endpoint-covered alternative matching by twice the returned pair count. All 1,024 ordered five-vertex graphs are checked against brute-force maximum matching. Callback purity, key bucketing, traversal fidelity and certificate validation remain executable boundaries; `CertifiedAcquirer` reuses passing prefixes for training and retains fresh final certification. `tests/retention/test_acquisition_screening.py` exhausts small samples and predictors and exactly enumerates a false-discard experiment. Key equivalence and separation soundness for the actual agreement rule are caller assumptions; passing is inconclusive, stochastic/hidden-state predictors are outside the guarantee. Optional persisted reuse is governed by the following row. The family budget uses the same telescoping union bound as `acquisition_sound`, separately from admission confidence. |
| Durable scoped acquisition refusals | Model proved; empirically linked | `durable_refusal_risk` bounds replayed false refusals by the original rejection events over any finite subset of non-reused spending indices. `retention.history.AcquisitionHistory` commits nonce-bearing reservations through `MemoryBackend.append_position` before sampling, and `CertifiedAcquirer` uses their indices for both screening and admission. Only screened impossibility is cached; keys include the full contract, caller-versioned semantic context, tolerance and both confidence budgets. The incremental index is bounded and checks retained references; misses and eviction cause fresh reservations. Tests cover restart reuse, changed scope, interrupted sampling, eviction, bounded-index misses, full storage and duplicate tickets. Conditional sampling, semantic scope identity, trusted history writers, nonce freshness and backend durability are assumptions; all tests in one confidence family must share a non-rewinding backend. Planner callback avoidance and storing learned implementations remain open. |
| Depth-independent risk by redundancy | Proved; empirically checked | `vote_correct` and `vote_risk` bound a majority over disjoint routes by `e_t` of their risks under independent failures; `evidence.redundancy` plans disjoint routes, votes and computes the bound, checked by `tests/evidence/test_redundancy.py` against exact enumeration and simulation. Independence is assumed, not established. |
| Staged training with fresh certification | Proved under the existing sampling hypothesis; finite-linked | `staged_acquisition_sound` specializes the nested confidence union bound to declared training stages and early stopping. `CertifiedAcquirer(stages=…)` splits each request level conservatively with `family_audit_alpha`, fits bounded training prefixes and tests each frozen candidate on new cases. Failed-test cases can train later candidates, never certify them; retained cases are capped by `train`. Default acquisition has one stage. `tests/retention/test_staged_acquisition.py` checks unseen-case memorizer refusal, reuse without double charging, early/later acceptance, contract matching, stage validation and exact-rational budget bounds over all subsets of up to eight stages. Conditional IID sampling, candidate immutability and the existing floating-point sample-size implementation remain trusted boundaries. No learning-rate or universal efficiency claim is made. |
| Supplied acquisition priorities preserve valid candidates | Model proved; finite-linked | `acquisition_order_valid` proves that permutation preserves candidate validity. `planner.gaps.gaps(priority=…)` stably sorts already-confirmed candidates with finite scores, and `repair(priority=…)` uses that order in its single-gap search without pruning; `Kernel(priority=…, arity=…)` exposes it to mediated acquisition requests. Multi-step fewest-missing paths retain their order. `acquisition_swap_difference` and `acquisition_swap` prove the local expected-cost exchange criterion for fixed independent success chances and costs; supplied estimates need not satisfy those assumptions. `tests/planner/test_acquisition_priority.py` checks candidate preservation, tie order, complete refusal traversal, nonfinite-score rejection, preferred repair, kernel-mediated multi-input acquisition and exact rational exchange costs. Python sorting and scorer purity remain trusted. The learned success-frequency scorer lives only in the benchmark; calibrated semantic prediction, context transfer and performance guarantees for adaptive scores remain open. |
| Majority risk without independent failures | Proved under marginal-risk and measurability hypotheses; finite-linked | `vote_omit_forces`, `dependent_vote_risk` and `dependent_majority_bound` prove that omitting r indices leaves at least t−r failures, then bound the remaining count by Markov without independence. `evidence.redundancy.dependent_vote_risk` minimizes the resulting bounds by omitting the largest marginals; exact rational evaluation and upward float conversion prevent numerical understatement. The independent `vote_risk` now uses the same conservative numerical discipline and both reject invalid probabilities. Tests enumerate dependent two-atom joint laws, all omitted-subset bounds for small risk vectors, exact independent products and subnormal underflow. Sorting, probability inputs and runtime failure semantics remain trusted; measured marginals need separate coverage guarantees outside an exactly enumerated distribution. No reliability amplification or risk-targeted acquisition is claimed from dependence alone. |
| Acquire toward a jointly certified vote target | Proved under stated fresh-case hypotheses; empirically linked | `ensemble_miss` applies the default zero-loss bound to the entire vote error, including abstention; `ensemble_search_sound` reuses the staged confidence union bound, without any route-independence hypothesis. `retention.ensembles.EnsembleSearch` asks a supplied route acquirer up to declared counts and returns the first vote passing a fresh test. `retention.certification.loss_test` is shared with `CertifiedAcquirer`; bounded retention, early stopping, insufficient draws and exception-time label accounting are tested. Exhaustive small Boolean histories link its admission to `earlyTest_admits`. Tests distinguish abstention from a unanimous None payload and cover stopping, common-mode refusal, unavailable/wrong-output routes and durable confidence continuation. Conditional IID sampling, truthful agreement, typed route/runtime fidelity, fixed expert/resolver behavior and backend durability remain assumptions; no saved-certificate restoration or learned proposal policy is proved. Refusal is not cached as impossibility. |
| Counterexamples inform later acquisition | Conditional progress proved; transport empirically linked | `EnsembleSearch(feedback=…)` emits one `VoteFailure` after a scored rejection, including the last stage; admission, insufficient data and execution/scoring exceptions emit no counterexample. The handler receives the failed vote, case and drawn count and may inform later proposals or searches. It cannot make old draws fresh; `ensemble_search_sound` still requires new conditional IID certification cases and fixed candidate behavior. `feedback_repair_progress` and `feedback_chain_bound` prove strict error-count progress only when the supplied learner removes the reported error without new errors. Tests check callback order, first-failure selection within a batch, no admission-data leakage, exception accounting, new draw identifiers and exhaustive finite-set progress. The benchmark supplies domain-specific simulator labels outside the core and audits regressions; inference of intermediate supervision, monotonicity of arbitrary fitters and persistent feedback retention remain open. |
| Whole-candidate revision from endpoint feedback | Proved conditionally; empirically linked | `EnsembleSearch.revise` requests a fresh nonempty candidate family within each declared cap and supplies earlier closed-test failures. Repeated caps support same-size revisions. Both growth and revision use one `_search` path and the existing `ensemble_search_sound` confidence allocation; no old implementation is mutated or automatically published. `keyCorrection_outside` and `endpoint_correction_errors` prove pointwise preservation for a supplied injective key and truthful endpoint label, linked to the existing `learning.discovery.Corrected` interpreter by exhaustive finite tests. These hypotheses are not inferred for arbitrary features or noisy targets. Tests cover curriculum order, candidate caps, immutable incumbents and configurable export/kernel planning depth. `install`, `install_scopes` and `Kernel` now expose planning fuel separately from execution budget. Export result-cache identities include planning/execution configuration while artifact bindings remain stable; binding-level purity refutations still disable caching. Generic `cache_identity` overrides are tested against different routes selected at different fuel values. The benchmark uses the existing correction learner through an exported public interface, with no new intermediate supervision; initial pretraining remains supervised. Unrestricted repair-feature discovery, certificate persistence and automatic publication remain open. |
| Remaining foundation guarantees | Open | Adaptive label efficiency, compression, shape-parametric refinement, semantic planning, arbitrary-policy preservation and distributed consistency require their own mechanism-level proofs and scaling curves. Existing numbered lemmas alone do not close these obligations. |


Open obligations require mechanism-level proofs, explicit assumptions and
executable links before their status changes. Separate proofs do not establish
correctness of interactions between mechanisms.

### Theorem declarations

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
| [2.11](theory/foundations/02-planning.md) | `assignment_bucket_complete`, `assignment_bucket_unique` | `Execution/Relevance` |
| [2.12](theory/foundations/02-planning.md) | `first_consistent_minimal`, `followPath_append`, `filter_sequential`, `conditional_agree`, `append_preserves_admitted`, `observed_pair_congruent`, `map_agree_on_calls`, `positive_children_arity_bound` (ordered candidates and partial path composition; enumeration completeness unproved) | `Planning/RouteSearch` |
| [2.12](theory/foundations/02-planning.md) | `frontier_lower_bound` (positive completion lengths bound a partial route's minimum size) | `Planning/RouteSearch` |
| [2.12](theory/foundations/02-planning.md) | `TypedCompletion.lower`, `TypedCompletions.lower`, `TypedCompletion.relax`, `TypedCompletions.relax` (admissible potentials and lower-cost grammar relaxations for typed completions) | `Planning/Completion` |
| [2.12](theory/foundations/02-planning.md) | `answer_sound` (typed pattern-planning model; deferred grounding implementation unproved) | `Types/Terms` |
| [2.12](theory/foundations/02-planning.md) | `WitnessDerivation`, `witness_derivation_sound` (sound decompositions and checked leaves imply a satisfied root) | `Planning/RouteSearch` |
| [2.12](theory/foundations/02-planning.md) | `fold_agree_on_elements` (fold steps agreeing on all relevant states and elements produce the same output) | `Planning/RouteSearch` |
| [2.12](theory/foundations/02-planning.md) | `ObservedTreeEval`, `observed_tree_fold_sound` (child-closed queried equations determine a tree-fold result) | `Planning/RouteSearch` |
| [2.12](theory/foundations/02-planning.md) | `mdl_extension_sound` (conditional compression, prior route typing and local Kraft bound) | `Planning/RouteSearch` |
| [2.13](theory/foundations/02-planning.md#213-proposal-only-libraries-and-retained-certificates) | `acquisition_sound`, `occam_adaptive_fresh` (existing fresh-case guarantees; trusted history/route identity required, checkpoint transport not formally proved) | `Reliability/SampledGate`, `Reliability/Occam` |
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
| [20.23](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `fuelWalk_finished`, `fuelWalk_completes` | `Continuation` |
| [20.8](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `choice_cost_le` | `Slots` |
| [20.9](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `PTyped.erase`, `WellTyped.positional` | `Relevance` |
| [20.10](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `PPlan.uses_apply`, `PPlan.given_not_relevant`, `PTyped.uses_lt` | `Relevance` |
| [20.11](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `gap_iff`, `gap_complete`, `gap_sound` | `Planning/Gaps` |
| [20.12](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `repair_complete`, `repair_sound` | `Planning/Gaps` |
| [20.13](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `founded_keeps`, `founded_medium` | `Planning/Gaps` |
| [20.14](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `acquisition_sound` (with `zeroLoss_miss`), `earlyTest_admits`, `earlyTest_reads` | `Reliability/SampledGate` |
| [20.16](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `contradictory_pairs_errors`, `contradiction_screen_risk` | `Reliability/Screening` |
| [20.20](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `unmatched_append`, `unmatched_remove`, `maximal_pairs_half` | `Reliability/Screening` |
| [20.21](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `batchedTest_admits`, `batchedTest_reads`, `batchedTest_excess` | `Reliability/BatchedTest` |
| [20.22](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `lossTest_admits`, `lossTest_reads`, `tolerant_test_miss` | `Reliability/TolerantTest` |
| [20.17](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `durable_refusal_risk` | `Reliability/Screening` |
| [20.18](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `staged_acquisition_sound` | `Reliability/SampledGate` |
| [20.19](theory/foundations/20-higher-order-experts-and-budgeted-requests.md) | `acquisition_order_valid`, `acquisition_swap_difference`, `acquisition_swap` | `Planning/Acquisition` |
| [43.6](theory/foundations/43-episodic-memory.md) | `cursorAppend_valid`, `cursorErase_valid`, `cursor_after_eviction` | `Execution/Memory` |
| [43.7](theory/foundations/43-episodic-memory.md#4313-conservative-numerical-sample-sizing) | `log_upper_ceil_size`, `zeroLoss_log_upper` | `Reliability/SampledGate` |
| [43.8](theory/foundations/43-episodic-memory.md#4314-downward-confidence-allocation) | `rounded_decision_budget`, `rounded_family_budget` | `Reliability/SampledGate` |
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
| [28.8](theory/foundations/28-packages-as-experts.md) | `scope_step_decreases`, `scope_no_infinite_run` | `Execution/DependencyWalk` |
| [28.9](theory/foundations/28-packages-as-experts.md) | `Artifacts.publicationRun_retains`, `Artifacts.publicationRun_source` | `Execution/Artifacts` |
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
| [31.15](theory/reliability/31-composing-uncertainty.md) | `occam_zero_loss`, `occam_family_sound`, `occam_adaptive_sound`, `occam_adaptive_fresh` | `Reliability/Occam` |
| [31.15](theory/reliability/31-composing-uncertainty.md) | `weighted_lengths_kraft`, `productionBits_capacity`, `productionBits_kraft` | `Reliability/Occam` |
| [31.16](theory/reliability/31-composing-uncertainty.md) | `finite_service_threshold` | `Reliability/Protocol` |
| [36.59](theory/evidence/36-interface-acquisition.md) | `featureClosure_iff` | `Planning/FeatureClosure` |
| [36.60](theory/evidence/36-interface-acquisition.md) | `featureTreeClosure_iff` | `Planning/FeatureClosure` |
| [36.61](theory/evidence/36-interface-acquisition.md) | `featureApplication_reloaded_eq` | `Planning/FeatureClosure` |
| [36.62](theory/evidence/36-interface-acquisition.md) | `feature_index_filter` | `Planning/FeatureClosure` |
| [36.63](theory/evidence/36-interface-acquisition.md) | `feature_demand_index_eq`, `feature_demand_prefix_filter` | `Planning/FeatureClosure` |
| [36.64](theory/evidence/36-interface-acquisition.md) | `feature_coarse_filter` | `Planning/FeatureClosure` |
| [36.65](theory/evidence/36-interface-acquisition.md) | `feature_priority_closure` | `Planning/FeatureClosure` |
| [36.67](theory/evidence/36-interface-acquisition.md) | `feature_target_reach` | `Planning/FeatureClosure` |
| [36.68](theory/evidence/36-interface-acquisition.md) | `empiricalModalScore_counts`, `empiricalModalScore_perm`, `empirical_identifier_count` | `Reliability/Acquire` |
| [36.69](theory/evidence/36-interface-acquisition.md) | `unary_continuation_eq` | `Planning/FeatureClosure` |
| [36.70](theory/evidence/36-interface-acquisition.md) | `empiricalModalScore_le_total`, `saturated_prefix` | `Reliability/Acquire` |
| [36.71](theory/evidence/36-interface-acquisition.md) | `structural_pair_correct` | `Reliability/Acquire` |
| [36.72](theory/evidence/36-interface-acquisition.md) | `bounded_candidate_evaluations` | `Reliability/Acquire` |
| [36.73](theory/evidence/36-interface-acquisition.md) | `selected_output_correct` | `Reliability/Acquire` |
| [36.74](theory/evidence/36-interface-acquisition.md) | `witness_prefix_prune` | `Reliability/Acquire` |
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
| [42.1](theory/foundations/42-working-state.md#425-stable-message-identities-and-suffix-rollback) | `workspace_extension_retains`, `workspace_suffix_restores`, `workspace_log_restores` | `Execution/Workspace` |
| [42.2](theory/foundations/42-working-state.md#426-component-declarations-inside-learned-compositions) | `composed_child_allowance`, `sibling_cannot_authorize` | `Execution/Effects` |
| [42.3](theory/foundations/42-working-state.md#427-evaluation-authority-follows-callback-ownership) | `effectPath_subset_parent`, `effectPath_subset_owner`, `effectPath_gateway_owner` | `Execution/Effects` |
| [43.1](theory/foundations/43-episodic-memory.md) | `zeroLoss_miss`, `decisionLevel_total`, `allocate_fresh`, `sampledGate_sound` | `Reliability/SampledGate` |
| [43.2](theory/foundations/43-episodic-memory.md) | `smooth_unit`, `smooth_step`, `hysteresis_gap`, `reopen_after_settle` | `Reliability/Plasticity` |
| [43.3](theory/foundations/43-episodic-memory.md) | `meanSignal_unit`, `dependentStability_unit`, `dependentStability_mono` | `Reliability/Plasticity` |
| [43.4](theory/foundations/43-episodic-memory.md) | `published_only_if_admitted`, `allocate_skips_drawn` | `Reliability/SampledGate` |
| [43.5](theory/foundations/43-episodic-memory.md) | `evict_keeps_protected`, `withdraw_fresh` | `Reliability/SampledGate` |

### Additional theorem declarations

| Lean declaration | Source |
|---|---|
| `accepted_clamp_length_eq` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `accepted_clamp_length_iff` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `adapter_composition_eq` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `adapter_consumer_family_eq` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `adapter_family_contains_route` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `affine_slope_optimal` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `auxiliary_feedback_separation` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `bernoulliStep_certain_succ` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `bernoulliStep_certain_zero` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `bernoulliStep_impossible` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `bernoulliStep_succ` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `bernoulliStep_zero` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `bernoulli_count_le_length` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `bernoulli_split_mass` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `bernoulli_step_upper` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `bernoulli_tail_step_upper` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `binary_modal_split_le` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `bounded_leaf_binary_posterior` | [Decoding/Product](lean/NCA/Decoding/Product.lean) |
| `bounded_leaf_binary_prior` | [Decoding/Product](lean/NCA/Decoding/Product.lean) |
| `bounded_shape_leaf_binary_count` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `certain_success_threshold` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `combined_allocation_cover` | [Reliability/Selective](lean/NCA/Reliability/Selective.lean) |
| `configuredExport_reloaded_eq` | [Planning/FeatureClosure](lean/NCA/Planning/FeatureClosure.lean) |
| `decoded_reloaded_eq` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `dependency_rank_acyclic` | [Execution/Package](lean/NCA/Execution/Package.lean) |
| `export_identity_eq` | [Execution/Package](lean/NCA/Execution/Package.lean) |
| `failure_partition_covers` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `feature_admission_bound` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `feedback_group_invariance` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `gap_boundary_preserves` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `grouped_mass_nonneg` | [Reliability/Selective](lean/NCA/Reliability/Selective.lean) |
| `grouped_mass_sum` | [Reliability/Selective](lean/NCA/Reliability/Selective.lean) |
| `grouped_modal_dominates` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `guardedPrefix_correct` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `head_fiber_consistency` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `incremented_allowance_distinct` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `joint_decoder_simulates` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `joint_key_refines_seed` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `joint_reloaded_eq` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `log_weight_sum_bound` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `lookahead_score_mono` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `matrix_shape_division` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `measurement_prefix_bound` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `midpoint_inside_gap` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `modal_decoder_optimal` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `modal_refinement_dominates` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `modal_refinement_le` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `nested_fit_comparison` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `nested_refinement_scope` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `normalized_common_factor` | [Decoding/Product](lean/NCA/Decoding/Product.lean) |
| `ordered_lower_bound_is_first` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `ordered_product_fold` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `ordered_search_excludes_lower` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `orthogonal_residual_square` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `oversized_route_infeasible` | [Planning/Eviction](lean/NCA/Planning/Eviction.lean) |
| `pair_codec_roundtrip` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `pair_gap_sum_nonneg` | [Decoding/Detection](lean/NCA/Decoding/Detection.lean) |
| `pair_prefix_step_upper` | [Decoding/Detection](lean/NCA/Decoding/Detection.lean) |
| `prior_relabel` | [Decoding/Product](lean/NCA/Decoding/Product.lean) |
| `prior_tilt` | [Decoding/Product](lean/NCA/Decoding/Product.lean) |
| `prior_tilt_ne_zero` | [Decoding/Product](lean/NCA/Decoding/Product.lean) |
| `projection_prototype_gap` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `proposal_budget_le` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `prototype_interval_choice` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `prototype_left_of_midpoint` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `pruned_branches_eq_leaves_sub_one` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `publicationRun_retains` | [Execution/Artifacts](lean/NCA/Execution/Artifacts.lean) |
| `reciprocal_evidence_order` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `regional_fallback_score` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `regional_policy_missing` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `regional_preserves_complement` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `regional_reloaded_eq` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `regional_training_maxima` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `reloaded_outcomes_eq` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `residual_successes_le` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `restored_chain_eq` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `retained_root_outputs_eq` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `router_score_selection` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `search_midpoint_bounds` | [Decoding/Decoding](lean/NCA/Decoding/Decoding.lean) |
| `shared_alignment_observation_bound` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `single_allowance_increment` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `state_factorization_eq` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `sum_excluding_absent` | [Decoding/Product](lean/NCA/Decoding/Product.lean) |
| `sum_filter_zero_readings` | [Decoding/Product](lean/NCA/Decoding/Product.lean) |
| `surviving_pins_maximal` | [Planning/Eviction](lean/NCA/Planning/Eviction.lean) |
| `symmetric_interaction_gap` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `temperature_rank` | [Reliability/Selective](lean/NCA/Reliability/Selective.lean) |
| `threshold_score_le` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `training_projection_fusion` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `training_snapshot_map_eq` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `two_point_mean_minimizes` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `vector_adapter_composition_eq` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `zero_failed_observations` | [Reliability/Acquire](lean/NCA/Reliability/Acquire.lean) |
| `zero_frontier_step` | [Decoding/Product](lean/NCA/Decoding/Product.lean) |
| `zero_frontier_suffix` | [Decoding/Product](lean/NCA/Decoding/Product.lean) |
| `horn_gap_list_iff` | [Planning/Horn](lean/NCA/Planning/Horn.lean) |

## Implementation boundaries

| Subsystem | Interfaces and wiring | Boundary |
|---|---|---|
| Types and planning | `abi`, `planner`, `index`, `optimize`, `router` | Contracts establish compatibility, not semantic usefulness. `planner.plan_task` requires every supplied input position; `planner.gaps` and single-gap `repair` accept the same explicit requirement. General reachability remains available through `planner.plan`. |
| Objects and packages | `objects.Store`, `objects.loaders`, `packages.install`, `loader.ExpertStore` | Canonical references identify immutable artifacts; contributed implementations and weights still require faithful loaders. |
| Requests and execution | `kernel.Kernel`, `runtime.execute`, `runtime.process`, `compile.compile_route` | Invocation, cost and request budgets are separate from host metadata work. Opaque callbacks can still recurse or perform unmediated effects. |
| Refinement and decoding | `refinement`, `ladder`, `selective`, `prefix`, `decoding`, `priors` | Domains supply vocabularies, arities, semantics, priors and certificates. A decoding or risk certificate depends on those supplied premises. |
| Learning | `learning.discovery`, `interfaces`, `features`, `numeric`, `projections` | Proposals use training observations and require independent selection. Supplied features and transformations are not autonomous representation discovery. |
| Learned graph retention | `learning.acquisition_objects`, `tree_objects`, `numeric_objects`, `regional_objects`, `export_objects` | Reloaded parameters and wiring do not restore mutable state or statistical admission certificates. |
| Evidence and accounting | `evidence`, `runtime.RiskLedger`, `cache.ResultCache` | Risk premises, contributor calibration and internal-accounting declarations must be faithful; cache replay must preserve charges. |
| Memory | `memory.MemoryBackend`, `memory.MemoryStore`, `retention.history` | Host-provisioned identifiers and read/write effects are generic. Durability and non-rewinding confidence positions remain backend obligations. |
| Guarded updates | `retention.routes.RouteCatalog`, `router.ReplayContext`, `retention.sampled.SampledGate` | Explicit dependencies determine replay coverage. Opaque implementations remain pinned; replay must not perform irreversible actions. |
| Consolidation and eviction | `retention.consolidation`, `retention.eviction`, `retention.plasticity` | Training may reuse consumed observations, while certification requires fresh cases. Retiring a piece does not delete its protected dependents. |

Effect gateways are cooperative: `effect_scope` narrows grants and
`expert_scope` installs callback declarations. Immediate calls use
`effect_call`/`invoke_scoped`; deferred objects need their own authority
mediation. These mechanisms do not isolate arbitrary Python or native code.

`Store.save` publishes complete individual files without overwriting existing
names. This is not a whole-graph transaction or a power-loss durability claim.
Likewise, immutable route publication does not provide transactional rollback
of workspace, memory, ledgers and external effects; that obligation remains open.

Acquisition and vote revision use the same confidence allocation and fresh-test
machinery. The zero-error default and optional fixed-size binomial test have
different label costs. Scores, screens and retained counterexamples inform
training; none makes training data fresh certification evidence.

## Native kernels

`src/nca/native/` contains optional Elisa CPython extensions. Build with
`.venv/bin/python -m nca.native`; `NCA_NATIVE=0` selects the reference paths.
Strict floating-point compilation is required for conservative numeric bounds.

| Kernel | Core callers |
|---|---|
| `decoding.elisa` | `decoding`, `prefix`: format, band and cursor operations |
| `partition.elisa` | `partition.PartitionCursor`: selected/alternative path mass |
| `stats.elisa` | `stats`, `retention.sampled`: count tails, confidence limits and sample sizing |
| `polynomial.elisa` | `learning.projections`: supplied polynomial feature evaluation |
| `prototypes.elisa` | `learning.projections`: certified nearest-prototype selection |
| `records.elisa` | `learning.features`, `learning.categorical`: record lookup and empirical category scores |
| `assignment.elisa` | `planner.terms`: stable position-assignment ordering for bounded cached tables |

Numerical bounds rely on compiler, ABI and IEEE behavior stated in the relevant
chapters and source docstrings. Differential tests provide implementation
coverage; exact-real Lean theorems do not prove arbitrary compiled arithmetic.
Native kernels belonging only to an expert package live in that package.

## Test organization

Tests are grouped under `tests/` by subsystem: planner, runtime, objects,
decoding, evidence, learning, retention, memory and native support. The root
`test_layout.py` recursively checks core and test imports. Pytest's configured
paths preserve fixture-module names across groups, including stored test loader
entries. Run individual files by their grouped paths or run the complete suite
with the commands above.
