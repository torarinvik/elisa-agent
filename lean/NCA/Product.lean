import NCA.Decoding
import Mathlib.Analysis.Real.Sqrt

/-!
# Decoding under a prior automaton

`NCA.Decoding` decodes under the format alone: every parseable sequence has
prior weight 1. A *prior expert* supplies a weighted automaton instead:
states `τ`, transitions `ε`, a weight `v t a` for reading symbol `a` in state
`t`, and a final weight `f t`. The prior weight of a sequence is the product
of the weights along its run (`prior`).

Decoding under the format and the prior together is the dynamic program on
the product automaton, whose states pair a format state with a prior state.
The sum-product recursion computes the total of score × prior over all
sequences (`pdpSum_eq`); the max-product recursion bounds every sequence's
score × prior and is attained by one (`pdpMax_ge`, `pdpMax_attained`). With
the one-state prior of weight 1 it is the format-only program (`pdpSum_unit`).
-/

namespace NCA

/-- Dropping zero reading weights preserves an ordered weighted sum. -/
theorem sum_filter_zero_readings {α : Type} (symbols : List α) (reading factor : α → ℝ) :
    ((symbols.filter fun a => reading a ≠ 0).map fun a => reading a * factor a).sum =
      (symbols.map fun a => reading a * factor a).sum := by
  classical
  induction symbols with
  | nil => simp
  | cons a rest ih =>
    simp only [ne_eq, decide_not] at ih
    by_cases h : reading a = 0 <;> simp [h, ih]

/-- A zero weighted-automaton frontier stays zero after any transition. -/
theorem zero_frontier_step {S : Type} [Fintype S] (front : S → ℝ) (edge : S → S → ℝ)
    (empty : ∀ s, front s = 0) (target : S) :
    ∑ s, front s * edge s target = 0 := by
  simp [empty]

section Product

variable {σ τ α : Type} (δ : σ → α → σ) (F : σ → Prop) [DecidablePred F] (as : List α)
  (ε : τ → α → τ) (v : τ → α → ℝ) (f : τ → ℝ)

/-- The prior weight of a sequence read from prior state `t`. -/
def prior : τ → List α → ℝ
  | t, [] => f t
  | t, a :: l => v t a * prior (ε t a) l

/-- Relabelling the symbols in a path with a left inverse preserves its weight. -/
theorem prior_relabel {β : Type} (encode : α → β) (decode : β → α)
    (t : τ) (l : List α) (inverse : ∀ a ∈ l, decode (encode a) = a) :
    prior (fun s b => ε s (decode b)) (fun s b => v s (decode b)) f t (l.map encode) =
      prior ε v f t l := by
  induction l generalizing t with
  | nil => rfl
  | cons a l ih =>
    have head := inverse a List.mem_cons_self
    have tail := fun b hb => inverse b (List.mem_cons_of_mem _ hb)
    simp only [List.map_cons, prior, head]
    rw [ih (ε t a) tail]

/-- The empty sequence has exactly its start state's final weight. -/
theorem prior_empty (t : τ) : prior ε v f t [] = f t := rfl

/-- Normalizing positive empty-sequence mass against itself gives one. -/
theorem prior_empty_normalized (t : τ) (hf : f t ≠ 0) :
    prior ε v f t [] / prior ε v f t [] = 1 := by
  simp [prior_empty, hf]

/-- Sum-product dynamic program on the product automaton. -/
def pdpSum : List (α → ℝ) → σ → τ → ℝ
  | [], s, t => if F s then f t else 0
  | w :: ws, s, t => (as.map fun a => w a * v t a * pdpSum ws (δ s a) (ε t a)).sum

/-- A zero reading row makes every complete product-automaton path weight zero. -/
theorem pdpSum_zero_row (front suffix : List (α → ℝ)) (s : σ) (t : τ) :
    pdpSum δ F as ε v f (front ++ (fun _ => 0) :: suffix) s t = 0 := by
  induction front generalizing s t with
  | nil => simp [pdpSum]
  | cons w rest ih => simp [pdpSum, ih]

