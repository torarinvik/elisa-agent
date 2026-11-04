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


/-- Adding a candidate leaves every previously admitted member available. -/
theorem append_preserves_admitted {α : Type} (old added : List α) {route : α}
    (admitted : route ∈ old) : route ∈ old ++ added := by
  exact List.mem_append_left added admitted


/-- Equal observed arguments stay equal through a pure binary context. -/
theorem observed_pair_congruent {α β γ δ : Type} (cases : List α)
    (left left' : α → β) (right right' : α → γ) (combine : β → γ → δ)
    (hl : ∀ x ∈ cases, left x = left' x)
    (hr : ∀ x ∈ cases, right x = right' x) :
    ∀ x ∈ cases, combine (left x) (right x) = combine (left' x) (right' x) := by
  intro x hx
  rw [hl x hx, hr x hx]


/-- Slot bodies that agree on every actual call give equal mapped results. -/
theorem map_agree_on_calls {α β : Type} (f g : α → β) (calls : List α)
    (agree : ∀ x ∈ calls, f x = g x) : calls.map f = calls.map g := by
  induction calls with
  | nil => rfl
  | cons x rest ih =>
    simp only [List.map_cons, List.cons.injEq]
    exact ⟨agree x (by simp), ih (by intro y hy; exact agree y (by simp [hy]))⟩

/-- Replacing a fold step preserves the result if the steps agree at every
state on each actual input element. Singleton examples alone do not imply
this hypothesis. -/
theorem fold_agree_on_elements {α σ : Type} (f g : σ → α → σ) (items : List α)
    (start : σ) (agree : ∀ state item, item ∈ items → f state item = g state item) :
    items.foldl f start = items.foldl g start := by
  induction items generalizing start with
  | nil => rfl
  | cons item rest ih =>
    simp only [List.foldl_cons]
    rw [agree start item (by simp)]
    apply ih
    intro state value member
    exact agree state value (by simp [member])


/-- Every positive-cost child consumes at least one unit of a route's budget. -/
theorem positive_children_arity_bound (parent : Nat) (children : List Nat)
    (positive : ∀ cost ∈ children, 1 ≤ cost) :
    parent + children.length ≤ parent + children.sum := by
  have lower : children.length ≤ children.sum := by
    induction children with
    | nil => simp
    | cons head tail ih =>
      have head_positive := positive head (by simp)
      have tail_positive : ∀ cost ∈ tail, 1 ≤ cost := by
        intro cost member
        exact positive cost (by simp [member])
      have tail_bound := ih tail_positive
      simp only [List.length_cons, List.sum_cons]
      omega
  omega

/-- A witness tree has checked leaves and witness-decomposed internal goals. -/
inductive WitnessDerivation {σ : Type} (satisfied : σ → Prop)
    (decomposes : σ → List σ → Prop) : σ → Prop
  | leaf (goal : σ) : satisfied goal → WitnessDerivation satisfied decomposes goal
  | split (goal : σ) (children : List σ) :
      decomposes goal children →
      (∀ child ∈ children, WitnessDerivation satisfied decomposes child) →
      WitnessDerivation satisfied decomposes goal

/-- Sound witnesses compose through arbitrarily nested decompositions. -/
theorem witness_derivation_sound {σ : Type} {satisfied : σ → Prop}
    {decomposes : σ → List σ → Prop}
    (sound : ∀ goal children, decomposes goal children →
      (∀ child ∈ children, satisfied child) → satisfied goal)
    {goal : σ} (derivation : WitnessDerivation satisfied decomposes goal) : satisfied goal := by
  induction derivation with
  | leaf _ valid => exact valid
  | split goal children witness _ ih =>
    exact sound goal children witness (by intro child member; exact ih child member)

end NCA
