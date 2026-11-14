import Mathlib.Data.Finset.Basic
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Ring
import Mathlib.Analysis.SpecialFunctions.Log.Basic

/-! Judgements that carry across observations: a set of components that suffices for the target is never refuted
by correct judgements, refutation is permanent, a learner whose every takeover lowers a potential is taken over at
most as often as the potential's start, and a weight that falls by a factor at each takeover falls by its power. -/

namespace NCA

/-- Two observations agree on the components in `S`. -/
def AgreeOn {Obs ι V : Type*} (component : Obs → ι → V) (S : Finset ι) (o o' : Obs) : Prop :=
  ∀ i ∈ S, component o i = component o' i

/-- No two judgements on observations agreeing on `S` give one action opposite verdicts. -/
def ConsistentWith {Obs ι V A : Type*} (component : Obs → ι → V) (S : Finset ι) (J : Finset (Obs × A × Bool)) :
    Prop :=
  ∀ j ∈ J, ∀ j' ∈ J, AgreeOn component S j.1 j'.1 → j.2.1 = j'.2.1 → j.2.2 = j'.2.2

/-- **Theorem 53.1 (a sufficient set is never refuted).** -/
theorem sufficient_set_consistent {Obs ι V A : Type*} (component : Obs → ι → V) (S : Finset ι)
    (J : Finset (Obs × A × Bool)) (t : Obs → A → Bool) (correct : ∀ j ∈ J, j.2.2 = t j.1 j.2.1)
    (suffices_for : ∀ o o', AgreeOn component S o o' → t o = t o') : ConsistentWith component S J := by
  intro j hj j' hj' agree same
  rw [correct j hj, correct j' hj', suffices_for _ _ agree, same]

/-- **Theorem 53.2 (refutation is permanent)**, for fewer judgements. -/
theorem consistent_of_subset_judgements {Obs ι V A : Type*} (component : Obs → ι → V) (S : Finset ι)
    {J J' : Finset (Obs × A × Bool)} (fewer : J' ⊆ J) (consistent : ConsistentWith component S J) :
    ConsistentWith component S J' :=
  fun j hj j' hj' => consistent j (fewer hj) j' (fewer hj')

/-- **Theorem 53.2 (refutation is permanent)**, for more components. -/
theorem consistent_of_subset {Obs ι V A : Type*} (component : Obs → ι → V) {S T : Finset ι}
    (J : Finset (Obs × A × Bool)) (more : S ⊆ T) (consistent : ConsistentWith component S J) :
    ConsistentWith component T J :=
  fun j hj j' hj' agree => consistent j hj j' hj' fun i inS => agree i (more inS)

/-- **Theorem 53.4 (corrections bounded by what matters)**, its counting step: steps that each lower a
natural-number potential number at most the potential at the start. -/
theorem steps_le_potential (potential : ℕ → ℕ) (steps : ℕ)
    (lowers : ∀ i < steps, potential (i + 1) < potential i) : steps ≤ potential 0 := by
  have bound : ∀ m ≤ steps, potential m + m ≤ potential 0 := by
    intro m
    induction m with
    | zero => intro _; simp
    | succ m ih =>
      intro hm
      have := lowers m (by omega)
      have := ih (by omega)
      omega
  have := bound steps le_rfl
  omega

/-- **Theorem 53.5 (weighted majority)**, its step to the power: a total weight that falls by at least the factor `c`
at each of `M` takeovers is at most `c ^ M` times its start. -/
theorem weight_le_pow (weight : ℕ → ℝ) (c : ℝ) (nonneg : 0 ≤ c) (M : ℕ)
    (falls : ∀ t < M, weight (t + 1) ≤ c * weight t) : weight M ≤ c ^ M * weight 0 := by
  induction M with
  | zero => simp
  | succ n ih =>
    calc weight (n + 1) ≤ c * weight n := falls n (by omega)
      _ ≤ c * (c ^ n * weight 0) := mul_le_mul_of_nonneg_left (ih fun t ht => falls t (by omega)) nonneg
      _ = c ^ (n + 1) * weight 0 := by ring

/-- **Theorem 53.8 (fewer contradictions weigh more).** -/
theorem fewer_contradictions_weigh_more (β : ℝ) (pos : 0 < β) (le_one : β ≤ 1) {a b : ℕ} (fewer : a ≤ b) :
    β ^ b ≤ β ^ a :=
  pow_le_pow_of_le_one pos.le le_one fewer

/-- **Proposition 53.9 (fewer contradictions, a greater share wrong).** A set can be contradicted less often than
another, and so outweigh it under any `β < 1`, while a greater share of its predictions failed. -/
theorem fewer_contradictions_can_be_a_greater_share_wrong (β : ℝ) (pos : 0 < β) (lt_one : β < 1) :
    ∃ h₁ m₁ h₂ m₂ : ℕ, m₁ < m₂ ∧ β ^ m₂ < β ^ m₁ ∧
      ((m₂ : ℚ) / (h₂ + m₂) < (m₁ : ℚ) / (h₁ + m₁)) := by
  refine ⟨1, 3, 96, 4, by norm_num, ?_, by norm_num⟩
  exact pow_lt_pow_right_of_lt_one₀ pos lt_one (by norm_num)

/-- The odds of a set right `h` times and contradicted `m` times. -/
def odds (h m : ℕ) : ℚ := ((h : ℚ) + 1) / ((m : ℚ) + 1)

/-- **Proposition 53.10 (odds).** The odds rise with a right prediction, fall with a contradiction, and are one
exactly when the set has been right as often as contradicted. -/
theorem odds_rise_and_fall (h m : ℕ) :
    odds h m < odds (h + 1) m ∧ odds h (m + 1) < odds h m ∧ (odds h m = 1 ↔ h = m) := by
  have hm : (0 : ℚ) < (m : ℚ) + 1 := by positivity
  have hh : (0 : ℚ) < (h : ℚ) + 1 := by positivity
  refine ⟨?_, ?_, ?_⟩
  · unfold odds
    push_cast
    exact div_lt_div_of_pos_right (by linarith) hm
  · unfold odds
    push_cast
    exact div_lt_div_of_pos_left hh hm (by linarith)
  · unfold odds
    rw [div_eq_one_iff_eq hm.ne']
    constructor
    · intro same
      exact_mod_cast add_right_cancel same
    · rintro rfl
      rfl

/-- **Proposition 53.11 (of two sets that disagree, the one of greater odds).** Where one set of odds `a` says good
and another of odds `b` says bad, the odds of good, `a / b`, exceed one exactly when the first's logarithm is the
greater. -/
theorem greater_odds_prevail (a b : ℝ) (ha : 0 < a) (hb : 0 < b) : 1 < a / b ↔ Real.log b < Real.log a := by
  rw [one_lt_div hb, Real.log_lt_log_iff hb ha]

end NCA
