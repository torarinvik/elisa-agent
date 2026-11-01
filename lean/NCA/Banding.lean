import Mathlib.Data.Nat.Factorial.Basic
import NCA.Decoding

/-!
# Efficient decoding

The dynamic programs of `NCA.Decoding` visit every live state of the counter
automaton. Two facts make decoding cheaper while keeping its risk an upper
bound.

**Banding.** Sequences that differ from a reference sequence (the reading)
in at least `j` positions carry little weight: with per-position weights
summing to at most 1, their total weight is at most the elementary symmetric
polynomial `e_j(ρ)` of the positions' off-reference masses (`tail_le_esym`),
and `j! · e_j(ρ) ≤ (Σ ρ)^j` (`factorial_mul_esym_le`). A sequence within
`j − 1` changes of the reference keeps its counter within `2 (j − 1)` of the
reference's (`sum_sub_le_diff`), so a dynamic program restricted to that band
sees every such sequence. Bounding the rest by the tail keeps the decoded
sequence's risk an upper bound (`banded_risk_le`).

**Splitting.** The sum over all sequences splits at any position into
prefixes weighted by the sum over suffixes from where each prefix ends
(`dpSum_append`), the forward–backward identity that lets a refinement step
that changes one word's weights recompute the normalizer from cached vectors.
-/

namespace NCA

section Symmetric

/-- Elementary symmetric polynomial `e_j` of a list: the sum over `j`-element
sub-multisets of their products. -/
def esym : List ℝ → ℕ → ℝ
  | _, 0 => 1
  | [], _ + 1 => 0
  | x :: l, j + 1 => esym l (j + 1) + x * esym l j

theorem esym_nonneg : ∀ (l : List ℝ), (∀ x ∈ l, 0 ≤ x) → ∀ j, 0 ≤ esym l j
  | _, _, 0 => by simp [esym]
  | [], _, _ + 1 => by simp [esym]
  | x :: l, h, j + 1 => by
    have hx := h x List.mem_cons_self
    have hl := fun y hy => h y (List.mem_cons_of_mem _ hy)
    simp only [esym]
    have := esym_nonneg l hl (j + 1)
    have := esym_nonneg l hl j
    positivity

/-- `s^(j+1) + (j+1) x s^j ≤ (s + x)^(j+1)` for `s, x ≥ 0`. -/
theorem pow_add_ge {s x : ℝ} (hs : 0 ≤ s) (hx : 0 ≤ x) :
    ∀ j : ℕ, s ^ (j + 1) + (j + 1) * x * s ^ j ≤ (s + x) ^ (j + 1)
  | 0 => by simp
  | j + 1 => by
    have ih := pow_add_ge hs hx j
    have h1 : 0 ≤ s ^ j := pow_nonneg hs j
    have h2 : 0 ≤ (j + 1 : ℝ) * x * x * s ^ j := by positivity
    have h3 : 0 ≤ s + x := by linarith
    calc s ^ (j + 1 + 1) + ((j + 1 : ℕ) + 1 : ℝ) * x * s ^ (j + 1)
        ≤ (s + x) * (s ^ (j + 1) + (j + 1) * x * s ^ j) := by
          push_cast; ring_nf; nlinarith
      _ ≤ (s + x) * (s + x) ^ (j + 1) := mul_le_mul_of_nonneg_left ih h3
      _ = (s + x) ^ (j + 1 + 1) := by ring

/-- **Maclaurin-type bound.** For nonnegative reals, `j! · e_j ≤ (Σ x)^j`. -/
theorem factorial_mul_esym_le : ∀ (l : List ℝ), (∀ x ∈ l, 0 ≤ x) → ∀ j,
    (j.factorial : ℝ) * esym l j ≤ l.sum ^ j
  | _, _, 0 => by simp [esym]
  | [], _, j + 1 => by simp [esym]
  | x :: l, h, j + 1 => by
    have hx := h x List.mem_cons_self
    have hl := fun y hy => h y (List.mem_cons_of_mem _ hy)
    have hs : 0 ≤ l.sum := List.sum_nonneg hl
    have ih1 := factorial_mul_esym_le l hl (j + 1)
    have ih0 := factorial_mul_esym_le l hl j
    simp only [esym, List.sum_cons]
    have hb := pow_add_ge hs hx j
    have hf : ((j + 1).factorial : ℝ) = (j + 1) * j.factorial := by
      push_cast [Nat.factorial_succ]; ring
    calc ((j + 1).factorial : ℝ) * (esym l (j + 1) + x * esym l j)
        = ((j + 1).factorial : ℝ) * esym l (j + 1) + (j + 1) * x * (j.factorial * esym l j) := by
          rw [hf]; ring
      _ ≤ l.sum ^ (j + 1) + (j + 1) * x * l.sum ^ j := by
          gcongr
      _ ≤ (l.sum + x) ^ (j + 1) := hb
      _ = (x + l.sum) ^ (j + 1) := by ring

