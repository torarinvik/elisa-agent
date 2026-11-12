import Mathlib.Data.Finset.Basic

/-! Judgements that carry across observations: a set of components that suffices for the target is never refuted
by correct judgements, refutation is permanent, and a learner whose every takeover lowers a potential is taken over
at most as often as the potential's start. -/

namespace NCA

/-- Two observations agree on the components in `S`. -/
def AgreeOn {Obs ι V : Type*} (component : Obs → ι → V) (S : Finset ι) (o o' : Obs) : Prop :=
  ∀ i ∈ S, component o i = component o' i

/-- No two judgements on observations agreeing on `S` give one action opposite verdicts. -/
def ConsistentWith {Obs ι V A : Type*} (component : Obs → ι → V) (S : Finset ι) (J : Finset (Obs × A × Bool)) :
    Prop :=
  ∀ j ∈ J, ∀ j' ∈ J, AgreeOn component S j.1 j'.1 → j.2.1 = j'.2.1 → j.2.2 = j'.2.2

/-- **Theorem 53.1 (a sufficient set is never refuted).** -/
theorem sufficient_set_consistent {Obs ι V A : Type*} (component : Obs → ι → V) (S : Finset ι)
    (J : Finset (Obs × A × Bool)) (t : Obs → A → Bool) (correct : ∀ j ∈ J, j.2.2 = t j.1 j.2.1)
    (suffices_for : ∀ o o', AgreeOn component S o o' → t o = t o') : ConsistentWith component S J := by
  intro j hj j' hj' agree same
  rw [correct j hj, correct j' hj', suffices_for _ _ agree, same]

/-- **Theorem 53.2 (refutation is permanent)**, for fewer judgements. -/
theorem consistent_of_subset_judgements {Obs ι V A : Type*} (component : Obs → ι → V) (S : Finset ι)
    {J J' : Finset (Obs × A × Bool)} (fewer : J' ⊆ J) (consistent : ConsistentWith component S J) :
    ConsistentWith component S J' :=
  fun j hj j' hj' => consistent j (fewer hj) j' (fewer hj')

/-- **Theorem 53.2 (refutation is permanent)**, for more components. -/
theorem consistent_of_subset {Obs ι V A : Type*} (component : Obs → ι → V) {S T : Finset ι}
    (J : Finset (Obs × A × Bool)) (more : S ⊆ T) (consistent : ConsistentWith component S J) :
    ConsistentWith component T J :=
  fun j hj j' hj' agree => consistent j hj j' hj' fun i inS => agree i (more inS)

/-- **Theorem 53.4 (corrections bounded by what matters)**, its counting step: steps that each lower a
natural-number potential number at most the potential at the start. -/
theorem steps_le_potential (potential : ℕ → ℕ) (steps : ℕ)
    (lowers : ∀ i < steps, potential (i + 1) < potential i) : steps ≤ potential 0 := by
  have bound : ∀ m ≤ steps, potential m + m ≤ potential 0 := by
    intro m
    induction m with
    | zero => intro _; simp
    | succ m ih =>
      intro hm
      have := lowers m (by omega)
      have := ih (by omega)
      omega
  have := bound steps le_rfl
  omega

end NCA