/-- Max-product dynamic program on the product automaton. -/
def pdpMax : List (α → ℝ) → σ → τ → ℝ
  | [], s, t => if F s then f t else 0
  | w :: ws, s, t => (as.map fun a => w a * v t a * pdpMax ws (δ s a) (ε t a)).foldr max 0

/-- A zero reading row also makes every maximum path weight zero. -/
theorem pdpMax_zero_row (front suffix : List (α → ℝ)) (s : σ) (t : τ) :
    pdpMax δ F as ε v f (front ++ (fun _ => 0) :: suffix) s t = 0 := by
  have zero_fold : ∀ n : ℕ, (List.replicate n (0 : ℝ)).foldr max 0 = 0 := by
    intro n
    induction n with
    | zero => simp
    | succ n ih => simp [List.replicate, ih]
  induction front generalizing s t with
  | nil => simp [pdpMax, zero_fold]
  | cons w rest ih => simp [pdpMax, ih, zero_fold]

theorem score_nil_mul_prior (s : σ) (t : τ) :
    score δ F [] s [] * prior ε v f t [] = if F s then f t else 0 := by
  rw [score_nil]
  by_cases h : F s <;> simp [h, prior]

/-- **Sum-product with a prior.** The product program sums score × prior
over all sequences. -/
theorem pdpSum_eq : ∀ (ws : List (α → ℝ)) (s : σ) (t : τ),
    pdpSum δ F as ε v f ws s t =
      ((words as ws.length).map fun l => score δ F ws s l * prior ε v f t l).sum
  | [], s, t => by
    simp only [pdpSum, words, List.length_nil, List.map_cons, List.map_nil, List.sum_cons,
      List.sum_nil, add_zero, score_nil_mul_prior]
  | w :: ws, s, t => by
    simp only [pdpSum, words, List.length_cons, List.map_flatten, sum_flatten, List.map_map]
    congr 1
    refine List.map_congr_left fun a _ => ?_
    rw [pdpSum_eq ws (δ s a) (ε t a), ← List.sum_map_mul_left]
    simp only [Function.comp_def, List.map_map, score_cons, prior]
    congr 1
    refine List.map_congr_left fun l _ => ?_
    ring

/-- With the one-state prior of weight 1, the product program is the
format-only program of `NCA.Decoding`. -/
theorem pdpSum_unit (ws : List (α → ℝ)) (s : σ) :
    pdpSum δ F as (fun _ _ => ()) (fun _ _ => 1) (fun _ => 1) ws s () = dpSum δ F as ws s := by
  induction ws generalizing s with
  | nil => rfl
  | cons w ws ih => simp only [pdpSum, dpSum, mul_one, ih]

theorem prior_nonneg (hv : ∀ t a, 0 ≤ v t a) (hf : ∀ t, 0 ≤ f t) :
    ∀ (t : τ) (l : List α), 0 ≤ prior ε v f t l
  | t, [] => hf t
  | t, a :: l => mul_nonneg (hv t a) (prior_nonneg hv hf (ε t a) l)

/-- A symbol-wise edge tilt multiplies the sequence weight by its symbol factors. -/
theorem prior_tilt (r : α → ℝ) (t : τ) (l : List α) :
    prior ε (fun t a => v t a * r a) f t l =
      prior ε v f t l * (l.map r).prod := by
  induction l generalizing t with
  | nil => simp [prior]
  | cons a l ih => simp only [prior, List.map_cons, List.prod_cons, ih]; ring

/-- Common edge and final factors scale every path of a fixed length equally. -/
theorem prior_common_factors (edge_factor final_factor : ℝ) (t : τ) (l : List α) :
    prior ε (fun s a => edge_factor * v s a) (fun s => final_factor * f s) t l =
      edge_factor ^ l.length * final_factor * prior ε v f t l := by
  induction l generalizing t with
  | nil => simp [prior]
  | cons a l ih => simp only [prior, List.length_cons, pow_succ, ih]; ring

