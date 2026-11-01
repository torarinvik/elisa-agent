import Mathlib.Data.Real.Basic
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Positivity
import Mathlib.Tactic.Ring

/-!
# Which item to climb, and when to stop

Three facts about refinement's control decisions.

* **Cost of reaching a target** (`cost_ge_of_ratio`). If no climb lowers the
  bound by more than `r` per unit of compute, lowering it by `D` costs at
  least `D / r`, whatever the order. This is the fractional relaxation of
  the covering problem refinement solves, and the bound climbing by largest
  drop per unit cost attains in that relaxation.
* **Floors grow quadratically in fixed words** (`pairs_ge_count`). The pairs
  function of `t` risks, each at least `a`, is at least `t (t − 1) / 2 · a²`.
  So the pairs floor passes `δ` after about `1 + √(2δ) / a` fixed words, with
  `a` the risk of the words fixed first, the riskiest ones.
* **One-step lookahead** (`lookahead_stop_optimal`,
  `lookahead_continue_better`). In a stopping problem on a finite tree, if
  the states where stopping now beats one more step and stopping are closed
  under continuation, stopping exactly there is optimal.
-/

namespace NCA

open Finset

/-- A positive target preserves strict order between bounds when rescaling. -/
theorem positive_target_preserves_order {a b δ : ℝ} (hδ : 0 < δ) :
    a / δ < b / δ ↔ a < b := by
  exact div_lt_div_iff_of_pos_right hδ

/-- First state accepted by a stopping policy on a finite trace. -/
def firstStoppingState {α : Type*} (p : α → Bool) : List α → Option α
  | [] => none
  | x :: xs => if p x then some x else firstStoppingState p xs

/-- Appending later states cannot change a policy's first stopping state. -/
theorem firstStoppingState_append {α : Type*} (p : α → Bool) (xs ys : List α) :
    firstStoppingState p (xs ++ ys) =
      (firstStoppingState p xs).orElse (fun _ => firstStoppingState p ys) := by
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    simp only [List.cons_append, firstStoppingState]
    cases p x <;> simp [ih]

/-- The gain in empirical squared error from splitting a bin is nonnegative
after multiplication by its total count. Generalization is a separate issue. -/
theorem split_bin_gain_nonneg {n₁ n₂ p₁ p₂ : ℝ} (h₁ : 0 ≤ n₁) (h₂ : 0 ≤ n₂) :
    0 ≤ (n₁ * p₁ ^ 2 + n₂ * p₂ ^ 2) * (n₁ + n₂) -
      (n₁ * p₁ + n₂ * p₂) ^ 2 := by
  have h : (n₁ * p₁ ^ 2 + n₂ * p₂ ^ 2) * (n₁ + n₂) -
      (n₁ * p₁ + n₂ * p₂) ^ 2 = n₁ * n₂ * (p₁ - p₂) ^ 2 := by ring
  rw [h]
  exact mul_nonneg (mul_nonneg h₁ h₂) (sq_nonneg _)

/-- Continuing to completion has positive expected net reward exactly when
its answer probability exceeds the weighted expected remaining cost. This
compares two fixed choices; it does not prove optimality of a stopping policy. -/
theorem committed_continuation_preferred (answerProbability remainingCost weight : ℝ) :
    0 < answerProbability - weight * remainingCost ↔
      weight * remainingCost < answerProbability := by
  constructor <;> intro h <;> linarith

/-- **Cost of a target drop.** If every item in `s` lowers the bound by at
most `r > 0` per unit of its cost, items lowering it by `D` in total cost at
least `D / r`. -/
theorem cost_ge_of_ratio {I : Type*} (s : Finset I) (d c : I → ℝ) {r D : ℝ} (hr : 0 < r)
    (h : ∀ i ∈ s, d i ≤ r * c i) (hD : D ≤ ∑ i ∈ s, d i) : D / r ≤ ∑ i ∈ s, c i := by
  rw [div_le_iff₀ hr]
  calc D ≤ ∑ i ∈ s, d i := hD
    _ ≤ ∑ i ∈ s, r * c i := sum_le_sum h
    _ = (∑ i ∈ s, c i) * r := by rw [← mul_sum, mul_comm]

/-- The pairs function `Σ_{i<j} ρᵢ ρⱼ` of a list of risks. -/
def pairsList : List ℝ → ℝ
  | [] => 0
  | x :: l => x * l.sum + pairsList l

theorem sum_ge_count {a : ℝ} : ∀ l : List ℝ, (∀ x ∈ l, a ≤ x) → l.length * a ≤ l.sum
  | [], _ => by simp
  | x :: l, h => by
    have ih := sum_ge_count l fun y hy => h y (List.mem_cons_of_mem _ hy)
    have hx := h x List.mem_cons_self
    simp only [List.length_cons, List.sum_cons, Nat.cast_succ]
    linarith

