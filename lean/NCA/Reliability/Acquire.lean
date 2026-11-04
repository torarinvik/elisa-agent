import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Data.Finset.Max
import Mathlib.Data.List.Count
import Mathlib.Tactic.Linarith

/-!
# Promoting a trained challenger

A challenger trained on a part `T` of the data and tested on an
independent part `E` is fixed before `E` is seen. If a test rejects with
probability at most `α` for every fixed challenger, it rejects with
probability at most `α` for the trained one (`split_test_le`).
-/

open Finset

namespace NCA

variable {T E C : Type*} [Fintype T] [Fintype E]

/-- **Split promotion** (Theorem 36.1). On the product of independent
weighted parts, a test whose rejection probability is at most `α` for
every fixed challenger keeps that bound for a challenger `train t`
computed from the training part alone. -/
theorem split_test_le (p : T → ℝ) (q : E → ℝ) (hp : ∀ t, 0 ≤ p t) (hsum : ∑ t, p t = 1)
    (train : T → C) (reject : C → E → Prop) [∀ c e, Decidable (reject c e)] {α : ℝ}
    (hα : ∀ c, ∑ e ∈ univ.filter (reject c), q e ≤ α) :
    ∑ t, p t * ∑ e ∈ univ.filter (reject (train t)), q e ≤ α := by
  calc ∑ t, p t * ∑ e ∈ univ.filter (reject (train t)), q e ≤ ∑ t, p t * α :=
        Finset.sum_le_sum fun t _ => mul_le_mul_of_nonneg_left (hα (train t)) (hp t)
    _ = α := by rw [← Finset.sum_mul, hsum, one_mul]

end NCA

namespace NCA

/-- Budget-sum step for a finite family of training-only proposals. -/
theorem proposal_budget_le {I : Type*} (family : Finset I) (mass budget : I → ℝ)
    (alpha : ℝ) (each : ∀ i ∈ family, mass i ≤ budget i)
    (total : ∑ i ∈ family, budget i ≤ alpha) :
    ∑ i ∈ family, mass i ≤ alpha := by
  exact (Finset.sum_le_sum each).trans total

/-- Reloading a candidate preserves its scored outcomes if it preserves its
function. This assumes executable equivalence; a digest alone does not prove it. -/
theorem reloaded_outcomes_eq {X Y L : Type*} (before after : X → Y)
    (score : Y → L → Bool) (samples : List (X × L))
    (same : ∀ x, before x = after x) :
    samples.map (fun row => score (before row.1) row.2) =
      samples.map (fun row => score (after row.1) row.2) := by
  simp_rw [same]

/-- Empirical optimality of a modal decoder on a fixed finite representation.
The hypothesis states that each chosen label has maximal training count. -/
theorem modal_decoder_optimal {K L : Type*} (keys : Finset K)
    (count : K → L → ℕ) (mode alternative : K → L)
    (maximal : ∀ k ∈ keys, ∀ label, count k label ≤ count k (mode k)) :
    ∑ k ∈ keys, count k (alternative k) ≤ ∑ k ∈ keys, count k (mode k) := by
  exact Finset.sum_le_sum fun k hk => maximal k hk (alternative k)

/-- An exact finite contingency-table score; no label ordering or meaning. -/
def empiricalModalScore {K L : Type*} (keys : Finset K) (labels : Finset L)
    (count : K → L → ℕ) : ℕ :=
  ∑ k ∈ keys, labels.sup (count k)

theorem empiricalModalScore_counts {K L : Type*} (keys : Finset K) (labels : Finset L)
    (before after : K → L → ℕ) (faithful : ∀ k l, before k l = after k l) :
    empiricalModalScore keys labels before = empiricalModalScore keys labels after := by
  have same : before = after := funext fun k => funext (faithful k)
  rw [same]

/-- Sorting observations preserves the exact empirical score. Native sorting
and injective identifier transport must still preserve these multiplicities. -/
theorem empiricalModalScore_perm {K L : Type*} [DecidableEq K] [DecidableEq L]
    (keys : Finset K) (labels : Finset L) (before after : List (K × L))
    (reorder : before.Perm after) :
    empiricalModalScore keys labels (fun k l => before.count (k, l)) =
      empiricalModalScore keys labels (fun k l => after.count (k, l)) := by
  apply empiricalModalScore_counts
  intro k l
  exact reorder.count_eq (k, l)

