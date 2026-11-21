import Mathlib.Tactic

/-! Teaching on as lessons grow (chapter 77). Before each teaching the weights are multiplied by a factor, and
the teaching adds to them. The additions lie newest first; a weight is one number, and the statements hold of
each weight alike. -/
namespace NCA

section TaughtOn

/-- The weights after the teachings: each addition, and the factor times the weights before it. -/
def weightsAfter (factor start : ℝ) : List ℝ → ℝ
  | [] => start
  | added :: older => added + factor * weightsAfter factor start older

/-- 77.1: the weights after newer teachings on top of older ones are what the newer ones made from nought and,
times the factor once for each newer teaching, the weights the older ones left. -/
theorem weights_append (factor start : ℝ) (newer older : List ℝ) :
    weightsAfter factor start (newer ++ older)
      = weightsAfter factor 0 newer + factor ^ newer.length * weightsAfter factor start older := by
  induction newer with
  | nil => simp [weightsAfter]
  | cons added rest ih =>
    simp only [List.cons_append, weightsAfter, ih, List.length_cons, pow_succ]
    ring

/-- What teachings leave is bounded where each addition is: by the bound over one less the factor. -/
theorem weights_within (factor bound : ℝ) (low : 0 ≤ factor) (high : factor < 1) (nonneg : 0 ≤ bound)
    (added : List ℝ) (each : ∀ a ∈ added, |a| ≤ bound) :
    |weightsAfter factor 0 added| ≤ bound / (1 - factor) := by
  have gap : 0 < 1 - factor := by linarith
  have ne : 1 - factor ≠ 0 := gap.ne'
  induction added with
  | nil => simpa [weightsAfter] using div_nonneg nonneg gap.le
  | cons a older ih =>
    have here := each a (List.mem_cons_self ..)
    have rest := ih (fun x hx => each x (List.mem_cons_of_mem _ hx))
    simp only [weightsAfter]
    calc |a + factor * weightsAfter factor 0 older|
        ≤ |a| + |factor * weightsAfter factor 0 older| := abs_add_le _ _
      _ ≤ bound + factor * (bound / (1 - factor)) := by
          rw [abs_mul, abs_of_nonneg low]
          exact add_le_add here (mul_le_mul_of_nonneg_left rest low)
      _ = bound / (1 - factor) := by field_simp; ring

/-- 77.2: what the teachings before the newer ones put into the weights counts in them at most the factor once
for each newer teaching, times their bound over one less the factor. -/
theorem old_teachings_fade (factor bound : ℝ) (low : 0 ≤ factor) (high : factor < 1) (nonneg : 0 ≤ bound)
    (newer older : List ℝ) (each : ∀ a ∈ older, |a| ≤ bound) :
    |weightsAfter factor 0 (newer ++ older) - weightsAfter factor 0 newer|
      ≤ factor ^ newer.length * (bound / (1 - factor)) := by
  rw [weights_append, add_sub_cancel_left, abs_mul, abs_of_nonneg (pow_nonneg low _)]
  exact mul_le_mul_of_nonneg_left (weights_within factor bound low high nonneg older each) (pow_nonneg low _)

/-- 77.2: taught on with the weights left as they were, the weights are the plain sum of what every teaching
added: nothing fades. -/
theorem warm_keeps_all (start : ℝ) (added : List ℝ) : weightsAfter 1 start added = added.sum + start := by
  induction added with
  | nil => simp [weightsAfter]
  | cons a older ih =>
    simp only [weightsAfter, ih, List.sum_cons]
    ring

/-- 77.3: where the factor, times the growth of the lessons between two teachings taken `power` times over, is
at most one, the factor over `k` teachings is at most one over the growth across them, `power` times over. -/
theorem fade_in_lessons (factor growth : ℝ) (power k : ℕ) (low : 0 ≤ factor) (grows : 0 ≤ growth)
    (enough : factor * growth ^ power ≤ 1) : factor ^ k * (growth ^ k) ^ power ≤ 1 := by
  have same : factor ^ k * (growth ^ k) ^ power = (factor * growth ^ power) ^ k := by
    rw [mul_pow, ← pow_mul, ← pow_mul, mul_comm k power]
  rw [same]
  exact pow_le_one₀ (mul_nonneg low (pow_nonneg grows _)) enough

end TaughtOn

end NCA
