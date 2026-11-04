import Mathlib.Data.Finset.Basic
import Mathlib.Data.List.Basic

/-! Finite declared-effect permissions. These results assume all resource
operations pass through the checked gateway; they do not establish a sandbox. -/
namespace NCA

variable {E : Type} [DecidableEq E]

def effectAllowance (parent requested : Finset E) : Finset E := parent ∩ requested

theorem effectAllowance_subset (parent requested : Finset E) :
    effectAllowance parent requested ⊆ parent := Finset.inter_subset_left

theorem effectAllowance_nested (parent first second : Finset E) :
    effectAllowance (effectAllowance parent first) second ⊆ parent :=
  Finset.Subset.trans (effectAllowance_subset _ _) (effectAllowance_subset _ _)

theorem gateway_authority {parent declared : Finset E} {effect : E}
    (allowed : effect ∈ effectAllowance parent declared) :
    effect ∈ parent ∧ effect ∈ declared := Finset.mem_inter.mp allowed

theorem denied_gateway {parent declared : Finset E} {effect : E}
    (denied : effect ∉ parent ∨ effect ∉ declared) :
    effect ∉ effectAllowance parent declared := by
  intro allowed
  have authority := gateway_authority allowed
  rcases denied with h | h
  · exact h authority.1
  · exact h authority.2

/-- A composite's union advertises its whole footprint, but each child regains
only its own declaration. A sibling adds no authority to that child. -/
theorem composed_child_allowance (parent child sibling : Finset E) :
    effectAllowance (effectAllowance parent (child ∪ sibling)) child =
      effectAllowance parent child := by
  ext effect
  simp only [effectAllowance, Finset.mem_inter, Finset.mem_union]
  constructor
  · intro h
    exact ⟨h.1.1, h.2⟩
  · intro h
    exact ⟨⟨h.1, Or.inl h.2⟩, h.2⟩

theorem sibling_cannot_authorize (parent child sibling : Finset E) (effect : E)
    (undeclared : effect ∉ child) :
    effect ∉ effectAllowance (effectAllowance parent (child ∪ sibling)) child := by
  rw [composed_child_allowance]
  exact denied_gateway (Or.inr undeclared)

/-- A callback's active allowance is the intersection along its call path. -/
def effectPath (parent : Finset E) (declarations : List (Finset E)) : Finset E :=
  declarations.foldl effectAllowance parent

theorem effectPath_subset_parent (parent : Finset E) (declarations : List (Finset E)) :
    effectPath parent declarations ⊆ parent := by
  induction declarations generalizing parent with
  | nil => exact Finset.Subset.refl _
  | cons first rest ih =>
    exact Finset.Subset.trans (ih (effectAllowance parent first)) (effectAllowance_subset _ _)

theorem effectPath_subset_owner (parent owner : Finset E) (declarations : List (Finset E))
    (present : owner ∈ declarations) : effectPath parent declarations ⊆ owner := by
  induction declarations generalizing parent with
  | nil => simp at present
  | cons first rest ih =>
    rcases List.mem_cons.mp present with same | later
    · subst owner
      exact Finset.Subset.trans (effectPath_subset_parent _ rest) Finset.inter_subset_right
    · exact ih (effectAllowance parent first) later

/-- An admitted gateway operation belongs to every callback declaration on
its path, including the candidate being evaluated by a privileged auditor. -/
theorem effectPath_gateway_owner (parent owner : Finset E) (declarations : List (Finset E))
    (present : owner ∈ declarations) {operation : E}
    (allowed : operation ∈ effectPath parent declarations) : operation ∈ owner :=
  effectPath_subset_owner parent owner declarations present allowed

end NCA