theorem empirical_identifier_count {A I : Type*} [DecidableEq A] [DecidableEq I]
    (pairs : List A) (name : A → I) (injective : Function.Injective name) (pair : A) :
    (pairs.map name).count (name pair) = pairs.count pair :=
  List.count_map_of_injective pairs name injective pair

/-- A decoder on the first component is also a decoder on the joint
representation, with exactly the same predictions (Proposition 36.5). -/
theorem joint_decoder_simulates {X A B Y : Type*}
    (f : X → A) (g : X → B) (d : A → Y) :
    (fun x => (fun ab : A × B => d ab.1) (f x, g x)) = (fun x => d (f x)) := by
  rfl

/-- Refining a modal leaf cannot lose empirical successes: each child can
retain the parent's label, and its mode does at least as well. -/
theorem modal_refinement_le {K L : Type*} (children : Finset K)
    (count : K → L → ℕ) (parent : L) (mode : K → L)
    (maximal : ∀ k ∈ children, count k parent ≤ count k (mode k)) :
    ∑ k ∈ children, count k parent ≤ ∑ k ∈ children, count k (mode k) := by
  exact Finset.sum_le_sum maximal

/-- Complete policy-set inclusion orders attainable training-score maxima.
This premise need not hold when a projection work budget is exhausted. -/
theorem lookahead_score_mono (shallow deep : Finset ℕ) (included : shallow ⊆ deep) :
    shallow.max ≤ deep.max := by
  exact Finset.max_mono included

/-- Factoring every stopping state, including fallback states, preserves
predictions whenever decoding each state code returns its chosen label. -/
theorem state_factorization_eq {X N S Y : Type*} (visit : X → N)
    (chosen : N → Y) (code : N → S) (head : S → Y)
    (decodes : ∀ n, head (code n) = chosen n) :
    (fun x => head (code (visit x))) = (fun x => chosen (visit x)) := by
  funext x
  exact decodes (visit x)

/-- Structural pair reconstruction follows from faithful component codecs.
This is the componentwise special case, not verification of the Python codec. -/
theorem pair_codec_roundtrip {A B U V : Type*} (ea : A → U) (da : U → A)
    (eb : B → V) (db : V → B) (ha : ∀ a, da (ea a) = a)
    (hb : ∀ b, db (eb b) = b) (a : A) (b : B) :
    (da (ea a), db (eb b)) = (a, b) := by
  rw [ha, hb]

/-- Choosing a local correction only when it improves cannot reduce the
sum of empirical successes. This asserts nothing about held-out samples. -/
theorem residual_successes_le {K : Type*} (groups : Finset K)
    (baseline mode : K → ℕ) :
    ∑ k ∈ groups, baseline k ≤ ∑ k ∈ groups, max (baseline k) (mode k) := by
  exact Finset.sum_le_sum fun k _ => Nat.le_max_left _ _

/-- A complete finite threshold-score search dominates every candidate.
Membership/completeness of the executable sweep remains a premise. -/
theorem threshold_score_le (scores : Finset ℕ) (candidate : ℕ) (member : candidate ∈ scores) :
    candidate ≤ scores.max' ⟨candidate, member⟩ := by
  exact Finset.le_max' scores candidate member

/-- Perfect paired alignment suffices for agreement after any consumer.
This premise is not proved for an empirically learned adapter. -/
theorem adapter_composition_eq {X A B Y : Type*} (source : X → A) (teacher : X → B)
    (adapter : A → B) (consumer : B → Y)
    (aligned : ∀ x, adapter (source x) = teacher x) :
    (fun x => consumer (adapter (source x))) = (fun x => consumer (teacher x)) := by
  funext x
  exact congrArg consumer (aligned x)

/-- Ideal centered least squares: the normal equation gives the minimum
of the scalar quadratic. This is not a floating-point implementation proof. -/
theorem affine_slope_optimal (xx xy estimate other : ℝ) (nonneg : 0 ≤ xx)
    (normal : xx * estimate = xy) :
    xx * estimate ^ 2 - 2 * xy * estimate ≤ xx * other ^ 2 - 2 * xy * other := by
  have h := mul_nonneg nonneg (sq_nonneg (other - estimate))
  rw [← normal]
  nlinarith

