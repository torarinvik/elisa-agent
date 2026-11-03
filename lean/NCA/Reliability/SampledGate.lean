import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Analysis.SpecialFunctions.Exp
import Mathlib.MeasureTheory.Measure.MeasureSpace
import Mathlib.Algebra.BigOperators.Intervals

/-! Sampled admission with fresh retained cases (§43.7). A decision draws `m`
unused cases per affected route and accepts only with zero losses. The
probabilistic step "fresh independent cases miss a loss rate `ℓ` with
probability `(1-ℓ)^m`" is the stated sampling hypothesis; everything else here
(sample size, unbounded decision budgets, freshness, union over decisions and
routes) is proved. -/
namespace NCA

open Finset MeasureTheory

/-- Zero losses in `m` cases miss a loss rate above `ε` with probability at most
`α`, once `log (1/α) ≤ ε m`. -/
theorem zeroLoss_miss {ε ℓ α : ℝ} {m : ℕ} (hεℓ : ε < ℓ) (hℓ : ℓ ≤ 1)
    (hα : 0 < α) (size : Real.log (1 / α) ≤ ε * m) :
    (1 - ℓ) ^ m ≤ α := by
  have base : 0 ≤ 1 - ℓ := by linarith
  have step : 1 - ℓ ≤ Real.exp (-ε) := by
    have := Real.add_one_le_exp (-ε); linarith
  calc (1 - ℓ) ^ m ≤ Real.exp (-ε) ^ m := pow_le_pow_left₀ base step m
    _ = Real.exp (-(ε * m)) := by rw [← Real.exp_nat_mul]; ring_nf
    _ ≤ Real.exp (-Real.log (1 / α)) := Real.exp_le_exp.mpr (by linarith)
    _ = α := by rw [Real.exp_neg, Real.exp_log (by positivity)]; field_simp

/-- Decision `k` (from 0) spends `δ / ((k+1)(k+2))`. -/
noncomputable def decisionLevel (δ : ℝ) (k : ℕ) : ℝ := δ / (((k : ℝ) + 1) * ((k : ℝ) + 2))

theorem decisionLevel_sum (δ : ℝ) (n : ℕ) :
    ∑ k ∈ range n, decisionLevel δ k = δ * (1 - 1 / ((n : ℝ) + 1)) := by
  induction n with
  | zero => simp
  | succ n ih =>
    rw [sum_range_succ, ih, decisionLevel]
    push_cast
    field_simp
    ring

/-- Any number of decisions spends at most `δ` in total. -/
theorem decisionLevel_total {δ : ℝ} (hδ : 0 ≤ δ) (n : ℕ) :
    ∑ k ∈ range n, decisionLevel δ k ≤ δ := by
  rw [decisionLevel_sum]
  have : 0 ≤ 1 / ((n : ℝ) + 1) := by positivity
  nlinarith

/-- A route's cursor after granting requests in order; a request beyond the pool
is refused and consumes nothing. -/
def allocate (pool : ℕ) : ℕ → List ℕ → List (Option (ℕ × ℕ))
  | _, [] => []
  | cursor, m :: rest =>
    if cursor + m ≤ pool then some (cursor, cursor + m) :: allocate pool (cursor + m) rest
    else none :: allocate pool cursor rest

theorem allocate_bounds (pool : ℕ) :
    ∀ (cursor : ℕ) (requests : List ℕ) (a b : ℕ),
      some (a, b) ∈ allocate pool cursor requests → cursor ≤ a ∧ a ≤ b ∧ b ≤ pool := by
  intro cursor requests
  induction requests generalizing cursor with
  | nil => simp [allocate]
  | cons m rest ih =>
    intro a b mem
    unfold allocate at mem
    split at mem
    · rcases List.mem_cons.mp mem with h | h
      · cases h; omega
      · have := ih (cursor + m) a b h; omega
    · rcases List.mem_cons.mp mem with h | h
      · cases h
      · exact ih cursor a b h

