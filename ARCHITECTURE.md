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
| [§1 Types and contracts](theory/01-types-and-contracts.md) | `Contract`, `Terms` | `abi`, `registry` |
| [§2 Planning](theory/02-planning.md) | `Planner`, `Check`, `Terms`, `Unification`, `PatternSearch` | `planner.plan`, `router.infer` |
| [§3 Routing stability](theory/03-routing-stability.md) | `Routing` | `planner.plan_stable` |
| [§4 Compositional reliability](theory/04-compositional-reliability.md) | `Reliability` | |
| [§5 Reliability under distribution shift](theory/05-reliability-under-distribution-shift.md) | `Shift` | `domains.arithmetic.pipeline` |
| [§6 Handwritten-arithmetic pipeline](theory/06-algorithms-of-the-handwritten-arithmetic-pipeline.md) | | `domains.arithmetic.segmenter`, `domains.arithmetic.symbols`, `domains.arithmetic.digit_recognizer`, `domains.arithmetic.operator_recognizer` |
| [§7 Measuring accumulation](theory/07-measuring-accumulation.md) | `Routing` | `domains.arithmetic.accumulation` |
| [§8 Explicit route upgrades](theory/08-explicit-route-upgrades.md) | `Upgrade` | `router.Router`, `router.sign_test` |
| [§9 Module substitution](theory/09-module-substitution.md) | `Substitution` | `domains.arithmetic.substitution` |
| [§10 Complementarity](theory/10-complementarity.md) | | `domains.arithmetic.complementarity` |
| [§11 Evaluation methodology](theory/11-evaluation-methodology.md) | | `domains.arithmetic.expressions`, `stats` |
| [§12 Lazy loading and discovery](theory/12-lazy-loading-and-scalable-discovery.md) | `Loading`, `Pruning`, `Eliminators`, `Eviction` | `loader`, `index`, `planner.plan_stable_indexed`, `registry`, `kernel`, `domains.arithmetic.scaling` |
| [§13 Efficiency](theory/13-efficiency.md) | `Cost`, `MinCost`, `Pareto` | `optimize`, `domains.arithmetic.efficiency`, `workspace` |
| [§14 Kernel-mediated requests](theory/14-kernel-mediated-requests-and-refinement.md) | `Request`, `Cascade`, `Demand`, `Continuation` | `kernel`, `runtime`, `modules.refinement`, `domains.arithmetic.cascade` |
| [§15 Normalization against shift](theory/15-normalization-against-shift.md) | `Normalize` | `domains.arithmetic.normalizer`, `domains.arithmetic.baseline` |
| [§16 Knowing when to be unsure](theory/16-knowing-when-to-be-unsure.md) | `Selective`, `Demand`, `Practice` | `ladder`, `selective`, `domains.arithmetic.practice` |
| [§17 Calibration under shift](theory/17-calibration-under-distribution-shift.md) | `Calibration` | `domains.arithmetic.certify` |
| [§18 Noisy Boolean formulas](theory/18-a-second-domain-noisy-boolean-formulas.md) | `Certificate` | `prefix`, `modules.edit`, `domains.boolean.logic`, `domains.boolean.formulas`, `domains.boolean.words` |
| [§19 Error detection by the format](theory/19-error-detection-by-the-format.md) | `Detection` | `prefix`, `shares`, `domains.boolean.logic`, `domains.boolean.formulas` |
| [§20 Higher-order experts, budgets](theory/20-higher-order-experts-and-budgeted-requests.md) | `Slots`, `Continuation`, `Relevance` | `modules.combinators`, `optimize`, `kernel`, `runtime` |
| [§21 Decoding by the format](theory/21-decoding-by-the-format.md) | `Decoding` | `decoding.decode`, `prefix.PrefixEvaluator` (`decode`), `native.decoding` |
| [§22 Abstaining early](theory/22-abstaining-early.md) | `Detection` | `selective` (`floors`), `prefix.PrefixEvaluator.floor`, `ladder` |
| [§23 Efficient decoding](theory/23-efficient-decoding.md) | `Banding` | `decoding.decode_banded`, `decoding.Split` (references), `native.decoding` (exact passes) |
| [§24 When the prior is wrong](theory/24-when-the-prior-is-wrong.md) | `Misspecification` | not implemented |
| [§25 Climbing order and stopping](theory/25-which-word-to-climb-and-when-to-stop.md) | `Stopping` | `ladder.stopping_rule` |
| [§26 Composing cascades](theory/26-composing-cascades.md) | `Composition` | not implemented |
| [§27 Priors as experts](theory/27-priors-as-experts.md) | `Product`, `Decoding` | `priors.ArityPrior`, `priors.select_prior`, `domains.boolean.words`, `domains.boolean.logic` |
| [§28 Packages as experts](theory/28-packages-as-experts.md) | `Package` | `objects`, `packages`, `cache` |
| [§29 Types as objects](theory/29-types-as-objects.md) | `Refinement` | `objects.Constructor`, `packages.Upcast`, `domains.*.types` |
| [§30 Selection by evidence](theory/30-selection-by-evidence.md) | `Selection`, `Calibration` | `evidence` |
| [§31 Composing uncertainty](theory/31-composing-uncertainty.md) | `Risk`, `Pareto` | `evidence.route_risk`, `evidence.error_bound`, `evidence.rates`, `packages.charge`, `optimize.plan_pareto` |

