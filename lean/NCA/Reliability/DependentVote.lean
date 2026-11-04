import NCA.Reliability.Vote
import Mathlib.MeasureTheory.Integral.Lebesgue.Markov
import Mathlib.MeasureTheory.Measure.Typeclasses.Probability
import Mathlib.Tactic.FunProp

/-! Majority bounds without independent route failures (§31.8). -/
namespace NCA

open Finset MeasureTheory Classical

/-- Omitting at most `|O|` indices can remove at most that many failures. -/
theorem vote_omit_forces (fails : ℕ → Prop) (k t : ℕ) (O : Finset ℕ)
    (many : t ≤ ((range k).filter fails).card) :
    t - O.card ≤ (((range k \ O).filter fails).card) := by
  classical
  have sub : (range k).filter fails ⊆ ((range k \ O).filter fails) ∪ O := by
    intro i hi
    by_cases h : i ∈ O
    · exact mem_union_right _ h
    · exact mem_union_left _ (mem_filter.mpr
        ⟨mem_sdiff.mpr ⟨(mem_filter.mp hi).1, h⟩, (mem_filter.mp hi).2⟩)
  have := (card_le_card sub).trans (card_union_le _ _)
  omega

/-- Markov's bound for any finite set of route failures. No joint-error
hypothesis is used: dependence may be arbitrary. -/
theorem dependent_vote_risk {Ω : Type*} [MeasurableSpace Ω]
    (μ : Measure Ω) (fails : ℕ → Set Ω) (meas : ∀ i, MeasurableSet (fails i))
    (S : Finset ℕ) (r : ℕ) (positive : 0 < r) (bad : Set Ω)
    (forced : ∀ ω ∈ bad, r ≤ (S.filter (fun i => ω ∈ fails i)).card)
    (p : ℕ → ENNReal) (marginal : ∀ i ∈ S, μ (fails i) ≤ p i) :
    μ bad ≤ (∑ i ∈ S, p i) / r := by
  classical
  let count : Ω → ENNReal := fun ω => ∑ i ∈ S, (fails i).indicator (fun _ => 1) ω
  have mi (i : ℕ) : Measurable ((fails i).indicator (fun _ : Ω => (1 : ENNReal))) :=
    measurable_const.indicator (meas i)
  have mc : Measurable count := by
    dsimp [count]
    fun_prop
  have counted (ω : Ω) : count ω = ((S.filter (fun i => ω ∈ fails i)).card : ENNReal) := by
    simp [count, Set.indicator_apply, Finset.sum_boole]
  have sub : bad ⊆ {ω | (r : ENNReal) ≤ count ω} := by
    intro ω hω
    change (r : ENNReal) ≤ count ω
    rw [counted]
    exact_mod_cast forced ω hω
  have integral : (∫⁻ ω, count ω ∂μ) ≤ ∑ i ∈ S, p i := by
    dsimp [count]
    rw [lintegral_finsetSum S (fun i _ => mi i)]
    refine sum_le_sum fun i hi => ?_
    simpa [lintegral_indicator_const (meas i)] using marginal i hi
  exact (measure_mono sub).trans ((meas_ge_le_lintegral_div mc.aemeasurable
    (by exact_mod_cast Nat.ne_of_gt positive) (by simp)).trans
      (ENNReal.div_le_div_right integral _))

/-- The executable omitted-subset bound, capped at one for probability
measures. `O` need not be independent of anything: it is a fixed index set. -/
theorem dependent_majority_bound {Ω : Type*} [MeasurableSpace Ω]
    (μ : Measure Ω) [IsProbabilityMeasure μ] (fails : ℕ → Set Ω)
    (meas : ∀ i, MeasurableSet (fails i)) (k t : ℕ) (O : Finset ℕ)
    (small : O.card < t) (p : ℕ → ENNReal)
    (marginal : ∀ i ∈ range k, μ (fails i) ≤ p i) :
    μ {ω | t ≤ ((range k).filter (fun i => ω ∈ fails i)).card}
      ≤ min 1 ((∑ i ∈ range k \ O, p i) / ((t - O.card : ℕ) : ENNReal)) := by
  refine le_min prob_le_one ?_
  apply dependent_vote_risk μ fails meas (range k \ O) (t - O.card) (by omega)
  · intro ω hω
    exact vote_omit_forces (fun i => ω ∈ fails i) k t O hω
  · intro i hi
    exact marginal i (mem_sdiff.mp hi).1

end NCA
