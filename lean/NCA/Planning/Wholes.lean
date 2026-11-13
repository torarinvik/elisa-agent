import Mathlib.Logic.Equiv.Defs

/-! Wholes judged by their parts: a whole is good when every part is, each judged by one function. -/

namespace NCA

/-- **Proposition 57.1 (parts exchanged).** A whole is good exactly when the whole with its parts exchanged is. -/
theorem whole_exchanged {I P : Type*} (good : P → Prop) (part : I → P) (exchange : I ≃ I) :
    (∀ i, good (part (exchange i))) ↔ ∀ i, good (part i) :=
  ⟨fun every i => by simpa using every (exchange.symm i), fun every i => every (exchange i)⟩

/-- **Proposition 57.2 (the blame lies where the two differ).** If every part of the choice is good and the proposal
is not good in every part, some part of the proposal that differs from the choice is bad. -/
theorem takeover_blames_differing {I P : Type*} (good : P → Prop) (proposed right : I → P)
    (choice : ∀ i, good (right i)) (bad : ¬∀ i, good (proposed i)) :
    ∃ i, proposed i ≠ right i ∧ ¬good (proposed i) :=
  Classical.byContradiction fun none => bad fun i =>
    (Classical.em (proposed i = right i)).elim (fun shared => by rw [shared]; exact choice i)
      (fun differs => Classical.byContradiction fun wrong => none ⟨i, differs, wrong⟩)

/-- **Proposition 57.3 (a bad part shows what no good part shows).** Where whether a part is good is a function of
what a view reads of it, the view reads of a bad part what it reads of no good part. -/
theorem bad_part_shows_unmet {P R : Type*} (good : P → Prop) (view : P → R)
    (settles : ∀ a b, view a = view b → (good a ↔ good b)) (bad kept : P) (wrong : ¬good bad) (right : good kept) :
    view kept ≠ view bad :=
  fun alike => wrong ((settles kept bad alike).mp right)

end NCA
