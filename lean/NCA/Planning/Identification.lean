import Mathlib.Data.List.Basic

/-! Identifiability limits of learning from final-answer observations. -/

namespace NCA

def agreesWithExamples {X Y : Type} (examples : List (X × Y)) (hypothesis : X → Y) : Prop :=
  ∀ entry ∈ examples, hypothesis entry.1 = entry.2

/-- A selector that is correct for every hypothesis consistent with the given
final answers must refuse whenever two such hypotheses disagree. -/
theorem universally_sound_refuses_ambiguity {X Y : Type}
    (examples : List (X × Y)) (query : X) (select : Option Y) (admissible : (X → Y) → Prop)
    (left right : X → Y)
    (leftAllowed : admissible left) (rightAllowed : admissible right)
    (leftConsistent : agreesWithExamples examples left)
    (rightConsistent : agreesWithExamples examples right)
    (different : left query ≠ right query)
    (sound : ∀ hypothesis, admissible hypothesis → agreesWithExamples examples hypothesis →
      ∀ answer, select = some answer → hypothesis query = answer) :
    select = none := by
  cases result : select with
  | none => rfl
  | some answer =>
    have leftAnswer := sound left leftAllowed leftConsistent answer result
    have rightAnswer := sound right rightAllowed rightConsistent answer result
    exact (different (leftAnswer.trans rightAnswer.symm)).elim

#print axioms universally_sound_refuses_ambiguity

end NCA
