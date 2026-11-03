import Mathlib.Data.Finset.Basic

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

end NCA
