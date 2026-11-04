import NCA.Reliability.Ensemble

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

end NCA