/-- Nonzero symbol factors cannot add or remove sequence support. -/
theorem prior_tilt_ne_zero (r : α → ℝ) (hr : ∀ a, r a ≠ 0) (t : τ) (l : List α) :
    prior ε (fun t a => v t a * r a) f t l ≠ 0 ↔ prior ε v f t l ≠ 0 := by
  have hprod : (l.map r).prod ≠ 0 := by
    induction l with
    | nil => simp
    | cons a l ih => simp [hr a, ih]
  rw [prior_tilt]
  simp [hprod]

/-- **Max-product with a prior, upper bound.** With nonnegative weights, no
sequence's score × prior exceeds the product program. -/
theorem pdpMax_ge (hv : ∀ t a, 0 ≤ v t a) : ∀ (ws : List (α → ℝ)), (∀ w ∈ ws, ∀ a, 0 ≤ w a) →
    ∀ (s : σ) (t : τ) (l : List α), l ∈ words as ws.length →
      score δ F ws s l * prior ε v f t l ≤ pdpMax δ F as ε v f ws s t
  | [], _, s, t, l, hl => by
    simp only [List.length_nil, words, List.mem_singleton] at hl
    subst hl
    rw [score_nil_mul_prior]; rfl
  | w :: ws, hw, s, t, l, hl => by
    simp only [words, List.length_cons, List.mem_flatten, List.mem_map] at hl
    obtain ⟨_, ⟨a, ha, rfl⟩, hl⟩ := hl
    obtain ⟨l', hl', rfl⟩ := List.mem_map.mp hl
    rw [score_cons]
    simp only [prior]
    have ih := pdpMax_ge hv ws (fun u hu => hw u (List.mem_cons_of_mem _ hu)) (δ s a) (ε t a) l' hl'
    have hwa := hw w List.mem_cons_self a
    calc w a * score δ F ws (δ s a) l' * (v t a * prior ε v f (ε t a) l')
        = w a * v t a * (score δ F ws (δ s a) l' * prior ε v f (ε t a) l') := by ring
      _ ≤ w a * v t a * pdpMax δ F as ε v f ws (δ s a) (ε t a) :=
          mul_le_mul_of_nonneg_left ih (mul_nonneg hwa (hv t a))
      _ ≤ _ := le_foldr_max (List.mem_map.mpr ⟨a, ha, rfl⟩)

/-- **Max-product with a prior, attained.** Unless the maximum is 0, some
sequence's score × prior equals it: backtracking decodes the most probable
sequence under format, readings and prior together. -/
theorem pdpMax_attained : ∀ (ws : List (α → ℝ)) (s : σ) (t : τ),
    pdpMax δ F as ε v f ws s t = 0 ∨
      ∃ l ∈ words as ws.length, score δ F ws s l * prior ε v f t l = pdpMax δ F as ε v f ws s t
  | [], s, t => Or.inr ⟨[], by simp [words], by rw [score_nil_mul_prior]; rfl⟩
  | w :: ws, s, t => by
    rcases foldr_max_mem (as.map fun a => w a * v t a * pdpMax δ F as ε v f ws (δ s a) (ε t a))
      with h | h
    · exact Or.inl (by simpa [pdpMax] using h)
    · obtain ⟨a, ha, hval⟩ := List.mem_map.mp h
      rcases pdpMax_attained ws (δ s a) (ε t a) with h0 | ⟨l, hl, hs⟩
      · left
        simp only [pdpMax]
        rw [← hval, h0, mul_zero]
      · right
        refine ⟨a :: l, ?_, ?_⟩
        · simp only [words, List.length_cons]
          exact List.mem_flatten.mpr ⟨_, List.mem_map.mpr ⟨a, ha, rfl⟩, List.mem_map.mpr ⟨l, hl, rfl⟩⟩
        · simp only [pdpMax]
          rw [score_cons, ← hval, ← hs]
          simp only [prior]
          ring

end Product

/-- A state with zero prefix weight contributes nothing to a split sum. -/
theorem prior_support_sum {S : Type} [Fintype S] (forward backward : S → ℝ) :
    ∑ s, forward s * backward s =
      ∑ s ∈ Finset.univ.filter (fun s => forward s ≠ 0), forward s * backward s := by
  classical
  rw [Finset.sum_filter]
  apply Finset.sum_congr rfl
  intro s _
  by_cases h : forward s = 0 <;> simp [h]

