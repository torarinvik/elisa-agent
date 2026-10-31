import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Data.Real.Basic
import Mathlib.MeasureTheory.Measure.MeasureSpace
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Positivity

/-!
# Calibration under distribution shift, and risk control

`selective_risk_le` (`NCA.Selective`) needs a *valid* bound: the true error
probability `q x` of each input must not exceed its bound `b x`. Calibration
fitted on a reference distribution `P` makes `b` right *on average over `P`*,
not pointwise, so on a deployment distribution `Q ≠ P` it can fail.

This file quantifies the failure and proves the two ingredients of a repair.

1. **Excess.** On any population, the error among answered inputs exceeds the
   target `δ` by at most the answered mass of the bound's deficit `(q − b)⁺`
   (`selective_risk_le_excess`). A density ratio `dQ/dP ≤ W` scales any
   `P`-quantity by at most `W` (`shift_ratio_le`).
2. **Inflation.** Answering only when `λ · b ≤ δ` shrinks the answered set as
   `λ` grows (`inflated_answered_mono`), giving a one-parameter family of
   increasingly cautious policies.
3. **Fixed-sequence testing.** Candidates are tested in a fixed order, from
   most to least cautious. Each test declares its candidate safe; testing stops
   at the first candidate not declared safe. If each test wrongly declares an
   unsafe candidate safe with probability at most `α`, then the probability of
   accepting *any* unsafe candidate is at most `α`
   (`fixed_sequence_le`), without any monotonicity assumption.
4. **Audits.** Labels drawn with known inclusion probabilities `π` estimate
   population sums without bias after weighting by `1 / π`
   (`horvitz_thompson`), so risk-weighted practice labels can also serve as
   audit data.
-/

namespace NCA

open Finset

section Excess

variable {X : Type} [Fintype X]

/-- **Excess over the target.** With weights `p ≥ 0`, true error
probabilities `q` and bounds `b`, the weighted error among inputs answered
under target `δ` is at most `δ` times their weight plus their weighted bound
deficit `max (q − b) 0`. With a valid bound the deficit vanishes and this is
`selective_risk_le`. -/
theorem selective_risk_le_excess (p q b : X → ℝ) (δ : ℝ) (hp : ∀ x, 0 ≤ p x) :
    ∑ x ∈ univ.filter (fun x => b x ≤ δ), p x * q x ≤
      δ * ∑ x ∈ univ.filter (fun x => b x ≤ δ), p x +
        ∑ x ∈ univ.filter (fun x => b x ≤ δ), p x * max (q x - b x) 0 := by
  rw [mul_sum, ← sum_add_distrib]
  refine sum_le_sum fun x hx => ?_
  have hb : b x ≤ δ := (mem_filter.mp hx).2
  have hq : q x ≤ δ + max (q x - b x) 0 := by
    have := le_max_left (q x - b x) 0
    linarith
  calc p x * q x ≤ p x * (δ + max (q x - b x) 0) := mul_le_mul_of_nonneg_left hq (hp x)
    _ = δ * p x + p x * max (q x - b x) 0 := by ring

omit [Fintype X] in
/-- **Density-ratio transfer.** If the deployment weights are at most `W`
times the reference weights, every nonnegative weighted sum grows by at most
the factor `W` (for example the bound deficit measured on the reference
distribution). -/
theorem shift_ratio_le (pP pQ f : X → ℝ) (W : ℝ) (S : Finset X) (hf : ∀ x, 0 ≤ f x)
    (hW : ∀ x, pQ x ≤ W * pP x) :
    ∑ x ∈ S, pQ x * f x ≤ W * ∑ x ∈ S, pP x * f x := by
  rw [mul_sum]
  refine sum_le_sum fun x _ => ?_
  calc pQ x * f x ≤ W * pP x * f x := mul_le_mul_of_nonneg_right (hW x) (hf x)
    _ = W * (pP x * f x) := by ring

/-- **Inflation is monotone.** For nonnegative bounds, a larger inflation
factor answers a subset of the inputs answered by a smaller one. -/
theorem inflated_answered_mono (b : X → ℝ) (δ lam lam' : ℝ) (hb : ∀ x, 0 ≤ b x)
    (hlam : lam ≤ lam') :
    univ.filter (fun x => lam' * b x ≤ δ) ⊆ univ.filter (fun x => lam * b x ≤ δ) := by
  intro x hx
  simp only [mem_filter, mem_univ, true_and] at hx ⊢
  exact (mul_le_mul_of_nonneg_right hlam (hb x)).trans hx

/-- **Horvitz–Thompson.** If input `x` is labeled with probability
`π x > 0`, weighting each label by `1 / π x` makes the expected weighted sum
of `f` over labeled inputs equal to the population sum of `f`. -/
theorem horvitz_thompson (π f : X → ℝ) (hπ : ∀ x, 0 < π x) :
    ∑ x, π x * (f x / π x) = ∑ x, f x :=
  sum_congr rfl fun x _ => by field_simp [(hπ x).ne']

end Excess

section FixedSequence

open MeasureTheory

variable {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω)

/-- Candidates `0, …, k` were all declared safe: testing reached past `k`. -/
def passed (safe : ℕ → Set Ω) (k : ℕ) : Set Ω := ⋂ j ∈ Finset.range (k + 1), safe j

omit [MeasurableSpace Ω] in
theorem passed_subset {safe : ℕ → Set Ω} {j k : ℕ} (hjk : j ≤ k) :
    passed safe k ⊆ safe j := by
  intro ω hω
  simp only [passed, Set.mem_iInter] at hω
  exact hω j (Finset.mem_range.mpr (Nat.lt_succ_of_le hjk))

/-- **Fixed-sequence testing.** Candidates are tested in the order
`0, 1, 2, …`; on the event `safe k` the test declares candidate `k` safe, and
the procedure accepts candidate `k` exactly when all of `0, …, k` were
declared safe. Let `violates k` say that candidate `k` truly violates the
target. If every unsafe candidate is wrongly declared safe with probability
at most `α`, the procedure accepts some unsafe candidate with probability at
most `α`. The proof needs no monotonicity: every acceptance of an unsafe
candidate passes through the *first* unsafe candidate, whose test must have
erred. -/
theorem fixed_sequence_le (safe : ℕ → Set Ω) (violates : ℕ → Prop) [DecidablePred violates]
    (α : ENNReal) (htest : ∀ k, violates k → μ (safe k) ≤ α) :
    μ (⋃ k, ⋃ (_ : violates k), passed safe k) ≤ α := by
  by_cases h : ∃ k, violates k
  · let first := Nat.find h
    have hsub : (⋃ k, ⋃ (_ : violates k), passed safe k) ⊆ safe first := by
      intro ω hω
      simp only [Set.mem_iUnion] at hω
      obtain ⟨k, hk, hω⟩ := hω
      exact passed_subset (Nat.find_min' h hk) hω
    exact (measure_mono hsub).trans (htest first (Nat.find_spec h))
  · push Not at h
    simp [h]

end FixedSequence

end NCA
