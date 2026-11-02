import NCA.Reliability.Reliability

/-!
# Module substitution

Replacing a module by another with the same contract leaves every plan
unchanged as a typed object (contracts are the only thing plans refer to), so
well-typedness is preserved trivially. What can change is behavior. These
bounds relate how often the composition's answer changes, and how much its
accuracy can move, to how often the two modules disagree on the inputs they
actually receive.
-/

open MeasureTheory

namespace NCA

variable {Ω ι : Type*} [MeasurableSpace Ω] [Fintype ι] {μ : Measure Ω}

/-- **Substitution change bound.** Suppose the composition's answer can change
only if some invocation `i` of the substituted module disagrees with the
original (`disagree i`). Then the answer changes with probability at most the
sum of the in-situ disagreement probabilities. -/
theorem substitution_change_le {disagree : ι → Set Ω} {d : ι → ENNReal} {same : Set Ω}
    (hd : ∀ i, μ (disagree i) ≤ d i)
    (hprop : (⋂ i, (disagree i)ᶜ) ⊆ same) :
    μ sameᶜ ≤ ∑ i, d i :=
  composition_error_le_sum hd hprop

/-- **Accuracy transfer.** If the original composition is correct and the
answer is unchanged, the substituted one is correct. Hence accuracy drops by
at most the probability that the answer changes. -/
theorem accuracy_transfer {correct correct' same : Set Ω}
    (h : correct ∩ same ⊆ correct') :
    μ correct ≤ μ correct' + μ sameᶜ := by
  calc μ correct ≤ μ (correct' ∪ sameᶜ) := measure_mono fun ω hω => by
        by_cases hs : ω ∈ same
        · exact Or.inl (h ⟨hω, hs⟩)
        · exact Or.inr hs
    _ ≤ μ correct' + μ sameᶜ := measure_union_le _ _

/-- **Substitution accuracy bound.** Combining the two: accuracy after
substitution is at least the original accuracy minus the summed in-situ
disagreement rates. -/
theorem substitution_accuracy_ge {disagree : ι → Set Ω} {d : ι → ENNReal}
    {correct correct' same : Set Ω}
    (hd : ∀ i, μ (disagree i) ≤ d i)
    (hprop : (⋂ i, (disagree i)ᶜ) ⊆ same)
    (h : correct ∩ same ⊆ correct') :
    μ correct ≤ μ correct' + ∑ i, d i :=
  (accuracy_transfer h).trans (by gcongr; exact substitution_change_le hd hprop)

end NCA