/-- Granted case ranges never overlap: no case informs two decisions. -/
theorem allocate_fresh (pool : ℕ) :
    ∀ (cursor : ℕ) (requests : List ℕ),
      (allocate pool cursor requests).Pairwise
        (fun x y => ∀ a b c d, x = some (a, b) → y = some (c, d) → b ≤ c) := by
  intro cursor requests
  induction requests generalizing cursor with
  | nil => simp [allocate]
  | cons m rest ih =>
    unfold allocate
    split
    · refine List.pairwise_cons.mpr ⟨?_, ih _⟩
      intro y hy a b c d hx hyv
      cases hx
      subst hyv
      exact (allocate_bounds pool _ rest c d hy).1
    · refine List.pairwise_cons.mpr ⟨?_, ih _⟩
      intro y _ a b c d hx
      cases hx

/-- Consolidation freshness (§43.10): a case at a position before the cursor,
already drawn, lies in no later allocation, so training on drawn cases keeps
every future decision's cases independent of the proposal. -/
theorem allocate_skips_drawn (pool cursor : ℕ) (requests : List ℕ) {a b x : ℕ}
    (mem : some (a, b) ∈ allocate pool cursor requests) (drawn : x < cursor) :
    ¬ (a ≤ x ∧ x < b) := by
  have := (allocate_bounds pool cursor requests a b mem).1
  omega

/-- A catalog changes only through admission: whatever a consolidation
proposes, the published snapshot differs from the old one only if the gate
accepted. -/
theorem published_only_if_admitted {S : Type*} (old proposed : S) (admitted : Bool)
    (changed : (if admitted then proposed else old) ≠ old) : admitted = true := by
  cases admitted
  · exact absurd rfl changed
  · rfl

/-- Union over decisions and affected routes: if each acceptance of a regressed
route has probability at most its share `decisionLevel δ k / |A k|` of decision
`k`'s budget, any acceptance of a regression across all decisions has
probability at most `δ`. -/
theorem sampledGate_sound {Ω R : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    {δ : ℝ} (hδ : 0 ≤ δ) (n : ℕ) (A : ℕ → Finset R) (bad : ℕ → R → Set Ω)
    (share : ∀ k ∈ range n, ∀ r ∈ A k,
      μ (bad k r) ≤ ENNReal.ofReal (decisionLevel δ k / (A k).card)) :
    μ (⋃ k ∈ range n, ⋃ r ∈ A k, bad k r) ≤ ENNReal.ofReal δ := by
  calc μ (⋃ k ∈ range n, ⋃ r ∈ A k, bad k r)
      ≤ ∑ k ∈ range n, μ (⋃ r ∈ A k, bad k r) := measure_biUnion_finset_le _ _
    _ ≤ ∑ k ∈ range n, ENNReal.ofReal (decisionLevel δ k) := by
        refine sum_le_sum fun k hk => ?_
        calc μ (⋃ r ∈ A k, bad k r) ≤ ∑ r ∈ A k, μ (bad k r) := measure_biUnion_finset_le _ _
          _ ≤ ∑ r ∈ A k, ENNReal.ofReal (decisionLevel δ k / (A k).card) :=
              sum_le_sum fun r hr => share k hk r hr
          _ ≤ ENNReal.ofReal (decisionLevel δ k) := by
              rw [sum_const, nsmul_eq_mul]
              rcases Nat.eq_zero_or_pos (A k).card with h | h
              · simp [h]
              · have hc : (0 : ℝ) < (A k).card := by exact_mod_cast h
                rw [← ENNReal.ofReal_natCast, ← ENNReal.ofReal_mul (by positivity)]
                exact ENNReal.ofReal_le_ofReal (le_of_eq (by field_simp))
    _ = ENNReal.ofReal (∑ k ∈ range n, decisionLevel δ k) := by
        rw [ENNReal.ofReal_sum_of_nonneg]
        intro k _
        unfold decisionLevel; positivity
    _ ≤ ENNReal.ofReal δ := ENNReal.ofReal_le_ofReal (decisionLevel_total hδ n)

end NCA
