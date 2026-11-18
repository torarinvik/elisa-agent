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

/-- Append positions are issued from retained metadata, not live records. -/
structure AppendCursor where
  high : Nat
  live : List Nat
  deriving Repr

def cursorAppend (s : AppendCursor) : AppendCursor :=
  ⟨s.high + 1, s.live ++ [s.high + 1]⟩

def cursorErase (s : AppendCursor) (position : Nat) : AppendCursor :=
  ⟨s.high, s.live.filter (fun p => p != position)⟩

def cursorValid (s : AppendCursor) : Prop := ∀ p ∈ s.live, p ≤ s.high

theorem cursorAppend_valid (s : AppendCursor) (valid : cursorValid s) :
    cursorValid (cursorAppend s) := by
  intro p hp
  simp only [cursorAppend, List.mem_append, List.mem_singleton] at hp
  rcases hp with hp | rfl
  · exact Nat.le_trans (valid p hp) (Nat.le_succ _)
  · exact Nat.le_refl _

theorem cursorErase_valid (s : AppendCursor) (valid : cursorValid s) (p : Nat) :
    cursorValid (cursorErase s p) := by
  intro q hq
  exact valid q (List.mem_filter.mp hq).1

/-- Eviction cannot lower the high-water mark; a later append remains beyond
every previously observed cursor bounded by that mark, even if no records live. -/
theorem cursor_after_eviction (s : AppendCursor) (removed saved : Nat)
    (observed : saved ≤ s.high) :
    saved < (cursorAppend (cursorErase s removed)).high := by
  simp only [cursorAppend, cursorErase]
  omega

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

/-! Working memory (chapter 64): a channel of capacity `c` holds, at step `n`, the entry written at step `i`. -/

namespace NCA

/-- A channel of capacity `c` holds at step `n` the entry written at step `i`. -/
def held (c n i : Nat) : Prop := i ≤ n ∧ n < i + c

/-- An entry is available when it is held or was kept. -/
def available (c : Nat) (kept : Nat → Prop) (n i : Nat) : Prop := held c n i ∨ (kept i ∧ i ≤ n)

/-- 64.1: an entry of age `n - i` is held exactly when its age is below the capacity. -/
theorem held_iff_age {c n i : Nat} (written : i ≤ n) : held c n i ↔ n - i < c := by
  unfold held
  omega

/-- 64.2: a larger holding serves all a smaller one does. -/
theorem held_mono {c c' n i : Nat} (larger : c ≤ c') (was : held c n i) : held c' n i := by
  unfold held at *
  omega

/-- 64.3: two channels read at one step are served as far back as the smaller capacity. -/
theorem held_together {a b n i : Nat} : held a n i ∧ held b n i ↔ held (min a b) n i := by
  unfold held
  omega

/-- 64.4: a decision made `d` steps after an entry was written can keep it exactly when `d < c`. -/
theorem kept_in_time {c i d : Nat} : held c (i + d) i ↔ d < c := by
  unfold held
  omega

/-- 64.5: an entry that is not kept is available at no step from `i + c` on. -/
theorem gone_when_unkept {c n i : Nat} {kept : Nat → Prop} (unkept : ¬ kept i) (late : i + c ≤ n) :
    ¬ available c kept n i := by
  unfold available held
  intro h
  rcases h with h | h
  · omega
  · exact unkept h.1

/-- 64.5: an entry that is kept is available at every step from its own on. -/
theorem kept_is_available {c n i : Nat} {kept : Nat → Prop} (is_kept : kept i) (after : i ≤ n) :
    available c kept n i := Or.inr ⟨is_kept, after⟩

/-- With `k` slots filled first in first out, the entry of keep number `q` is in a slot, when `m` keeps have
been made in all, if it was made and fewer than `k` keeps came after it. -/
def slotted (k m q : Nat) : Prop := q ≤ m ∧ m < q + k

/-- 64.6: what is in a slot stays there until `k` more entries are kept, however many steps that takes:
being in a slot turns on the keeps made and not on the step. -/
theorem slotted_iff_few_since {k m q : Nat} (made : q ≤ m) : slotted k m q ↔ m - q < k := by
  unfold slotted
  omega

/-- 64.6: more slots hold all that fewer do. -/
theorem slotted_mono {k k' m q : Nat} (larger : k ≤ k') (was : slotted k m q) : slotted k' m q := by
  unfold slotted at *
  omega

end NCA
