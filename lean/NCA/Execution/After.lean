import Mathlib.Data.Fintype.Card
import Mathlib.Tactic

/-! What the frame after a judged press tells (chapter 74). -/
namespace NCA

section After

variable {P X : Type}

/-- 74.1: a paid press leaves one port that may be the paid one. -/
theorem paid_leaves_one [Fintype P] [DecidableEq P] (pressed : P) :
    (Finset.univ.filter (· = pressed)).card = 1 := by
  simp [Finset.filter_eq']

/-- 74.1: of the ports, an unpaid press leaves all but one that may be the paid one. -/
theorem unpaid_leaves_rest [Fintype P] [DecidableEq P] (pressed : P) :
    (Finset.univ.filter (· ≠ pressed)).card = Fintype.card P - 1 := by
  rw [Finset.filter_ne', Finset.card_erase_of_mem (Finset.mem_univ _), Finset.card_univ]

/-- 74.2: on unpaid presses the teller is seen to err wherever it names the port pressed, so it errs at least
that often. -/
theorem named_pressed_le_errs [DecidableEq P] (presses : Finset X) (paid pressed told : X → P)
    (unpaid : ∀ x ∈ presses, pressed x ≠ paid x) :
    (presses.filter (fun x => told x = pressed x)).card ≤ (presses.filter (fun x => told x ≠ paid x)).card := by
  apply Finset.card_le_card
  intro x hx
  simp only [Finset.mem_filter] at hx ⊢
  exact ⟨hx.1, fun h => unpaid x hx.1 (hx.2.symm.trans h)⟩

/-- 74.2: the lessons taken from unpaid presses are those where the teller names a port other than the one
pressed. The false ones among them number the teller's errors less the errors seen. -/
theorem false_lessons [DecidableEq P] (presses : Finset X) (paid pressed told : X → P)
    (unpaid : ∀ x ∈ presses, pressed x ≠ paid x) :
    ((presses.filter (fun x => told x ≠ pressed x)).filter (fun x => told x ≠ paid x)).card
      = (presses.filter (fun x => told x ≠ paid x)).card - (presses.filter (fun x => told x = pressed x)).card := by
  classical
  have within : presses.filter (fun x => told x = pressed x) ⊆ presses.filter (fun x => told x ≠ paid x) := by
    intro x hx
    simp only [Finset.mem_filter] at hx ⊢
    exact ⟨hx.1, fun h => unpaid x hx.1 (hx.2.symm.trans h)⟩
  rw [← Finset.card_sdiff_of_subset within]
  congr 1
  ext x
  simp only [Finset.mem_filter, Finset.mem_sdiff]
  tauto

/-- 74.3: where the paid port is named on more lessons of a situation than any other port, the port named on
most of them is the paid one. -/
theorem most_named_is_paid (named : P → Nat) (paid most : P) (more : ∀ p, p ≠ paid → named p < named paid)
    (top : ∀ p, named p ≤ named most) : most = paid := by
  by_contra other
  exact absurd (top paid) (not_le.mpr (more most other))

end After

end NCA
