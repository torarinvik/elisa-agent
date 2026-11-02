import NCA.Reliability.Certificate
import Mathlib.MeasureTheory.Integral.Lebesgue.Markov

/-!
# Error detection by the format

A consumer answers only when the readings are well formed: a prefix formula
whose arities parse. The truth is well formed too, and the two have the same
number of words. Every well-formed arity sequence satisfies
`Σ (arity − 1) = −1` (`code_sum`), so two of them of equal length cannot
differ in exactly one position (`code_no_single_change`): a single wrong
arity is always *detected*. A wrong arity that goes unnoticed needs at least
two.

The certificate bound of `NCA.Certificate` charges every word's arity risk as
if each error were silent. Crediting detection, the arity part of the bound
becomes the probability that at least two arity decisions fail:

* at most half the summed arity risks, with no further premise
  (`two_occur_le_half`, Markov's inequality on the number of failures);
* at most the sum over pairs of products of risks, if failures at two
  different words are never positively correlated
  (`two_occur_le_pairs`), quadratically small when the risks are.

The identity of an evaluated word is then charged only for errors that keep
its arity, whose joint probability is at most the risk of the decision
restricted to the word's arity group (`joint_le_restricted`).
`detected_error_le` assembles the bound.

Both arity charges are monotone in the risks (`detection_account_mono`). So
the charge computed from the words whose readings can no longer change, with
the others' risks set to zero, is a floor under every bound refinement can
still reach: once it exceeds the target, abstaining at once changes no
answer.
-/

namespace NCA

section Codes

variable {ω ω' : Type}

/-- **Arity balance.** Every formula's preorder arity sequence sums to one
less than its length. -/
theorem code_sum : ∀ f : Formula ω, (code f).sum + 1 = (code f).length
  | .const _ _ => rfl
  | .not _ f => by
      have := code_sum f
      simp only [code, List.sum_cons, List.length_cons]
      omega
  | .bin _ _ f g => by
      have := code_sum f
      have := code_sum g
      simp only [code, List.sum_cons, List.sum_append, List.length_cons, List.length_append]
      omega

/-- Lists of equal length and equal sum that agree everywhere except possibly
at position `i` are equal. -/
theorem List.eq_of_sum_eq_of_agree : ∀ (l₁ l₂ : List ℕ) (i : ℕ), l₁.length = l₂.length →
    (∀ j, j ≠ i → l₁[j]? = l₂[j]?) → l₁.sum = l₂.sum → l₁ = l₂
  | [], [], _, _, _, _ => rfl
  | [], _ :: _, _, hl, _, _ | _ :: _, [], _, hl, _, _ => by simp at hl
  | a :: l₁, b :: l₂, 0, _, hd, hs => by
      have ht : l₁ = l₂ := List.ext_getElem? fun j => by simpa using hd (j + 1) (by omega)
      subst ht
      simp only [List.sum_cons, Nat.add_right_cancel_iff] at hs
      rw [hs]
  | a :: l₁, b :: l₂, i + 1, hl, hd, hs => by
      have hab : a = b := by simpa using hd 0 (by omega)
      subst hab
      have ht := List.eq_of_sum_eq_of_agree l₁ l₂ i (by simpa using hl)
        (fun j hj => by simpa using hd (j + 1) (by omega))
        (by simp only [List.sum_cons] at hs; omega)
      rw [ht]

/-- **No single change.** Two formulas with the same number of words whose
arity sequences agree everywhere except possibly at one position have the
same arity sequence: one wrong arity always breaks the parse. -/
theorem code_no_single_change (f : Formula ω) (g : Formula ω') (i : ℕ)
    (hl : (code f).length = (code g).length)
    (hd : ∀ j, j ≠ i → (code f)[j]? = (code g)[j]?) : code f = code g :=
  List.eq_of_sum_eq_of_agree _ _ i hl hd (by have := code_sum f; have := code_sum g; omega)

end Codes

section Counting

open MeasureTheory Finset

variable {Ω ι : Type*} [MeasurableSpace Ω] [Fintype ι] (μ : Measure Ω)

open Classical in
/-- The number of the events `A i` that occur at `ω`. -/
noncomputable def occurring (A : ι → Set Ω) (ω : Ω) : ℕ := (univ.filter fun i => ω ∈ A i).card

/-- **At least two, without independence.** By Markov's inequality on the
number of occurring events, at least two occur with probability at most half
the sum of their probabilities. -/
theorem two_occur_le_half (A : ι → Set Ω) (hA : ∀ i, MeasurableSet (A i)) :
    2 * μ {ω | 2 ≤ occurring A ω} ≤ ∑ i, μ (A i) := by
  set F : Ω → ENNReal := fun ω => ∑ i, (A i).indicator 1 ω
  have hF : ∀ ω, F ω = occurring A ω := by
    intro ω
    classical
    simp only [F, occurring, Set.indicator_apply, Pi.one_apply, card_filter]
    push_cast
    rfl
  have hmeas : Measurable F :=
    Finset.measurable_sum _ fun i _ => measurable_one.indicator (hA i)
  have hint : ∫⁻ ω, F ω ∂μ = ∑ i, μ (A i) := by
    rw [lintegral_finsetSum _ fun i _ => measurable_one.indicator (hA i)]
    exact sum_congr rfl fun i _ => lintegral_indicator_one (hA i)
  have hset : {ω | 2 ≤ occurring A ω} = {ω | 2 ≤ F ω} := by
    ext ω
    simp only [Set.mem_ofPred_eq, hF]
    exact_mod_cast Iff.rfl
  rw [hset, ← hint]
  exact mul_meas_ge_le_lintegral hmeas 2

/-- **At least two, without positive correlation.** If no two events are
positively correlated, at least two occur with probability at most the sum
over pairs of the products of their probabilities. -/
theorem two_occur_le_pairs [LinearOrder ι] (A : ι → Set Ω)
    (h : ∀ i j, i < j → μ (A i ∩ A j) ≤ μ (A i) * μ (A j)) :
    μ {ω | 2 ≤ occurring A ω} ≤
      ∑ p ∈ univ.filter (fun p : ι × ι => p.1 < p.2), μ (A p.1) * μ (A p.2) := by
  have hsub : {ω | 2 ≤ occurring A ω} ⊆
      ⋃ p ∈ univ.filter (fun p : ι × ι => p.1 < p.2), A p.1 ∩ A p.2 := by
    intro ω hω
    classical
    simp only [Set.mem_ofPred_eq, occurring] at hω
    obtain ⟨a, ha, b, hb, hab⟩ := one_lt_card.mp hω
    simp only [mem_filter, mem_univ, true_and] at ha hb
    simp only [Set.mem_iUnion, Set.mem_inter_iff, mem_filter, mem_univ, true_and]
    rcases lt_or_gt_of_ne hab with h | h
    · exact ⟨(a, b), h, ha, hb⟩
    · exact ⟨(b, a), h, hb, ha⟩
  calc μ {ω | 2 ≤ occurring A ω}
      ≤ μ (⋃ p ∈ univ.filter (fun p : ι × ι => p.1 < p.2), A p.1 ∩ A p.2) := measure_mono hsub
    _ ≤ ∑ p ∈ univ.filter (fun p : ι × ι => p.1 < p.2), μ (A p.1 ∩ A p.2) :=
        measure_biUnion_finset_le _ _
    _ ≤ _ := sum_le_sum fun p hp => h _ _ (mem_filter.mp hp).2

/-- **Assembled bound.** If a wrong answer implies that some evaluated word
`i ∈ E` is misread within its arity group (`W i`) or that at least two arity
decisions fail, the error probability is at most the evaluated words'
within-group risks plus the probability of two arity failures. -/
theorem detected_error_le (wrong : Set Ω) (E : Finset ι) (W A : ι → Set Ω)
    (h : wrong ⊆ (⋃ i ∈ E, W i) ∪ {ω | 2 ≤ occurring A ω}) :
    μ wrong ≤ ∑ i ∈ E, μ (W i) + μ {ω | 2 ≤ occurring A ω} :=
  (measure_mono h).trans <| (measure_union_le _ _).trans <|
    add_le_add_left (measure_biUnion_finset_le _ _) _

/-- **Floors.** The detection account `min (S / 2, e₂)` is monotone in the
risks: lowering any risk, for instance to zero for words still open to
refinement, never raises it. -/
theorem detection_account_mono [LinearOrder ι] {ρ ρ' : ι → ℝ} (h0 : ∀ i, 0 ≤ ρ' i)
    (h : ∀ i, ρ' i ≤ ρ i) :
    min ((∑ i, ρ' i) / 2) (∑ p ∈ univ.filter (fun p : ι × ι => p.1 < p.2), ρ' p.1 * ρ' p.2) ≤
      min ((∑ i, ρ i) / 2) (∑ p ∈ univ.filter (fun p : ι × ι => p.1 < p.2), ρ p.1 * ρ p.2) := by
  apply min_le_min
  · gcongr with i _
    exact h i
  · apply sum_le_sum
    intro p _
    exact mul_le_mul (h p.1) (h p.2) (h0 p.2) ((h0 p.1).trans (h p.1))

end Counting

/-- The sum of nonnegative pair products at a minimum separation is nonnegative. -/
theorem pair_gap_sum_nonneg (risk : ℕ → ℝ) (n gap : ℕ) (h : ∀ i, 0 ≤ risk i) :
    0 ≤ ∑ i ∈ Finset.range n, ∑ j ∈ Finset.range n,
      if i + gap ≤ j then risk i * risk j else 0 := by
  apply Finset.sum_nonneg
  intro i hi
  apply Finset.sum_nonneg
  intro j hj
  split
  · exact mul_nonneg (h i) (h j)
  · exact le_rfl

/-- Adding one risk preserves a pair-sum bound when its prefix is bounded. -/
theorem pair_prefix_step_upper (total pref risk totalUpper prefixUpper riskUpper : ℝ)
    (hTotal : total ≤ totalUpper) (hPrefix : pref ≤ prefixUpper)
    (hRisk : risk ≤ riskUpper) (hRisk0 : 0 ≤ risk) (hPrefixUpper0 : 0 ≤ prefixUpper) :
    total + pref * risk ≤ totalUpper + prefixUpper * riskUpper := by
  exact add_le_add hTotal (mul_le_mul hPrefix hRisk hRisk0 hPrefixUpper0)

/-- Upper bounds on the risks before and after an item upper-bound its pair share. -/
theorem pair_share_prefix_suffix_upper (risk left right leftUpper rightUpper : ℝ)
    (hr : 0 ≤ risk) (hl : left ≤ leftUpper) (hh : right ≤ rightUpper) :
    risk * (left + right) / 2 ≤ risk * (leftUpper + rightUpper) / 2 := by
  have h : 0 ≤ risk * ((leftUpper - left) + (rightUpper - right)) :=
    mul_nonneg hr (add_nonneg (sub_nonneg.mpr hl) (sub_nonneg.mpr hh))
  nlinarith

/-- Upper bounds on a detection share and within-group risk bound their sum. -/
theorem detection_share_combine_upper (share within shareUpper withinUpper : ℝ)
    (hs : share ≤ shareUpper) (hw : within ≤ withinUpper) :
    share + within ≤ shareUpper + withinUpper := by
  linarith

/-- **Within-group errors.** Under a reading `p`, the probability that the
true class lies in the read class's group `g` but differs from it,
`p(g) − p(a)`, is at most the risk `1 − p(a) / p(g)` of the decision
restricted to `g`. -/
theorem joint_le_restricted {a g : ℝ} (hg : 0 < g) (hg1 : g ≤ 1) (ha : a ≤ g) :
    g - a ≤ 1 - a / g := by
  have hq : 0 ≤ 1 - a / g := by
    rw [sub_nonneg, div_le_one hg]
    exact ha
  have : g - a = g * (1 - a / g) := by field_simp
  rw [this]
  nlinarith

end NCA