/-- Coordinatewise alignment suffices for downstream agreement. It is a premise,
not a claim that finite least-squares training recovers all future vectors. -/
theorem vector_adapter_composition_eq {X A Y I : Type*} (source : X → A)
    (teacher : X → I → ℝ) (adapter : A → I → ℝ) (consumer : (I → ℝ) → Y)
    (aligned : ∀ x i, adapter (source x) i = teacher x i) :
    (fun x => consumer (adapter (source x))) = (fun x => consumer (teacher x)) := by
  apply adapter_composition_eq
  intro x
  funext i
  exact aligned x i

/-- A centroid-difference direction separates its two prototypes by their
squared distance. This is not a separability claim for the training classes. -/
theorem projection_prototype_gap {I : Type*} (indices : Finset I) (a b : I → ℝ) :
    (∑ i ∈ indices, (b i - a i) * b i) -
      (∑ i ∈ indices, (b i - a i) * a i) =
      ∑ i ∈ indices, (b i - a i) ^ 2 := by
  rw [← Finset.sum_sub_distrib]
  apply Finset.sum_congr rfl
  intro i _
  nlinarith

/-- A quadratic interaction separates symmetric prototype classes with equal
original centroids. This is an expressivity witness, not learned recovery. -/
theorem symmetric_interaction_gap (a b : ℝ) (ha : 0 < a) (hb : 0 < b) :
    (a * b + (-a) * (-b)) / 2 - (a * (-b) + (-a) * b) / 2 = 2 * a * b ∧
    0 < 2 * a * b := by
  have h := mul_pos ha hb
  constructor <;> nlinarith

/-- Moving a threshold inside an empty observed gap preserves outside comparisons. -/
theorem gap_boundary_preserves (lower upper threshold x : ℝ)
    (admitted : lower < threshold ∧ threshold ≤ upper)
    (outside : x ≤ lower ∨ upper ≤ x) :
    (threshold ≤ x) ↔ (upper ≤ x) := by
  constructor
  · intro h
    rcases outside with left | right
    · exfalso
      linarith [admitted.1]
    · exact right
  · exact fun h => le_trans admitted.2 h

/-- The exact real midpoint is admissible; this does not verify float rounding. -/
theorem midpoint_inside_gap (lower upper : ℝ) (gap : lower < upper) :
    lower < lower / 2 + upper / 2 ∧ lower / 2 + upper / 2 ≤ upper := by
  constructor <;> linarith

/-- Reusing pure training observations preserves projection values. Determinism
of an external executable measurement is an assumption, not verified here. -/
theorem training_projection_fusion {X V Y : Type*} (rows : List X)
    (measure : X → V) (project : V → Y) :
    (rows.map measure).map project = rows.map (fun x => project (measure x)) := by
  simp only [List.map_map, Function.comp_def]

/-- An ordered real multiplication loop evaluates the product. This does not
verify packed offsets, IEEE behavior, compiler output, or the Python FFI. -/
theorem ordered_product_fold (values : List ℝ) (acc : ℝ) :
    values.foldl (fun a x => a * x) acc = acc * values.prod := by
  induction values generalizing acc with
  | nil => simp
  | cons x xs ih => simp [List.foldl_cons, List.prod_cons, ih, mul_assoc]

/-- A strongest simple case of faithful chain restoration: corresponding
endomorphisms agree everywhere, so their ordered executions agree. -/
theorem restored_chain_eq {X : Type*} (before after : List (X → X))
    (faithful : List.Forall₂ (fun f g => ∀ x, f x = g x) before after) (value : X) :
    before.foldl (fun x f => f x) value = after.foldl (fun x f => f x) value := by
  induction faithful generalizing value with
  | nil => rfl
  | cons same rest ih =>
    simp only [List.foldl_cons]
    rw [same value]
    exact ih _

/-- Pure regional replacement preserves every output outside the chosen region.
This does not assert that effectful routing leaves executions unchanged. -/
theorem regional_preserves_complement {X Y K : Type*} [DecidableEq K]
    (incumbent specialist : X → Y) (feature : X → K) (key : K) (x : X)
    (outside : feature x ≠ key) :
    (if feature x = key then specialist x else incumbent x) = incumbent x := by
  simp only [outside, if_false]

