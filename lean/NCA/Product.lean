import NCA.Decoding

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

section Product

variable {σ τ α : Type} (δ : σ → α → σ) (F : σ → Prop) [DecidablePred F] (as : List α)
  (ε : τ → α → τ) (v : τ → α → ℝ) (f : τ → ℝ)

/-- The prior weight of a sequence read from prior state `t`. -/
def prior : τ → List α → ℝ
  | t, [] => f t
  | t, a :: l => v t a * prior (ε t a) l

/-- The empty sequence has exactly its start state's final weight. -/
theorem prior_empty (t : τ) : prior ε v f t [] = f t := rfl

/-- Sum-product dynamic program on the product automaton. -/
def pdpSum : List (α → ℝ) → σ → τ → ℝ
  | [], s, t => if F s then f t else 0
  | w :: ws, s, t => (as.map fun a => w a * v t a * pdpSum ws (δ s a) (ε t a)).sum

/-- Max-product dynamic program on the product automaton. -/
def pdpMax : List (α → ℝ) → σ → τ → ℝ
  | [], s, t => if F s then f t else 0
  | w :: ws, s, t => (as.map fun a => w a * v t a * pdpMax ws (δ s a) (ε t a)).foldr max 0

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

end NCA
