import Mathlib.MeasureTheory.Measure.Dirac
import Mathlib.MeasureTheory.Measure.Typeclasses.Probability

/-! Slot risk under refinement (§29.7). A consumer's failure rate is measured
on the inputs it was evaluated on (`μT`); filled through an upcast, it sees a
refined producer's inputs (`μS`). -/
namespace NCA

open MeasureTheory

/-- With a certificate `μS ≤ c • μT`, the consumer's failure probability on the
refined inputs is at most `c` times its measured rate. -/
theorem slot_risk_transfer {α : Type*} [MeasurableSpace α] {μS μT : Measure α} {c : ENNReal}
    (cert : μS ≤ c • μT) (fails : Set α) : μS fails ≤ c * μT fails := by
  simpa using cert fails

/-- Without such a certificate no rate transfers: for every `ε ≤ 1` there are
probability measures under which the consumer fails with measured rate `ε` and
with certainty on the refined inputs. -/
theorem slot_risk_unbounded {ε : ENNReal} (hε : ε ≤ 1) :
    ∃ μT μS : Measure Bool, IsProbabilityMeasure μT ∧ IsProbabilityMeasure μS ∧
      μT {true} = ε ∧ μS {true} = 1 := by
  refine ⟨ε • Measure.dirac true + (1 - ε) • Measure.dirac false, Measure.dirac true,
    ⟨?_⟩, inferInstance, ?_, by simp⟩
  · simp [add_tsub_cancel_of_le hε]
  · simp
end NCA