/-- Conditional training coverage only: a perfectly aligned failure router
covers every failed training row, with no held-out guarantee. -/
theorem failure_partition_covers {X : Type*} (rows : List X) (route success : X → Bool)
    (aligned : ∀ x ∈ rows, route x = !(success x)) (x : X) (member : x ∈ rows)
    (failed : success x = false) : route x = true := by
  simpa [failed] using aligned x member

/-- Splitting a binary histogram cannot reduce attainable empirical successes.
This does not assert optimal future cuts or executable histogram correctness. -/
theorem binary_modal_split_le (a b c d : ℕ) :
    max (a + c) (b + d) ≤ max a b + max c d := by
  apply max_le
  · exact Nat.add_le_add (le_max_left _ _) (le_max_left _ _)
  · exact Nat.add_le_add (le_max_right _ _) (le_max_right _ _)

/-- Regional restoration is faithful conditional on matching routing/branches
and an unchanged key. Codecs, effects and executable factories are unproved. -/
theorem regional_reloaded_eq {X Y K : Type*} [DecidableEq K]
    (inc0 inc1 spec0 spec1 : X → Y) (route0 route1 : X → K) (key : K)
    (hi : ∀ x, inc0 x = inc1 x) (hs : ∀ x, spec0 x = spec1 x)
    (hr : ∀ x, route0 x = route1 x) :
    (fun x => if route0 x = key then spec0 x else inc0 x) =
      (fun x => if route1 x = key then spec1 x else inc1 x) := by
  funext x
  rw [hr x, hs x, hi x]

/-- A pure regional policy preserves incumbent output for keys without an expert.
No empirical gain or executable dictionary behavior is asserted here. -/
theorem regional_policy_missing {X Y K : Type*} (incumbent : X → Y) (feature : X → K)
    (experts : K → Option (X → Y)) (x : X) (missing : experts (feature x) = none) :
    (match experts (feature x) with | none => incumbent x | some f => f x) = incumbent x := by
  rw [missing]

/-- Independent regional training maxima maximize their summed training score.
Scoring, heap enumeration and held-out generalization remain unproved. -/
theorem regional_training_maxima {I : Type*} (regions : Finset I) (best other : I → ℕ)
    (maximal : ∀ i ∈ regions, other i ≤ best i) :
    ∑ i ∈ regions, other i ≤ ∑ i ∈ regions, best i := by
  exact Finset.sum_le_sum maximal

/-- With one offered alternative, local training preference plus fallback
realizes the larger empirical score. This does not imply held-out improvement. -/
theorem regional_fallback_score (baseline offered : ℕ) :
    (if baseline < offered then some offered else none).getD baseline = max baseline offered := by
  by_cases better : baseline < offered
  · simp [better, max_eq_right (Nat.le_of_lt better)]
  · have weak : offered ≤ baseline := le_of_not_gt better
    simp [better, max_eq_left weak]

/-- Nested pure gates sharing a fallback specialize only their intersection.
This does not prove how learned regions or specialists are selected. -/
theorem nested_refinement_scope {Y : Type*} (outer inner : Prop)
    [Decidable outer] [Decidable inner] (fallback specialist : Y) :
    (if outer then (if inner then specialist else fallback) else fallback) =
      (if outer ∧ inner then specialist else fallback) := by
  by_cases h : outer <;> simp [h]

/-- Restoring a feature and a head faithfully restores their pure composition.
This does not verify executable snapshots, traversal, codecs or factories. -/
theorem decoded_reloaded_eq {X A Y : Type*} (f0 f1 : X → A) (h0 h1 : A → Y)
    (hf : ∀ x, f0 x = f1 x) (hh : ∀ a, h0 a = h1 a) :
    (fun x => h0 (f0 x)) = (fun x => h1 (f1 x)) := by
  funext x
  rw [hf x, hh (f1 x)]

