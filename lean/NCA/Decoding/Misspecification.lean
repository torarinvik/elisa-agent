import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-!
# Decoding under a wrong prior

The decoder of `NCA.Decoding` weights each parseable arity sequence `a` by
`w a`, the product of per-word arity probabilities: its posterior weight
under the model prior `π_P` of premise (P). If formulas actually come from a
prior `π*`, the true posterior weights are `w a · ρ a` with `ρ = π* / π_P`,
since the readings' likelihoods are the same under both. Let `E` be the
event that the decoded sequence is wrong.

* If `ρ ≤ C` on `E` and `ρ ≥ c` off `E` (that is, at the decoded sequence),
  the true odds of an error are at most `C / c` times the model's odds
  (`reweighted_odds`). The true risk is then at most `Λ R / (1 − R + Λ R)`
  with `Λ = C / c` (`reweighted_risk_le`), hence at most `Λ R` when `Λ ≥ 1`
  (`reweighted_risk_le_mul`).
* If `ρ` at the decoded sequence is at least `ρ` everywhere else, `Λ = 1`
  and the model's risk is conservative (`dominated_risk_le`). This is the
  case of a true prior that only removes mass from (P), when the decoded
  sequence keeps its mass.
* With no constraint on the prior, nothing holds: a prior with weight 1 on
  any competitor of positive weight and weight `t` on the decoded sequence
  makes the true risk at least `1 − t ŵ / w'` (`adversarial_prior`), which
  tends to 1 as `t → 0`.
-/

namespace NCA

open Finset

section Reweighting

variable {ι : Type} (s : Finset ι) (E : ι → Prop) [DecidablePred E] (w ρ : ι → ℝ)

/-- **Odds under reweighting.** With nonnegative weights and ratios,
`ρ ≤ C` on the event and `ρ ≥ c ≥ 0` off it, the reweighted odds of the
event are at most `C / c` times the original odds (stated without
division). -/
theorem reweighted_odds {c C : ℝ} (hw : ∀ i ∈ s, 0 ≤ w i) (hρ : ∀ i ∈ s, 0 ≤ ρ i)
    (hc0 : 0 ≤ c) (hC : ∀ i ∈ s, E i → ρ i ≤ C) (hc : ∀ i ∈ s, ¬E i → c ≤ ρ i) :
    c * (∑ i ∈ s.filter E, w i * ρ i) * (∑ i ∈ s.filter (¬E ·), w i) ≤
      C * (∑ i ∈ s.filter E, w i) * (∑ i ∈ s.filter (¬E ·), w i * ρ i) := by
  have hA : ∑ i ∈ s.filter E, w i * ρ i ≤ C * ∑ i ∈ s.filter E, w i := by
    rw [mul_sum]
    refine sum_le_sum fun i hi => ?_
    obtain ⟨hs, he⟩ := mem_filter.mp hi
    nlinarith [hw i hs, hC i hs he]
  have hB : c * ∑ i ∈ s.filter (¬E ·), w i ≤ ∑ i ∈ s.filter (¬E ·), w i * ρ i := by
    rw [mul_sum]
    refine sum_le_sum fun i hi => ?_
    obtain ⟨hs, he⟩ := mem_filter.mp hi
    nlinarith [hw i hs, hc i hs he]
  have hA0 : 0 ≤ ∑ i ∈ s.filter E, w i * ρ i :=
    sum_nonneg fun i hi => mul_nonneg (hw i (mem_filter.mp hi).1) (hρ i (mem_filter.mp hi).1)
  have hb0 : 0 ≤ c * ∑ i ∈ s.filter (¬E ·), w i :=
    mul_nonneg hc0 (sum_nonneg fun i hi => hw i (mem_filter.mp hi).1)
  calc c * (∑ i ∈ s.filter E, w i * ρ i) * (∑ i ∈ s.filter (¬E ·), w i)
      = (∑ i ∈ s.filter E, w i * ρ i) * (c * ∑ i ∈ s.filter (¬E ·), w i) := by ring
    _ ≤ (C * ∑ i ∈ s.filter E, w i) * (∑ i ∈ s.filter (¬E ·), w i * ρ i) :=
        mul_le_mul hA hB hb0 (hA0.trans hA)
    _ = _ := by ring

