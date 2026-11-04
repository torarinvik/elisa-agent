import NCA.Reliability.Ensemble
import Mathlib.Algebra.BigOperators.Field
import Mathlib.Data.Nat.Size

/-! Description-length confidence allocation. The fresh zero-loss probability
bound is a sampling hypothesis; code-length budgets require a Kraft bound. -/

namespace NCA

/-- A route of length `L` spends `δ / 2^L`; the stated sample size bounds
its zero-loss miss probability when its true error exceeds `ε`. -/
theorem occam_zero_loss {ε loss δ : ℝ} {L m : ℕ}
    (bad : ε < loss) (rate : loss ≤ 1) (positive : 0 < δ)
    (size : (L : ℝ) * Real.log 2 + Real.log (1 / δ) ≤ ε * m) :
    (1 - loss) ^ m ≤ δ / (2 : ℝ) ^ L := by
  apply zeroLoss_miss bad rate (by positivity)
  have pow_pos : (0 : ℝ) < (2 : ℝ) ^ L := by positivity
  have identity : Real.log (1 / (δ / (2 : ℝ) ^ L)) =
      (L : ℝ) * Real.log 2 + Real.log (1 / δ) := by
    rw [one_div, Real.log_inv, Real.log_div (ne_of_gt positive) (ne_of_gt pow_pos),
        Real.log_pow, one_div, Real.log_inv]
    ring
  rw [identity]
  exact size


open MeasureTheory Finset