end Symmetric

section Tail

variable {α : Type} [DecidableEq α] (as : List α)

/-- Positions at which two sequences differ. -/
def diff : List α → List α → ℕ
  | a :: l, r :: rs => (if a = r then 0 else 1) + diff l rs
  | _, _ => 0

/-- Mass of the reference symbol `r` under `w`, over the alphabet. -/
def onMass (w : α → ℝ) (r : α) : ℝ := ((as.filter (· = r)).map w).sum

/-- Mass of every other symbol: the position's off-reference mass `ρ`. -/
def offMass (w : α → ℝ) (r : α) : ℝ := ((as.filter (· ≠ r)).map w).sum

/-- Total weight of the sequences differing from the reference in at least
`j` positions; each position is a weight function and a reference symbol. -/
def tail (ps : List ((α → ℝ) × α)) (j : ℕ) : ℝ :=
  ((words as ps.length).map fun l =>
    if j ≤ diff l (ps.map Prod.snd) then weightOf (ps.map Prod.fst) l else 0).sum

omit [DecidableEq α] in
theorem sum_split (p : α → Prop) [DecidablePred p] (f : α → ℝ) : ∀ l : List α,
    (l.map f).sum = ((l.filter p).map f).sum + ((l.filter (¬p ·)).map f).sum
  | [] => by simp
  | a :: l => by
    by_cases h : p a <;> simp [h, sum_split p f l] <;> ring

theorem tail_cons (w : α → ℝ) (r : α) (ps : List ((α → ℝ) × α)) (j : ℕ) :
    tail as ((w, r) :: ps) j =
      (as.map fun a => w a * tail as ps (if a = r then j else j - 1)).sum := by
  simp only [tail, List.length_cons, words, List.map_flatten, sum_flatten, List.map_map]
  congr 1
  refine List.map_congr_left fun a _ => ?_
  rw [← List.sum_map_mul_left]
  simp only [Function.comp_apply, List.map_map]
  congr 1
  refine List.map_congr_left fun l _ => ?_
  simp only [Function.comp_def, List.map_cons, diff, weightOf]
  by_cases h : a = r
  · simp [h]
  · simp only [h, if_false]
    by_cases hj : j ≤ 1 + diff l (ps.map Prod.snd)
    · rw [if_pos hj, if_pos (by omega)]
    · rw [if_neg hj, if_neg (by omega), mul_zero]

omit [DecidableEq α] in
theorem weightOf_nonneg : ∀ (ws : List (α → ℝ)), (∀ w ∈ ws, ∀ a, 0 ≤ w a) →
    ∀ l : List α, 0 ≤ weightOf ws l
  | w :: ws, h, a :: l => mul_nonneg (h w List.mem_cons_self a)
      (weightOf_nonneg ws (fun v hv => h v (List.mem_cons_of_mem _ hv)) l)
  | [], _, _ => by simp [weightOf]
  | _ :: _, _, [] => by simp [weightOf]

