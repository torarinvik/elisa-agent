import NCA.Reliability.SampledGate

/-! End-to-end ensemble certification (§31.9). Failure rate is that of the
whole vote, including abstention. No hypothesis about internal route-error
independence occurs; the fresh-case miss law remains a sampling hypothesis. -/
namespace NCA

open MeasureTheory Finset

theorem ensemble_miss {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    (passed : Set Ω) {ε loss α : ℝ} {m : ℕ}
    (bad : ε < loss) (rate : loss ≤ 1) (positive : 0 < α)
    (size : Real.log (1 / α) ≤ ε * m)
    (fresh : μ passed ≤ ENNReal.ofReal ((1 - loss) ^ m)) :
    μ passed ≤ ENNReal.ofReal α :=
  fresh.trans (ENNReal.ofReal_le_ofReal (zeroLoss_miss bad rate positive size))

/-- Route growth and early stopping use a finite stage allocation. Each
stage's rate is the actual vote's rate, not a product of marginal rates. -/
theorem ensemble_search_sound {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    {δ : ℝ} (positive : 0 ≤ δ) (n : ℕ) (sizes : ℕ → ℕ)
    (wrong : ℕ → ℕ → Set Ω) (returned : Set Ω)
    (tested : returned ⊆ ⋃ k ∈ range n, ⋃ s ∈ range (sizes k), wrong k s)
    (share : ∀ k ∈ range n, ∀ s ∈ range (sizes k),
      μ (wrong k s) ≤ ENNReal.ofReal (decisionLevel δ k / sizes k)) :
    μ returned ≤ ENNReal.ofReal δ :=
  staged_acquisition_sound μ positive n sizes wrong returned tested share

end NCA
