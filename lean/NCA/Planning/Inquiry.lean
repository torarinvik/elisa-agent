import NCA.Planning.Relevance

/-! Choosing what to look at: two situations a view cannot tell apart, whose targets differ, differ on a probe the
target depends on that the view lacks. -/

namespace NCA

/-- **Theorem 54.1 (a contradiction lies outside the view).** -/
theorem disagreeing_probe_outside_view {Obs ι V A : Type*} (component : Obs → ι → V) (Q R : Finset ι)
    (t : Obs → A → Bool) (suffices_for : ∀ o o', AgreeOn component R o o' → t o = t o') (o o' : Obs) (a : A)
    (agree : AgreeOn component Q o o') (differ : t o a ≠ t o' a) :
    ∃ i ∈ R, i ∉ Q ∧ component o i ≠ component o' i := by
  by_contra none
  apply differ
  have alike : AgreeOn component R o o' := by
    intro i inR
    by_contra unlike
    exact none ⟨i, inR, fun inQ => unlike (agree i inQ), unlike⟩
  rw [suffices_for o o' alike]

/-- **Proposition 54.10 (a block of known side holds a marked position), along one axis.** Any `w` positions in a
row, starting anywhere, include a multiple of `w`. -/
theorem run_holds_multiple (w a : ℕ) (positive : 0 < w) : ∃ k, a ≤ w * k ∧ w * k < a + w := by
  have split := Nat.div_add_mod (a + w - 1) w
  have small := Nat.mod_lt (a + w - 1) positive
  exact ⟨(a + w - 1) / w, by omega, by omega⟩

end NCA
