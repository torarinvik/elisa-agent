import Mathlib.Tactic

/-! A reading by which things recur (chapter 80). A frame is a family of things, each a picture at a place; a
likeness is read from two pictures alone. How new a thing is against an earlier frame is one less the likeness
of the most alike thing there. -/
namespace NCA

section Recurring

variable {κ P : Type*} [Fintype κ] [Nonempty κ]

/-- How new a picture is against the things of an earlier frame: one less the likeness of the most alike. -/
noncomputable def newness (like : P → P → ℝ) (thing : P) (earlier : κ → P) : ℝ :=
  1 - Finset.univ.sup' Finset.univ_nonempty fun place => like thing (earlier place)

/-- 80.2: rearranging the things of the earlier frame over its places leaves how new a thing is. -/
theorem newness_unmoved (like : P → P → ℝ) (thing : P) (earlier : κ → P) (moved : Equiv.Perm κ) :
    newness like thing (earlier ∘ moved) = newness like thing earlier := by
  unfold newness
  congr 1
  apply le_antisymm
  · apply Finset.sup'_le
    intro place _
    exact Finset.le_sup' (fun place => like thing (earlier place)) (Finset.mem_univ (moved place))
  · apply Finset.sup'_le
    intro place _
    have found := Finset.le_sup' (fun place => like thing ((earlier ∘ moved) place)) (Finset.mem_univ (moved.symm place))
    simp only [Function.comp_apply, Equiv.apply_symm_apply] at found
    exact found

/-- 80.2: a thing whose picture an earlier thing has is not new, where a picture is wholly like itself and no
two are more alike than that. -/
theorem seen_before_is_not_new (like : P → P → ℝ) (self : ∀ picture, like picture picture = 1)
    (most : ∀ one other, like one other ≤ 1) (thing : P) (earlier : κ → P) (place : κ)
    (same : earlier place = thing) : newness like thing earlier = 0 := by
  unfold newness
  have here : like thing (earlier place) = 1 := by rw [same]; exact self thing
  have reached : (1 : ℝ) ≤ Finset.univ.sup' Finset.univ_nonempty fun place => like thing (earlier place) := by
    rw [← here]
    exact Finset.le_sup' (fun place => like thing (earlier place)) (Finset.mem_univ place)
  have bound : Finset.univ.sup' Finset.univ_nonempty (fun place => like thing (earlier place)) ≤ 1 :=
    Finset.sup'_le _ _ fun place _ => most thing (earlier place)
  linarith

omit [Fintype κ] [Nonempty κ] in
/-- 80.3: where no two things of the earlier frame are the same, a rearrangement that moves a place changes
what lies there: what is read at the same place is moved by it. -/
theorem same_place_moves (earlier : κ → P) (apart : Function.Injective earlier) (moved : Equiv.Perm κ)
    (place : κ) (off : moved place ≠ place) : (earlier ∘ moved) place ≠ earlier place :=
  fun same => off (apart same)

end Recurring

end NCA
