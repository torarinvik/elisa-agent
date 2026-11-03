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


/-- A managed publication is the old snapshot unless both replay checks accept. -/
def guardedPublish {S : Type} (original proposed : S) (retained current : Bool) : S :=
  if retained && current then proposed else original

theorem guardedPublish_refused {S : Type} (original proposed : S) (retained current : Bool)
    (refused : retained = false ∨ current = false) :
    guardedPublish original proposed retained current = original := by
  rcases refused with h | h <;> simp [guardedPublish, h]

theorem guardedPublish_invariant {S : Type} (P : S → Prop) (original proposed : S)
    (retained current : Bool) (old : P original)
    (checked : retained = true → current = true → P proposed) :
    P (guardedPublish original proposed retained current) := by
  cases retained <;> cases current <;> simp_all [guardedPublish]

end NCA

namespace NCA

/-- Protected dispatch has no implicit fallback outside its registered bindings. -/
def protectedLookup {Q A P : Type} (bindings : Q → Option A) (catalog : A → Option P)
    (request : Q) : Option P := (bindings request).bind catalog

theorem protectedLookup_missing {Q A P : Type} (bindings : Q → Option A)
    (catalog : A → Option P) (request : Q) (missing : bindings request = none) :
    protectedLookup bindings catalog request = none := by
  simp [protectedLookup, missing]

theorem protectedLookup_refused {Q A P : Type} (bindings : Q → Option A)
    (original proposed : A → Option P) (request : Q) (retained current : Bool)
    (refused : retained = false ∨ current = false) :
    protectedLookup bindings (guardedPublish original proposed retained current) request =
      protectedLookup bindings original request := by
  rw [guardedPublish_refused original proposed retained current refused]

end NCA