`prefix.PrefixEvaluator` reads per-position distributions over any
`RankedVocabulary` as a prefix term and evaluates it with semantics the domain
supplies; it carries the certificate, detection, correction and prior accounts
and their floors, so any domain whose answers are terms over a ranked alphabet
gets them by supplying its vocabulary, its semantics and, optionally, its
short-circuit rule. `domains.boolean.words.FormulaEvaluator` is the Boolean
instance. `modules.edit.EditDistanceReader` reads noisy strings against any
vocabulary. Formula data generation lives in `domains.boolean.formulas`; counter
decoding and incremental bands live in `decoding`; weighted automata and prior
selection live in `priors`. Numerical kernels remain in `native/decoding.elisa`,
with Python reference implementations for validation and fallback.

## Layout

`src/nca/` is the generic core: the ABI, planners, index, kernel, runtime,
loader, ladders and selective refinement, statistics, decoding over ranked
alphabets, priors, prefix-term evaluation and its accounts (`prefix`,
`shares`), measured costs (`cost`), the generic library experts in `modules/`
(combinators, request wrappers and the edit-distance reader), and the native
kernels. Nothing
in it names a task, a data set, or a domain type.

`src/nca/domains/` holds the research domains, each a package of its data, its
experts and its experiments: `arithmetic` (handwritten arithmetic and
comparison) and `boolean` (noisy Boolean formulas). A domain depends only on
the core, never on another domain, and the core never imports a domain;
`tests/test_layout.py` enforces both directions. Domains share a type only by
naming the same type identifier, as independently written experts would.

## Theorems

Numbered theorems in the theory chapters and their formal statements in `lean/NCA/`.

