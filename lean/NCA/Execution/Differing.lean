import Mathlib.Algebra.BigOperators.Field
import Mathlib.Algebra.Order.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.Round
import Mathlib.Tactic
import NCA.Execution.Looked

/-! A window laid where presses are foretold to differ (chapter 69, from 69.8 on). -/
namespace NCA

variable {K : Type} [Field K] [LinearOrder K] [IsStrictOrderedRing K]

section Mean

variable {P : Type}

/-- The weighted mean of some numbers. -/
def weightedMean (s : Finset P) (w x : P → K) : K :=
  (∑ p ∈ s, w p * x p) / ∑ p ∈ s, w p

/-- 69.10: a weighted mean, with weights not negative and not all nought, lies in every stretch
that holds the numbers that carry weight. -/
theorem weighted_mean_between (s : Finset P) (w x : P → K) (a b : K)
    (nonneg : ∀ p ∈ s, 0 ≤ w p) (some : 0 < ∑ p ∈ s, w p)
    (inside : ∀ p ∈ s, w p ≠ 0 → a ≤ x p ∧ x p ≤ b) :
    a ≤ weightedMean s w x ∧ weightedMean s w x ≤ b := by
  unfold weightedMean
  rw [le_div_iff₀ some, div_le_iff₀ some, Finset.mul_sum, Finset.mul_sum]
  constructor
  · refine Finset.sum_le_sum fun p ps => ?_
    by_cases zero : w p = 0
    · simp [zero]
    · rw [mul_comm]
      exact mul_le_mul_of_nonneg_left (inside p ps zero).1 (nonneg p ps)
  · refine Finset.sum_le_sum fun p ps => ?_
    by_cases zero : w p = 0
    · simp [zero]
    · rw [mul_comm b]
      exact mul_le_mul_of_nonneg_left (inside p ps zero).2 (nonneg p ps)

/-- 69.10: so it lies between two of the numbers that carry weight, the least and the greatest. -/
theorem weighted_mean_between_two (s : Finset P) (w x : P → K)
    (nonneg : ∀ p ∈ s, 0 ≤ w p) (some : 0 < ∑ p ∈ s, w p) :
    ∃ p ∈ s, ∃ q ∈ s, w p ≠ 0 ∧ w q ≠ 0 ∧ x p ≤ weightedMean s w x ∧ weightedMean s w x ≤ x q := by
  classical
  have weighted : (s.filter fun p => w p ≠ 0).Nonempty := by
    by_contra none
    rw [Finset.not_nonempty_iff_eq_empty, Finset.filter_eq_empty_iff] at none
    have nought : ∑ p ∈ s, w p = 0 :=
      Finset.sum_eq_zero fun p ps => not_not.1 (none ps)
    exact some.ne' nought
  obtain ⟨p, pIn, least⟩ := Finset.exists_min_image _ x weighted
  obtain ⟨q, qIn, greatest⟩ := Finset.exists_max_image _ x weighted
  rw [Finset.mem_filter] at pIn qIn
  obtain ⟨low, high⟩ := weighted_mean_between s w x (x p) (x q) nonneg some fun r rs ne =>
    ⟨least r (Finset.mem_filter.2 ⟨rs, ne⟩), greatest r (Finset.mem_filter.2 ⟨rs, ne⟩)⟩
  exact ⟨p, pIn.1, q, qIn.1, pIn.2, qIn.2, low, high⟩

