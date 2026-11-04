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


/-- Follow a partial projection path; a missing field yields `none`. -/
def followPath {α : Type} (field : α → Nat → Option α) : List Nat → α → Option α
  | [], value => some value
  | i :: rest, value => (field value i).bind (followPath field rest)

/-- Concatenated paths have the same partial behavior as sequential routes. -/
theorem followPath_append {α : Type} (field : α → Nat → Option α)
    (first second : List Nat) (value : α) :
    followPath field (first ++ second) value =
      (followPath field first value).bind (followPath field second) := by
  induction first generalizing value with
  | nil => rfl
  | cons i rest ih =>
    simp only [List.cons_append, followPath]
    cases h : field value i with
    | none => rfl
    | some v => simpa [h] using ih v


/-- Sequential filters equal a short-circuiting conjunction of predicates. -/
theorem filter_sequential {α : Type} (p q : α → Bool) (xs : List α) :
    (xs.filter p).filter q = xs.filter (fun x => p x && q x) := by
  induction xs with
  | nil => rfl
  | cons x rest ih =>
    cases hp : p x <;> cases hq : q x <;> simp [List.filter, hp, hq, ih]


/-- A conditional agrees pointwise when each branch is correct on its own guard. -/
theorem conditional_agree {α β : Type} (guard : α → Bool) (yes no truth : α → β)
    (hy : ∀ x, guard x = true → yes x = truth x)
    (hn : ∀ x, guard x = false → no x = truth x) (x : α) :
    (if guard x then yes x else no x) = truth x := by
  cases h : guard x with
  | false => simpa [h] using hn x h
  | true => simpa [h] using hy x h

end NCA
