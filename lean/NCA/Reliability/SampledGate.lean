import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Analysis.SpecialFunctions.Exp
import Mathlib.MeasureTheory.Measure.MeasureSpace
import Mathlib.MeasureTheory.Measure.Typeclasses.Probability
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

/-- The exact count: zero losses in `m` cases miss a rate above `ε` with probability at most
`α`, once `log (1/α) ≤ -log (1 - ε) * m`. -/
theorem zeroLoss_miss_exact {ε ℓ α : ℝ} {m : ℕ} (hεℓ : ε < ℓ) (hℓ : ℓ ≤ 1)
    (hα : 0 < α) (size : Real.log (1 / α) ≤ -Real.log (1 - ε) * m) :
    (1 - ℓ) ^ m ≤ α := by
  have positive : 0 < 1 - ε := by linarith
  have base : 0 ≤ 1 - ℓ := by linarith
  calc (1 - ℓ) ^ m ≤ (1 - ε) ^ m := pow_le_pow_left₀ base (by linarith) m
    _ = Real.exp (Real.log (1 - ε) * m) := by
        rw [mul_comm, Real.exp_nat_mul, Real.exp_log positive]
    _ ≤ Real.exp (-Real.log (1 / α)) := Real.exp_le_exp.mpr (by linarith)
    _ = α := by rw [Real.exp_neg, Real.exp_log (by positivity)]; field_simp

/-- `N` known decisions at equal shares spend exactly the whole budget. -/
theorem known_decisions_total {δ : ℝ} {N : ℕ} (positive : 0 < N) :
    ∑ _k ∈ Finset.range N, δ / (N : ℝ) = δ := by
  have : (N : ℝ) ≠ 0 := by positivity
  simp only [Finset.sum_const, Finset.card_range, nsmul_eq_mul]
  field_simp

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

/-- Eviction (§43.11): removing requested records unless protected keeps every
protected record that was stored. -/
theorem evict_keeps_protected {α : Type*} [DecidableEq α] (stored requested protected_ : List α)
    {x : α} (hx : x ∈ protected_) (stored_x : x ∈ stored) :
    x ∈ stored.filter (fun y => y ∉ requested ∨ y ∈ protected_) :=
  List.mem_filter.mpr ⟨stored_x, by simp [hx]⟩

/-- Forced withdrawal keeps sampled cases fresh: with distinct cases split into
drawn and unused, the next draw after removing any set of cases takes only
cases that were unused and never drawn. -/
theorem withdraw_fresh {α : Type*} (drawn unused : List α) (keep : α → Bool) (m : ℕ)
    (distinct : (drawn ++ unused).Nodup) {x : α}
    (hx : x ∈ (unused.filter keep).take m) : x ∈ unused ∧ x ∉ drawn := by
  have mem : x ∈ unused := (List.mem_filter.mp (List.mem_of_mem_take hx)).1
  refine ⟨mem, fun hd => ?_⟩
  exact (List.disjoint_of_nodup_append distinct) hd mem

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

