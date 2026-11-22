import Mathlib.Tactic

/-! Readers given whole plays (chapter 79). Each reader has weights of its own and a gate gives each step one
of them; a teaching of one reader changes its weights alone. A reading is rescaled by a factor fitted with a
penalty of half its square, and a reader is taught each time its lessons have grown by a share. -/
namespace NCA

section Several

variable {ι W X Y : Type*} [DecidableEq ι]

/-- What is read at a step: what the reader the gate gives it reads, by that reader's weights. -/
def gatedReading (gate : X → ι) (read : W → X → Y) (weights : ι → W) (x : X) : Y :=
  read (weights (gate x)) x

/-- 79.1: teaching one reader, which gives it new weights and leaves every other's, leaves the reading as it
was at every step the gate gives another reader. -/
theorem untaught_keeps_reading (gate : X → ι) (read : W → X → Y) (weights : ι → W) (taught : ι) (made : W)
    (x : X) (other : gate x ≠ taught) :
    gatedReading gate read (Function.update weights taught made) x = gatedReading gate read weights x := by
  simp [gatedReading, Function.update_of_ne other]

end Several

/-- 79.2: where a factor fitted with a penalty of half its square leaves the least penalised loss there is, the
loss it leaves is no more than that of the factor nought, which is each port's rate alone. -/
theorem rescaled_nests_rates (loss : ℝ → ℝ) (factor : ℝ)
    (best : ∀ other, loss factor + factor ^ 2 / 2 ≤ loss other + other ^ 2 / 2) : loss factor ≤ loss 0 := by
  have nought := best 0
  have penalty : 0 ≤ factor ^ 2 / 2 := by positivity
  norm_num at nought
  linarith

/-- 79.3: lesson counts at teachings, each at least `1 + g` times the one before, are at least `(1 + g) ^ i`
times the first. -/
theorem counts_grow (g : ℝ) (grows : 0 ≤ g) (counts : ℕ → ℝ) (step : ∀ i, (1 + g) * counts i ≤ counts (i + 1))
    (i : ℕ) : (1 + g) ^ i * counts 0 ≤ counts i := by
  induction i with
  | zero => simp
  | succ i ih =>
    calc (1 + g) ^ (i + 1) * counts 0 = (1 + g) * ((1 + g) ^ i * counts 0) := by ring
      _ ≤ (1 + g) * counts i := mul_le_mul_of_nonneg_left ih (by linarith)
      _ ≤ counts (i + 1) := step i

/-- 79.3: counted over all the lessons, a play that begins when `held` are held and ends with `held + brought`
has teachings `0` to `k` within it only where `(1 + g) ^ k * held ≤ held + brought`. -/
theorem shared_count_starves (g held brought : ℝ) (grows : 0 ≤ g) (counts : ℕ → ℝ)
    (step : ∀ i, (1 + g) * counts i ≤ counts (i + 1)) (k : ℕ) (after : held ≤ counts 0)
    (within : counts k ≤ held + brought) : (1 + g) ^ k * held ≤ held + brought :=
  calc (1 + g) ^ k * held ≤ (1 + g) ^ k * counts 0 := mul_le_mul_of_nonneg_left after (pow_nonneg (by linarith) k)
    _ ≤ counts k := counts_grow g grows counts step k
    _ ≤ held + brought := within

end NCA