/-- 69.13: weight that stands off a thing moves the weighted mean beyond the thing by no more than
its share of all the weight times how far off the points that carry it stand. -/
theorem stray_moves_little [DecidableEq P] (s thing : Finset P) (sub : thing ⊆ s) (w x : P → K)
    (a b far : K) (nonneg : ∀ p ∈ s, 0 ≤ w p) (some : 0 < ∑ p ∈ s, w p)
    (inside : ∀ p ∈ thing, a ≤ x p ∧ x p ≤ b)
    (near : ∀ p ∈ s \ thing, w p ≠ 0 → a - far ≤ x p ∧ x p ≤ b + far) :
    a - far * ((∑ p ∈ s \ thing, w p) / ∑ p ∈ s, w p) ≤ weightedMean s w x
      ∧ weightedMean s w x ≤ b + far * ((∑ p ∈ s \ thing, w p) / ∑ p ∈ s, w p) := by
  have total := Finset.sum_sdiff (f := w) sub
  have split := Finset.sum_sdiff (f := fun p => w p * x p) sub
  have onLow : (∑ p ∈ thing, w p) * a ≤ ∑ p ∈ thing, w p * x p := by
    rw [Finset.sum_mul]
    exact Finset.sum_le_sum fun p pT =>
      mul_le_mul_of_nonneg_left (inside p pT).1 (nonneg p (sub pT))
  have onHigh : ∑ p ∈ thing, w p * x p ≤ (∑ p ∈ thing, w p) * b := by
    rw [Finset.sum_mul]
    exact Finset.sum_le_sum fun p pT =>
      mul_le_mul_of_nonneg_left (inside p pT).2 (nonneg p (sub pT))
  have offLow : (∑ p ∈ s \ thing, w p) * (a - far) ≤ ∑ p ∈ s \ thing, w p * x p := by
    rw [Finset.sum_mul]
    refine Finset.sum_le_sum fun p pS => ?_
    by_cases zero : w p = 0
    · simp [zero]
    · exact mul_le_mul_of_nonneg_left (near p pS zero).1 (nonneg p (Finset.sdiff_subset pS))
  have offHigh : ∑ p ∈ s \ thing, w p * x p ≤ (∑ p ∈ s \ thing, w p) * (b + far) := by
    rw [Finset.sum_mul]
    refine Finset.sum_le_sum fun p pS => ?_
    by_cases zero : w p = 0
    · simp [zero]
    · exact mul_le_mul_of_nonneg_left (near p pS zero).2 (nonneg p (Finset.sdiff_subset pS))
  have ne := some.ne'
  unfold weightedMean
  constructor
  · rw [le_div_iff₀ some]
    have spread : (a - far * ((∑ p ∈ s \ thing, w p) / ∑ p ∈ s, w p)) * ∑ p ∈ s, w p
        = a * (∑ p ∈ s, w p) - far * ∑ p ∈ s \ thing, w p := by
      field_simp
    rw [spread, ← total, ← split]
    linarith
  · rw [div_le_iff₀ some]
    have spread : (b + far * ((∑ p ∈ s \ thing, w p) / ∑ p ∈ s, w p)) * ∑ p ∈ s, w p
        = b * (∑ p ∈ s, w p) + far * ∑ p ∈ s \ thing, w p := by
      field_simp
    rw [spread, ← total, ← split]
    linarith

end Mean

section Weight

variable {A : Type} [Fintype A]

/-- The mean, over the ports, of how surely each is foretold to change a point. -/
def portMean (c : A → K) : K := (∑ a, c a) / (Fintype.card A : K)

/-- The weight of a point: how much the ports are foretold to differ there, as the mean over the
ports of the square of what each lies from their mean. -/
def differing (c : A → K) : K := (∑ a, (c a - portMean c) ^ 2) / (Fintype.card A : K)

/-- A weight is never negative. -/
theorem differing_nonneg (c : A → K) : 0 ≤ differing c :=
  div_nonneg (Finset.sum_nonneg fun a _ => sq_nonneg (c a - portMean c)) (Nat.cast_nonneg _)

/-- The mean over the ports lies in every stretch that holds what each port is foretold. -/
theorem portMean_between [Nonempty A] (c : A → K) (lo hi : K)
    (inside : ∀ a, lo ≤ c a ∧ c a ≤ hi) : lo ≤ portMean c ∧ portMean c ≤ hi := by
  have ports : (0 : K) < (Fintype.card A : K) := Nat.cast_pos.2 Fintype.card_pos
  have mean := weighted_mean_between Finset.univ (fun _ : A => (1 : K)) c lo hi
    (fun _ _ => zero_le_one) (by simpa using ports) (fun a _ _ => inside a)
  simpa [weightedMean, portMean] using mean

/-- 69.8: a point every port is foretold to change alike has no weight. -/
theorem alike_no_weight (c : A → K) (v : K) (alike : ∀ a, c a = v) : differing c = 0 := by
  unfold differing
  rw [Finset.sum_eq_zero, zero_div]
  intro a _
  have : Nonempty A := ⟨a⟩
  obtain ⟨low, high⟩ := portMean_between c v v fun b => ⟨(alike b).ge, (alike b).le⟩
  rw [alike a, le_antisymm high low]
  simp

/-- 69.8: and only such a point has none. -/
theorem no_weight_iff_alike [Nonempty A] (c : A → K) : differing c = 0 ↔ ∀ a b, c a = c b := by
  constructor
  · intro none a b
    have ports : (Fintype.card A : K) ≠ 0 := Nat.cast_ne_zero.2 Fintype.card_ne_zero
    unfold differing at none
    rw [div_eq_zero_iff, or_iff_left ports,
      Finset.sum_eq_zero_iff_of_nonneg fun a _ => sq_nonneg (c a - portMean c)] at none
    have atMean : ∀ a, c a = portMean c := fun a =>
      sub_eq_zero.1 ((pow_eq_zero_iff two_ne_zero).1 (none a (Finset.mem_univ a)))
    rw [atMean a, atMean b]
  · intro alike
    exact alike_no_weight c (c (Classical.arbitrary A)) fun a => alike a _

