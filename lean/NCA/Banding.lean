import Mathlib.Data.Nat.Factorial.Basic
import Mathlib.Analysis.SpecialFunctions.Exp
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
sequence's risk an upper bound (`banded_risk_le`), within `U / (Zb + U)` of the
exact risk (`banded_risk_slack`).

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

/-- Two sequences cannot differ in more positions than the reference has. -/
theorem diff_le_reference_length : ∀ (l r : List α), diff l r ≤ r.length
  | [], _ => by simp [diff]
  | _ :: _, [] => by simp [diff]
  | a :: l, b :: r => by
    have ih := diff_le_reference_length l r
    simp only [diff, List.length_cons]
    split <;> omega

/-- Mass of the reference symbol `r` under `w`, over the alphabet. -/
def onMass (w : α → ℝ) (r : α) : ℝ := ((as.filter (· = r)).map w).sum

/-- Mass of every other symbol: the position's off-reference mass `ρ`. -/
def offMass (w : α → ℝ) (r : α) : ℝ := ((as.filter (· ≠ r)).map w).sum

/-- Off-mass and log-scale sums can be combined from separate row blocks. -/
theorem row_summary_append (xs ys : List (ℝ × ℝ)) :
    (((xs ++ ys).map Prod.fst).sum, ((xs ++ ys).map Prod.snd).sum) =
      ((xs.map Prod.fst).sum + (ys.map Prod.fst).sum,
       (xs.map Prod.snd).sum + (ys.map Prod.snd).sum) := by
  simp

/-- Total weight of the sequences differing from the reference in at least
`j` positions; each position is a weight function and a reference symbol. -/
def tail (ps : List ((α → ℝ) × α)) (j : ℕ) : ℝ :=
  ((words as ps.length).map fun l =>
    if j ≤ diff l (ps.map Prod.snd) then weightOf (ps.map Prod.fst) l else 0).sum

/-- The tail beyond the number of positions is empty. -/
theorem tail_above_length (ps : List ((α → ℝ) × α)) (j : ℕ) (h : ps.length < j) :
    tail as ps j = 0 := by
  unfold tail
  have hz : ∀ l : List α, ¬j ≤ diff l (ps.map Prod.snd) := by
    intro l
    have bound := diff_le_reference_length l (ps.map Prod.snd)
    simp only [List.length_map] at bound
    omega
  simp [hz]

/-- Scaling a bounded normalized tail by a nonnegative factor preserves its bound. -/
theorem scaled_tail_bound (tail normalized bound factor : ℝ)
    (factor_nonneg : 0 ≤ factor) (scaled : tail = factor * normalized)
    (normalized_le : normalized ≤ bound) : tail ≤ factor * bound := by
  rw [scaled]
  exact mul_le_mul_of_nonneg_left normalized_le factor_nonneg

omit [DecidableEq α] in
theorem sum_split (p : α → Prop) [DecidablePred p] (f : α → ℝ) : ∀ l : List α,
    (l.map f).sum = ((l.filter p).map f).sum + ((l.filter (¬p ·)).map f).sum
  | [] => by simp
  | a :: l => by
    by_cases h : p a <;> simp [h, sum_split p f l] <;> ring

/-- The reference mass and off-reference mass partition the row total. -/
theorem row_mass_partition (w : α → ℝ) (r : α) :
    onMass as w r + offMass as w r = (as.map w).sum := by
  simpa [onMass, offMass] using (sum_split (· = r) w as).symm

/-- Recentered exponentials sum to the same mass as the original weights. -/
theorem anchored_exp_mass (peak : ℝ) (others : List ℝ) :
    Real.exp peak * (1 + (others.map fun x => Real.exp (x - peak)).sum) =
      Real.exp peak + (others.map Real.exp).sum := by
  rw [mul_add, mul_one, ← List.sum_map_mul_left]
  congr 1
  congr 1
  apply List.map_congr_left
  intro x _
  rw [← Real.exp_add]
  congr 1
  ring

