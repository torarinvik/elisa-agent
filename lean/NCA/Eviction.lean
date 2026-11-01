import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Algebra.Order.BigOperators.Group.Finset

/-!
# Route-aware eviction

The expert store holds a set `S` of experts, each of size `w e`, within a byte
budget. Executing a route needs its working set `R` resident. A *transition*
from `S` to `S'` serves `R` when `R ⊆ S'`, and costs the bytes loaded,
`bytes (S' \ S)`.

Every transition serving `R` loads at least `bytes (R \ S)`. A route-aware
transition keeps `R ∪ K` for some `K ⊆ S` (it evicts only experts outside
the route, and loads only the route's missing experts), so it loads exactly
`bytes (R \ S)`: it is optimal at every switch. Keeping `K = ∅` is feasible
whenever the route fits the budget. Recency-based policies do not have this property:
they may evict an expert the next route needs.
-/

namespace NCA

open Finset

variable {E : Type} [DecidableEq E] (w : E → Nat)

/-- Total size of a set of experts. -/
def bytes (s : Finset E) : Nat := ∑ e ∈ s, w e

variable {w}

omit [DecidableEq E] in
theorem bytes_mono {s t : Finset E} (h : s ⊆ t) : bytes w s ≤ bytes w t :=
  sum_le_sum_of_subset h

/-- No resident set within budget can serve a route whose working set exceeds it. -/
omit [DecidableEq E] in
theorem oversized_route_infeasible {R S : Finset E} {budget : ℕ}
    (hR : R ⊆ S) (hS : bytes w S ≤ budget) : bytes w R ≤ budget :=
  le_trans (bytes_mono hR) hS

/-- **Lower bound.** Any transition serving `R` loads the route's missing experts. -/
theorem load_lower_bound {S S' R : Finset E} (hR : R ⊆ S') :
    bytes w (R \ S) ≤ bytes w (S' \ S) :=
  bytes_mono (sdiff_subset_sdiff hR le_rfl)

/-- **Route-aware transitions load exactly the missing experts.** -/
theorem routeAware_load {S R K : Finset E} (hK : K ⊆ S) :
    (R ∪ K) \ S = R \ S := by
  ext e
  simp only [mem_sdiff, mem_union]
  constructor
  · rintro ⟨h | h, hS⟩
    · exact ⟨h, hS⟩
    · exact absurd (hK h) hS
  · rintro ⟨h, hS⟩
    exact ⟨Or.inl h, hS⟩

/-- **Optimality.** A route-aware transition loads no more than any transition
serving the same route from the same state. -/
theorem routeAware_optimal {S S' R K : Finset E} (hK : K ⊆ S) (hR : R ⊆ S') :
    bytes w ((R ∪ K) \ S) ≤ bytes w (S' \ S) := by
  rw [routeAware_load hK]
  exact load_lower_bound hR

/-- **Alternation.** Serving `A` then `B` route-aware from a state holding `A`
loads `bytes (B \ A)` at most: experts shared by the routes are never
reloaded. -/
theorem routeAware_switch {A B K : Finset E} (hK : K ⊆ A) :
    bytes w ((B ∪ K) \ A) ≤ bytes w (B \ A) := by
  rw [routeAware_load hK]

/-- **Repetition is free.** Serving a route whose experts are resident loads
nothing, so a task sequence costs only at route changes, and grouping tasks
by route minimizes the number of changes. -/
theorem routeAware_repeat {S R K : Finset E} (hK : K ⊆ S) (hR : R ⊆ S) :
    bytes w ((R ∪ K) \ S) = 0 := by
  rw [routeAware_load hK, sdiff_eq_empty_iff_subset.mpr hR]
  rfl

end NCA