/-- 69.9: where what the ports are foretold lies within a stretch, the weight is at most the square
of the stretch's length. -/
theorem differing_le_sq (c : A → K) (lo e : K) (near : ∀ a, lo ≤ c a ∧ c a ≤ lo + e) :
    differing c ≤ e ^ 2 := by
  rcases isEmpty_or_nonempty A with empty | nonempty
  · simp [differing, sq_nonneg]
  · have ports : (0 : K) < (Fintype.card A : K) := Nat.cast_pos.2 Fintype.card_pos
    obtain ⟨low, high⟩ := portMean_between c lo (lo + e) near
    unfold differing
    rw [div_le_iff₀ ports]
    calc ∑ a, (c a - portMean c) ^ 2 ≤ ∑ _a : A, e ^ 2 := by
          refine Finset.sum_le_sum fun a _ => ?_
          obtain ⟨below, above⟩ := near a
          exact sq_le_sq' (by linarith) (by linarith)
      _ = e ^ 2 * (Fintype.card A : K) := by
          rw [Finset.sum_const, Finset.card_univ, nsmul_eq_mul, mul_comm]

end Weight

section Rounded

variable [FloorRing K]

/-- 69.11: rounding a number that lies between two whole numbers keeps it between them. -/
theorem round_between (x : K) (a b : ℤ) (low : (a : K) ≤ x) (high : x ≤ (b : K)) :
    a ≤ round x ∧ round x ≤ b := by
  rw [round_eq]
  constructor
  · exact Int.le_floor.2 (by linarith)
  · have under : ⌊x + 1 / 2⌋ < b + 1 := Int.floor_lt.2 (by push_cast; linarith)
    omega

/-- The whole number nearest a number, nought for a number below nought. -/
def nearestWhole (x : K) : Nat := (round x).toNat

/-- 69.11: the same for the coordinates of points, which are not negative. -/
theorem nearestWhole_between (x : K) (a b : Nat) (low : (a : K) ≤ x) (high : x ≤ (b : K)) :
    a ≤ nearestWhole x ∧ nearestWhole x ≤ b := by
  obtain ⟨above, below⟩ := round_between x a b (by exact_mod_cast low) (by exact_mod_cast high)
  unfold nearestWhole
  omega

/-- 69.12: if the points that carry weight lie in a box no taller and no wider than the half-width,
the window about the rounded weighted mean of their rows and of their columns holds the box. -/
theorem weighted_window_holds (U : Finset (Nat × Nat)) (w : Nat × Nat → K) (h a b c d : Nat)
    (tall : b ≤ a + h) (wide : d ≤ c + h)
    (nonneg : ∀ p ∈ U, 0 ≤ w p) (some : 0 < ∑ p ∈ U, w p)
    (inside : ∀ p ∈ U, w p ≠ 0 → (a ≤ p.1 ∧ p.1 ≤ b) ∧ (c ≤ p.2 ∧ p.2 ≤ d))
    (z : Nat × Nat) (zr : a ≤ z.1 ∧ z.1 ≤ b) (zc : c ≤ z.2 ∧ z.2 ≤ d) :
    Near h (nearestWhole (weightedMean U w fun p => (p.1 : K))) z.1
      ∧ Near h (nearestWhole (weightedMean U w fun p => (p.2 : K))) z.2 := by
  obtain ⟨rowLow, rowHigh⟩ := weighted_mean_between U w (fun p => (p.1 : K)) a b nonneg some
    fun p pU ne => ⟨Nat.cast_le.2 (inside p pU ne).1.1, Nat.cast_le.2 (inside p pU ne).1.2⟩
  obtain ⟨colLow, colHigh⟩ := weighted_mean_between U w (fun p => (p.2 : K)) c d nonneg some
    fun p pU ne => ⟨Nat.cast_le.2 (inside p pU ne).2.1, Nat.cast_le.2 (inside p pU ne).2.2⟩
  obtain ⟨rowAbove, rowBelow⟩ := nearestWhole_between _ a b rowLow rowHigh
  obtain ⟨colAbove, colBelow⟩ := nearestWhole_between _ c d colLow colHigh
  exact ⟨window_holds h a b _ tall rowAbove rowBelow z.1 zr.1 zr.2,
    window_holds h c d _ wide colAbove colBelow z.2 zc.1 zc.2⟩