/-- The smallest factor at least one that makes a row a subprobability. -/
def rowFactor (w : α → ℝ) : ℝ := max 1 (as.map w).sum

/-- Dividing nonnegative weights by their row factor gives a subprobability. -/
theorem rowFactor_normalizes (w : α → ℝ) (r : α) (hw : ∀ a, 0 ≤ w a) :
    1 ≤ rowFactor as w ∧
    (∀ a, 0 ≤ w a / rowFactor as w) ∧
    onMass as (fun a => w a / rowFactor as w) r +
      offMass as (fun a => w a / rowFactor as w) r ≤ 1 := by
  have hc : 1 ≤ rowFactor as w := le_max_left _ _
  have hcpos : 0 < rowFactor as w := by linarith
  have hsum := row_mass_partition as w r
  refine ⟨hc, fun a => div_nonneg (hw a) (le_of_lt hcpos), ?_⟩
  have hm : (as.map w).sum ≤ rowFactor as w := le_max_right _ _
  have he : onMass as (fun a => w a / rowFactor as w) r +
      offMass as (fun a => w a / rowFactor as w) r =
      (onMass as w r + offMass as w r) / rowFactor as w := by
    simp [onMass, offMass, div_eq_mul_inv, List.sum_map_mul_right, add_mul]
  rw [he, hsum]
  exact (div_le_one hcpos).2 hm

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

/-- Scaling each row scales every tail by the product of its row factors. -/
theorem tail_row_scale : ∀ (rows : List (ℝ × ((α → ℝ) × α))) (j : ℕ),
    tail as (rows.map fun p => ((fun a => p.1 * p.2.1 a), p.2.2)) j =
      (rows.map Prod.fst).prod * tail as (rows.map Prod.snd) j
  | [], j => by simp
  | (c, (w, r)) :: rows, j => by
    simp only [List.map_cons, List.prod_cons]
    rw [tail_cons, tail_cons, ← List.sum_map_mul_left]
    congr 1
    refine List.map_congr_left fun a _ => ?_
    simp only [tail_row_scale rows]
    ring

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

/-- A row-scaled subprobability tail obeys the scaled polynomial bound. -/
theorem scaled_rows_tail_le (rows : List (ℝ × ((α → ℝ) × α))) (j : ℕ)
    (hf : ∀ p ∈ rows, 0 ≤ p.1)
    (hrows : ∀ p ∈ rows, (∀ a, 0 ≤ p.2.1 a) ∧
      onMass as p.2.1 p.2.2 + offMass as p.2.1 p.2.2 ≤ 1) :
    tail as (rows.map fun p => ((fun a => p.1 * p.2.1 a), p.2.2)) j ≤
      (rows.map Prod.fst).prod *
        ((rows.map fun p => offMass as p.2.1 p.2.2).sum ^ j / j.factorial) := by
  have hp : 0 ≤ (rows.map Prod.fst).prod := List.prod_nonneg fun x hx => by
    obtain ⟨p, hp, rfl⟩ := List.mem_map.mp hx
    exact hf p hp
  have hr : ∀ p ∈ rows.map Prod.snd, (∀ a, 0 ≤ p.1 a) ∧
      onMass as p.1 p.2 + offMass as p.1 p.2 ≤ 1 := by
    intro p hp
    obtain ⟨q, hq, rfl⟩ := List.mem_map.mp hp
    exact hrows q hq
  have ho : ∀ x ∈ rows.map (fun p => offMass as p.2.1 p.2.2), 0 ≤ x := by
    intro x hx
    obtain ⟨p, hp, rfl⟩ := List.mem_map.mp hx
    exact List.sum_nonneg fun y hy => by
      obtain ⟨a, _, rfl⟩ := List.mem_map.mp hy
      exact (hrows p hp).1 a
  have he := factorial_mul_esym_le _ ho j
  have hj : (0 : ℝ) < j.factorial := by exact_mod_cast Nat.factorial_pos j
  have hb : esym (rows.map fun p => offMass as p.2.1 p.2.2) j ≤
      (rows.map fun p => offMass as p.2.1 p.2.2).sum ^ j / j.factorial := by
    apply (le_div_iff₀ hj).2
    nlinarith
  rw [tail_row_scale]
  apply mul_le_mul_of_nonneg_left _ hp
  calc tail as (rows.map Prod.snd) j
      ≤ esym ((rows.map Prod.snd).map fun p => offMass as p.1 p.2) j :=
        tail_le_esym as _ hr j
    _ ≤ _ := by simpa [List.map_map, Function.comp_def] using hb

