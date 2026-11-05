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

def unanimousAnswer {Y : Type} [DecidableEq Y] : List Y → Option Y
  | [] => none
  | first :: rest => if rest.all (fun value => decide (value = first)) then some first else none

def backoffAnswer {Y : Type} [DecidableEq Y] (narrow broad : List Y) : Option Y :=
  if narrow.isEmpty then unanimousAnswer broad else unanimousAnswer narrow

/-- Backoff cannot change the result, including refusal, when the narrow search
has at least one derivation. -/
theorem backoff_preserves_nonempty {Y : Type} [DecidableEq Y] (first : Y)
    (rest broad : List Y) : backoffAnswer (first :: rest) broad = unanimousAnswer (first :: rest) := by
  rfl

/-- If the true output is present among the considered derivations, a returned
unanimous answer is correct for it. -/
theorem unanimous_answer_correct {Y : Type} [DecidableEq Y] (outcomes : List Y)
    (truth answer : Y) (present : truth ∈ outcomes)
    (returned : unanimousAnswer outcomes = some answer) : truth = answer := by
  cases outcomes with
  | nil => simp at present
  | cons first rest =>
    simp only [unanimousAnswer] at returned
    split at returned
    · rename_i agreement
      have equal : first = answer := Option.some.inj returned
      simp only [List.mem_cons] at present
      rcases present with head | tail
      · exact head.trans equal
      · have every := List.all_eq_true.mp agreement truth tail
        have same : truth = first := of_decide_eq_true every
        exact same.trans equal
    · contradiction

#print axioms universally_sound_refuses_ambiguity
#print axioms backoff_preserves_nonempty
#print axioms unanimous_answer_correct

end NCA