/-- **Floors grow quadratically.** `t` risks, each at least `a ≥ 0`, have
pairs function at least `t (t − 1) / 2 · a²`. -/
theorem pairs_ge_count {a : ℝ} (ha : 0 ≤ a) : ∀ l : List ℝ, (∀ x ∈ l, a ≤ x) →
    (l.length * (l.length - 1) / 2 : ℝ) * a ^ 2 ≤ pairsList l
  | [], _ => by simp [pairsList]
  | x :: l, h => by
    have hl : ∀ y ∈ l, a ≤ y := fun y hy => h y (List.mem_cons_of_mem _ hy)
    have ih := pairs_ge_count ha l hl
    have hs := sum_ge_count l hl
    have hx := h x List.mem_cons_self
    have hxs : x * l.sum ≥ a * (l.length * a) :=
      mul_le_mul hx hs (by positivity) (ha.trans hx)
    simp only [pairsList, List.length_cons, Nat.cast_succ]
    nlinarith

/-- A stopping problem on a finite tree: at every state one may stop, with
reward `g`, or pay `c` and move to a random next state. -/
inductive StopTree where
  | leaf (g : ℝ)
  | node (g c : ℝ) (next : List (ℝ × StopTree))

namespace StopTree

/-- Reward for stopping now. -/
def stop : StopTree → ℝ
  | leaf g => g
  | node g _ _ => g

mutual
/-- Value of the best policy. -/
def value : StopTree → ℝ
  | leaf g => g
  | node g c next => max g (-c + expect next)

/-- Expected value of the next state. -/
def expect : List (ℝ × StopTree) → ℝ
  | [] => 0
  | (p, t) :: rest => p * t.value + expect rest
end

/-- Expected reward for stopping at the next state. -/
def expectStop : List (ℝ × StopTree) → ℝ
  | [] => 0
  | (p, t) :: rest => p * t.stop + expectStop rest

/-- The one-step-lookahead stopping set: stopping now is at least as good as
one more step and stopping then. -/
def Lookahead : StopTree → Prop
  | leaf _ => True
  | node g c next => -c + expectStop next ≤ g

/-- The problem is *monotone*: from every state of the lookahead set, every
next state is in it too. -/
inductive Monotone : StopTree → Prop
  | leaf {g : ℝ} : Monotone (leaf g)
  | node {g c : ℝ} {next : List (ℝ × StopTree)} :
      (Lookahead (node g c next) → ∀ b ∈ next, Lookahead b.2) →
      (∀ b ∈ next, Monotone b.2) → Monotone (node g c next)

theorem expect_eq_expectStop : ∀ next : List (ℝ × StopTree),
    (∀ b ∈ next, b.2.value = b.2.stop) → expect next = expectStop next
  | [], _ => rfl
  | (p, t) :: rest, h => by
    simp only [expect, expectStop]
    rw [h (p, t) List.mem_cons_self,
      expect_eq_expectStop rest fun b hb => h b (List.mem_cons_of_mem _ hb)]

theorem stop_le_value : ∀ t : StopTree, t.stop ≤ t.value
  | leaf _ => le_rfl
  | node _ _ _ => le_max_left _ _

theorem expectStop_le_expect : ∀ next : List (ℝ × StopTree), (∀ b ∈ next, 0 ≤ b.1) →
    expectStop next ≤ expect next
  | [], _ => le_rfl
  | (p, t) :: rest, h => by
    simp only [expect, expectStop]
    have hp := h (p, t) List.mem_cons_self
    have := expectStop_le_expect rest fun b hb => h b (List.mem_cons_of_mem _ hb)
    have := mul_le_mul_of_nonneg_left (stop_le_value t) hp
    linarith

/-- **Stopping in the lookahead set is optimal.** In a monotone problem, the
value of every state of the lookahead set is its stopping reward. -/
theorem lookahead_stop_optimal {t : StopTree} (hm : Monotone t) (hl : Lookahead t) :
    t.value = t.stop := by
  induction hm with
  | leaf => rfl
  | @node g c next hclosed _ ih =>
    have hnext : ∀ b ∈ next, b.2.value = b.2.stop := fun b hb => ih b hb (hclosed hl b hb)
    simp only [value, stop]
    rw [expect_eq_expectStop next hnext]
    exact max_eq_left hl

/-- **Continuing outside the lookahead set is better.** With nonnegative
transition probabilities, a state outside the lookahead set is worth more
than stopping there. -/
theorem lookahead_continue_better {g c : ℝ} {next : List (ℝ × StopTree)}
    (hp : ∀ b ∈ next, 0 ≤ b.1) (hl : ¬ Lookahead (node g c next)) :
    (node g c next).stop < (node g c next).value := by
  simp only [Lookahead, not_le] at hl
  simp only [stop, value]
  have := expectStop_le_expect next hp
  exact lt_max_of_lt_right (by linarith)

end StopTree
end NCA
