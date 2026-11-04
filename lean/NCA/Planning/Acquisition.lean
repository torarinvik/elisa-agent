import Mathlib.Data.List.Perm.Basic
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

/-! Acquisition priorities (§20.19). Scores select an order, not validity. -/
namespace NCA

theorem acquisition_order_valid {α : Type*} {original ranked : List α}
    (order : ranked.Perm original) (P : α → Prop)
    (valid : ∀ x ∈ original, P x) : ∀ x ∈ ranked, P x := by
  intro x hx
  exact valid x (order.mem_iff.mp hx)

/-- Expected cost for trying A then B, with a common remaining suffix.
The probabilistic interpretation assumes independent, fixed success chances
and expected attempt costs unaffected by previous outcomes. -/
def acquisitionPairCost (ca cb qa qb tail : ℝ) : ℝ :=
  ca + (1 - qa) * cb + (1 - qa) * (1 - qb) * tail

theorem acquisition_swap_difference (ca cb qa qb tail : ℝ) :
    acquisitionPairCost ca cb qa qb tail - acquisitionPairCost cb ca qb qa tail
      = ca * qb - cb * qa := by
  unfold acquisitionPairCost
  ring

/-- A before B is no more expensive precisely when ca*qb ≤ cb*qa.
For positive costs this is decreasing success probability per unit cost.
No claim is made that supplied predictions equal those true probabilities. -/
theorem acquisition_swap (ca cb qa qb tail : ℝ) (order : ca * qb ≤ cb * qa) :
    acquisitionPairCost ca cb qa qb tail ≤ acquisitionPairCost cb ca qb qa tail := by
  have := acquisition_swap_difference ca cb qa qb tail
  linarith

end NCA