/-- The scaled bound can use the original, rather than normalized, off-mass. -/
theorem scaled_rows_tail_le_original (rows : List (ℝ × ((α → ℝ) × α))) (j : ℕ)
    (hf : ∀ p ∈ rows, 1 ≤ p.1)
    (hrows : ∀ p ∈ rows, (∀ a, 0 ≤ p.2.1 a) ∧
      onMass as p.2.1 p.2.2 + offMass as p.2.1 p.2.2 ≤ 1) :
    tail as (rows.map fun p => ((fun a => p.1 * p.2.1 a), p.2.2)) j ≤
      (rows.map Prod.fst).prod *
        ((rows.map fun p => offMass as (fun a => p.1 * p.2.1 a) p.2.2).sum ^ j /
          j.factorial) := by
  have hfactor : ∀ p ∈ rows, 0 ≤ p.1 := by
    intro p hp
    linarith [hf p hp]
  have hp : 0 ≤ (rows.map Prod.fst).prod := List.prod_nonneg fun x hx => by
    obtain ⟨p, hp, rfl⟩ := List.mem_map.mp hx
    exact hfactor p hp
  have hs : 0 ≤ (rows.map fun p => offMass as p.2.1 p.2.2).sum :=
    List.sum_nonneg fun x hx => by
      obtain ⟨p, hp, rfl⟩ := List.mem_map.mp hx
      exact List.sum_nonneg fun y hy => by
        obtain ⟨a, _, rfl⟩ := List.mem_map.mp hy
        exact (hrows p hp).1 a
  have hle : (rows.map fun p => offMass as p.2.1 p.2.2).sum ≤
      (rows.map fun p => offMass as (fun a => p.1 * p.2.1 a) p.2.2).sum := by
    apply List.sum_le_sum
    intro p hp
    have hm : 0 ≤ offMass as p.2.1 p.2.2 := List.sum_nonneg fun y hy => by
      obtain ⟨a, _, rfl⟩ := List.mem_map.mp hy
      exact (hrows p hp).1 a
    have he : offMass as (fun a => p.1 * p.2.1 a) p.2.2 =
        p.1 * offMass as p.2.1 p.2.2 := by
      simp [offMass, List.sum_map_mul_left]
    rw [he]
    nlinarith [hf p hp]
  calc tail as (rows.map fun p => ((fun a => p.1 * p.2.1 a), p.2.2)) j
      ≤ (rows.map Prod.fst).prod *
          ((rows.map fun p => offMass as p.2.1 p.2.2).sum ^ j / j.factorial) :=
        scaled_rows_tail_le as rows j hfactor hrows
    _ ≤ _ := by
      gcongr

