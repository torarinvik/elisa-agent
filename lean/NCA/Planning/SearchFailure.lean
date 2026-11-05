import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.Ring

/-! What a failed bounded search establishes, what more budget can buy, and how
reuse, decomposition and sharing change the cost. `reach b` is the set of
hypotheses a search examines at budget `b`; `ok` is consistency with the goal.
Search costs are model assumptions about a concrete generator. -/

namespace NCA

/-- A search at budget `b` succeeds when it examines a consistent hypothesis. -/
def SearchFound {H : Type} (reach : Nat → Set H) (ok : H → Prop) (b : Nat) : Prop :=
  ∃ h ∈ reach b, ok h

theorem searchFound_mono {H : Type} {reach : Nat → Set H} {ok : H → Prop}
    (mono : ∀ {a b}, a ≤ b → reach a ⊆ reach b) {a b : Nat} (le : a ≤ b)
    (found : SearchFound reach ok a) : SearchFound reach ok b := by
  obtain ⟨h, member, good⟩ := found
  exact ⟨h, mono le member, good⟩

/-- No budget helps a goal that the hypothesis space cannot express. -/
theorem inexpressible_never_found {H : Type} {reach : Nat → Set H} {ok : H → Prop}
    (none : ∀ h, ¬ ok h) (b : Nat) : ¬ SearchFound reach ok b := by
  rintro ⟨h, _, good⟩
  exact none h good

/-- Failure of an exhaustive stage bounds the size of every consistent hypothesis. -/
theorem exhaustive_failure_bounds_size {H : Type} {reach : Nat → Set H} {ok : H → Prop}
    (size : H → Nat) {b n : Nat} (covers : ∀ h, size h ≤ n → h ∈ reach b)
    (failed : ¬ SearchFound reach ok b) {h : H} (good : ok h) : n < size h := by
  by_contra small
  exact failed ⟨h, covers h (Nat.le_of_not_lt small), good⟩

/-- Failure says nothing about an unexamined hypothesis: it may be made consistent
without changing the outcome. -/
theorem failure_silent_on_unreached {H : Type} {reach : Nat → Set H} {ok : H → Prop} {b : Nat}
    (failed : ¬ SearchFound reach ok b) {h : H} (outside : h ∉ reach b) :
    ¬ SearchFound reach (fun x => ok x ∨ x = h) b := by
  rintro ⟨x, member, good | rfl⟩
  · exact failed ⟨x, member, good⟩
  · exact outside member

/-- A budget factor `k` buys `d` further size levels exactly when `m ^ d ≤ k`. -/
theorem budget_factor_buys_size {m : Nat} (positive : 0 < m) (k n d : Nat) :
    m ^ (n + d) ≤ k * m ^ n ↔ m ^ d ≤ k := by
  have base : 0 < m ^ n := Nat.pow_pos positive
  rw [pow_add, Nat.mul_comm (m ^ n) (m ^ d)]
  exact Nat.mul_le_mul_right_iff base

/-- Rerunning all smaller sizes costs at most twice the last when `2 ≤ m`. -/
theorem deepening_overhead {m : Nat} (two : 2 ≤ m) (n : Nat) :
    ∑ i ∈ Finset.range (n + 1), m ^ i ≤ 2 * m ^ n := by
  induction n with
  | zero => simp
  | succ n ih =>
    rw [Finset.sum_range_succ, pow_succ]
    have : 2 * m ^ n ≤ m ^ n * m := by
      rw [Nat.mul_comm]
      exact Nat.mul_le_mul_left _ two
    nlinarith

/-- A library entry that is never used makes uniform enumeration strictly dearer. -/
theorem unused_entry_costs {m n : Nat} (nonzero : n ≠ 0) : m ^ n < (m + 1) ^ n :=
  Nat.pow_lt_pow_left (Nat.lt_succ_self m) nonzero

/-- One new entry pays when it more than halves the size of the route. -/
theorem reuse_pays {m n reduced : Nat} (two : 2 ≤ m) (short : 2 * reduced < n) :
    (m + 1) ^ reduced < m ^ n := by
  have square : m + 1 ≤ m ^ 2 := by nlinarith
  calc (m + 1) ^ reduced ≤ (m ^ 2) ^ reduced := Nat.pow_le_pow_left square _
    _ = m ^ (2 * reduced) := (pow_mul m 2 reduced).symm
    _ < m ^ n := Nat.pow_lt_pow_right (by omega) short

/-- Independently solvable subgoals add where a joint enumeration multiplies. -/
theorem decomposition_adds {m a b : Nat} (two : 2 ≤ m) (left : a ≠ 0) (right : b ≠ 0) :
    m ^ a + m ^ b ≤ m ^ (a + b) := by
  have first : 2 ≤ m ^ a := le_trans two (Nat.le_self_pow left m)
  have second : 2 ≤ m ^ b := le_trans two (Nat.le_self_pow right m)
  rw [pow_add]
  nlinarith

/-- Cost of `depth` binary decompositions with `w` alternatives at each level. -/
def guidedCost (w leaf : Nat) : Nat → Nat
  | 0 => leaf
  | depth + 1 => w * (2 * guidedCost w leaf depth)

theorem guidedCost_closed (w leaf depth : Nat) :
    guidedCost w leaf depth = (2 * w) ^ depth * leaf := by
  induction depth with
  | zero => simp [guidedCost]
  | succ depth ih =>
    simp only [guidedCost, ih, pow_succ]
    ring

/-- A strategy with share `p / q` of `T` steps receives its `t` steps once `t * q ≤ p * T`. -/
theorem share_suffices {p q t T : Nat} (positive : 0 < q) (enough : t * q ≤ p * T) :
    t ≤ p * T / q :=
  (Nat.le_div_iff_mul_le positive).mpr enough

/-- Sharing `T` steps finds nothing a strategy would not find when given all `T`. -/
theorem sharing_only_redistributes {H : Type} {reach : Nat → Set H} {ok : H → Prop}
    (mono : ∀ {a b}, a ≤ b → reach a ⊆ reach b) {share T : Nat} (within : share ≤ T)
    (found : SearchFound reach ok share) : SearchFound reach ok T :=
  searchFound_mono mono within found

end NCA