end Reweighting

section Risk

/-- **Risk under reweighting.** If the true odds `A / B` are at most
`C / c` times the model's odds `a / b`, the true risk `A / (A + B)` is at
most `Λ a / (b + Λ a)` with `Λ = C / c`, which is `Λ R / (1 − R + Λ R)` in
terms of the model's risk `R = a / (a + b)`. -/
theorem reweighted_risk_le {A B a b c C : ℝ} (hA : 0 ≤ A) (hB : 0 ≤ B) (ha : 0 ≤ a)
    (hc : 0 < c) (hC : 0 ≤ C) (hpos : 0 < b + C / c * a) (h : c * A * b ≤ C * a * B) :
    A / (A + B) ≤ C / c * a / (b + C / c * a) := by
  have hΛ : 0 ≤ C / c * a := mul_nonneg (div_nonneg hC hc.le) ha
  rcases (add_nonneg hA hB).eq_or_lt with h0 | h0
  · rw [← h0, div_zero]
    exact div_nonneg hΛ hpos.le
  · rw [div_le_div_iff₀ h0 hpos]
    have hcC : c * (C / c * a * B) = C * a * B := by field_simp
    have key : A * b ≤ C / c * a * B :=
      le_of_mul_le_mul_left (by rw [hcC]; linarith) hc
    nlinarith

/-- **At most `Λ` times the model's risk.** When `Λ = C / c ≥ 1`, the bound
of `reweighted_risk_le` is at most `Λ R`. -/
theorem reweighted_risk_le_mul {A B a b c C : ℝ} (hA : 0 ≤ A) (hB : 0 ≤ B) (ha : 0 ≤ a)
    (hc : 0 < c) (hcC : c ≤ C) (hab : 0 < a + b) (h : c * A * b ≤ C * a * B) :
    A / (A + B) ≤ C / c * (a / (a + b)) := by
  have hΛ1 : 1 ≤ C / c := by rw [le_div_iff₀ hc]; linarith
  have hle : a + b ≤ b + C / c * a := by nlinarith
  calc A / (A + B) ≤ C / c * a / (b + C / c * a) :=
        reweighted_risk_le hA hB ha hc (hc.le.trans hcC) (hab.trans_le hle) h
    _ ≤ C / c * a / (a + b) :=
        div_le_div_of_nonneg_left (mul_nonneg (by linarith) ha) hab hle
    _ = C / c * (a / (a + b)) := by ring

/-- **Dominated competitors.** If the prior ratio at the decoded sequence is
at least the ratio at every wrong sequence (`Λ = 1`), the true risk is at
most the model's: removing prior mass from competitors only helps. -/
theorem dominated_risk_le {A B a b κ : ℝ} (hA : 0 ≤ A) (hB : 0 ≤ B) (ha : 0 ≤ a)
    (hκ : 0 < κ) (hab : 0 < a + b) (h : κ * A * b ≤ κ * a * B) :
    A / (A + B) ≤ a / (a + b) := by
  have := reweighted_risk_le_mul hA hB ha hκ le_rfl hab h
  rwa [div_self hκ.ne', one_mul] at this

/-- **No prior, no bound.** A prior with weight 1 on a competitor of
positive weight `w'` and weight `t ≥ 0` on the decoded sequence (weight
`ŵ`) gives true risk `w' / (w' + t ŵ) ≥ 1 − t ŵ / w'`, which tends to 1 as
`t → 0`. -/
theorem adversarial_prior {w' ŵ t : ℝ} (hw' : 0 < w') (hŵ : 0 ≤ ŵ) (ht : 0 ≤ t) :
    1 - t * ŵ / w' ≤ w' / (w' + t * ŵ) := by
  have h0 : 0 ≤ t * ŵ := mul_nonneg ht hŵ
  have hle : t * ŵ / (w' + t * ŵ) ≤ t * ŵ / w' :=
    div_le_div_of_nonneg_left h0 hw' (by linarith)
  have e : w' / (w' + t * ŵ) = 1 - t * ŵ / (w' + t * ŵ) := by
    field_simp
    ring
  linarith

end Risk

end NCA