/-- The row factors chosen from arbitrary nonnegative weights bound their tail. -/
theorem tail_le_row_factors (ps : List ((α → ℝ) × α)) (j : ℕ)
    (hw : ∀ p ∈ ps, ∀ a, 0 ≤ p.1 a) :
    tail as ps j ≤ (ps.map fun p => rowFactor as p.1).prod *
      ((ps.map fun p => offMass as p.1 p.2).sum ^ j / j.factorial) := by
  let rows := ps.map fun p => (rowFactor as p.1, ((fun a => p.1 a / rowFactor as p.1), p.2))
  have hf : ∀ p ∈ rows, 1 ≤ p.1 := by
    intro p hp
    obtain ⟨q, hq, rfl⟩ := List.mem_map.mp hp
    exact (rowFactor_normalizes as q.1 q.2 (hw q hq)).1
  have hr : ∀ p ∈ rows, (∀ a, 0 ≤ p.2.1 a) ∧
      onMass as p.2.1 p.2.2 + offMass as p.2.1 p.2.2 ≤ 1 := by
    intro p hp
    obtain ⟨q, hq, rfl⟩ := List.mem_map.mp hp
    exact (rowFactor_normalizes as q.1 q.2 (hw q hq)).2
  have hfactor : ∀ p ∈ ps, rowFactor as p.1 ≠ 0 := by
    intro p hp
    have := (rowFactor_normalizes as p.1 p.2 (hw p hp)).1
    linarith
  have hs := scaled_rows_tail_le_original as rows j hf hr
  have he : ∀ p ∈ ps, (fun a => rowFactor as p.1 * (p.1 a / rowFactor as p.1)) = p.1 := by
    intro p hp
    funext a
    field_simp [hfactor p hp]
  have hlist : ps.map (fun p => ((fun a => rowFactor as p.1 *
      (p.1 a / rowFactor as p.1)), p.2)) = ps := by
    conv_rhs => rw [← List.map_id ps]
    apply List.map_congr_left
    intro p hp
    simp [he p hp]
  have hoff : ps.map (fun p => offMass as (fun a => rowFactor as p.1 *
      (p.1 a / rowFactor as p.1)) p.2) = ps.map (fun p => offMass as p.1 p.2) := by
    apply List.map_congr_left
    intro p hp
    rw [he p hp]
  simp only [rows, List.map_map, Function.comp_def] at hs
  rw [hlist, hoff] at hs
  exact hs

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

/-- The same band bound applies for any nonnegative upper bound on arities. -/
theorem sum_sub_le_diff_bounded (bound : ℕ) : ∀ (l r : List ℕ),
    l.length = r.length → (∀ a ∈ l, a ≤ bound) → (∀ a ∈ r, a ≤ bound) →
    |(l.sum : ℤ) - r.sum| ≤ (bound : ℤ) * diff l r
  | [], [], _, _, _ => by simp [diff]
  | [], _ :: _, h, _, _ | _ :: _, [], h, _, _ => by simp at h
  | a :: l, b :: r, h, hl, hr => by
    have ih := sum_sub_le_diff_bounded bound l r (by simpa using h)
      (fun x hx => hl x (List.mem_cons_of_mem _ hx))
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
        _ ≤ bound + bound * diff l r := by
            have : |(a : ℤ) - b| ≤ bound := abs_le.mpr ⟨by omega, by omega⟩
            linarith
        _ = bound * (1 + diff l r) := by ring

/-- A band covers the whole interval when its half-width reaches both ends. -/
theorem band_covers_interval (centre last half state : ℤ)
    (left : centre ≤ half) (right : last - centre ≤ half)
    (state_left : 0 ≤ state) (state_right : state ≤ last) :
    |state - centre| ≤ half := by
  apply abs_le.mpr
  constructor <;> omega

/-- A state admitted by a row fits storage sized above every row's upper bound. -/
theorem band_storage_covers (state row_upper max_upper width : ℤ)
    (nonneg : 0 ≤ state) (admitted : state ≤ row_upper)
    (row_bound : row_upper ≤ max_upper) (capacity : max_upper < width) :
    0 ≤ state ∧ state < width := by
  omega

/-- An admitted state fits a row stored relative to its lower state bound. -/
theorem packed_band_storage_covers (state low high width : ℤ)
    (lower : low ≤ state) (upper : state ≤ high) (capacity : high - low < width) :
    0 ≤ state - low ∧ state - low < width := by
  omega

/-- Prefix offsets place every admitted state inside its own row interval. -/
theorem ragged_band_storage_covers (state low high start next : ℤ)
    (lower : low ≤ state) (upper : state ≤ high)
    (next_row : next = start + (high - low + 1)) :
    start ≤ start + (state - low) ∧ start + (state - low) < next := by
  omega

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