/-- A finite Kraft-bounded code family spends at most its declared level. -/
theorem occam_family_sound {Ω ι : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    (family : Finset ι) (length : ι → ℕ) (bad : ι → Set Ω) {δ : ℝ}
    (nonnegative : 0 ≤ δ)
    (kraft : ∑ i ∈ family, (1 : ℝ) / (2 : ℝ) ^ length i ≤ 1)
    (share : ∀ i ∈ family, μ (bad i) ≤ ENNReal.ofReal (δ / (2 : ℝ) ^ length i)) :
    μ (⋃ i ∈ family, bad i) ≤ ENNReal.ofReal δ := by
  calc
    μ (⋃ i ∈ family, bad i) ≤ ∑ i ∈ family, μ (bad i) := measure_biUnion_finset_le _ _
    _ ≤ ∑ i ∈ family, ENNReal.ofReal (δ / (2 : ℝ) ^ length i) :=
      sum_le_sum fun i hi => share i hi
    _ = ENNReal.ofReal (∑ i ∈ family, δ / (2 : ℝ) ^ length i) := by
      rw [ENNReal.ofReal_sum_of_nonneg]
      intro i _
      positivity
    _ ≤ ENNReal.ofReal δ := by
      apply ENNReal.ofReal_le_ofReal
      have bound := mul_le_mul_of_nonneg_left kraft nonnegative
      have eq : (∑ i ∈ family, δ / (2 : ℝ) ^ length i) =
          δ * (∑ i ∈ family, (1 : ℝ) / (2 : ℝ) ^ length i) := by
        rw [mul_sum]
        apply sum_congr rfl
        intro i _
        ring
      rw [eq]
      linarith

/-- Kraft-bounded route families may be charged within each adaptive decision. -/
theorem occam_adaptive_sound {Ω ι : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    {δ : ℝ} (nonnegative : 0 ≤ δ) (n : ℕ) (families : ℕ → Finset ι)
    (length : ℕ → ι → ℕ) (bad : ℕ → ι → Set Ω)
    (kraft : ∀ k ∈ range n, ∑ i ∈ families k, (1 : ℝ) / (2 : ℝ) ^ length k i ≤ 1)
    (share : ∀ k ∈ range n, ∀ i ∈ families k,
      μ (bad k i) ≤ ENNReal.ofReal (decisionLevel δ k / (2 : ℝ) ^ length k i)) :
    μ (⋃ k ∈ range n, ⋃ i ∈ families k, bad k i) ≤ ENNReal.ofReal δ := by
  apply acquisition_sound μ nonnegative n
  intro k hk
  apply occam_family_sound μ (families k) (length k) (bad k)
  · unfold decisionLevel
    positivity
  · exact kraft k hk
  · exact share k hk


/-- Fresh zero-loss bounds combine with Kraft and adaptive decision budgets. -/
theorem occam_adaptive_fresh {Ω ι : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    {δ ε : ℝ} (positive : 0 < δ) (n : ℕ) (families : ℕ → Finset ι)
    (length : ℕ → ι → ℕ) (bad : ℕ → ι → Set Ω)
    (loss : ℕ → ι → ℝ) (samples : ℕ → ι → ℕ)
    (kraft : ∀ k ∈ range n, ∑ i ∈ families k, (1 : ℝ) / (2 : ℝ) ^ length k i ≤ 1)
    (bad_rate : ∀ k ∈ range n, ∀ i ∈ families k, ε < loss k i ∧ loss k i ≤ 1)
    (size : ∀ k ∈ range n, ∀ i ∈ families k,
      (length k i : ℝ) * Real.log 2 + Real.log (1 / decisionLevel δ k) ≤
        ε * samples k i)
    (fresh : ∀ k ∈ range n, ∀ i ∈ families k,
      μ (bad k i) ≤ ENNReal.ofReal ((1 - loss k i) ^ samples k i)) :
    μ (⋃ k ∈ range n, ⋃ i ∈ families k, bad k i) ≤ ENNReal.ofReal δ := by
  apply occam_adaptive_sound μ (le_of_lt positive) n families length bad kraft
  intro k hk i hi
  have level_positive : 0 < decisionLevel δ k := by
    unfold decisionLevel
    positivity
  exact (fresh k hk i hi).trans (ENNReal.ofReal_le_ofReal
    (occam_zero_loss (bad_rate k hk i hi).1 (bad_rate k hk i hi).2
      level_positive (size k hk i hi)))


/-- Local dyadic production lengths satisfy Kraft when each assigned length
has enough capacity for its smoothed weight. -/
theorem weighted_lengths_kraft {ι : Type*} (choices : Finset ι)
    (weight : ι → ℝ) (length : ι → ℕ) (total : ℝ) (positive : 0 < total)
    (sum_weight : ∑ i ∈ choices, weight i = total)
    (capacity : ∀ i ∈ choices, total ≤ weight i * (2 : ℝ) ^ length i) :
    ∑ i ∈ choices, (1 : ℝ) / (2 : ℝ) ^ length i ≤ 1 := by
  have each : ∀ i ∈ choices, (1 : ℝ) / (2 : ℝ) ^ length i ≤ weight i / total := by
    intro i hi
    have hp : (0 : ℝ) < (2 : ℝ) ^ length i := by positivity
    apply (div_le_div_iff₀ hp positive).2
    simpa using capacity i hi
  calc
    ∑ i ∈ choices, (1 : ℝ) / (2 : ℝ) ^ length i ≤ ∑ i ∈ choices, weight i / total :=
      sum_le_sum each
    _ = (∑ i ∈ choices, weight i) / total := by rw [Finset.sum_div]
    _ = 1 := by rw [sum_weight, div_self (ne_of_gt positive)]


/-- The bit-length formula used by the implementation for a local choice. -/
def productionBits (total weight : ℕ) : ℕ :=
  max 1 (Nat.size ((total - 1) / weight))

/-- Rounded integer lengths have enough dyadic capacity for their weight. -/
theorem productionBits_capacity {total weight : ℕ} (htotal : 0 < total)
    (hweight : 0 < weight) : total ≤ weight * 2 ^ productionBits total weight := by
  have hsize := Nat.lt_size_self ((total - 1) / weight)
  have hle : Nat.size ((total - 1) / weight) ≤ productionBits total weight := by
    exact Nat.le_max_right _ _
  have hp : 2 ^ Nat.size ((total - 1) / weight) ≤ 2 ^ productionBits total weight :=
    Nat.pow_le_pow_right (by decide) hle
  have hdiv : (total - 1) / weight < 2 ^ productionBits total weight := lt_of_lt_of_le hsize hp
  have hmul : total - 1 < 2 ^ productionBits total weight * weight :=
    (Nat.div_lt_iff_lt_mul hweight).mp hdiv
  rw [Nat.mul_comm] at hmul
  omega


/-- Smoothed natural-number production weights satisfy local Kraft. -/
theorem productionBits_kraft {ι : Type*} (choices : Finset ι) (weight : ι → ℕ)
    (total : ℕ) (positive : 0 < total)
    (weights_positive : ∀ i ∈ choices, 0 < weight i)
    (sum_weight : ∑ i ∈ choices, weight i = total) :
    ∑ i ∈ choices, (1 : ℝ) / (2 : ℝ) ^ productionBits total (weight i) ≤ 1 := by
  apply weighted_lengths_kraft choices (fun i => (weight i : ℝ))
    (fun i => productionBits total (weight i)) (total : ℝ)
  · exact_mod_cast positive
  · exact_mod_cast sum_weight
  · intro i hi
    exact_mod_cast productionBits_capacity positive (weights_positive i hi)

end NCA
