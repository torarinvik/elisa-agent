import Mathlib.Tactic.GCongr
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring
import NCA.Planning.Upgrade

/-!
# Cost of a composition

Each contract `c` costs `κ c` per invocation. A `map` runs its body once per
element; with sequences of length `L`, a plan's cost is defined
compositionally. Cost is additive (no interaction term between modules),
unaffected by installing modules, and polynomial in `L` with degree equal to
the plan's map nesting depth: plans without nested maps are linear in the
input length.
-/

namespace NCA

variable {Ty : Type}

mutual
/-- Cost of executing a plan on sequences of length `L`. -/
def Plan.cost (κ : Contract Ty → Nat) (L : Nat) : Plan Ty → Nat
  | .given _ => 0
  | .apply c ps => κ c + Plan.costArgs κ L ps
  | .map _ body src => L * body.cost κ L + src.cost κ L

/-- Total cost of a list of plans. -/
def Plan.costArgs (κ : Contract Ty → Nat) (L : Nat) : List (Plan Ty) → Nat
  | [] => 0
  | p :: ps => p.cost κ L + Plan.costArgs κ L ps
end

mutual
/-- Map nesting depth: the largest number of `map` bodies enclosing a module. -/
def Plan.nest : Plan Ty → Nat
  | .given _ => 0
  | .apply _ ps => Plan.nestArgs ps
  | .map _ body src => max (body.nest + 1) src.nest

/-- Largest nesting depth in a list of plans. -/
def Plan.nestArgs : List (Plan Ty) → Nat
  | [] => 0
  | p :: ps => max p.nest (Plan.nestArgs ps)
end

mutual
/-- **Polynomial degree = map nesting.** On sequences of length `L`, a plan
costs at most `(L + 1) ^ nest` times its cost on length-1 sequences. -/
theorem Plan.cost_le_pow (κ : Contract Ty → Nat) (L : Nat) :
    (p : Plan Ty) → p.cost κ L ≤ (L + 1) ^ p.nest * p.cost κ 1
  | .given _ => by simp [Plan.cost]
  | .apply c ps => by
    have h := Plan.costArgs_le_pow κ L ps
    simp only [Plan.cost, Plan.nest]
    have h1 : 1 ≤ (L + 1) ^ Plan.nestArgs ps := Nat.one_le_pow _ _ (by omega)
    nlinarith
  | .map _ body src => by
    have hb := Plan.cost_le_pow κ L body
    have hs := Plan.cost_le_pow κ L src
    simp only [Plan.cost, Plan.nest, one_mul]
    have hb' : (L + 1) ^ (body.nest + 1) ≤ (L + 1) ^ max (body.nest + 1) src.nest :=
      Nat.pow_le_pow_right (by omega) (le_max_left _ _)
    have hs' : (L + 1) ^ src.nest ≤ (L + 1) ^ max (body.nest + 1) src.nest :=
      Nat.pow_le_pow_right (by omega) (le_max_right _ _)
    have hL : L * (L + 1) ^ body.nest ≤ (L + 1) ^ (body.nest + 1) := by
      rw [pow_succ]; nlinarith [Nat.zero_le ((L + 1) ^ body.nest)]
    calc L * body.cost κ L + src.cost κ L
        ≤ L * ((L + 1) ^ body.nest * body.cost κ 1) + (L + 1) ^ src.nest * src.cost κ 1 := by
          gcongr
      _ = (L * (L + 1) ^ body.nest) * body.cost κ 1 + (L + 1) ^ src.nest * src.cost κ 1 := by
          ring
      _ ≤ (L + 1) ^ max (body.nest + 1) src.nest * body.cost κ 1 +
          (L + 1) ^ max (body.nest + 1) src.nest * src.cost κ 1 := by
          gcongr
          exact hL.trans hb'
      _ = (L + 1) ^ max (body.nest + 1) src.nest * (body.cost κ 1 + src.cost κ 1) := by ring

theorem Plan.costArgs_le_pow (κ : Contract Ty → Nat) (L : Nat) :
    (ps : List (Plan Ty)) → Plan.costArgs κ L ps ≤ (L + 1) ^ Plan.nestArgs ps * Plan.costArgs κ 1 ps
  | [] => by simp [Plan.costArgs]
  | p :: ps => by
    have hp := Plan.cost_le_pow κ L p
    have hps := Plan.costArgs_le_pow κ L ps
    simp only [Plan.costArgs, Plan.nestArgs]
    have h1 : (L + 1) ^ p.nest ≤ (L + 1) ^ max p.nest (Plan.nestArgs ps) :=
      Nat.pow_le_pow_right (by omega) (le_max_left _ _)
    have h2 : (L + 1) ^ Plan.nestArgs ps ≤ (L + 1) ^ max p.nest (Plan.nestArgs ps) :=
      Nat.pow_le_pow_right (by omega) (le_max_right _ _)
    calc p.cost κ L + Plan.costArgs κ L ps
        ≤ (L + 1) ^ p.nest * p.cost κ 1 + (L + 1) ^ Plan.nestArgs ps * Plan.costArgs κ 1 ps :=
          add_le_add hp hps
      _ ≤ (L + 1) ^ max p.nest (Plan.nestArgs ps) * p.cost κ 1 +
          (L + 1) ^ max p.nest (Plan.nestArgs ps) * Plan.costArgs κ 1 ps := by gcongr
      _ = _ := by ring
end

/-- **Linear cost.** A plan with no nested maps costs at most `(L + 1)` times
its length-1 cost: linear in the input length. -/
theorem Plan.cost_linear (κ : Contract Ty → Nat) (L : Nat) {p : Plan Ty} (h : p.nest ≤ 1) :
    p.cost κ L ≤ (L + 1) * p.cost κ 1 := by
  calc p.cost κ L ≤ (L + 1) ^ p.nest * p.cost κ 1 := p.cost_le_pow κ L
    _ ≤ (L + 1) ^ 1 * p.cost κ 1 := Nat.mul_le_mul_right _ (Nat.pow_le_pow_right (by omega) h)
    _ = (L + 1) * p.cost κ 1 := by ring

variable [DecidableEq Ty] [SeqTypes Ty]

/-- **Installation never changes cost.** A task that already had a route costs
the same after any modules are installed. -/
theorem route_cost_append {pins : Pins Ty} {lib : List (Contract Ty)}
    (extra : List (Contract Ty)) {avail : List Ty} {n : Nat} {t : Ty}
    (κ : Contract Ty → Nat) (L : Nat) (h : (route pins lib avail n t).isSome) :
    (route pins (lib ++ extra) avail n t).map (Plan.cost κ L) =
      (route pins lib avail n t).map (Plan.cost κ L) := by
  rw [route_append extra h]

end NCA