/-- **Relative slack.** The certified banded risk exceeds the exact risk by at
most `U / (Zb + U)`: a tail bound small next to the band's weight costs little. -/
theorem banded_risk_slack {x Z Zb U : ℝ} (hxZ : x ≤ Z) (hZ : 0 < Z)
    (hb : Zb ≤ Z) (h : Z ≤ Zb + U) :
    (1 - x / (Zb + U)) - (1 - x / Z) ≤ U / (Zb + U) := by
  have hS : 0 < Zb + U := lt_of_lt_of_le hZ h
  have key : x / Z - x / (Zb + U) = x / Z * ((Zb + U - Z) / (Zb + U)) := by
    field_simp
  have hq : x / Z ≤ 1 := (div_le_one hZ).mpr hxZ
  have hr : 0 ≤ (Zb + U - Z) / (Zb + U) := div_nonneg (by linarith) hS.le
  have hr' : (Zb + U - Z) / (Zb + U) ≤ U / (Zb + U) :=
    div_le_div_of_nonneg_right (by linarith) hS.le
  calc (1 - x / (Zb + U)) - (1 - x / Z) = x / Z * ((Zb + U - Z) / (Zb + U)) := by
        linarith [key]
    _ ≤ 1 * ((Zb + U - Z) / (Zb + U)) :=
        mul_le_mul_of_nonneg_right hq hr
    _ ≤ U / (Zb + U) := by linarith

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

theorem foldr_max_nonneg : ∀ l : List ℝ, 0 ≤ l.foldr max 0
  | [] => le_refl 0
  | _ :: l => le_max_of_le_right (foldr_max_nonneg l)

theorem foldr_max_init {b : ℝ} (hb : 0 ≤ b) : ∀ l : List ℝ,
    l.foldr max b = max (l.foldr max 0) b
  | [] => (max_eq_right hb).symm
  | a :: l => by simp only [List.foldr_cons, foldr_max_init hb l, max_assoc]

theorem foldr_max_flatten : ∀ L : List (List ℝ),
    L.flatten.foldr max 0 = (L.map fun l => l.foldr max 0).foldr max 0
  | [] => rfl
  | l :: L => by
    rw [List.flatten_cons, List.foldr_append, foldr_max_init (foldr_max_nonneg _),
      foldr_max_flatten L]
    rfl

theorem mul_foldr_max {c : ℝ} (hc : 0 ≤ c) : ∀ l : List ℝ,
    c * l.foldr max 0 = (l.map (c * ·)).foldr max 0
  | [] => by simp
  | a :: l => by simp only [List.foldr_cons, List.map_cons, mul_max_of_nonneg _ _ hc,
      mul_foldr_max hc l]

/-- **Max-product split.** With nonnegative weights, the best score over all
sequences splits at any position into prefixes, each weighted by the best
suffix score from the state it ends in. -/
theorem dpMax_append : ∀ (ws₁ ws₂ : List (α → ℝ)), (∀ w ∈ ws₁, ∀ a, 0 ≤ w a) → ∀ s : σ,
    dpMax δ F as (ws₁ ++ ws₂) s =
      ((words as ws₁.length).map fun l =>
        weightOf ws₁ l * dpMax δ F as ws₂ (l.foldl δ s)).foldr max 0
  | [], ws₂, _, s => by
    simpa [words, weightOf] using dpMax_nonneg δ F as ws₂ s
  | w :: ws₁, ws₂, hw, s => by
    have hw₁ : ∀ v ∈ ws₁, ∀ a, 0 ≤ v a := fun v hv => hw v (List.mem_cons_of_mem _ hv)
    simp only [List.cons_append, dpMax, List.length_cons, words, List.map_flatten,
      foldr_max_flatten, List.map_map]
    congr 1
    refine List.map_congr_left fun a _ => ?_
    rw [Function.comp_apply, dpMax_append ws₁ ws₂ hw₁ (δ s a),
      mul_foldr_max (hw w (List.mem_cons_self) a), List.map_map]
    simp only [Function.comp_apply, List.map_map]
    congr 1
    refine List.map_congr_left fun l _ => ?_
    simp only [Function.comp_apply, weightOf, List.foldl_cons]
    ring