/-- Zero-weight readings contribute nothing to a transition sum. -/
theorem prior_prune_zero_readings {α : Type} (symbols : List α) (reading edge : α → ℝ) :
    (symbols.map (fun a => reading a * edge a)).sum =
      ((symbols.filter fun a => reading a ≠ 0).map (fun a => reading a * edge a)).sum := by
  classical
  induction symbols with
  | nil => simp
  | cons a rest ih =>
    by_cases h : reading a = 0 <;> simp [h, ih]

private theorem max_fold_zero_le (values : List ℝ) : 0 ≤ values.foldr max 0 := by
  induction values with
  | nil => simp
  | cons x xs ih => exact ih.trans (le_max_right _ _)

/-- Removing unreachable (zero-weight) candidates preserves a maximum seeded at zero. -/
theorem prior_support_max {S : Type} (states : List S) (weight : S → ℝ)
    (active : S → Bool) (hzero : ∀ s, active s = false → weight s = 0) :
    (states.map weight).foldr max 0 = ((states.filter active).map weight).foldr max 0 := by
  induction states with
  | nil => simp
  | cons s states ih =>
      cases hs : active s with
      | false => simp [hs, hzero s hs, ih, max_eq_right (max_fold_zero_le _)]
      | true => simp [hs, ih]

/-- Forward support remains inside any envelope containing all live successors. -/
theorem prior_step_zero_outside {S : Type} [Fintype S]
    (forward : S → ℝ) (weight : S → S → ℝ) (active next : Finset S)
    (hforward : ∀ s, s ∉ active → forward s = 0)
    (hedge : ∀ s ∈ active, ∀ t, t ∉ next → weight s t = 0)
    (t : S) (ht : t ∉ next) : ∑ s, forward s * weight s t = 0 := by
  classical
  apply Finset.sum_eq_zero
  intro s _
  by_cases hs : s ∈ active
  · rw [hedge s hs t ht, mul_zero]
  · rw [hforward s hs, zero_mul]

/-- Normalized tilted-prior evidence from a shared base posterior. -/
theorem prior_evidence_identity {S : Type} [Fintype S]
    (v base likelihood posterior : S → ℝ) (Z c : ℝ)
    (hZ : Z ≠ 0) (hc : c ≠ 0)
    (hq : ∀ a, posterior a = base a * likelihood a / c) :
    ∑ a, (v a * base a / Z) * likelihood a =
      c / Z * ∑ a, v a * posterior a := by
  simp_rw [hq]
  rw [Finset.mul_sum]
  apply Finset.sum_congr rfl
  intro a _
  field_simp

/-- Prior selection within twice a uniform score error loses at most four errors. -/
theorem prior_selection_regret {best chosen reportedBest reportedChosen ε : ℝ}
    (hbest : |best - reportedBest| ≤ ε)
    (hchosen : |chosen - reportedChosen| ≤ ε)
    (hnear : reportedBest ≤ reportedChosen + 2 * ε) : best ≤ chosen + 4 * ε := by
  have hb := (abs_le.mp hbest).2
  have hc := (abs_le.mp hchosen).1
  linarith

/-- The half-scaled priority test is equivalent over exact real arithmetic. -/
theorem prior_selection_half_gap (best score error : ℝ) :
    best - score ≤ 2 * error ↔ best / 2 - score / 2 ≤ error := by
  constructor <;> intro h <;> linarith

