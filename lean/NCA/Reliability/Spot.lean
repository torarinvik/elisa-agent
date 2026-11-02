import Mathlib.Analysis.SpecialFunctions.Exp

/-!
# Spot checks

If each of `N` cache hits is independently checked with probability `q`
and a fraction `f` of hits are wrong, all `N` pass undetected with
probability `(1 - q f)^N`, which is at most `exp (-(q f N))`
(`undetected_le_exp`).
-/

namespace NCA

/-- **Detection.** `(1 - x)^N ≤ exp (-(x N))` for a per-hit detection
probability `x ≤ 1`. -/
theorem undetected_le_exp {x : ℝ} (hx1 : x ≤ 1) (N : ℕ) :
    (1 - x) ^ N ≤ Real.exp (-(x * N)) := by
  have hstep : 1 - x ≤ Real.exp (-x) := by
    have := Real.add_one_le_exp (-x)
    linarith
  calc (1 - x) ^ N ≤ Real.exp (-x) ^ N := pow_le_pow_left₀ (by linarith) hstep N
    _ = Real.exp (-(x * N)) := by
      rw [← Real.exp_nat_mul]
      ring_nf

end NCA