/-- Auxiliary labels can separate ordered observations even with constant correctness.
No feedback quality or generalization claim is made. -/
theorem auxiliary_feedback_separation {A : Type*} (a c : A)
    (lower upper boundary : ℝ) (hl : lower < boundary) (hu : boundary ≤ upper) :
    (if lower < boundary then a else c) = a ∧
    (if upper < boundary then a else c) = c := by
  constructor
  · simp [hl]
  · simp [not_lt.mpr hu]

/-- Larger positive denominators yield strictly smaller reciprocal evidence. -/
theorem reciprocal_evidence_order (a b : ℝ) (ha : 0 < a) (hab : a < b) :
    1 / b < 1 / a := by
  exact one_div_lt_one_div_of_lt ha hab

/-- The higher of two empirical scores dominates both; no generalization claim. -/
theorem router_score_selection (a b : ℕ) :
    a ≤ (if a ≤ b then b else a) ∧ b ≤ (if a ≤ b then b else a) := by
  split_ifs with h <;> omega

/-- Renaming auxiliary categories without changing membership preserves each group. -/
theorem feedback_group_invariance {X : Type*} (xs : List X) (p q : X → Bool)
    (h : ∀ x, p x = q x) : xs.filter p = xs.filter q := by
  have hpq : p = q := funext h
  rw [hpq]

/-- Retaining a bounded prefix cannot exceed its requested candidate count. -/
theorem measurement_prefix_bound {X : Type*} (xs : List X) (budget : ℕ) :
    (xs.take budget).length ≤ budget := by
  simp only [List.length_take]
  exact Nat.min_le_left _ _

/-- An exact shared head cannot distinguish inputs collapsed by its representation. -/
theorem head_fiber_consistency {X A Y : Type*} (f : X → A) (h : A → Y)
    (target : X → Y) (x y : X) (same : f x = f y)
    (hx : target x = h (f x)) (hy : target y = h (f y)) :
    target x = target y := by
  rw [hx, hy, same]

/-- Scalar special case of the orthogonal least-squares residual identity. -/
theorem orthogonal_residual_square (r p : ℝ) (h : r * p = 0) :
    (r + p)^2 = r^2 + p^2 := by
  nlinarith [sq_nonneg r, sq_nonneg p]

/-- A larger-class optimizer cannot exceed an admitted smaller-class witness. -/
theorem nested_fit_comparison {H : Type*} (admitted : H → Prop) (error : H → ℝ)
    (best witness : H) (hw : admitted witness)
    (optimal : ∀ h, admitted h → error best ≤ error h) :
    error best ≤ error witness := by
  exact optimal witness hw

/-- Equal deterministic observations give equal mapped training snapshots. -/
theorem training_snapshot_map_eq {X A : Type*} (xs : List X) (f g : X → A)
    (same : ∀ x, f x = g x) : xs.map f = xs.map g := by
  rw [show f = g from funext same]

/-- Admitting no more than the remaining slots preserves a total feature budget. -/
theorem feature_admission_bound (used added budget : ℕ) (hu : used ≤ budget)
    (ha : added ≤ budget - used) : used + added ≤ budget := by
  omega

/-- Pairing cannot merge inputs that the seed feature already distinguished. -/
theorem joint_key_refines_seed {X A B : Type*} (f : X → A) (g : X → B)
    (x y : X) (same : (f x, g x) = (f y, g y)) : f x = f y := by
  exact congrArg Prod.fst same

/-- Restoring both children restores the ordered structural product. -/
theorem joint_reloaded_eq {X A B : Type*} (f0 f1 : X → A) (g0 g1 : X → B)
    (hf : ∀ x, f0 x = f1 x) (hg : ∀ x, g0 x = g1 x) :
    (fun x => (f0 x, g0 x)) = (fun x => (f1 x, g1 x)) := by
  funext x
  rw [hf x, hg x]

/-- Child modal scores dominate any fixed coarse label's summed counts. -/
theorem modal_refinement_dominates {G L : Type*} [Fintype G]
    (counts : G → L → ℕ) (modal : G → ℕ) (label : L)
    (dominates : ∀ g, counts g label ≤ modal g) :
    (∑ g, counts g label) ≤ ∑ g, modal g := by
  exact Finset.sum_le_sum (fun g _ => dominates g)