theorem weightOf_append : ∀ (ws₁ ws₂ : List (α → ℝ)) (l₁ l₂ : List α),
    l₁.length = ws₁.length → weightOf (ws₁ ++ ws₂) (l₁ ++ l₂) = weightOf ws₁ l₁ * weightOf ws₂ l₂
  | [], _, [], _, _ => by simp [weightOf]
  | w :: ws₁, ws₂, a :: l₁, l₂, h => by
    simp only [List.cons_append, weightOf]
    rw [weightOf_append ws₁ ws₂ l₁ l₂ (by simpa using h)]
    ring
  | [], _, _ :: _, _, h => by simp at h
  | _ :: _, _, [], _, h => by simp at h

/-- A sequence split at a position scores the prefix's weight times the
suffix's score from the state the prefix ends in. -/
theorem score_append (ws₁ ws₂ : List (α → ℝ)) (s : σ) (l₁ l₂ : List α)
    (h : l₁.length = ws₁.length) :
    score δ F (ws₁ ++ ws₂) s (l₁ ++ l₂) = weightOf ws₁ l₁ * score δ F ws₂ (l₁.foldl δ s) l₂ := by
  unfold score
  rw [List.foldl_append, weightOf_append ws₁ ws₂ l₁ l₂ h]
  split_ifs <;> ring

/-- **Stitching.** A prefix whose weight times the best suffix score attains
the split maximum, followed by a best suffix from its end state, is a best
sequence: the decoded sequence is traced from the split vectors. -/
theorem stitch_attains (ws₁ ws₂ : List (α → ℝ)) (s : σ) (l₁ l₂ : List α)
    (h : l₁.length = ws₁.length)
    (hpre : weightOf ws₁ l₁ * dpMax δ F as ws₂ (l₁.foldl δ s) = dpMax δ F as (ws₁ ++ ws₂) s)
    (hsuf : score δ F ws₂ (l₁.foldl δ s) l₂ = dpMax δ F as ws₂ (l₁.foldl δ s)) :
    score δ F (ws₁ ++ ws₂) s (l₁ ++ l₂) = dpMax δ F as (ws₁ ++ ws₂) s := by
  rw [score_append δ F ws₁ ws₂ s l₁ l₂ h, hsuf, hpre]

end Split

section Sweep

open Finset

theorem sum_row (m : ℕ) : 2 * ∑ i ∈ range m, |(i : ℤ) - m| = m * (m + 1) := by
  induction m with
  | zero => simp
  | succ n ih =>
    have h : ∀ i ∈ range n, |(i : ℤ) - (n + 1 : ℕ)| = |(i : ℤ) - n| + 1 := by
      intro i hi
      have := mem_range.mp hi
      rw [abs_of_neg (by push_cast; omega), abs_of_neg (by omega)]; push_cast; ring
    rw [sum_range_succ, sum_congr rfl h, sum_add_distrib]
    push_cast at ih ⊢
    simp only [sum_const, card_range, nsmul_eq_mul, mul_one]
    rw [abs_of_neg (by linarith)]
    nlinarith [ih]

/-- **Cursor sweep.** Over all ordered pairs of positions among `m`, the
distances `|i − j|` sum to `(m³ − m) / 3`: a cursor moving between uniformly
random positions sweeps `(m² − 1) / (3m) < m / 3` positions on average. -/
theorem sum_pair_dist (m : ℕ) :
    3 * ∑ i ∈ range m, ∑ j ∈ range m, |(i : ℤ) - j| = (m : ℤ) ^ 3 - m := by
  induction m with
  | zero => simp
  | succ n ih =>
    have row := sum_row n
    have col : ∑ i ∈ range n, |(n : ℤ) - i| = ∑ i ∈ range n, |(i : ℤ) - n| :=
      sum_congr rfl fun i _ => abs_sub_comm _ _
    simp only [sum_range_succ, sum_add_distrib, sub_self, abs_zero, add_zero]
    rw [col]
    push_cast
    nlinarith [ih, row]

end Sweep

end NCA
