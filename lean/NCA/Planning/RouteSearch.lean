import NCA.Planning.Routing

/-! A finite, nondecreasing list searched from the front returns a smallest
consistent member. Enumeration completeness and execution fidelity are separate
assumptions about a concrete route generator and evaluator. -/

namespace NCA

theorem first_consistent_minimal {α : Type} (cost : α → Nat) (accept : α → Bool)
    (xs : List α) (chosen other : α)
    (ordered : xs.Pairwise (fun x y => cost x ≤ cost y))
    (found : xs.find? accept = some chosen)
    (member : other ∈ xs) (valid : accept other = true) :
    cost chosen ≤ cost other := by
  induction xs with
  | nil => simp at found
  | cons head tail ih =>
    simp only [List.pairwise_cons] at ordered
    by_cases h : accept head = true
    · simp [List.find?, h] at found
      subst chosen
      simp only [List.mem_cons] at member
      rcases member with rfl | member
      · exact Nat.le_refl _
      · exact ordered.1 other member
    · simp [List.find?, h] at found
      simp only [List.mem_cons] at member
      rcases member with rfl | member
      · exact False.elim (h valid)
      · exact ih ordered.2 found member

end NCA
