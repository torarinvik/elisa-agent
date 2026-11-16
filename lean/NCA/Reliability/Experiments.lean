import Mathlib.Tactic

/-! Experiments that tell rules apart: narrowing a set of rules by what a test shows (§65). -/
namespace NCA

variable {H X O : Type} [DecidableEq O]

/-- 65.1: keeping the rules that agree with what a test showed keeps the true rule. -/
theorem narrowed_keeps_truth (rules : List H) (read : H → X → O) (truth : H) (x : X)
    (among : truth ∈ rules) : truth ∈ rules.filter (fun h => read h x = read truth x) := by
  simp [List.mem_filter, among]

/-- 65.2: when one rule is left, it is the true rule. -/
theorem one_left_is_truth (rules : List H) (read : H → X → O) (truth h : H) (x : X)
    (among : truth ∈ rules) (left : rules.filter (fun h => read h x = read truth x) = [h]) :
    h = truth := by
  have kept := narrowed_keeps_truth rules read truth x among
  rw [left] at kept
  exact (List.mem_singleton.mp kept).symm

/-- 65.3: if each of `k` tests can leave a `b`-th of the rules, `r 0` rules come down to `r k` only
when `r 0 ≤ b ^ k * r k`; to one rule only when `r 0 ≤ b ^ k`. -/
theorem tests_needed (b : Nat) : ∀ (k : Nat) (r : Nat → Nat),
    (∀ j, j < k → r j ≤ b * r (j + 1)) → r 0 ≤ b ^ k * r k
  | 0, r, _ => by simp
  | k + 1, r, h => by
      have first : r 0 ≤ b * r 1 := h 0 (Nat.succ_pos k)
      have rest : r 1 ≤ b ^ k * r (k + 1) := by
        simpa using tests_needed b k (fun j => r (j + 1)) (fun j hj => h (j + 1) (Nat.succ_lt_succ hj))
      calc r 0 ≤ b * r 1 := first
        _ ≤ b * (b ^ k * r (k + 1)) := Nat.mul_le_mul_left b rest
        _ = b ^ (k + 1) * r (k + 1) := by ring

end NCA
