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

end NCA
