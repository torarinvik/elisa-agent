import Mathlib.Data.Option.Basic

/-! Immutable-key exact memory, abstracting away hashing and database machinery. -/
namespace NCA

variable {K V : Type} [DecidableEq K]

def memoryInsert (store : K → Option V) (key : K) (value : V) : K → Option V :=
  fun query => if query = key then
    match store key with
    | none => some value
    | some old => some old
  else store query

theorem memoryInsert_recall (store : K → Option V) (key : K) (value : V)
    (fresh : store key = none) : memoryInsert store key value key = some value := by
  simp [memoryInsert, fresh]

theorem memoryInsert_preserves (store : K → Option V) (key query : K) (value old : V)
    (existing : store query = some old) :
    memoryInsert store key value query = some old := by
  by_cases same : query = key
  · subst query
    simp [memoryInsert, existing]
  · simp [memoryInsert, same, existing]

/-- Capacity admission is conditional on exact transactional byte accounting. -/
theorem memory_capacity {used charge capacity : Nat}
    (admitted : used + charge ≤ capacity) : used ≤ used + charge ∧ used + charge ≤ capacity := by
  exact ⟨Nat.le_add_right used charge, admitted⟩


/-- Zero replay losses preserve each retained success (finite evidence only). -/
theorem retained_success_preserved {I : Type} (baseline candidate : I → Bool)
    (noLoss : ∀ i, ¬ (baseline i = true ∧ candidate i = false)) :
    ∀ i, baseline i = true → candidate i = true := by
  intro i good
  cases current : candidate i with
  | false => exact False.elim (noLoss i ⟨good, current⟩)
  | true => rfl


/-- The executable finite loss count being zero preserves every baseline success. -/
theorem retained_zero_losses (cases : List (Bool × Bool))
    (zero : (cases.filter (fun p => p.1 && !p.2)).length = 0) :
    ∀ p ∈ cases, p.1 = true → p.2 = true := by
  induction cases with
  | nil => simp
  | cons head tail ih =>
    rcases head with ⟨old, current⟩
    cases old <;> cases current <;> simp_all [List.filter]

end NCA
