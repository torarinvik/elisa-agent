import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Positivity

/-!
# Verified answers

If a verifier accepts a wrong answer with probability at most `m` and
rejects a right one with probability at most `f`, and the answer is wrong
with probability `w ≤ c < 1`, then given acceptance the answer is wrong
with probability at most `m c / ((1 - c)(1 - f))` (`verified_le`).
-/

namespace NCA

/-- **Verified answers** (Theorem 41.1). `wa` is the probability of a
wrong, accepted answer and `a` that of acceptance. -/
theorem verified_le {m f w c wa a : ℝ} (hm : 0 ≤ m) (hf : f < 1) (hw : 0 ≤ w) (hwc : w ≤ c)
    (hc : c < 1) (hwa : wa ≤ m * w) (ha : (1 - f) * (1 - w) ≤ a) :
    wa / a ≤ m * c / ((1 - c) * (1 - f)) := by
  have h1f : 0 < 1 - f := by linarith
  have h1c : 0 < 1 - c := by linarith
  have h1w : 0 < 1 - w := by linarith
  have hpos : 0 < (1 - f) * (1 - w) := mul_pos h1f h1w
  have ha0 : 0 < a := lt_of_lt_of_le hpos ha
  rw [div_le_div_iff₀ ha0 (mul_pos h1c h1f)]
  have step1 : wa * ((1 - c) * (1 - f)) ≤ m * w * ((1 - c) * (1 - f)) :=
    mul_le_mul_of_nonneg_right hwa (by positivity)
  have step2 : m * w * ((1 - c) * (1 - f)) ≤ m * c * ((1 - f) * (1 - w)) := by
    have : w * (1 - c) ≤ c * (1 - w) := by nlinarith
    have := mul_le_mul_of_nonneg_left this (mul_nonneg hm h1f.le)
    nlinarith
  have step3 : m * c * ((1 - f) * (1 - w)) ≤ m * c * a :=
    mul_le_mul_of_nonneg_left ha (mul_nonneg hm (le_trans hw hwc))
  linarith

end NCA
