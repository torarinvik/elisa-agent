import NCA.Banding

/-! The first threshold crossing of the polynomial band bound lies on its
decreasing side, so its qualifying indices form a suffix. -/

namespace NCA

/-- A nonnegative sequence with successive ratio `s / (n + 1)` is below
its initial threshold only on its nonincreasing side. -/
theorem ratio_threshold_suffix (u : ℕ → ℝ) (s threshold : ℝ)
    (hu : ∀ n, 0 ≤ u n)
    (hrec : ∀ n : ℕ, ((n : ℝ) + 1) * u (n + 1) = s * u n)
    (hfirst : threshold < u 1) (k : ℕ) (hk : 1 ≤ k)
    (hbelow : u k ≤ threshold) : ∀ n ≥ k, u n ≤ threshold := by
  have hpre : ∀ n : ℕ, 1 ≤ n → (n : ℝ) ≤ s → u 1 ≤ u n := by
    intro n
    induction n with
    | zero => simp
    | succ n ih =>
      intro hn hns
      by_cases hzero : n = 0
      · subst n; simp
      · have hn1 : 1 ≤ n := by omega
        have hns' : (n : ℝ) ≤ s := by push_cast at hns; linarith
        have hi := ih hn1 hns'
        have hp := hu n
        have hr := hrec n
        push_cast at hns hr
        nlinarith
  have hs : s < (k + 1 : ℝ) := by
    by_contra h
    have hk_s : (k : ℝ) ≤ s := by linarith
    have := hpre k hk hk_s
    linarith
  intro n hn
  induction n, hn using Nat.le_induction with
  | base => exact hbelow
  | succ n hn ih =>
    have hkn : (k : ℝ) ≤ n := by exact_mod_cast hn
    have hnpos : (0 : ℝ) < n + 1 := by positivity
    have hp := hu n
    have hr := hrec n
    nlinarith

/-- The polynomial tail estimate before taking logarithms. -/
noncomputable def bandPolynomial (factor mass : ℝ) (j : ℕ) : ℝ :=
  factor * mass ^ j / j.factorial

theorem bandPolynomial_recurrence (factor mass : ℝ) (n : ℕ) :
    ((n : ℝ) + 1) * bandPolynomial factor mass (n + 1) =
      mass * bandPolynomial factor mass n := by
  have hf : (n.factorial : ℝ) ≠ 0 := by exact_mod_cast Nat.factorial_ne_zero n
  have hn : ((n : ℝ) + 1) ≠ 0 := by positivity
  simp only [bandPolynomial, pow_succ, Nat.factorial_succ, Nat.cast_mul, Nat.cast_add,
    Nat.cast_one]
  field_simp

/-- Once the first bound fails, later bounds below the threshold form a suffix. -/
theorem bandPolynomial_threshold_suffix (factor mass threshold : ℝ)
    (hf : 0 ≤ factor) (hm : 0 ≤ mass) (hfirst : threshold < factor * mass)
    (k : ℕ) (hk : 1 ≤ k) (hbelow : bandPolynomial factor mass k ≤ threshold) :
    ∀ n ≥ k, bandPolynomial factor mass n ≤ threshold := by
  apply ratio_threshold_suffix (bandPolynomial factor mass) mass threshold
  · intro n
    exact div_nonneg (mul_nonneg hf (pow_nonneg hm n)) (Nat.cast_nonneg _)
  · exact bandPolynomial_recurrence factor mass
  · simpa [bandPolynomial] using hfirst
  · exact hk
  · exact hbelow

/-- A binary-search step preserves the failed lower and qualifying upper
bounds for any predicate whose qualifying indices form a suffix. -/
theorem threshold_search_step (p : ℕ → Prop) [DecidablePred p]
    (suffix : ∀ a b, a ≤ b → p a → p b)
    (low high : ℕ) (hgap : low + 1 < high)
    (hlow : ¬p low) (hhigh : p high) :
    let mid := low + (high - low) / 2
    (low < mid ∧ mid < high) ∧
    (if p mid then ¬p low ∧ p mid else ¬p mid ∧ p high) ∧
    (∀ n ≤ low, ¬p n) ∧ (∀ n ≥ high, p n) := by
  have hmid : low < low + (high - low) / 2 ∧
      low + (high - low) / 2 < high := by omega
  refine ⟨hmid, ?_, ?_, ?_⟩
  · split <;> simp_all
  · intro n hn hp
    exact hlow (suffix n low hn hp)
  · intro n hn
    exact suffix high n hn hhigh

/-- Either branch retains at most half of the old interval, rounded up. -/
theorem threshold_search_shrinks (low high : ℕ) (h : low ≤ high) :
    let mid := low + (high - low) / 2
    mid - low ≤ (high - low + 1) / 2 ∧
      high - mid ≤ (high - low + 1) / 2 := by
  omega

/-- Repeated worst-case interval widths when each step rounds half upward. -/
def searchGap : ℕ → ℕ → ℕ
  | 0, gap => gap
  | steps + 1, gap => searchGap steps ((gap + 1) / 2)

/-- An interval of at most `2^steps` becomes adjacent within `steps` steps. -/
theorem searchGap_le_one (steps gap : ℕ) (h : gap ≤ 2 ^ steps) :
    searchGap steps gap ≤ 1 := by
  induction steps generalizing gap with
  | zero => simp_all [searchGap]
  | succ steps ih =>
    simp only [searchGap]
    apply ih
    rw [pow_succ] at h
    omega

/-- A representable signed 64-bit interval reaches adjacency in 63 steps. -/
theorem searchGap_i64 (gap : ℕ) (h : gap < 2 ^ 63) : searchGap 63 gap ≤ 1 :=
  searchGap_le_one 63 gap (Nat.le_of_lt h)

/-- Adjacent failed and qualifying bounds identify the first qualifying index. -/
theorem threshold_search_adjacent (p : ℕ → Prop) (low high : ℕ)
    (suffix : ∀ a b, a ≤ b → p a → p b)
    (hgap : high = low + 1) (hlow : ¬p low) (hhigh : p high) :
    p high ∧ ∀ n, n < high → ¬p n := by
  refine ⟨hhigh, ?_⟩
  intro n hn hp
  exact hlow (suffix n low (by omega) hp)

end NCA
