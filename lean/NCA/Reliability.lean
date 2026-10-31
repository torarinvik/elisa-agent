import Mathlib.Probability.Independence.Basic

/-!
# Compositional reliability

Error bounds for a composition whose correctness follows from the correctness
of its parts. Each invocation `i` of a finite execution fails on an event
`fail i` of probability at most `ε i`; the composition is correct whenever no
invocation fails (exact downstream modules such as parsers and arithmetic
fail with `ε i = 0`).

These bounds are falsifiable predictions: measured pipeline accuracy below
the independent bound indicates correlated module errors, and below the
union bound indicates that the propagation hypothesis itself is false.
-/

open MeasureTheory ProbabilityTheory

namespace NCA

variable {Ω ι : Type*} [MeasurableSpace Ω] [Fintype ι] {μ : Measure Ω}
  {fail : ι → Set Ω} {ε : ι → ENNReal} {correct : Set Ω}

/-- **Union bound.** Without any independence assumption, the failure
probability of the composition is at most the sum of its parts' failure
probabilities. -/
theorem composition_error_le_sum
    (hfail : ∀ i, μ (fail i) ≤ ε i)
    (hprop : (⋂ i, (fail i)ᶜ) ⊆ correct) :
    μ correctᶜ ≤ ∑ i, ε i := by
  have hsub : correctᶜ ⊆ ⋃ i, fail i := by
    intro ω hω
    by_contra hnot
    exact hω (hprop (by simpa [Set.mem_iInter] using hnot))
  calc μ correctᶜ ≤ μ (⋃ i, fail i) := measure_mono hsub
    _ ≤ ∑ i, μ (fail i) := measure_iUnion_fintype_le μ fail
    _ ≤ ∑ i, ε i := Finset.sum_le_sum fun i _ => hfail i

/-- **Independent product bound.** If invocation failures are independent,
the composition is correct with probability at least `∏ (1 - ε i)`. -/
theorem composition_success_ge_prod [IsProbabilityMeasure μ]
    (hmeas : ∀ i, MeasurableSet (fail i))
    (hindep : iIndepSet fail μ)
    (hfail : ∀ i, μ (fail i) ≤ ε i)
    (hprop : (⋂ i, (fail i)ᶜ) ⊆ correct) :
    ∏ i, (1 - ε i) ≤ μ correct := by
  have hcompl : ∀ i, MeasurableSet[MeasurableSpace.comap (· ∈ fail i) ⊤] (fail i)ᶜ :=
    fun i => ⟨{p | ¬p}, trivial, by ext; simp⟩
  calc ∏ i, (1 - ε i) ≤ ∏ i, (1 - μ (fail i)) :=
        Finset.prod_le_prod' fun i _ => tsub_le_tsub_left (hfail i) 1
    _ = ∏ i, μ (fail i)ᶜ := by simp [prob_compl_eq_one_sub (hmeas _)]
    _ = μ (⋂ i, (fail i)ᶜ) := (hindep.iIndep_comap_mem.meas_iInter hcompl).symm
    _ ≤ μ correct := measure_mono hprop

end NCA