/-- Keys with a common modal label retain that mode when grouped together. -/
theorem grouped_modal_dominates {K L : Type*} [Fintype K]
    (counts : K → L → ℕ) (label : L)
    (modal : ∀ k l, counts k l ≤ counts k label) :
    ∀ l, (∑ k, counts k l) ≤ ∑ k, counts k label := by
  intro l
  exact Finset.sum_le_sum (fun k _ => modal k l)

/-- One-dimensional two-center nearest-prototype separation. -/
theorem prototype_left_of_midpoint (a b x : ℝ) (hab : a < b)
    (hx : x < (a + b) / 2) : (x - a)^2 < (x - b)^2 := by
  have hp : 0 < (b - a) * (a + b - 2*x) :=
    mul_pos (sub_pos.mpr hab) (by linarith)
  nlinarith

/-- A two-observation scalar centroid minimizes its within-group squared loss. -/
theorem two_point_mean_minimizes (a b c : ℝ) :
    (a - (a+b)/2)^2 + (b - (a+b)/2)^2 ≤ (a-c)^2 + (b-c)^2 := by
  nlinarith [sq_nonneg (c - (a+b)/2)]

/-- Strictly separated enclosing intervals certify the smallest reference score. -/
theorem prototype_interval_choice {I : Type*} (score low high : I → ℝ) (best : I)
    (inside : ∀ i, low i ≤ score i ∧ score i ≤ high i)
    (gap : ∀ i, i ≠ best → high best < low i) :
    ∀ i, i ≠ best → score best < score i := by
  intro i hi
  exact lt_of_le_of_lt (inside best).2 (lt_of_lt_of_le (gap i hi) (inside i).1)

/-- No false outcomes means every observation in a finite sample succeeded. -/
theorem zero_failed_observations (outcomes : List Bool)
    (h : outcomes.count false = 0) : outcomes.all id = true := by
  induction outcomes with
  | nil => simp
  | cons b bs ih => cases b <;> simp_all

/-- Adding one reserved slot at one category increases total reservation by one. -/
theorem single_allowance_increment {K : Type*} [Fintype K] [DecidableEq K]
    (allowance : K → ℕ) (chosen : K) :
    (∑ k, (allowance k + if k = chosen then 1 else 0)) = (∑ k, allowance k) + 1 := by
  simp [Finset.sum_add_distrib]

/-- A one-slot increment cannot leave an allowance state unchanged. -/
theorem incremented_allowance_distinct {K : Type*} [DecidableEq K]
    (allowance : K → ℕ) (chosen : K) :
    allowance ≠ (fun k => allowance k + if k = chosen then 1 else 0) := by
  intro h
  have impossible := congrFun h chosen
  simp at impossible

/-- Faithful restoration preserves the ordered outputs of all exposed roots. -/
theorem retained_root_outputs_eq {X Y : Type*} (roots : List (X → Y))
    (restore : (X → Y) → (X → Y)) (same : ∀ f ∈ roots, ∀ x, restore f x = f x)
    (x : X) : roots.map (fun f => restore f x) = roots.map (fun f => f x) := by
  apply List.map_congr_left
  intro f hf
  exact same f hf x

/-- Pointwise bridge agreement preserves every consumer in a supplied family. -/
theorem adapter_consumer_family_eq {X A B Y : Type*} (source : X → A)
    (teacher : X → B) (adapter : A → B) (consumers : List (B → Y))
    (agree : ∀ x, adapter (source x) = teacher x) (x : X) :
    consumers.map (fun c => c (adapter (source x))) =
      consumers.map (fun c => c (teacher x)) := by
  simp only [agree x]

/-- One shared alignment uses no more paired observations than repeated fits. -/
theorem shared_alignment_observation_bound (rows consumers : ℕ) (h : 0 < consumers) :
    rows ≤ consumers * rows := by
  simpa using Nat.mul_le_mul_right rows (show 1 ≤ consumers by omega)

/-- A present adapter yields a present completed route in the mapped family. -/
theorem adapter_family_contains_route {X A B Y : Type*} (source : X → A)
    (consumer : B → Y) (adapters : List (A → B)) (adapter : A → B)
    (present : adapter ∈ adapters) :
    (fun x => consumer (adapter (source x))) ∈
      adapters.map (fun a x => consumer (a (source x))) := by
  exact List.mem_map.mpr ⟨adapter, present, rfl⟩

end NCA