| THEORY.md | Lean name | File |
|---|---|---|
| [1.1](theory/01-types-and-contracts.md) | `WellTyped.mono` | `Contract` |
| [1.2](theory/01-types-and-contracts.md) | `WellTyped.subst` | `Terms` |
| [2.1](theory/02-planning.md) | `plan_sound` | `Planner` |
| [2.1](theory/02-planning.md) | `planShallow_sound` | `Routing` |
| [2.2](theory/02-planning.md) | `zero_fuel_nonempty_inputs` | `Planner` |
| [2.2](theory/02-planning.md) | `traverse_singleton` | `Planner` |
| [2.2](theory/02-planning.md) | `zero_fuel_map_children` | `Planner` |
| [2.2](theory/02-planning.md) | `renVar_ne_external`, `renVar_injective` | `PatternSearch` |
| [2.2](theory/02-planning.md) | `subst_ground` | `PatternSearch` |
| [2.2](theory/02-planning.md) | `HTypedSlots.has_filling` | `Slots` |
| [2.2](theory/02-planning.md) | `plan_complete` | `Planner` |
| [2.3](theory/02-planning.md) | `infer_iff` | `Check` |
| [2.4](theory/02-planning.md) | `Contract.subst_determined` | `Terms` |
| [2.5](theory/02-planning.md) | `InstanceOf.subst`, `answer_sound` | `Terms` |
| [2.6](theory/02-planning.md) | `Term.subst_app_ne` | `Terms` |
| [2.7](theory/02-planning.md) | `mgu_exists` | `Unification` |
| [2.8](theory/02-planning.md) | `unifies_eqSubst`, `isMGU_append` | `Unification` |
| [2.9](theory/02-planning.md) | `Skel.sound`, `Skel.complete`, `Skel.most_general` | `PatternSearch` |
| [2.10](theory/02-planning.md) | `SeqMGU.isMGU`, `SeqMGU.exists` | `PatternSearch` |
| [3.1](theory/03-routing-stability.md) | `plan_not_stable` | `Routing` |
| [3.2](theory/03-routing-stability.md) | `planStable_sound` | `Routing` |
| [3.2](theory/03-routing-stability.md) | `planStable_complete` | `Routing` |
| [3.2](theory/03-routing-stability.md) | `planShallow_complete`, `planShallowStable_sound`, `planShallowStable_complete` | `Routing` |
| [3.3](theory/03-routing-stability.md) | `planStable_append` | `Routing` |
| [3.3](theory/03-routing-stability.md) | `planShallowStable_append` | `Routing` |
| [4.1](theory/04-compositional-reliability.md) | `composition_error_le_sum` | `Reliability` |
| [4.2](theory/04-compositional-reliability.md) | `composition_success_ge_prod` | `Reliability` |
| [5.1](theory/05-reliability-under-distribution-shift.md) | `composition_error_le_shifted` | `Shift` |
| [5.2](theory/05-reliability-under-distribution-shift.md) | `offline_rate_insufficient` | `Shift` |
| [5.3](theory/05-reliability-under-distribution-shift.md) | `shift_ge_gap` | `Shift` |
| [8.1](theory/08-explicit-route-upgrades.md) | `route_sound` | `Upgrade` |
| [8.2](theory/08-explicit-route-upgrades.md) | `upgrade_valid` | `Upgrade` |
| [8.3](theory/08-explicit-route-upgrades.md) | `upgrade_target` | `Upgrade` |
| [8.4](theory/08-explicit-route-upgrades.md) | `upgrade_local` | `Upgrade` |
| [8.5](theory/08-explicit-route-upgrades.md) | `upgrade_rollback` | `Upgrade` |
| [8.6](theory/08-explicit-route-upgrades.md) | `route_append` | `Upgrade` |
| [8.7](theory/08-explicit-route-upgrades.md) | `PinsValid.append` | `Upgrade` |
| [9.1](theory/09-module-substitution.md) | `substitution_change_le` | `Substitution` |
| [9.2](theory/09-module-substitution.md) | `accuracy_transfer` | `Substitution` |
| [9.3](theory/09-module-substitution.md) | `substitution_accuracy_ge` | `Substitution` |
| [11](theory/11-evaluation-methodology.md) | `paired_zip_length` | `Calibration` |
| [12.1](theory/12-lazy-loading-and-scalable-discovery.md) | `WellTyped.contracts_subset` | `Loading` |
| [12.2](theory/12-lazy-loading-and-scalable-discovery.md) | `route_contracts_append` | `Loading` |
| [12.3](theory/12-lazy-loading-and-scalable-discovery.md) | `plan_derivable` | `Loading` |
| [12.4](theory/12-lazy-loading-and-scalable-discovery.md) | `Derivable.mono` | `Loading` |
| [12.4](theory/12-lazy-loading-and-scalable-discovery.md) | `plan_mono` | `Loading` |
| [12.5](theory/12-lazy-loading-and-scalable-discovery.md) | `plan_prefix_mono` | `Loading` |
| [12.6](theory/12-lazy-loading-and-scalable-discovery.md) | `planIdx_eq` | `Loading` |
| [12.7](theory/12-lazy-loading-and-scalable-discovery.md) | `planPruned_eq` | `Pruning` |
| [12.8](theory/12-lazy-loading-and-scalable-discovery.md) | `derivable_closure` | `Pruning` |
| [12.9](theory/12-lazy-loading-and-scalable-discovery.md) | `closure_oracle_sound` | `Pruning` |
| [12.10](theory/12-lazy-loading-and-scalable-discovery.md) | `load_lower_bound` | `Eviction` |
| [12.11](theory/12-lazy-loading-and-scalable-discovery.md) | `routeAware_load` | `Eviction` |
| [12.11](theory/12-lazy-loading-and-scalable-discovery.md) | `routeAware_optimal` | `Eviction` |
| [12.12](theory/12-lazy-loading-and-scalable-discovery.md) | `routeAware_switch` | `Eviction` |
| [12.13](theory/12-lazy-loading-and-scalable-discovery.md) | `routeAware_repeat` | `Eviction` |
| [12.15](theory/12-lazy-loading-and-scalable-discovery.md) | `demanded_missing_le` | `Eviction` |
| [12.16](theory/12-lazy-loading-and-scalable-discovery.md) | `pinned_next_fits` | `Eviction` |
| [12.17](theory/12-lazy-loading-and-scalable-discovery.md) | `derivable_seq_source` | `Pruning` |
| [12.18](theory/12-lazy-loading-and-scalable-discovery.md) | `plan_prefix_append` | `Loading` |
| [12.19](theory/12-lazy-loading-and-scalable-discovery.md) | `HTyped.eclosure`, `ECl.trans` | `Eliminators` |
| [12.20](theory/12-lazy-loading-and-scalable-discovery.md) | `HTyped.seq_source` | `Eliminators` |
| [13.1](theory/13-efficiency.md) | `Plan.cost_le_pow` | `Cost` |
| [13.2](theory/13-efficiency.md) | `Plan.cost_linear` | `Cost` |
| [13.3](theory/13-efficiency.md) | `route_cost_append` | `Cost` |
| [13.4](theory/13-efficiency.md) | `planMin_sound` | `MinCost` |
| [13.5](theory/13-efficiency.md) | `planMin_optimal` | `MinCost` |
| [13.6](theory/13-efficiency.md) | `front_cover` | `Pareto` |
| [13.7](theory/13-efficiency.md) | `planPareto_sound` | `Pareto` |
| [13.8](theory/13-efficiency.md) | `planPareto_cover` | `Pareto` |
| [13.9](theory/13-efficiency.md) | `planPareto_within` | `Pareto` |
| [14.1](theory/14-kernel-mediated-requests-and-refinement.md) | `resolve_sound` | `Request` |
| [14.2](theory/14-kernel-mediated-requests-and-refinement.md) | `resolve_avoids` | `Request` |
| [14.3](theory/14-kernel-mediated-requests-and-refinement.md) | `RequestChain.length_le` | `Request` |
| [14.4](theory/14-kernel-mediated-requests-and-refinement.md) | `cascade_error_eq` | `Cascade` |
| [14.5](theory/14-kernel-mediated-requests-and-refinement.md) | `cascade_le_fallback` | `Cascade` |
| [14.6](theory/14-kernel-mediated-requests-and-refinement.md) | `cascade_expected_cost` | `Cascade` |
| [14.7](theory/14-kernel-mediated-requests-and-refinement.md) | `gated_error_le` | `Cascade` |
| [14.8](theory/14-kernel-mediated-requests-and-refinement.md) | `gated_error_eq_of_sound` | `Cascade` |
| [14.9](theory/14-kernel-mediated-requests-and-refinement.md) | `gated_expected_cost` | `Cascade` |
| [14.10](theory/14-kernel-mediated-requests-and-refinement.md) | `DemandSound.comp` | `Demand` |
| [14.11](theory/14-kernel-mediated-requests-and-refinement.md) | `DemandSound.pair` | `Demand` |
| [14.12](theory/14-kernel-mediated-requests-and-refinement.md) | `DemandSound.map` | `Demand` |
| [14.13](theory/14-kernel-mediated-requests-and-refinement.md) | `DemandSound.exact` | `Demand` |
| [14.14](theory/14-kernel-mediated-requests-and-refinement.md) | `Safe.run` | `Continuation` |
| [14.15](theory/14-kernel-mediated-requests-and-refinement.md) | `Safe.bind` | `Continuation` |
| [14.16](theory/14-kernel-mediated-requests-and-refinement.md) | `Depth.run_le` | `Continuation` |
| [14.17](theory/14-kernel-mediated-requests-and-refinement.md) | `Depth.bind` | `Continuation` |
| [14.18](theory/14-kernel-mediated-requests-and-refinement.md) | `positive_scale_preserves_maximum`, `zero_scale_collapses_order` | `Demand` |
| [15.1](theory/15-normalization-against-shift.md) | `ShiftBound.map` | `Normalize` |
| [15.2](theory/15-normalization-against-shift.md) | `shift_le_of_invariant_on` | `Normalize` |
| [15.3](theory/15-normalization-against-shift.md) | `shift_zero_of_invariant` | `Normalize` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `selective_risk_le`, `selective_risk_le_available`, `upper_fold_ge` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `positive_alternative_risk` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `positive_observation_floor` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `observation_weight_sum_positive` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `collapsed_pair_cannot_choose_both` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `original_value_distinguishes` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `monotone_normalized_rank`, `batched_monotone_normalized_rank`, `ranked_tie_keeps_first`, `integer_shift_preserves_order`, `rowwise_shift_order`, `exp_shift_ratio`, `ranked_restriction_ext`, `calibration_subset_membership`, `calibration_subset_empty`, `calibration_matrix_restriction_ext`, `grouped_normalization`, `batched_group_mass_ext`, `batched_group_risk_bounds`, `calibrated_difference_rescale`, `grouped_negative_log_likelihood` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `asymmetric_group_risk` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `grouped_selection_risk_difference` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `unsigned_bitpattern_order` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `average_calibrated_difference` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `singleton_target_normalizer` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `target_maximum_unit_weight` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `calibration_relabel_normalization` | `Selective` |
| [16.1](theory/16-knowing-when-to-be-unsure.md) | `positive_target_group_nonempty` | `Selective` |
| [16.2](theory/16-knowing-when-to-be-unsure.md) | `threshold_optimal` | `Selective` |
| [16.3](theory/16-knowing-when-to-be-unsure.md) | `bound_ge_floor` | `Selective` |
| [16.3](theory/16-knowing-when-to-be-unsure.md) | `length_limit` | `Selective` |
| [16.4](theory/16-knowing-when-to-be-unsure.md) | `restricted_risk_le`, `zero_total_no_positive_entry`, `risk_scale_invariant` | `Selective` |
| [16.5](theory/16-knowing-when-to-be-unsure.md) | `queued_value` | `Practice` |
| [16.6](theory/16-knowing-when-to-be-unsure.md) | `unqueued_errors` | `Practice` |
| [16.7](theory/16-knowing-when-to-be-unsure.md) | `queued_captures` | `Practice` |
| [16.8](theory/16-knowing-when-to-be-unsure.md) | `proportional_value` | `Practice` |
| [17.1](theory/17-calibration-under-distribution-shift.md) | `selective_risk_le_excess` | `Calibration` |
| [17.2](theory/17-calibration-under-distribution-shift.md) | `shift_ratio_le` | `Calibration` |
| [17.3](theory/17-calibration-under-distribution-shift.md) | `horvitz_thompson` | `Calibration` |
| [17.4](theory/17-calibration-under-distribution-shift.md) | `inflated_answered_mono` | `Calibration` |
| [17.8](theory/17-calibration-under-distribution-shift.md) | `threshold_trace_prefix` | `Calibration` |
| [17.9](theory/17-calibration-under-distribution-shift.md) | `audit_family_le` | `Calibration` |
| [17.7](theory/17-calibration-under-distribution-shift.md) | `audit_rejection_of_completion` | `Calibration` |
| [17.6](theory/17-calibration-under-distribution-shift.md) | `audit_budget_obstruction` | `Calibration` |
| [17.6](theory/17-calibration-under-distribution-shift.md) | `audit_cdf_upper_refutes`, `audit_cdf_lower_proves` | `Calibration` |
| [17.5](theory/17-calibration-under-distribution-shift.md) | `fixed_sequence_le` | `Calibration` |
| [18.1](theory/18-a-second-domain-noisy-boolean-formulas.md) | `grouped_risk_le` | `Certificate` |
| [18.1](theory/18-a-second-domain-noisy-boolean-formulas.md) | `risk_as_alternative_mass` | `Selective` |
| [18.1](theory/18-a-second-domain-noisy-boolean-formulas.md) | `osa_symmetric` | `Edit` |
| [18.1](theory/18-a-second-domain-noisy-boolean-formulas.md) | `osa_empty_left`, `osa_empty_right` | `Edit` |
| [18.1](theory/18-a-second-domain-noisy-boolean-formulas.md) | `osa_self` | `Edit` |
| [18.2](theory/18-a-second-domain-noisy-boolean-formulas.md) | `certificate_error_le` | `Certificate` |
| [18.2](theory/18-a-second-domain-noisy-boolean-formulas.md) | `certificate_error_le_support` | `Certificate` |
| [18.3](theory/18-a-second-domain-noisy-boolean-formulas.md) | `cert_sound` | `Certificate` |
| [18.4](theory/18-a-second-domain-noisy-boolean-formulas.md) | `bestCert_valid` | `Certificate` |
| [18.4](theory/18-a-second-domain-noisy-boolean-formulas.md) | `bestCert_le` | `Certificate` |
| [18.5](theory/18-a-second-domain-noisy-boolean-formulas.md) | `bestCert_le_full` | `Certificate` |
| [18.6](theory/18-a-second-domain-noisy-boolean-formulas.md) | `code_prefix` | `Certificate` |
| [18.7](theory/18-a-second-domain-noisy-boolean-formulas.md) | `alternating_cert_leaves` | `Certificate` |
| [19.1](theory/19-error-detection-by-the-format.md) | `code_sum` | `Detection` |
| [19.2](theory/19-error-detection-by-the-format.md) | `code_no_single_change` | `Detection` |
| [19.3](theory/19-error-detection-by-the-format.md) | `detected_error_le` | `Detection` |
| [19.4](theory/19-error-detection-by-the-format.md) | `joint_le_restricted` | `Detection` |
| [19.5](theory/19-error-detection-by-the-format.md) | `two_occur_le_half` | `Detection` |
| [19.6](theory/19-error-detection-by-the-format.md) | `two_occur_le_pairs` | `Detection` |
| [19.6](theory/19-error-detection-by-the-format.md) | `pair_share_prefix_suffix_upper` | `Detection` |
| [19.6](theory/19-error-detection-by-the-format.md) | `detection_share_combine_upper` | `Detection` |
| [20.1](theory/20-higher-order-experts-and-budgeted-requests.md) | `HTyped.mono` | `Slots` |
| [20.2](theory/20-higher-order-experts-and-budgeted-requests.md) | `embed_wellTyped` | `Slots` |
| [20.3](theory/20-higher-order-experts-and-budgeted-requests.md) | `HPlan.cost_le_pow` | `Slots` |
| [20.4](theory/20-higher-order-experts-and-budgeted-requests.md) | `HPlan.cost_mono` | `Slots` |
| [20.5](theory/20-higher-order-experts-and-budgeted-requests.md) | `serve_sound` | `Continuation` |
| [20.6](theory/20-higher-order-experts-and-budgeted-requests.md) | `serve_spent` | `Continuation` |
| [20.7](theory/20-higher-order-experts-and-budgeted-requests.md) | `Prog.runB_le` | `Continuation` |
| [20.8](theory/20-higher-order-experts-and-budgeted-requests.md) | `choice_cost_le` | `Slots` |
| [20.9](theory/20-higher-order-experts-and-budgeted-requests.md) | `PTyped.erase`, `WellTyped.positional` | `Relevance` |
| [20.10](theory/20-higher-order-experts-and-budgeted-requests.md) | `PPlan.uses_apply`, `PPlan.given_not_relevant`, `PTyped.uses_lt` | `Relevance` |
| [21.1](theory/21-decoding-by-the-format.md) | `await_code` | `Decoding` |
| [21.2](theory/21-decoding-by-the-format.md) | `code_accepted` | `Decoding` |
| [21.3](theory/21-decoding-by-the-format.md) | `accepts_iff_codes` | `Decoding` |
| [21.3](theory/21-decoding-by-the-format.md) | `await_balance`, `accepted_arity_sum`, `accepted_arity_lt_length` | `Decoding` |
| [21.4](theory/21-decoding-by-the-format.md) | `dpSum_eq` | `Decoding` |
| [21.5](theory/21-decoding-by-the-format.md) | `dpMax_ge` | `Decoding` |
| [21.6](theory/21-decoding-by-the-format.md) | `dpMax_attained`, `tiedChoice_eq_min`, `tiedChoice_comm`, `arity_exceeds_state_bound`, `completion_transition_bound`, `counter_growth_bound`, `foldl_await_zero_nonempty` | `Decoding` |
| [21.7](theory/21-decoding-by-the-format.md) | `exact_risk_le_union` | `Decoding` |
| [21.7](theory/21-decoding-by-the-format.md) | `one_sub_prod_le_sum` | `Decoding` |
| [22.1](theory/22-abstaining-early.md) | `detection_account_mono` | `Detection` |
| [22.3](theory/22-abstaining-early.md) | `lower_fold_le` | `Selective` |
| [22.4](theory/22-abstaining-early.md) | `committed_continuation_preferred` | `Stopping` |
| [22.4](theory/22-abstaining-early.md) | `firstStoppingState_append` | `Stopping` |
| [22.4](theory/22-abstaining-early.md) | `positive_target_preserves_order` | `Stopping` |
| [23.1](theory/23-efficient-decoding.md) | `tail_le_esym` | `Banding` |
| [23.2](theory/23-efficient-decoding.md) | `factorial_mul_esym_le` | `Banding` |
| [23.3](theory/23-efficient-decoding.md) | `outside_le_tail`, `diff_le_reference_length`, `tail_above_length`, `tail_row_scale`, `row_mass_partition`, `anchored_exp_mass`, `rowFactor_normalizes`, `tail_le_row_factors`, `row_summary_append` | `Banding` |
| [23.3](theory/23-efficient-decoding.md) | `bandPolynomial_recurrence`, `bandPolynomial_threshold_suffix`, `threshold_search_step`, `threshold_search_shrinks`, `searchGap_i64`, `threshold_search_adjacent` | `BandSearch` |
| [23.4](theory/23-efficient-decoding.md) | `sum_sub_le_diff`, `sum_sub_le_diff_bounded`, `band_covers_interval`, `ragged_band_storage_covers` | `Banding` |
| [23.4](theory/23-efficient-decoding.md) | `sum_filter_support`, `max_filter_support`, `support_shift_bounds`, `split_support_intersection`, `trace_predecessor_monotone`, `trace_successor_monotone`, `ordered_arity_exceeds_envelope`, `scoredChoice_comm`, `scoredChoice_assoc` | `Decoding` |
| [23.5](theory/23-efficient-decoding.md) | `banded_risk_le` | `Banding` |
| [23.6](theory/23-efficient-decoding.md) | `banded_risk_slack` | `Banding` |
| [23.7](theory/23-efficient-decoding.md) | `dpSum_append` | `Banding` |
| [23.8](theory/23-efficient-decoding.md) | `dpMax_append` | `Banding` |
| [23.9](theory/23-efficient-decoding.md) | `sum_pair_dist` | `Banding` |
| [23.10](theory/23-efficient-decoding.md) | `stitch_attains` | `Banding` |
| [23.15](theory/23-efficient-decoding.md) | `cache_lookup_correct`, `cache_evict_sound`, `cache_store_sound` | `Selective` |
| [23.14](theory/23-efficient-decoding.md) | `sum_row_shift`, `row_shift_order` | `Selective` |
| [23.13](theory/23-efficient-decoding.md) | `selective_risk_le_approx`, `threshold_stable` | `Selective` |
| [23.12](theory/23-efficient-decoding.md) | `revision_cache_eq` | `Selective` |
| [23.11](theory/23-efficient-decoding.md) | `priority_allocation_sum`, `priority_allocation_nonneg`, `priority_allocation_cover` | `Selective` |
| [24.1](theory/24-when-the-prior-is-wrong.md) | `reweighted_odds` | `Misspecification` |
| [24.2](theory/24-when-the-prior-is-wrong.md) | `reweighted_risk_le` | `Misspecification` |
| [24.3](theory/24-when-the-prior-is-wrong.md) | `reweighted_risk_le_mul` | `Misspecification` |
| [24.4](theory/24-when-the-prior-is-wrong.md) | `dominated_risk_le` | `Misspecification` |
| [24.5](theory/24-when-the-prior-is-wrong.md) | `adversarial_prior` | `Misspecification` |
| [25.1](theory/25-which-word-to-climb-and-when-to-stop.md) | `cost_ge_of_ratio` | `Stopping` |
| [25.1](theory/25-which-word-to-climb-and-when-to-stop.md) | `fractional_ratio_bound_strict` | `Stopping` |
| [25.1](theory/25-which-word-to-climb-and-when-to-stop.md) | `selective_risk_le_selected` | `Selective` |
| [25.1](theory/25-which-word-to-climb-and-when-to-stop.md) | `charge_cost_ratio_order` | `Stopping` |
| [25.2](theory/25-which-word-to-climb-and-when-to-stop.md) | `pairs_ge_count` | `Stopping` |
| [25.3](theory/25-which-word-to-climb-and-when-to-stop.md) | `lookahead_stop_optimal` | `Stopping` |
| [25.4](theory/25-which-word-to-climb-and-when-to-stop.md) | `lookahead_continue_better` | `Stopping` |
| [25.4](theory/25-which-word-to-climb-and-when-to-stop.md) | `split_bin_gain_nonneg` | `Stopping` |
| [25.5](theory/25-which-word-to-climb-and-when-to-stop.md) | `single_climb_account` | `Stopping` |
| [26.1](theory/26-composing-cascades.md) | `fallback_cost_eq` | `Composition` |
| [26.2](theory/26-composing-cascades.md) | `fallback_cost_conditional` | `Composition` |
| [26.3](theory/26-composing-cascades.md) | `fallback_cost_sub_independent` | `Composition` |
| [26.4](theory/26-composing-cascades.md) | `fallback_cost_ge_independent` | `Composition` |
| [26.5](theory/26-composing-cascades.md) | `chain_error_eq` | `Composition` |
| [26.6](theory/26-composing-cascades.md) | `chain_cost_eq` | `Composition` |
| [26.7](theory/26-composing-cascades.md) | `split_error_eq` | `Composition` |
| [26.8](theory/26-composing-cascades.md) | `argmin_within` | `Composition` |
| [26.9](theory/26-composing-cascades.md) | `some_deviates_le` | `Composition` |
| [27.1](theory/27-priors-as-experts.md) | `pdpSum_eq` | `Product` |
| [27.2](theory/27-priors-as-experts.md) | `pdpMax_ge` | `Product` |
| [27.3](theory/27-priors-as-experts.md) | `pdpMax_attained` | `Product` |
| [27.4](theory/27-priors-as-experts.md) | `pdpSum_unit` | `Product` |
| [27.5](theory/27-priors-as-experts.md) | `complete_shape_length` | `Decoding` |
| [27.6](theory/27-priors-as-experts.md) | `prior_support_sum`, `prior_support_max`, `prior_step_zero_outside`, `prior_prune_zero_readings`, `pdpSum_zero_row`, `pdpMax_zero_row`, `partitionCompose_zero_left` | `Product` |
| [27.7](theory/27-priors-as-experts.md) | `bounded_shape_length`, `complete_shape_bounded` | `Decoding` |
| [27.8](theory/27-priors-as-experts.md) | `prior_evidence_identity` | `Product` |
| [27.9](theory/27-priors-as-experts.md) | `prior_selection_regret`, `prior_selection_half_gap` | `Product` |
| [27.10](theory/27-priors-as-experts.md) | `clipped_evidence_bounds`, `clipped_error_bound_mono` (concentration not formalized) | `Product` |
| [27.11](theory/27-priors-as-experts.md) | `selected_audit_failure_le` (conditional finite mixture) | `Product` |
| [27.12](theory/27-priors-as-experts.md) | `partial_evidence_bounds` (bounded range for optional scores) | `Product` |
| [27.15](theory/27-priors-as-experts.md) | `prior_empty`, `prior_empty_normalized` | `Product` |
| [27.16](theory/27-priors-as-experts.md) | `risk_from_other_mass`, `partition_risk_common_factor`, `prior_common_factors`, `equal_positive_mass_increases`, `two_sum_residual_identity`, `compensated_evidence_step` | `Product` |
| [27.17](theory/27-priors-as-experts.md) | `partitionCompose_assoc`, `partitionCompose_identity`, `partitionCompose_nonneg` | `Product` |
| [27.18](theory/27-priors-as-experts.md) | `partitionBoundary_total`, `partitionBoundary_nonneg`, `partitionBoundary_assoc`, `partitionBoundary_identity` | `Product` |
| [27.19](theory/27-priors-as-experts.md) | `partition_prefix_reuse` | `Product` |
| [28.1](theory/28-packages-as-experts.md) | `Pkg.flattenList_append` | `Package` |
| [28.2](theory/28-packages-as-experts.md) | `install_stable` | `Package` |
| [28.3](theory/28-packages-as-experts.md) | `WellTyped.inline` (via `WellTyped.instantiate`, `lookupArg_typed`) | `Package` |
| [28.4](theory/28-packages-as-experts.md) | `cache_lookup_correct`, `cache_store_sound`, `cache_evict_sound` | `Selective` |
| [29.1](theory/29-types-as-objects.md) | `WellTypedSub.coerce` | `Refinement` |
| [29.2](theory/29-types-as-objects.md) | `Plan.eval_erase` | `Refinement` |
| [29.3](theory/29-types-as-objects.md) | `planShallowStable_append` (for the stability half) | `Routing` |
| [30.1](theory/30-selection-by-evidence.md) | `audit_family_le` (the union bound; the sign test's validity is assumed) | `Calibration` |
| [30.2](theory/30-selection-by-evidence.md) | `plan_rename`, `planShallow_rename`, `planShallowStable_rename`, `WellTyped.rename` | `Selection` |
| [31.1](theory/31-composing-uncertainty.md) | `risk_le_expected_failures` | `Risk` |
| [31.2](theory/31-composing-uncertainty.md) | `expected_failures_eq`, `risk_le_charges` | `Risk` |

## Native kernels

`src/nca/native/` holds optional kernels written in Elisa and built as CPython
extensions with `python -m nca.native` (needs `elisac-stage1`). Each has a
NumPy reference that gives the same results within rounding and is used when
the kernel is not built or `NCA_NATIVE=0`. Kernels that only a domain needs
live beside that domain's code (`domains/boolean/kernels.elisa`) and are
built by the same command. `decoding.elisa` runs the exact
passes of §21.4 in linear space with per-row rescaling (THEORY §23.7).
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
the runtime uses for message types. `index.ProducerIndex` keeps polymorphic producers
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

`NCA.Skel` (`lean/NCA/PatternSearch.lean`) models a plan skeleton and its
equations, with each node's variables renamed by its path, as
`index.rename_apart` does with fresh tags. Each input pattern the search
unifies with a candidate's output is one equation of `Skel.eqs`, solved in
search order with the bindings found so far applied, as in `SeqMGU`.

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

`NCA.ECl` (`lean/NCA/Eliminators.lean`) models this closure over plans of
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

Available inputs are addressed by position where types do not tell them
apart (THEORY §20.8): `planner.Given` carries an optional `position`, the
runtime binds slot and request inputs as an ordered list, and
`router.infer` checks that a position holds the named type. `NCA.PPlan`
(`lean/NCA/Relevance.lean`) models positional plans. `abi.Contract.relevant`
lists, per slot, the inputs every filling must use; `Fold` declares both
inputs of its step. `planner.uses` computes the positions a plan reads, and
`router.infer` rejects a filling that misses a relevant one. The planner and
the cost planners carry a set of required positions with every sub-goal:
an input meets it only if it is the one required, an application divides it
among its arguments (`planner.assignments`, spread-out divisions first), and
a `map` passes it to its source. `plan`, `plan_min` and `plan_pareto` accept
a requirement on the task's own inputs.

## 5. Reliability under distribution shift

`nca.domains.arithmetic.pipeline` reports, per recognizer, the excess of in-situ over offline
failure rate: the lower bound on induced shift of `shift_ge_gap`.

## 6. Algorithms of the handwritten-arithmetic pipeline

**Segmentation** (`nca.domains.arithmetic.segmenter`). Ink columns (intensity > 0.1) are
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

The add-and-freeze runner (`nca.domains.arithmetic.accumulation`) checks the stability theorem
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
is not sound (a digit misjudged as an operator is skipped); `nca.domains.arithmetic.cascade`
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

**Normalizer** (`nca.domains.arithmetic.normalizer.GlyphNormalizer`, contract
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

**Practice** (`nca.domains.arithmetic.practice`). Practice is offline. A copy of the recognizer
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

The Boolean domain's own native module, `domains.boolean.kernels`, exports
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
entire checking budget. `domains.boolean.logic.shifted` skips candidate fit/check evaluations
when even that bound exceeds the target. The uncontrolled evaluation remains
unchanged, and feasible audit budgets use the existing fixed-sequence test.
The Lean obstruction theorem covers the zero-error power inequality; the
binomial bound's monotonicity in errors is used as its standard statistical
property, not newly formalized here.

For feasible audit budgets, `domains.boolean.logic.shifted` computes checking outcomes lazily
in the fit-half-determined order. It stops at the first rejected candidate
and chooses maximum coverage only among the accepted prefix. Fit-half
candidate evaluation remains complete, and the order never changes in
response to checking labels. This implements §17.5's existing stopping rule.

Checking calls to `domains.boolean.logic.outcomes` pass `reject_above` and `alpha`. After a
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

`domains.boolean.logic.outcomes_many` accumulates fit-half answer/error counts from
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

`domains.boolean.words.CompleteTreePrior` exposes the independent contract
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

`objects` holds the content-addressed object model: `Primitive`, `Composite`
and `Attestation`, each identified by the SHA-256 digest of its canonical
JSON (`canonical`, `digest`). A primitive loads by calling its `entry` with
JSON `arguments` and checks that the loaded manifest equals the declared one;
`weights` carries the digest of the bytes it loads (`file_digest`). `Store`
admits a composite only after its members and only when its declared effects
cover theirs, keeps attestations by subject, and saves one canonical file per
object, rechecking digests on `open`. `Names` maps mutable names to
references. Manifests declare `effects` (`None`: undeclared; empty: pure).

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

`domains.arithmetic.package.arithmetic` is the first real package: the
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
(`domains.arithmetic.package.arithmetic`) and `nca.formulas`
(`domains.boolean.package.formulas`: tokenizer and formula evaluator, with
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
(`domains.arithmetic.types`, `domains.boolean.types`); its modules take their
type ids from them, and its package puts them into the store as members, so
installing a package brings its types. `tests/test_layout.py` checks that
every contract of a discovered package names only constructor objects or the
core's `seq`, `pair`, `either` and `unit`. Domains share a type by stating
its constructor with identical contents, which gives it one reference: both
domains state the same `BOOLEAN`, and a test checks that their references
agree.

## 30. Selection by evidence

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
