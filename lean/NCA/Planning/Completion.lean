import Mathlib.Data.List.Basic

/-! A finite typed completion is a production plus a completion for each
child scope. Any Bellman subsolution is a lower bound on every completion.
This model assumes that the concrete production table and lengths are faithful.
-/

namespace NCA

mutual
inductive TypedCompletion (Ctx : Type) (rule : Ctx → Nat → List Ctx → Prop) : Ctx → Nat → Prop
  | apply {goal cost children lengths} : rule goal cost children →
      TypedCompletions Ctx rule children lengths →
      TypedCompletion Ctx rule goal (cost + lengths.sum)

inductive TypedCompletions (Ctx : Type) (rule : Ctx → Nat → List Ctx → Prop) :
    List Ctx → List Nat → Prop
  | nil : TypedCompletions Ctx rule [] []
  | cons {goal cost goals costs} : TypedCompletion Ctx rule goal cost →
      TypedCompletions Ctx rule goals costs →
      TypedCompletions Ctx rule (goal :: goals) (cost :: costs)
end

mutual
/-- A production-wise lower potential bounds every finite completion. -/
theorem TypedCompletion.lower {Ctx : Type} {rule : Ctx → Nat → List Ctx → Prop}
    (bound : Ctx → Nat)
    (admissible : ∀ goal cost children, rule goal cost children →
      bound goal ≤ cost + (children.map bound).sum) :
    ∀ {goal length}, TypedCompletion Ctx rule goal length → bound goal ≤ length
  | _, _, .apply edge children => by
    apply Nat.le_trans (admissible _ _ _ edge)
    exact Nat.add_le_add_left (TypedCompletions.lower bound admissible children) _

/-- Pointwise completion bounds compose across argument and slot lists. -/
theorem TypedCompletions.lower {Ctx : Type} {rule : Ctx → Nat → List Ctx → Prop}
    (bound : Ctx → Nat)
    (admissible : ∀ goal cost children, rule goal cost children →
      bound goal ≤ cost + (children.map bound).sum) :
    ∀ {goals lengths}, TypedCompletions Ctx rule goals lengths →
      (goals.map bound).sum ≤ lengths.sum
  | _, _, .nil => by simp
  | _, _, .cons head tail => by
    simp only [List.map_cons, List.sum_cons]
    exact Nat.add_le_add (TypedCompletion.lower bound admissible head)
      (TypedCompletions.lower bound admissible tail)
end

end NCA
