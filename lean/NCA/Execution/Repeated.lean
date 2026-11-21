import Mathlib.Tactic

/-! A reading repeated (chapter 78). A reading makes a holding of values at places from a holding; it is local
where what it gives a place turns only on what is held near that place. -/
namespace NCA

section Repeated

variable {V α β : Type*}

/-- The places within `k` nears of a place: the place itself, and the places near some place within one less. -/
def within (near : V → Set V) : ℕ → V → Set V
  | 0, place => {place}
  | k + 1, place => {far | ∃ between ∈ within near k place, far ∈ near between}

/-- A reading is local where two holdings alike at every place near a place are read alike there. -/
def Local (near : V → Set V) (read : (V → α) → V → α) : Prop :=
  ∀ one other place, (∀ close ∈ near place, one close = other close) → read one place = read other place

/-- 78.1: after `k` repeats of a local reading, two holdings alike at every place within `k` of a place are
read alike there. -/
theorem repeats_reach (near : V → Set V) (read : (V → α) → V → α) (isLocal : Local near read) (k : ℕ) :
    ∀ (one other : V → α) (place : V), (∀ far ∈ within near k place, one far = other far) →
      read^[k] one place = read^[k] other place := by
  induction k with
  | zero =>
    intro one other place alike
    simpa using alike place (by simp [within])
  | succ k ih =>
    intro one other place alike
    rw [Function.iterate_succ_apply, Function.iterate_succ_apply]
    apply ih
    intro between among
    apply isLocal
    intro far close
    exact alike far ⟨between, among, close⟩

/-- 78.2: where one more repeat leaves a holding as it was, so does every further one. -/
theorem stood_still_stays (read : β → β) (held : β) (k n : ℕ) (still : read^[k + 1] held = read^[k] held)
    (later : k ≤ n) : read^[n] held = read^[k] held := by
  obtain ⟨more, rfl⟩ := Nat.exists_eq_add_of_le later
  have fixed : read (read^[k] held) = read^[k] held := (Function.iterate_succ_apply' read k held).symm.trans still
  rw [Nat.add_comm, Function.iterate_add_apply]
  exact Function.iterate_fixed fixed more

end Repeated

end NCA
