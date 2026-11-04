import NCA.Reliability.SampledGate

/-! Fixed-size tolerant admission (§20.22). Sampling/coupling and the reference
CDF bound are hypotheses, not a proof of an arbitrary external sampler. -/
namespace NCA
open MeasureTheory

def lossTest : ℕ → List Bool → Bool × ℕ
  | _, [] => (true, 0)
  | k, true :: rest => ((lossTest k rest).1, (lossTest k rest).2 + 1)
  | 0, false :: _ => (false, 1)
  | k + 1, false :: rest => ((lossTest k rest).1, (lossTest k rest).2 + 1)

theorem lossTest_admits (cases : List Bool) (allowance : ℕ) :
    (lossTest allowance cases).1 = true ↔ cases.count false ≤ allowance := by
  induction cases generalizing allowance with
  | nil => simp [lossTest]
  | cons bit rest ih =>
    cases bit <;> cases allowance <;> simp [lossTest, ih]

theorem lossTest_reads (cases : List Bool) (allowance : ℕ) :
    (lossTest allowance cases).2 ≤ cases.length ∧
      ((lossTest allowance cases).1 = true → (lossTest allowance cases).2 = cases.length) := by
  induction cases generalizing allowance with
  | nil => simp [lossTest]
  | cons bit rest ih =>
    cases bit
    · cases allowance with
      | zero => simp [lossTest]
      | succ n =>
        have h := ih n
        simp only [lossTest, List.length_cons]
        exact ⟨by omega, fun passed => by rw [h.2 passed]⟩
    · have h := ih allowance
      simp only [lossTest, List.length_cons]
      exact ⟨by omega, fun passed => by rw [h.2 passed]⟩

theorem tolerant_test_miss {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    (passed : Set Ω) (errors reference : Ω → ℕ) (cutoff : ℕ) (α : ℝ)
    (admission : passed ⊆ {ω | errors ω ≤ cutoff})
    (coupling : ∀ ω, reference ω ≤ errors ω)
    (cdf : μ {ω | reference ω ≤ cutoff} ≤ ENNReal.ofReal α) :
    μ passed ≤ ENNReal.ofReal α := by
  apply le_trans (measure_mono admission)
  apply le_trans (measure_mono (show {ω | errors ω ≤ cutoff} ⊆
      {ω | reference ω ≤ cutoff} from fun ω h => (coupling ω).trans h))
  exact cdf

end NCA