/-- Increasing nonnegative inputs cannot reduce the clipped-score error bound. -/
theorem clipped_error_bound_mono (B n t B' n' t' : ℝ)
    (hB : 0 ≤ B) (hn : 0 ≤ n) (ht : 0 ≤ t)
    (B_le : B ≤ B') (n_le : n ≤ n') (t_le : t ≤ t') :
    B * Real.sqrt (2 * n * t) ≤ B' * Real.sqrt (2 * n' * t') := by
  have hn' : 0 ≤ n' := le_trans hn n_le
  have ht' : 0 ≤ t' := le_trans ht t_le
  have hB' : 0 ≤ B' := le_trans hB B_le
  gcongr

/-- Clipping a real evidence score supplies the deterministic bounded range. -/
theorem clipped_evidence_bounds {x B : ℝ} (hB : 0 ≤ B) :
    -B ≤ max (-B) (min B x) ∧ max (-B) (min B x) ≤ B := by
  exact ⟨le_max_left _ _, max_le (by linarith) (min_le_left _ _)⟩

/-- Mixing conditional audit failure bounds preserves the audit level. -/
theorem selected_audit_failure_le {S : Type} [Fintype S]
    (selection failure : S → ℝ) (α : ℝ)
    (hp : ∀ s, 0 ≤ selection s) (htotal : ∑ s, selection s = 1)
    (haudit : ∀ s, failure s ≤ α) :
    ∑ s, selection s * failure s ≤ α := by
  calc
    ∑ s, selection s * failure s ≤ ∑ s, selection s * α :=
      Finset.sum_le_sum fun s _ => mul_le_mul_of_nonneg_left (haudit s) (hp s)
    _ = α := by rw [← Finset.sum_mul, htotal, one_mul]

/-- A fixed bounded score for partial models, with absence scored at the floor. -/
def partialEvidenceScore (B : ℝ) : Option ℝ → ℝ
  | none => -B
  | some x => max (-B) (min B x)

/-- Partial-model scoring retains the clipping interval for every input. -/
theorem partial_evidence_bounds {B : ℝ} (hB : 0 ≤ B) (score : Option ℝ) :
    -B ≤ partialEvidenceScore B score ∧ partialEvidenceScore B score ≤ B := by
  cases score with
  | none => exact ⟨le_rfl, by dsimp [partialEvidenceScore]; linarith⟩
  | some x => exact clipped_evidence_bounds hB

/-- A common nonzero factor cancels from every normalized finite weight. -/
theorem normalized_common_factor {S : Type} (items : Finset S)
    (weight : S → ℝ) (factor : ℝ) (hf : factor ≠ 0) (item : S) :
    (factor * weight item) / (∑ x ∈ items, factor * weight x) =
      weight item / (∑ x ∈ items, weight x) := by
  rw [← Finset.mul_sum]
  exact mul_div_mul_left (weight item) (∑ x ∈ items, weight x) hf

/-- Computing other mass directly gives the same risk as the complement. -/
theorem risk_from_other_mass (chosen other : ℝ) (h : chosen + other ≠ 0) :
    1 - chosen / (chosen + other) = other / (chosen + other) := by
  field_simp
  ring

/-- Scaling both parts of a partition leaves the normalized alternative mass unchanged. -/
theorem partition_risk_common_factor (chosen other factor : ℝ) (hf : factor ≠ 0) :
    (factor * other) / (factor * chosen + factor * other) = other / (chosen + other) := by
  rw [← mul_add]
  exact mul_div_mul_left other (chosen + other) hf

/-- Adding a second positive equal mass strictly increases the partition. -/
theorem equal_positive_mass_increases (mass : ℝ) (positive : 0 < mass) :
    mass < mass + mass := by
  linarith

/-- The unrounded TwoSum residual expression is the exact addition error. -/
theorem two_sum_residual_identity (x y result : ℝ) :
    (x - (result - (result - x))) + (y - (result - x)) = x + y - result := by
  ring

/-- Adding the TwoSum residual to a correction preserves the exact total. -/
theorem compensated_evidence_step (total correction value result : ℝ) :
    result + (correction + ((total - (result - (result - total))) +
      (value - (result - total)))) = total + correction + value := by
  rw [two_sum_residual_identity]
  ring

/-- Combine selected and alternative mass from independent segments. -/
def partitionCompose (left right : ℝ × ℝ) : ℝ × ℝ :=
  (left.1 * right.1, left.2 * (right.1 + right.2) + left.1 * right.2)

/-- Once selected and alternative mass are both zero, extending the path keeps them zero. -/
theorem partitionCompose_zero_left (right : ℝ × ℝ) :
    partitionCompose (0, 0) right = (0, 0) := by
  apply Prod.ext <;> simp [partitionCompose]

/-- The composition is independent of how segments are parenthesized. -/
theorem partitionCompose_assoc (a b c : ℝ × ℝ) :
    partitionCompose (partitionCompose a b) c = partitionCompose a (partitionCompose b c) := by
  apply Prod.ext <;> dsimp [partitionCompose] <;> ring

/-- An empty segment contributes the multiplicative identity. -/
theorem partitionCompose_identity (a : ℝ × ℝ) :
    partitionCompose (1, 0) a = a ∧ partitionCompose a (1, 0) = a := by
  constructor <;> apply Prod.ext <;> simp [partitionCompose]

/-- Nonnegative segment masses remain nonnegative under composition. -/
theorem partitionCompose_nonneg (a b : ℝ × ℝ)
    (ha : 0 ≤ a.1 ∧ 0 ≤ a.2) (hb : 0 ≤ b.1 ∧ 0 ≤ b.2) :
    0 ≤ (partitionCompose a b).1 ∧ 0 ≤ (partitionCompose a b).2 := by
  exact ⟨mul_nonneg ha.1 hb.1,
    add_nonneg (mul_nonneg ha.2 (add_nonneg hb.1 hb.2)) (mul_nonneg ha.1 hb.2)⟩

/-- Compose segment partitions while summing only matching boundary states. -/
def partitionBoundaryCompose {S : Type} [Fintype S]
    (left right : S → S → ℝ × ℝ) (start finish : S) : ℝ × ℝ :=
  (∑ middle, (partitionCompose (left start middle) (right middle finish)).1,
   ∑ middle, (partitionCompose (left start middle) (right middle finish)).2)

/-- The two partition components sum to the ordinary boundary-state product. -/
theorem partitionBoundary_total {S : Type} [Fintype S]
    (left right : S → S → ℝ × ℝ) (start finish : S) :
    (partitionBoundaryCompose left right start finish).1 +
      (partitionBoundaryCompose left right start finish).2 =
    ∑ middle, ((left start middle).1 + (left start middle).2) *
      ((right middle finish).1 + (right middle finish).2) := by
  simp only [partitionBoundaryCompose, ← Finset.sum_add_distrib]
  apply Finset.sum_congr rfl
  intro middle _
  dsimp [partitionCompose]
  ring

/-- Boundary composition preserves nonnegative selected and alternative mass. -/
theorem partitionBoundary_nonneg {S : Type} [Fintype S]
    (left right : S → S → ℝ × ℝ)
    (hl : ∀ i j, 0 ≤ (left i j).1 ∧ 0 ≤ (left i j).2)
    (hr : ∀ i j, 0 ≤ (right i j).1 ∧ 0 ≤ (right i j).2)
    (start finish : S) :
    0 ≤ (partitionBoundaryCompose left right start finish).1 ∧
      0 ≤ (partitionBoundaryCompose left right start finish).2 := by
  constructor <;> apply Finset.sum_nonneg <;> intro middle _
  · exact (partitionCompose_nonneg _ _ (hl start middle) (hr middle finish)).1
  · exact (partitionCompose_nonneg _ _ (hl start middle) (hr middle finish)).2

def partitionSum {S : Type} [Fintype S] (f : S → ℝ × ℝ) : ℝ × ℝ :=
  (∑ i, (f i).1, ∑ i, (f i).2)

theorem partitionCompose_sum_left {S : Type} [Fintype S]
    (f : S → ℝ × ℝ) (b : ℝ × ℝ) :
    partitionCompose (partitionSum f) b = partitionSum (fun i => partitionCompose (f i) b) := by
  apply Prod.ext
  · simp [partitionCompose, partitionSum, Finset.sum_mul]
  · simp [partitionCompose, partitionSum, Finset.sum_mul, Finset.sum_add_distrib]

theorem partitionCompose_sum_right {S : Type} [Fintype S]
    (a : ℝ × ℝ) (f : S → ℝ × ℝ) :
    partitionCompose a (partitionSum f) = partitionSum (fun i => partitionCompose a (f i)) := by
  apply Prod.ext
  · simp [partitionCompose, partitionSum, Finset.mul_sum]
  · simp only [partitionCompose, partitionSum]
    rw [← Finset.sum_add_distrib, Finset.mul_sum, Finset.mul_sum, ← Finset.sum_add_distrib]

theorem partitionSum_comm {S : Type} [Fintype S] (f : S → S → ℝ × ℝ) :
    partitionSum (fun i => partitionSum (fun j => f i j)) =
      partitionSum (fun j => partitionSum (fun i => f i j)) := by
  apply Prod.ext
  · exact Finset.sum_comm
  · exact Finset.sum_comm

/-- Boundary-aware composition is associative over exact real arithmetic. -/
theorem partitionBoundary_assoc {S : Type} [Fintype S]
    (a b c : S → S → ℝ × ℝ) (start finish : S) :
    partitionBoundaryCompose (partitionBoundaryCompose a b) c start finish =
      partitionBoundaryCompose a (partitionBoundaryCompose b c) start finish := by
  change partitionSum (fun j => partitionCompose
      (partitionSum (fun i => partitionCompose (a start i) (b i j))) (c j finish)) =
    partitionSum (fun i => partitionCompose (a start i)
      (partitionSum (fun j => partitionCompose (b i j) (c j finish))))
  simp only [partitionCompose_sum_left, partitionCompose_sum_right]
  rw [partitionSum_comm]
  congr 1
  funext i
  congr 1
  funext j
  exact partitionCompose_assoc _ _ _

/-- The state-preserving empty segment. -/
def partitionBoundaryIdentity {S : Type} [DecidableEq S] (i j : S) : ℝ × ℝ :=
  if i = j then (1, 0) else (0, 0)

theorem partitionSum_single {S : Type} [Fintype S] [DecidableEq S]
    (index : S) (value : ℝ × ℝ) :
    partitionSum (fun i => if i = index then value else (0, 0)) = value := by
  apply Prod.ext
  · simp only [partitionSum, apply_ite, Finset.sum_ite_eq', Finset.mem_univ, if_true]
  · simp only [partitionSum, apply_ite, Finset.sum_ite_eq', Finset.mem_univ, if_true]

/-- Empty boundary segments are left and right identities. -/
theorem partitionBoundary_identity {S : Type} [Fintype S] [DecidableEq S]
    (a : S → S → ℝ × ℝ) (start finish : S) :
    partitionBoundaryCompose partitionBoundaryIdentity a start finish = a start finish ∧
    partitionBoundaryCompose a partitionBoundaryIdentity start finish = a start finish := by
  constructor
  · change partitionSum (fun i => partitionCompose (partitionBoundaryIdentity start i) (a i finish)) = _
    have h (i : S) : partitionCompose (partitionBoundaryIdentity start i) (a i finish) =
        if i = start then a start finish else (0, 0) := by
      by_cases hi : i = start
      · subst i
        simp [partitionBoundaryIdentity, partitionCompose]
      · have hs : start ≠ i := Ne.symm hi
        simp [partitionBoundaryIdentity, partitionCompose, hi, hs]
    simp_rw [h]
    exact partitionSum_single start (a start finish)
  · change partitionSum (fun i => partitionCompose (a start i) (partitionBoundaryIdentity i finish)) = _
    have h (i : S) : partitionCompose (a start i) (partitionBoundaryIdentity i finish) =
        if i = finish then a start finish else (0, 0) := by
      by_cases hi : i = finish
      · subst i
        simp [partitionBoundaryIdentity, partitionCompose]
      · simp [partitionBoundaryIdentity, partitionCompose, hi]
    simp_rw [h]
    exact partitionSum_single finish (a start finish)

/-- A deterministic prefix summary can be reused when the paired inputs agree. -/
theorem partition_prefix_reuse {Input State : Type} (step : State → Input → State)
    (initial : State) (old new : List Input) (k : ℕ)
    (same : old.take k = new.take k) :
    new.foldl step initial = (new.drop k).foldl step ((old.take k).foldl step initial) := by
  calc
    new.foldl step initial = ((new.take k) ++ new.drop k).foldl step initial := by
      rw [List.take_append_drop]
    _ = (new.drop k).foldl step ((new.take k).foldl step initial) := by
      rw [List.foldl_append]
    _ = (new.drop k).foldl step ((old.take k).foldl step initial) := by rw [same]

/-- A one-symbol factor product is the factor raised to its occurrence count. -/
theorem symbol_factor_product (symbols : List ℕ) (key : ℕ) (factor : ℝ) :
    (symbols.map (fun a => if a = key then factor else 1)).prod =
      factor ^ symbols.count key := by
  induction symbols with
  | nil => simp
  | cons a rest ih =>
      by_cases h : a = key <;> simp [h, ih, pow_succ, mul_comm]

/-- On bounded trees, leaf and binary symbol factors differ by one common factor. -/
theorem bounded_leaf_binary_factors {d : ℕ} {symbols : List ℕ}
    (shape : BoundedShape d symbols) (factor : ℝ) :
    (symbols.map (fun a => if a = 0 then factor else 1)).prod =
      factor * (symbols.map (fun a => if a = 2 then factor else 1)).prod := by
  rw [symbol_factor_product, symbol_factor_product, bounded_shape_leaf_binary_count shape]
  simp [pow_succ, mul_comm]

/-- The two tilted automata assign weights differing by a common factor. -/
theorem bounded_leaf_binary_prior {τ : Type} (ε : τ → ℕ → τ)
    (v : τ → ℕ → ℝ) (f : τ → ℝ) (state : τ) {d : ℕ} {symbols : List ℕ}
    (shape : BoundedShape d symbols) (factor : ℝ) :
    prior ε (fun t a => v t a * (if a = 0 then factor else 1)) f state symbols =
      factor * prior ε (fun t a => v t a * (if a = 2 then factor else 1)) f state symbols := by
  rw [prior_tilt, prior_tilt, bounded_leaf_binary_factors shape factor]
  ring

/-- Leaf and binary tilts give the same normalized weights on bounded trees. -/
theorem bounded_leaf_binary_posterior {τ : Type} (ε : τ → ℕ → τ)
    (v : τ → ℕ → ℝ) (f : τ → ℝ) (state : τ) (items : Finset (List ℕ))
    (likelihood : List ℕ → ℝ) (factor : ℝ) (hf : factor ≠ 0)
    (shapes : ∀ symbols ∈ items, ∃ d, BoundedShape d symbols)
    (symbols : List ℕ) (hm : symbols ∈ items) :
    let leaf := fun l => likelihood l * prior ε (fun t a => v t a * (if a = 0 then factor else 1)) f state l
    let binary := fun l => likelihood l * prior ε (fun t a => v t a * (if a = 2 then factor else 1)) f state l
    leaf symbols / (∑ l ∈ items, leaf l) = binary symbols / (∑ l ∈ items, binary l) := by
  dsimp only
  have h : ∀ l ∈ items, likelihood l * prior ε (fun t a => v t a * (if a = 0 then factor else 1)) f state l =
      factor * (likelihood l * prior ε (fun t a => v t a * (if a = 2 then factor else 1)) f state l) := by
    intro l hl
    obtain ⟨d, shape⟩ := shapes l hl
    rw [bounded_leaf_binary_prior ε v f state shape factor]
    ring
  rw [h symbols hm, Finset.sum_congr rfl h]
  exact normalized_common_factor items
    (fun l => likelihood l * prior ε (fun t a => v t a * (if a = 2 then factor else 1)) f state l)
    factor hf symbols

/-- A selected mass bounded by the positive total has probability at most one. -/
theorem selected_mass_probability_le_one (chosen total : ℝ)
    (ht : 0 < total) (hc : chosen ≤ total) : chosen / total ≤ 1 := by
  apply (div_le_iff₀ ht).2
  simpa using hc

/-- In a zero-based alphabet, a valid symbol is its own column index. -/
theorem range_alphabet_column (width symbol : ℕ) (h : symbol < width) :
    (List.range width)[symbol]'(by simpa using h) = symbol := by
  simp

end NCA
