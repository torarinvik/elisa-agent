import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Data.Finset.Max
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

end NCA