/-- 69.12: so a window laid by a map of what each port is foretold to change, weighing each point by
how much the ports differ there, holds every box no larger than its half-width outside which the
ports are foretold alike. -/
theorem differing_window_holds {A : Type} [Fintype A] (U : Finset (Nat × Nat))
    (said : Nat × Nat → A → K) (h a b c d : Nat) (tall : b ≤ a + h) (wide : d ≤ c + h)
    (some : ∃ p ∈ U, ∃ i j, said p i ≠ said p j)
    (inside : ∀ p ∈ U, (∃ i j, said p i ≠ said p j) → (a ≤ p.1 ∧ p.1 ≤ b) ∧ (c ≤ p.2 ∧ p.2 ≤ d))
    (z : Nat × Nat) (zr : a ≤ z.1 ∧ z.1 ≤ b) (zc : c ≤ z.2 ∧ z.2 ≤ d) :
    Near h (nearestWhole (weightedMean U (fun p => differing (said p)) fun p => (p.1 : K))) z.1
      ∧ Near h (nearestWhole (weightedMean U (fun p => differing (said p)) fun p => (p.2 : K)))
        z.2 := by
  obtain ⟨p, pU, i, j, ne⟩ := some
  have : Nonempty A := ⟨i⟩
  have differs : ∀ q, differing (said q) ≠ 0 → ∃ i j, said q i ≠ said q j := by
    intro q weight
    by_contra alike
    exact weight ((no_weight_iff_alike (said q)).2 fun i j =>
      by_contra fun ne => alike ⟨i, j, ne⟩)
  have atP : 0 < differing (said p) :=
    lt_of_le_of_ne (differing_nonneg _)
      (fun none => ne ((no_weight_iff_alike (said p)).1 none.symm i j))
  exact weighted_window_holds U _ h a b c d tall wide (fun q _ => differing_nonneg _)
    (Finset.sum_pos' (fun q _ => differing_nonneg _) ⟨p, pU, atP⟩)
    (fun q qU weight => inside q qU (differs q weight)) z zr zc

omit [FloorRing K] [IsStrictOrderedRing K] in
/-- 69.14: the weighted mean of two coordinates lies from the first by the second's share of the
weight times how far apart they are. -/
theorem mean_of_two (W v a d : K) (some : 0 < W + v) :
    (W * a + v * (a + d)) / (W + v) = a + d * (v / (W + v)) := by
  have ne := some.ne'
  field_simp
  ring

/-- 69.14: weight that stands far from a coordinate draws the middle off it. With weight `W` at `a`
and `v` at `a + d`, the window about the rounded weighted mean leaves `a` out as soon as `v` is more
than the share `(h + 1) / d` of all the weight. -/
theorem stray_weight_misses (h a d : Nat) (W v : K) (some : 0 < W + v)
    (much : ((h : K) + 1) * (W + v) ≤ d * v) :
    ¬ Near h (nearestWhole ((W * a + v * ((a : K) + d)) / (W + v))) a := by
  have far : ((a + h + 1 : Nat) : K) ≤ (W * a + v * ((a : K) + d)) / (W + v) := by
    rw [le_div_iff₀ some]
    push_cast
    nlinarith
  have above : ((a + h + 1 : Nat) : ℤ) ≤ round ((W * a + v * ((a : K) + d)) / (W + v)) := by
    rw [round_eq]
    exact Int.le_floor.2 (by push_cast at far ⊢; linarith)
  unfold Near nearestWhole
  omega

/-- 69.15: two weights far enough apart draw the middle to between them, where the window holds
neither: each need only be more than the share `(h + 1) / d` of all the weight. -/
theorem two_groups_miss_both (h a d : Nat) (W v : K) (some : 0 < W + v)
    (muchFar : ((h : K) + 1) * (W + v) ≤ d * v) (muchNear : ((h : K) + 1) * (W + v) ≤ d * W) :
    ¬ Near h (nearestWhole ((W * a + v * ((a : K) + d)) / (W + v))) a
      ∧ ¬ Near h (nearestWhole ((W * a + v * ((a : K) + d)) / (W + v))) (a + d) := by
  refine ⟨stray_weight_misses h a d W v some muchFar, ?_⟩
  have near : (W * a + v * ((a : K) + d)) / (W + v) ≤ (((a : ℤ) + d - h - 1 : ℤ) : K) := by
    rw [div_le_iff₀ some]
    push_cast
    nlinarith
  have low : ((a : ℤ) : K) ≤ (W * a + v * ((a : K) + d)) / (W + v) := by
    rw [le_div_iff₀ some]
    push_cast
    have : 0 ≤ (d : K) * v := le_trans (by positivity) muchFar
    nlinarith
  obtain ⟨above, below⟩ := round_between _ _ _ low near
  unfold Near nearestWhole
  omega

end Rounded

end NCA