/-- **Tail bound.** If every position's weights are nonnegative and sum to at
most 1 over the alphabet, the sequences differing from the reference in at
least `j` positions weigh at most `e_j` of the off-reference masses. -/
theorem tail_le_esym : ∀ (ps : List ((α → ℝ) × α)),
    (∀ p ∈ ps, (∀ a, 0 ≤ p.1 a) ∧ onMass as p.1 p.2 + offMass as p.1 p.2 ≤ 1) →
    ∀ j, tail as ps j ≤ esym (ps.map fun p => offMass as p.1 p.2) j
  | [], _, j => by
    cases j <;> simp [tail, words, diff, weightOf, esym]
  | (w, r) :: ps, h, j => by
    obtain ⟨hw, hm⟩ := h (w, r) List.mem_cons_self
    have hps := fun p hp => h p (List.mem_cons_of_mem _ hp)
    have ih := tail_le_esym ps hps
    have hon : 0 ≤ onMass as w r := List.sum_nonneg fun x hx => by
      obtain ⟨a, _, rfl⟩ := List.mem_map.mp hx; exact hw a
    have hoff : 0 ≤ offMass as w r := List.sum_nonneg fun x hx => by
      obtain ⟨a, _, rfl⟩ := List.mem_map.mp hx; exact hw a
    have hρ : ∀ x ∈ ps.map (fun p => offMass as p.1 p.2), 0 ≤ x := by
      intro x hx
      obtain ⟨p, hp, rfl⟩ := List.mem_map.mp hx
      exact List.sum_nonneg fun y hy => by
        obtain ⟨a, _, rfl⟩ := List.mem_map.mp hy; exact (hps p hp).1 a
    rw [tail_cons, sum_split (· = r)]
    have hA : ((as.filter (· = r)).map fun a =>
        w a * tail as ps (if a = r then j else j - 1)).sum = onMass as w r * tail as ps j := by
      rw [onMass, ← List.sum_map_mul_right]
      congr 1
      refine List.map_congr_left fun a ha => ?_
      have : a = r := by simpa using (List.mem_filter.mp ha).2
      simp [this]
    have hB : ((as.filter (¬· = r)).map fun a =>
        w a * tail as ps (if a = r then j else j - 1)).sum =
        offMass as w r * tail as ps (j - 1) := by
      rw [offMass, ← List.sum_map_mul_right]
      congr 1
      refine List.map_congr_left fun a ha => ?_
      have : a ≠ r := by simpa using (List.mem_filter.mp ha).2
      simp [this]
    rw [hA, hB]
    cases j with
    | zero =>
      have h0 := ih 0
      simp only [esym] at h0 ⊢
      have : 0 ≤ tail as ps 0 := List.sum_nonneg fun x hx => by
        obtain ⟨l, -, rfl⟩ := List.mem_map.mp hx
        simp only [zero_le, if_true]
        exact weightOf_nonneg _ (fun v hv => by
          obtain ⟨p, hp, rfl⟩ := List.mem_map.mp hv; exact (hps p hp).1) l
      nlinarith
    | succ j =>
      simp only [List.map_cons, esym, Nat.add_sub_cancel]
      have h1 := ih (j + 1)
      have h2 := ih j
      have he := esym_nonneg _ hρ (j + 1)
      have hon1 : onMass as w r ≤ 1 := by linarith
      calc onMass as w r * tail as ps (j + 1) + offMass as w r * tail as ps j
          ≤ onMass as w r * esym _ (j + 1) + offMass as w r * esym _ j := by gcongr
        _ ≤ esym _ (j + 1) + offMass as w r * esym _ j := by nlinarith

/-- **The band.** Sequences of equal length with symbols at most 2 that differ
in `d` positions have sums at most `2 d` apart: a sequence within `d`
changes of the reference keeps the counter of `NCA.await`, which moves by
`a − 1` per word, within `2 d` of the reference's at every position. -/
theorem sum_sub_le_diff : ∀ (l r : List ℕ), l.length = r.length → (∀ a ∈ l, a ≤ 2) →
    (∀ a ∈ r, a ≤ 2) → |(l.sum : ℤ) - r.sum| ≤ 2 * diff l r
  | [], [], _, _, _ => by simp
  | [], _ :: _, h, _, _ | _ :: _, [], h, _, _ => by simp at h
  | a :: l, b :: r, h, hl, hr => by
    have ih := sum_sub_le_diff l r (by simpa using h) (fun x hx => hl x (List.mem_cons_of_mem _ hx))
      (fun x hx => hr x (List.mem_cons_of_mem _ hx))
    have ha := hl a List.mem_cons_self
    have hb := hr b List.mem_cons_self
    simp only [List.sum_cons, diff, Nat.cast_add]
    by_cases hab : a = b
    · subst hab; simp only [if_true, Nat.cast_zero, zero_add]
      calc |((a : ℤ) + l.sum) - (a + r.sum)| = |(l.sum : ℤ) - r.sum| := by ring_nf
        _ ≤ _ := ih
    · simp only [hab, if_false, Nat.cast_one]
      calc |((a : ℤ) + l.sum) - (b + r.sum)| ≤ |(a : ℤ) - b| + |(l.sum : ℤ) - r.sum| := by
            rw [show ((a : ℤ) + l.sum) - (b + r.sum) = ((a : ℤ) - b) + ((l.sum : ℤ) - r.sum) by ring]
            exact abs_add_le _ _
        _ ≤ 2 + 2 * diff l r := by
            have : |(a : ℤ) - b| ≤ 2 := abs_le.mpr ⟨by omega, by omega⟩
            linarith
        _ = 2 * (1 + diff l r) := by ring

