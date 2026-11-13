import Mathlib.Data.Set.Basic

/-! Looking ahead: a situation lasts `d + 1` steps when an action not ruled out leads to one that lasts `d`. -/

namespace NCA

/-- A situation lasts `d` steps when `d` actions in a row can be taken from it, none ruled out. -/
def Lasts {S A : Type*} (ruled : S → A → Prop) (follow : S → A → S) : ℕ → S → Prop
  | 0, _ => True
  | d + 1, s => ∃ a, ¬ruled s a ∧ Lasts ruled follow d (follow s a)

/-- **Proposition 56.1 (lasting longer is lasting shorter).** -/
theorem lasts_shorter {S A : Type*} (ruled : S → A → Prop) (follow : S → A → S) :
    ∀ d s, Lasts ruled follow (d + 1) s → Lasts ruled follow d s := by
  intro d
  induction d with
  | zero => intro _ _; trivial
  | succ d step =>
    rintro s ⟨a, open_, rest⟩
    exact ⟨a, open_, step _ rest⟩

/-- **Proposition 56.2 (ruling out less rules out no path).** -/
theorem lasts_of_fewer_ruled {S A : Type*} (ruled ruled' : S → A → Prop) (follow : S → A → S)
    (fewer : ∀ s a, ruled s a → ruled' s a) :
    ∀ d s, Lasts ruled' follow d s → Lasts ruled follow d s := by
  intro d
  induction d with
  | zero => intro _ _; trivial
  | succ d step =>
    rintro s ⟨a, open_, rest⟩
    exact ⟨a, fun out => open_ (fewer s a out), step _ rest⟩

end NCA
