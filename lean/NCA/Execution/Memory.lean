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

end NCA
