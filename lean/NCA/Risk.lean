import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.FieldSimp

/-!
# Risk as an expected count

Over a finite weighted sample space, a route invokes expert `e` `I e ω`
times on input `ω`, of which `F e ω` fail. If every wrong answer has a
failed invocation, the probability of a wrong answer is at most the
expected number of failed invocations (`risk_le_expected_failures`). That
expectation is the sum over experts of expected invocations times the
in-situ rate `E[F e] / E[I e]` (`expected_failures_eq`), and is bounded by
any per-input invocation bounds times any upper bounds on the rates
(`risk_le_charges`). No independence is assumed.
-/

open Finset

namespace NCA

variable {Ω E : Type*} [Fintype Ω] [Fintype E] (p : Ω → ℝ)

/-- Expected value of a natural-number count. -/
def expect (X : Ω → ℕ) : ℝ := ∑ ω, p ω * X ω

/-- The in-situ failure rate of an expert: failed over all invocations, in
expectation; zero if it is never invoked. -/
noncomputable def rate (F I : Ω → ℕ) : ℝ :=
  if expect p I = 0 then 0 else expect p F / expect p I

variable {p}

/-- **Risk is an expected count.** If every wrong answer has at least one
failed invocation, the probability of a wrong answer is at most the
expected number of failed invocations. -/
theorem risk_le_expected_failures (hp : ∀ ω, 0 ≤ p ω) (wrong : Ω → Prop) [DecidablePred wrong]
    (F : E → Ω → ℕ) (hprop : ∀ ω, wrong ω → 1 ≤ ∑ e, F e ω) :
    ∑ ω ∈ univ.filter wrong, p ω ≤ ∑ e, expect p (F e) := by
  simp only [expect]
  rw [Finset.sum_comm, Finset.sum_filter]
  apply Finset.sum_le_sum
  intro ω _
  rw [← Finset.mul_sum]
  split
  · next h =>
    have h1 : (1 : ℝ) ≤ ∑ e, (F e ω : ℝ) := by exact_mod_cast hprop ω h
    nlinarith [hp ω]
  · exact mul_nonneg (hp ω) (Finset.sum_nonneg fun _ _ => Nat.cast_nonneg _)

theorem expect_eq_zero_of_le (hp : ∀ ω, 0 ≤ p ω) {F I : Ω → ℕ} (hle : ∀ ω, F ω ≤ I ω)
    (h : expect p I = 0) : expect p F = 0 := by
  have hF : 0 ≤ expect p F := Finset.sum_nonneg fun ω _ => mul_nonneg (hp ω) (Nat.cast_nonneg _)
  have hFI : expect p F ≤ expect p I := Finset.sum_le_sum fun ω _ =>
    mul_le_mul_of_nonneg_left (by exact_mod_cast hle ω) (hp ω)
  linarith

/-- **Risk decomposes.** The expected number of failed invocations is the
sum over experts of expected invocations times in-situ rate. -/
theorem expected_failures_eq (hp : ∀ ω, 0 ≤ p ω) (F I : E → Ω → ℕ)
    (hle : ∀ e ω, F e ω ≤ I e ω) :
    ∑ e, expect p (F e) = ∑ e, expect p (I e) * rate p (F e) (I e) := by
  apply Finset.sum_congr rfl
  intro e _
  unfold rate
  split
  · next h => rw [h, zero_mul]; exact expect_eq_zero_of_le hp (hle e) h
  · next h => field_simp

theorem rate_nonneg (hp : ∀ ω, 0 ≤ p ω) (F I : Ω → ℕ) : 0 ≤ rate p F I := by
  unfold rate
  split
  · exact le_rfl
  · exact div_nonneg (Finset.sum_nonneg fun ω _ => mul_nonneg (hp ω) (Nat.cast_nonneg _))
      (Finset.sum_nonneg fun ω _ => mul_nonneg (hp ω) (Nat.cast_nonneg _))

/-- **Charges bound risk.** On a probability space, with at most `ν e`
invocations of `e` per input and rate bounds `r e`, the probability of a
wrong answer is at most `Σ ν e · r e`. -/
theorem risk_le_charges (hp : ∀ ω, 0 ≤ p ω) (hsum : ∑ ω, p ω = 1) (wrong : Ω → Prop)
    [DecidablePred wrong] (F I : E → Ω → ℕ) (hle : ∀ e ω, F e ω ≤ I e ω)
    (hprop : ∀ ω, wrong ω → 1 ≤ ∑ e, F e ω) (ν r : E → ℝ) (hν : ∀ e ω, (I e ω : ℝ) ≤ ν e)
    (hr : ∀ e, rate p (F e) (I e) ≤ r e) :
    ∑ ω ∈ univ.filter wrong, p ω ≤ ∑ e, ν e * r e := by
  refine (risk_le_expected_failures hp wrong F hprop).trans ?_
  rw [expected_failures_eq hp F I hle]
  apply Finset.sum_le_sum
  intro e _
  have hI : expect p (I e) ≤ ν e := by
    calc expect p (I e) ≤ ∑ ω, p ω * ν e :=
          Finset.sum_le_sum fun ω _ => mul_le_mul_of_nonneg_left (hν e ω) (hp ω)
      _ = ν e := by rw [← Finset.sum_mul, hsum, one_mul]
  have hI0 : 0 ≤ expect p (I e) :=
    Finset.sum_nonneg fun ω _ => mul_nonneg (hp ω) (Nat.cast_nonneg _)
  have hr0 := rate_nonneg hp (F e) (I e)
  calc expect p (I e) * rate p (F e) (I e) ≤ ν e * rate p (F e) (I e) :=
        mul_le_mul_of_nonneg_right hI hr0
    _ ≤ ν e * r e := mul_le_mul_of_nonneg_left (hr e) (hI0.trans hI)

end NCA
