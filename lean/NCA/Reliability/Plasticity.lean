import Mathlib.Algebra.Order.Field.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Positivity
import Mathlib.Tactic.Ring
import Mathlib.Algebra.Order.BigOperators.Group.List

/-! Self-regulating plasticity (§43.8). Each key's plasticity is smoothed toward
its signal `surprise · (1 - stability)`; a key opens at `hi` and closes at `lo`
(`lo < hi`). Plasticity stays in `[0, 1]`, moves at most `η` per observation,
and so an open key cannot close, nor a closed key reopen, in fewer than
`(hi - lo) / η` observations. Admission of changes stays with the gate. -/
namespace NCA

variable {α : Type*} [Field α] [LinearOrder α] [IsStrictOrderedRing α]

/-- One smoothing step toward the signal `s · (1 - w)`. -/
def smooth (η p s w : α) : α := (1 - η) * p + η * (s * (1 - w))

theorem signal_unit {s w : α} (hs : 0 ≤ s ∧ s ≤ 1) (hw : 0 ≤ w ∧ w ≤ 1) :
    0 ≤ s * (1 - w) ∧ s * (1 - w) ≤ 1 := by
  refine ⟨mul_nonneg hs.1 (by linarith), ?_⟩
  nlinarith

/-- Plasticity stays in `[0, 1]`. -/
theorem smooth_unit {η p s w : α} (hη : 0 ≤ η ∧ η ≤ 1) (hp : 0 ≤ p ∧ p ≤ 1)
    (hs : 0 ≤ s ∧ s ≤ 1) (hw : 0 ≤ w ∧ w ≤ 1) :
    0 ≤ smooth η p s w ∧ smooth η p s w ≤ 1 := by
  obtain ⟨x0, x1⟩ := signal_unit hs hw
  unfold smooth
  constructor <;> nlinarith

/-- Plasticity moves by at most `η` per observation. -/
theorem smooth_step {η p s w : α} (hη : 0 ≤ η ∧ η ≤ 1) (hp : 0 ≤ p ∧ p ≤ 1)
    (hs : 0 ≤ s ∧ s ≤ 1) (hw : 0 ≤ w ∧ w ≤ 1) :
    |smooth η p s w - p| ≤ η := by
  obtain ⟨x0, x1⟩ := signal_unit hs hw
  have : smooth η p s w - p = η * (s * (1 - w) - p) := by unfold smooth; ring
  rw [this, abs_mul, abs_of_nonneg hη.1]
  have : |s * (1 - w) - p| ≤ 1 := abs_le.mpr ⟨by linarith, by linarith⟩
  nlinarith [abs_nonneg (s * (1 - w) - p)]

/-- Hysteresis: whether a key is open after observing plasticity `p`. -/
def nextOpen (lo hi : α) (open_ : Bool) (p : α) : Bool :=
  if open_ then decide (lo < p) else decide (hi ≤ p)

/-- Over a trajectory moving at most `η` per step, values `n` steps apart
differ by at most `n η`. -/
theorem drift_le {η : α} (traj : ℕ → α) (step : ∀ t, |traj (t + 1) - traj t| ≤ η)
    (i n : ℕ) : |traj (i + n) - traj i| ≤ n * η := by
  induction n with
  | zero => simp
  | succ n ih =>
    calc |traj (i + (n + 1)) - traj i|
        ≤ |traj (i + n + 1) - traj (i + n)| + |traj (i + n) - traj i| := by
          rw [show i + (n + 1) = i + n + 1 by omega]; exact abs_sub_le _ _ _
      _ ≤ η + n * η := add_le_add (step _) ih
      _ = ((n + 1 : ℕ) : α) * η := by push_cast; ring

/-- No oscillation: if a key is open at step `i` (so `traj i ≥ hi`) and closed
at step `i + n` (so `traj (i + n) ≤ lo`), or the reverse, then `n η ≥ hi - lo`. -/
theorem hysteresis_gap {η lo hi : α} (traj : ℕ → α)
    (step : ∀ t, |traj (t + 1) - traj t| ≤ η) (i n : ℕ)
    (crossed : (hi ≤ traj i ∧ traj (i + n) ≤ lo) ∨ (traj i ≤ lo ∧ hi ≤ traj (i + n))) :
    hi - lo ≤ n * η := by
  have := abs_le.mp (drift_le traj step i n)
  rcases crossed with ⟨a, b⟩ | ⟨a, b⟩ <;> linarith [this.1, this.2]

/-- Settling resets plasticity to `initial ≤ lo` and closes the key; reopening
needs `traj (i + n) ≥ hi`, so at least `(hi - lo) / η` further observations. -/
theorem reopen_after_settle {η lo hi initial : α} (traj : ℕ → α)
    (step : ∀ t, |traj (t + 1) - traj t| ≤ η) (i n : ℕ) (settled : traj i = initial)
    (low : initial ≤ lo) (reopened : hi ≤ traj (i + n)) : hi - lo ≤ n * η :=
  hysteresis_gap traj step i n (Or.inr ⟨settled ▸ low, reopened⟩)

omit [Field α] [IsStrictOrderedRing α] in
/-- Opening requires `hi ≤ p`. -/
theorem nextOpen_opens {lo hi p : α} (h : nextOpen lo hi false p = true) : hi ≤ p := by
  simpa [nextOpen] using h

omit [Field α] [IsStrictOrderedRing α] in
/-- Closing requires `p ≤ lo`. -/
theorem nextOpen_closes {lo hi p : α} (h : nextOpen lo hi true p = false) : p ≤ lo := by
  simpa [nextOpen] using h

/-- Ledger surprise (§43.9): the mean of reported risks in `[0, 1]`, or 1 when an
audit refutes, lies in `[0, 1]`, so it is a valid Theorem 43.2 input. -/
theorem meanSignal_unit (reports : List α) (ne : reports ≠ [])
    (unit : ∀ r ∈ reports, 0 ≤ r ∧ r ≤ 1) :
    0 ≤ reports.sum / reports.length ∧ reports.sum / reports.length ≤ 1 := by
  have len : (0 : α) < reports.length := by
    exact_mod_cast List.length_pos_of_ne_nil ne
  have lo : 0 ≤ reports.sum := List.sum_nonneg fun r hr => (unit r hr).1
  have hi : reports.sum ≤ reports.length := by
    have := List.sum_le_card_nsmul reports 1 (fun r hr => (unit r hr).2)
    simpa using this
  exact ⟨div_nonneg lo len.le, (div_le_one len).mpr hi⟩

/-- Dependent stability `d / (d + h)` lies in `[0, 1)` and grows with `d`. -/
theorem dependentStability_unit {h : α} (hh : 0 < h) (d : ℕ) :
    0 ≤ (d : α) / (d + h) ∧ (d : α) / (d + h) < 1 := by
  have : (0 : α) < d + h := by positivity
  exact ⟨by positivity, (div_lt_one this).mpr (by linarith)⟩

theorem dependentStability_mono {h : α} (hh : 0 < h) {d e : ℕ} (le : d ≤ e) :
    (d : α) / (d + h) ≤ (e : α) / (e + h) := by
  have hd : (d : α) ≤ e := by exact_mod_cast le
  rw [div_le_div_iff₀ (by positivity) (by positivity)]
  nlinarith

end NCA
