import Mathlib.MeasureTheory.Measure.MeasureSpace
import Mathlib.Data.Finset.Powerset

/-! Majority over redundant routes (§31.7). Route `i < k` fails on the event
`fails i`. -/
namespace NCA

open Finset MeasureTheory Classical

/-- With threshold `t = ⌈(k+1)/2⌉` (`2t ≤ k + 1`), the vote over `k` routes
answers correctly whenever fewer than `t` fail: the correct answer then has
more than half the votes. -/
theorem vote_correct {k t : ℕ} (small : 2 * t ≤ k + 1) (failing : Finset ℕ)
    (sub : failing ⊆ range k) (few : failing.card < t) :
    k < 2 * (range k \ failing).card := by
  rw [card_sdiff_of_subset sub, card_range]
  omega

/-- If the vote fails, some `t` routes all fail. -/
theorem vote_fails_subset {Ω : Type*} (fails : ℕ → Set Ω) (k t : ℕ) (ω : Ω)
    (many : t ≤ ((range k).filter (fun i => ω ∈ fails i)).card) :
    ω ∈ ⋃ S ∈ (range k).powersetCard t, ⋂ i ∈ S, fails i := by
  obtain ⟨S, hS, card⟩ := exists_subset_card_eq many
  simp only [Set.mem_iUnion, Set.mem_iInter, mem_powersetCard]
  exact ⟨S, ⟨hS.trans (filter_subset _ _), card⟩, fun i hi => (mem_filter.mp (hS hi)).2⟩

/-- The vote's risk: if every set `S` of routes fails jointly with probability
at most `∏ i ∈ S, p i` (independent failures), then `t` or more routes fail
with probability at most `∑_{|S| = t} ∏ i ∈ S, p i`. -/
theorem vote_risk {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω) (fails : ℕ → Set Ω)
    (p : ℕ → ENNReal) (k t : ℕ)
    (joint : ∀ S ∈ (range k).powersetCard t, μ (⋂ i ∈ S, fails i) ≤ ∏ i ∈ S, p i) :
    μ {ω | t ≤ ((range k).filter (fun i => ω ∈ fails i)).card}
      ≤ ∑ S ∈ (range k).powersetCard t, ∏ i ∈ S, p i :=
  calc μ {ω | t ≤ ((range k).filter (fun i => ω ∈ fails i)).card}
      ≤ μ (⋃ S ∈ (range k).powersetCard t, ⋂ i ∈ S, fails i) :=
        measure_mono fun ω h => vote_fails_subset fails k t ω h
    _ ≤ ∑ S ∈ (range k).powersetCard t, μ (⋂ i ∈ S, fails i) := measure_biUnion_finset_le _ _
    _ ≤ ∑ S ∈ (range k).powersetCard t, ∏ i ∈ S, p i := sum_le_sum joint

end NCA
