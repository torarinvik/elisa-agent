import Mathlib.Data.Option.Basic
import Mathlib.Data.Rat.Defs
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Positivity
import Mathlib.Tactic.Ring

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

/-- `r` slots are kept at random over the steps counted `1, 2, …` since a mark: step `n` is kept with chance
`r / n`, or surely while the slots are not full, and takes the place of one of the `r` steps held, each as
likely as another. This is the chance that step `t` is held `d` steps later. -/
def keptAtRandom (r t : Nat) : Nat → ℚ
  | 0 => min 1 ((r : ℚ) / t)
  | d + 1 =>
    if t + d + 1 ≤ r then keptAtRandom r t d
    else keptAtRandom r t d * (1 - (r : ℚ) / (t + d + 1 : Nat) * (1 / r))

/-- 64.7: after `n` steps since the mark every one of them is held with the same chance, `r / n`, or surely
while `n ≤ r`: no step is favoured for being early or late. -/
theorem keptAtRandom_even {r t : Nat} (slots : 0 < r) (counted : 0 < t) (d : Nat) :
    keptAtRandom r t d = min 1 ((r : ℚ) / (t + d : Nat)) := by
  induction d with
  | zero => simp [keptAtRandom]
  | succ d ih =>
    have hr : (0 : ℚ) < r := by exact_mod_cast slots
    have hn : (0 : ℚ) < ((t + d : Nat) : ℚ) := by exact_mod_cast Nat.add_pos_left counted d
    have hn' : (0 : ℚ) < ((t + d + 1 : Nat) : ℚ) := by exact_mod_cast Nat.succ_pos (t + d)
    have step : ((t + d + 1 : Nat) : ℚ) = ((t + d : Nat) : ℚ) + 1 := by push_cast; ring
    unfold keptAtRandom
    by_cases full : t + d + 1 ≤ r
    · have h1 : (1 : ℚ) ≤ (r : ℚ) / ((t + d : Nat) : ℚ) := by
        rw [le_div_iff₀ hn]; have : t + d ≤ r := by omega
        simpa using (show ((t + d : Nat) : ℚ) ≤ r by exact_mod_cast this)
      have h2 : (1 : ℚ) ≤ (r : ℚ) / ((t + d + 1 : Nat) : ℚ) := by
        rw [le_div_iff₀ hn']
        simpa using (show ((t + d + 1 : Nat) : ℚ) ≤ r by exact_mod_cast full)
      rw [if_pos full, ih, min_eq_left h1, show t + (d + 1) = t + d + 1 by omega, min_eq_left h2]
    · have over : r ≤ t + d := by omega
      have h1 : (r : ℚ) / ((t + d : Nat) : ℚ) ≤ 1 := by
        rw [div_le_iff₀ hn]
        simpa using (show (r : ℚ) ≤ ((t + d : Nat) : ℚ) by exact_mod_cast over)
      have h2 : (r : ℚ) / ((t + d + 1 : Nat) : ℚ) ≤ 1 := by
        rw [div_le_iff₀ hn', step]; linarith [(div_le_iff₀ hn).mp h1]
      rw [if_neg full, ih, min_eq_right h1, show t + (d + 1) = t + d + 1 by omega, min_eq_right h2, step]
      field_simp
      ring

end NCA
