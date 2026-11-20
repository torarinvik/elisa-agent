import Mathlib.Data.Fintype.Card
import Mathlib.Data.Finset.Lattice.Fold
import Mathlib.Tactic

/-! Payment read off what a press is foretold to change (chapter 68). -/
namespace NCA

variable {P C A : Type}

/-- Whatever a context and a press, they are paid at exactly one of the places the paid place may be:
a context alone gives payment the same chance at every context. -/
theorem paid_once_over_places [Fintype P] [DecidableEq P] (land : C → A → P) (c : C) (a : A) :
    (Finset.univ.filter fun g : P => land c a = g).card = 1 := by
  refine Finset.card_eq_one.mpr ⟨land c a, ?_⟩
  ext g
  simp [eq_comm]

/-- Where landing places fall evenly over the contexts, a paid place alone gives payment the same chance
at every paid place. -/
theorem paid_alike_over_contexts [DecidableEq P] [Fintype C] (land : C → A → P) (a : A) (m : Nat)
    (even : ∀ p : P, (Finset.univ.filter fun c : C => land c a = p).card = m) (g g' : P) :
    (Finset.univ.filter fun c : C => land c a = g).card
      = (Finset.univ.filter fun c : C => land c a = g').card := by
  rw [even g, even g']

/-- A map that is one at a place and nought elsewhere. -/
def shown [DecidableEq P] (l p : P) : Nat := if p = l then 1 else 0

/-- The map of where a press lands laid on the map of the paid place: the largest sum at any place is two
exactly when the press lands on the paid place. One window of two weights, the same at every place, and
the largest over the places tell paid from unpaid. -/
theorem window_two_iff [Fintype P] [DecidableEq P] (l g : P) :
    (Finset.univ.sup fun p => shown l p + shown g p) = 2 ↔ l = g := by
  constructor
  · intro two
    by_contra ne
    have le : (Finset.univ.sup fun p => shown l p + shown g p) ≤ 1 := by
      apply Finset.sup_le
      intro p _
      by_cases hl : p = l
      · simp [shown, hl]
        intro same
        exact ne same
      · have : shown l p = 0 := by simp [shown, hl]
        have : shown g p ≤ 1 := by
          unfold shown
          split_ifs <;> omega
        omega
    omega
  · rintro rfl
    apply le_antisymm
    · apply Finset.sup_le
      intro p _
      unfold shown
      split_ifs <;> omega
    · have at_l := Finset.le_sup (f := fun p => shown l p + shown l p) (Finset.mem_univ l)
      simpa [shown] using at_l

/-- A foretelling that names several places, the true landing place among them, misses no paid press. -/
theorem wide_map_misses_none (told : Finset P) (l g : P) (holds : l ∈ told) (paid : l = g) :
    ∃ p ∈ told, p = g :=
  ⟨l, holds, paid⟩

/-- It answers wrongly only where the paid place is one of the places it named besides the true one. -/
theorem wide_map_wrong_only_at_named [DecidableEq P] (told : Finset P) (l g : P) (fires : ∃ p ∈ told, p = g) (unpaid : l ≠ g) :
    g ∈ told.erase l := by
  obtain ⟨p, named, same⟩ := fires
  subst same
  exact Finset.mem_erase.mpr ⟨fun back => unpaid back.symm, named⟩

end NCA