/-- Certified acquisition (§20.9): acquisition `k` admits a learned connector
only after zero errors on fresh cases at level `decisionLevel δ k`. If each
admission of a connector whose error exceeds its certified rate has at most
that probability (`zeroLoss_miss`), then across any number of acquisitions
some such admission happens with probability at most `δ`. -/
theorem acquisition_sound {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    {δ : ℝ} (hδ : 0 ≤ δ) (n : ℕ) (wronglyAdmitted : ℕ → Set Ω)
    (each : ∀ k ∈ range n, μ (wronglyAdmitted k) ≤ ENNReal.ofReal (decisionLevel δ k)) :
    μ (⋃ k ∈ range n, wronglyAdmitted k) ≤ ENNReal.ofReal δ := by
  have := sampledGate_sound μ hδ n (fun _ => ({()} : Finset Unit)) (fun k _ => wronglyAdmitted k)
    (fun k hk r _ => by simpa using each k hk)
  simpa [Set.iUnion_const] using this

/-- Early rejection (§20.9): a test reading held-out outcomes in order (`true`
for agreement) until the first disagreement. It returns whether it admits and
how many cases it read. -/
def earlyTest : List Bool → Bool × ℕ
  | [] => (true, 0)
  | true :: rest => ((earlyTest rest).1, (earlyTest rest).2 + 1)
  | false :: _ => (false, 1)

/-- Stopping at the first disagreement admits exactly when every case agrees,
so the guarantee of `acquisition_sound` is unchanged. -/
theorem earlyTest_admits : ∀ cases : List Bool, (earlyTest cases).1 = cases.all id
  | [] => rfl
  | true :: rest => by simp [earlyTest, earlyTest_admits rest]
  | false :: _ => rfl

/-- It never reads more cases than the full test, and an admission reads them all. -/
theorem earlyTest_reads : ∀ cases : List Bool,
    (earlyTest cases).2 ≤ cases.length ∧ ((earlyTest cases).1 = true → (earlyTest cases).2 = cases.length)
  | [] => by simp [earlyTest]
  | true :: rest => by
    have := earlyTest_reads rest
    simp only [earlyTest, List.length_cons]
    exact ⟨by omega, fun h => by rw [this.2 h]⟩
  | false :: _ => by simp [earlyTest]

/-- Staged acquisition (§20.18): stop after any passing candidate, but charge
each candidate test its share of that request's confidence. Fitters may use
all earlier observations, including failed tests; the per-test miss bound
requires new cases independent of that history and a frozen candidate. -/
theorem staged_acquisition_sound {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    {δ : ℝ} (hδ : 0 ≤ δ) (n : ℕ) (stages : ℕ → ℕ)
    (wrong : ℕ → ℕ → Set Ω) (admittedWrong : Set Ω)
    (tested : admittedWrong ⊆ ⋃ k ∈ range n, ⋃ r ∈ range (stages k), wrong k r)
    (share : ∀ k ∈ range n, ∀ r ∈ range (stages k),
      μ (wrong k r) ≤ ENNReal.ofReal (decisionLevel δ k / stages k)) :
    μ admittedWrong ≤ ENNReal.ofReal δ := by
  refine (measure_mono tested).trans ?_
  simpa using sampledGate_sound μ hδ n (fun k => range (stages k)) wrong
    (fun k hk r hr => by simpa using share k hk r hr)

/-- Ranked candidates at one gate (§45.6): training fixes how many candidates `c` will
be tested, before any fresh case. If each of the `c` tests has conditional miss probability
at most `α / c` on that training outcome, a wrong admission has probability at most `α`,
including when `c` depends on the training data. -/
theorem ranked_acquisition_sound {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    [IsProbabilityMeasure μ] {α : ℝ} (K : ℕ) (ranked : ℕ → Set Ω)
    (measurable : ∀ c ∈ range K, MeasurableSet (ranked c))
    (disjoint : Set.PairwiseDisjoint (↑(range K)) ranked)
    (wrong : ℕ → ℕ → Set Ω) (admittedWrong : Set Ω)
    (tested : admittedWrong ⊆ ⋃ c ∈ range K, ⋃ r ∈ range c, wrong c r)
    (share : ∀ c ∈ range K, ∀ r ∈ range c,
      μ (wrong c r) ≤ ENNReal.ofReal (α / c) * μ (ranked c)) :
    μ admittedWrong ≤ ENNReal.ofReal α := by
  have each : ∀ c ∈ range K,
      μ (⋃ r ∈ range c, wrong c r) ≤ ENNReal.ofReal α * μ (ranked c) := by
    intro c hc
    have scaled : (c : ENNReal) * ENNReal.ofReal (α / c) ≤ ENNReal.ofReal α := by
      rcases Nat.eq_zero_or_pos c with rfl | positive
      · simp
      · have cast : (0 : ℝ) < c := by exact_mod_cast positive
        rw [← ENNReal.ofReal_natCast, ← ENNReal.ofReal_mul cast.le]
        apply le_of_eq
        congr 1
        field_simp
    calc μ (⋃ r ∈ range c, wrong c r)
        ≤ ∑ r ∈ range c, μ (wrong c r) := measure_biUnion_finset_le _ _
      _ ≤ ∑ _r ∈ range c, ENNReal.ofReal (α / c) * μ (ranked c) :=
          sum_le_sum (share c hc)
      _ = (c : ENNReal) * ENNReal.ofReal (α / c) * μ (ranked c) := by
          simp [sum_const, nsmul_eq_mul, mul_assoc]
      _ ≤ ENNReal.ofReal α * μ (ranked c) := by gcongr
  calc μ admittedWrong
      ≤ μ (⋃ c ∈ range K, ⋃ r ∈ range c, wrong c r) := measure_mono tested
    _ ≤ ∑ c ∈ range K, μ (⋃ r ∈ range c, wrong c r) := measure_biUnion_finset_le _ _
    _ ≤ ∑ c ∈ range K, ENNReal.ofReal α * μ (ranked c) := sum_le_sum each
    _ = ENNReal.ofReal α * μ (⋃ c ∈ range K, ranked c) := by
        rw [← mul_sum, measure_biUnion_finset disjoint measurable]
    _ ≤ ENNReal.ofReal α * 1 := by gcongr; exact prob_le_one
    _ = ENNReal.ofReal α := mul_one _

/-- Exact ceiling division of an upper logarithm supplies the required size.
The numerical logarithm must establish the stated upper-bound hypothesis. -/
theorem log_upper_ceil_size {ε upper : ℝ} (positive : 0 < ε) :
    upper ≤ ε * (⌈upper / ε⌉₊ : ℝ) := by
  have bound := Nat.le_ceil (upper / ε)
  have result := (div_le_iff₀ positive).mp bound
  simpa [mul_comm] using result

theorem zeroLoss_log_upper {ε ℓ α upper : ℝ} (positive : 0 < ε)
    (hεℓ : ε < ℓ) (hℓ : ℓ ≤ 1) (hα : 0 < α)
    (faithful : -Real.log α ≤ upper) :
    (1 - ℓ) ^ (⌈upper / ε⌉₊) ≤ α := by
  apply zeroLoss_miss hεℓ hℓ hα
  have bound := faithful.trans (log_upper_ceil_size positive)
  simpa only [one_div, Real.log_inv] using bound

/-- Rounded allocations remain within the original budget if each is no
larger than its exact share. Missing spending positions need not be reused. -/
theorem rounded_decision_budget {δ : ℝ} (nonnegative : 0 ≤ δ)
    (levels : ℕ → ℝ) (used : Finset ℕ)
    (lower : ∀ k ∈ used, levels k ≤ decisionLevel δ k) :
    ∑ k ∈ used, levels k ≤ δ := by
  have subset : used ⊆ range (used.sup id + 1) := by
    intro k hk
    exact mem_range.mpr (Nat.lt_succ_of_le (le_sup (f := id) hk))
  calc
    ∑ k ∈ used, levels k ≤ ∑ k ∈ used, decisionLevel δ k := sum_le_sum lower
    _ ≤ ∑ k ∈ range (used.sup id + 1), decisionLevel δ k := by
      apply sum_le_sum_of_subset_of_nonneg subset
      intro k _ _
      dsimp [decisionLevel]
      positivity
    _ ≤ δ := decisionLevel_total nonnegative _

/-- A finite family's downward-rounded share cannot overspend its parent. -/
theorem rounded_family_budget {total level : ℝ} (count : ℕ) (positive : 0 < count)
    (lower : level ≤ total / count) : (count : ℝ) * level ≤ total := by
  have pos : (0 : ℝ) < count := by exact_mod_cast positive
  have bound := (le_div_iff₀ pos).mp lower
  simpa [mul_comm] using bound

end NCA