variable {σ : Type} (δ : σ → α → σ) (F : σ → Prop) [DecidablePred F]

/-- Accepted sequences outside the band weigh at most the tail: the
normalizer's part a banded dynamic program does not see. -/
theorem outside_le_tail (ps : List ((α → ℝ) × α)) (hw : ∀ p ∈ ps, ∀ a, 0 ≤ p.1 a)
    (s : σ) (j : ℕ) :
    ((words as ps.length).map fun l =>
      if j ≤ diff l (ps.map Prod.snd) then score δ F (ps.map Prod.fst) s l else 0).sum ≤
      tail as ps j := by
  apply List.sum_le_sum
  intro l _
  by_cases hj : j ≤ diff l (ps.map Prod.snd)
  · simp only [hj, if_true, score]
    split
    · exact le_rfl
    · exact weightOf_nonneg _ (fun v hv => by
        obtain ⟨p, hp, rfl⟩ := List.mem_map.mp hv; exact hw p hp) l
  · simp [hj]

/-- **Certified banded risk.** If the decoded sequence has weight `x ≥ 0` and
the true normalizer `Z > 0` is at most the banded normalizer plus any upper
bound `U` on the weight outside the band, its posterior risk `1 − x / Z` is at
most `1 − x / (Z_band + U)`, which is what is computed. With `U` the tail
bound `(Σ ρ)^j / j!`, the reported risk is an upper bound. -/
theorem banded_risk_le {x Z Zb U : ℝ} (hx : 0 ≤ x) (hZ : 0 < Z) (h : Z ≤ Zb + U) :
    1 - x / Z ≤ 1 - x / (Zb + U) := by
  have := div_le_div_of_nonneg_left hx hZ h
  linarith

end Tail

section Split

variable {σ α : Type} (δ : σ → α → σ) (F : σ → Prop) [DecidablePred F] (as : List α)

/-- **Forward–backward split.** The sum over all sequences splits at any
position into prefixes, each weighted by the sum over suffixes from the state
it ends in. Grouping prefixes by end state gives
`Z = Σₙ F_k(n) · B_k(n)`, and with the next word's weights separated,
`Z = Σₙ F_k(n) Σₐ q_k(a) B_{k+1}(δ n a)`. -/
theorem dpSum_append : ∀ (ws₁ ws₂ : List (α → ℝ)) (s : σ),
    dpSum δ F as (ws₁ ++ ws₂) s =
      ((words as ws₁.length).map fun l => weightOf ws₁ l * dpSum δ F as ws₂ (l.foldl δ s)).sum
  | [], ws₂, s => by simp [words, weightOf]
  | w :: ws₁, ws₂, s => by
    simp only [List.cons_append, dpSum, List.length_cons, words, List.map_flatten, sum_flatten,
      List.map_map]
    congr 1
    refine List.map_congr_left fun a _ => ?_
    rw [dpSum_append ws₁ ws₂ (δ s a), ← List.sum_map_mul_left]
    simp only [Function.comp_apply, List.map_map]
    congr 1
    refine List.map_congr_left fun l _ => ?_
    simp only [Function.comp_apply, weightOf, List.foldl_cons]
    ring

end Split

end NCA
