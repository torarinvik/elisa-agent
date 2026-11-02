import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.FieldSimp

/-!
# Selective answering and budgeted refinement

Each input `x` (from a finite population with weights `p x`) carries an error
bound `b x`, e.g. the sum of its symbols' calibrated error probabilities
(`composition_error_le_sum`), valid when the true error probability `q x` is
at most `b x`. Answering only when `b x ≤ δ` keeps the error rate among
answered inputs at most `δ`, whatever the input distribution.

Lowering bounds costs compute: refining symbol `i` costs `κ i` and lowers the
bound by `β i`. For a price `λ` per unit of compute, the refinement set
minimizing `bound + λ · cost` is the per-symbol threshold rule
`{i | λ κ i ≤ β i}`: refine exactly the symbols whose bound reduction is worth
their cost. Sweeping `λ` traces the optimal trade-off with local decisions.

A ladder of readings has a floor: the lowest risk each glyph can reach. A
target `δ` is reachable only if the floors sum to at most `δ`, so with a
per-glyph floor `ρ` an `L`-glyph input needs `L · ρ ≤ δ`: holding `δ` fixed as
inputs grow requires floors shrinking like `1 / L`.

When a decision ranges over a subset `C` of a reading's classes (an argmax
restricted to `C`), only errors of that restricted decision matter, and its
risk is `1 − max_C p / Σ_C p`. If the overall most probable class lies in
`C`, this is at most the unrestricted risk `1 − max p`: measuring risk
against the decision never loosens the bound and drops doubt about classes
the decision never chooses.
-/

namespace NCA

/-- A shared positive scaling leaves a ratio unchanged. -/
theorem risk_scale_invariant (outside total scale : ℝ) (hscale : scale ≠ 0) :
    (outside / scale) / (total / scale) = outside / total := by
  field_simp

/-- Scaling the operands separately has the same exact-real result. -/
theorem calibrated_difference_rescale (a b temperature : ℝ) :
    (a - b) / temperature = a / temperature - b / temperature := by
  exact sub_div a b temperature

/-- A nonnegative finite family with zero total has no positive entry. -/
theorem zero_total_no_positive_entry {ι : Type*} [Fintype ι]
    (mass : ι → ℝ) (nonneg : ∀ x, 0 ≤ mass x)
    (zero : ∑ x, mass x = 0) (x : ι) : mass x = 0 := by
  classical
  have bound : mass x ≤ ∑ y, mass y :=
    Finset.single_le_sum (fun y _ => nonneg y) (Finset.mem_univ x)
  rw [zero] at bound
  exact le_antisymm bound (nonneg x)

open Finset

variable {X : Type} [Fintype X]

/-- **Selective risk.** If `q ≤ b` and only inputs with `b x ≤ δ` are
answered, the weighted error among answered inputs is at most `δ` times their
weight. -/
theorem selective_risk_le (p q b : X → ℝ) (δ : ℝ) (hp : ∀ x, 0 ≤ p x)
    (hq : ∀ x, q x ≤ b x) :
    ∑ x ∈ univ.filter (fun x => b x ≤ δ), p x * q x ≤
      δ * ∑ x ∈ univ.filter (fun x => b x ≤ δ), p x := by
  rw [mul_sum]
  refine sum_le_sum fun x hx => ?_
  have hb : b x ≤ δ := (mem_filter.mp hx).2
  calc p x * q x ≤ p x * δ := mul_le_mul_of_nonneg_left ((hq x).trans hb) (hp x)
    _ = δ * p x := mul_comm _ _

/-- The risk bound is needed only where a certificate exists and is accepted. -/
theorem selective_risk_le_available (p q b : X → ℝ) (available : X → Prop)
    [DecidablePred available] (δ : ℝ) (hp : ∀ x, 0 ≤ p x)
    (hq : ∀ x, available x → q x ≤ b x) :
    ∑ x ∈ univ.filter (fun x => available x ∧ b x ≤ δ), p x * q x ≤
      δ * ∑ x ∈ univ.filter (fun x => available x ∧ b x ≤ δ), p x := by
  rw [mul_sum]
  refine sum_le_sum fun x hx => ?_
  have h := (mem_filter.mp hx).2
  calc p x * q x ≤ p x * δ := mul_le_mul_of_nonneg_left ((hq x h.1).trans h.2) (hp x)
    _ = δ * p x := mul_comm _ _

/-- Any selection policy preserves the bound when it is valid conditional on
the selected states. The hypothesis must be rechecked for a new policy. -/
theorem selective_risk_le_selected (p q b : X → ℝ) (selected : X → Prop)
    [DecidablePred selected] (δ : ℝ) (hp : ∀ x, 0 ≤ p x)
    (hq : ∀ x, selected x → q x ≤ b x) :
    ∑ x ∈ univ.filter (fun x => selected x ∧ b x ≤ δ), p x * q x ≤
      δ * ∑ x ∈ univ.filter (fun x => selected x ∧ b x ≤ δ), p x := by
  exact selective_risk_le_available p q b selected δ hp hq

/-- Composing upper-bounding additions bounds the exact real sum. -/
theorem upper_fold_ge (add : ℝ → ℝ → ℝ) (xs : List ℝ) (initial : ℝ)
    (upper : ∀ a x, a + x ≤ add a x) :
    initial + xs.sum ≤ xs.foldl add initial := by
  induction xs generalizing initial with
  | nil => simp
  | cons x rest ih =>
      simp only [List.foldl_cons, List.sum_cons]
      calc
        initial + (x + rest.sum) = (initial + x) + rest.sum := by rw [add_assoc]
        _ ≤ add initial x + rest.sum := by linarith [upper initial x]
        _ ≤ rest.foldl add (add initial x) := ih _

/-- Composing lower-bounding additions bounds the exact real sum from below. -/
theorem lower_fold_le (add : ℝ → ℝ → ℝ) (xs : List ℝ) (initial : ℝ)
    (lower : ∀ a x, add a x ≤ a + x) :
    xs.foldl add initial ≤ initial + xs.sum := by
  induction xs generalizing initial with
  | nil => simp
  | cons x rest ih =>
      simp only [List.foldl_cons, List.sum_cons]
      calc
        rest.foldl add (add initial x) ≤ add initial x + rest.sum := ih _
        _ ≤ (initial + x) + rest.sum := by linarith [lower initial x]
        _ = initial + (x + rest.sum) := by rw [add_assoc]

variable {I : Type} [DecidableEq I]

/-- Positive alternative mass gives strictly positive decision risk. -/
theorem positive_alternative_risk {chosen outside : ℝ} (hc : 0 < chosen)
    (ho : 0 < outside) : 0 < outside / (chosen + outside) := by
  exact div_pos ho (add_pos hc ho)

/-- A positive observation floor leaves every represented input positive. -/
theorem positive_observation_floor {p ε : ℝ} (hε : 0 < ε) : 0 < max p ε := by
  exact lt_of_lt_of_le hε (le_max_right p ε)

omit [DecidableEq I] in
/-- Nonnegative weights with a positive member have positive total mass. -/
theorem observation_weight_sum_positive (s : Finset I) (w : I → ℝ)
    (hn : ∀ i ∈ s, 0 ≤ w i) (i : I) (hi : i ∈ s) (hp : 0 < w i) :
    0 < ∑ j ∈ s, w j := by
  exact lt_of_lt_of_le hp (single_le_sum hn hi)

/-- A deterministic decision over an encoding cannot distinguish two orders
when the encoded values coincide. -/
theorem collapsed_pair_cannot_choose_both {α β γ : Type*}
    (encode : α → β) (choose : β × β → γ) {x y : α}
    (h : encode x = encode y) {left right : γ} (hne : left ≠ right) :
    ¬ (choose (encode x, encode y) = left ∧
       choose (encode y, encode x) = right) := by
  intro choices
  have same : choose (encode x, encode y) = choose (encode y, encode x) := by rw [h]
  exact hne (choices.1.symm.trans (same.trans choices.2))

/-- Retaining the original value alongside any encoding preserves distinction. -/
theorem original_value_distinguishes {α β : Type*} (encode : α → β)
    {x y : α} (h : x ≠ y) : (encode x, x) ≠ (encode y, y) := by
  intro same
  exact h (congrArg Prod.snd same)

/-- A strictly increasing transform followed by positive normalization
preserves the ordering of weights. -/
theorem monotone_normalized_rank (f : ℝ → ℝ) (hf : StrictMono f)
    {a b total : ℝ} (ht : 0 < total) :
    f a / total < f b / total ↔ a < b := by
  rw [div_lt_div_iff_of_pos_right ht]
  exact hf.lt_iff_lt

/-- A strict-improvement scan retains the earlier choice on equal weights. -/
theorem ranked_tie_keeps_first {α : Type*} (first candidate : α) (a b : ℝ)
    (equal : a = b) : (if b > a then candidate else first) = first := by
  simp [equal]

/-- Positive temperature preserves logit order; negative temperature reverses it. -/
theorem temperature_rank (a b temperature : ℝ) :
    (0 < temperature → (a / temperature < b / temperature ↔ a < b)) ∧
    (temperature < 0 → (a / temperature < b / temperature ↔ b < a)) := by
  constructor
  · intro positive
    exact div_lt_div_iff_of_pos_right positive
  · intro negative
    exact div_lt_div_right_of_neg negative

/-- Choosing different groups can change risk by more than the gap between
their leading classes, because the groups can contain other mass. -/
theorem asymmetric_group_risk {x y z : ℝ} (ht : 0 < x + y + z)
    (h : y < x + z) : y / (x + y + z) < (x + z) / (x + y + z) := by
  exact (div_lt_div_iff_of_pos_right ht).2 h

/-- Bound plus priced compute after refining the symbols in `T`. -/
def refinedObjective (r β κ : I → ℝ) (lam : ℝ) (S T : Finset I) : ℝ :=
  ∑ i ∈ S, r i - ∑ i ∈ T, β i + lam * ∑ i ∈ T, κ i

/-- **Threshold optimality.** Refining exactly the symbols whose bound
reduction is at least their priced cost minimizes bound plus priced compute
over all refinement sets. -/
theorem threshold_optimal (r β κ : I → ℝ) (lam : ℝ) (S T : Finset I) (hT : T ⊆ S) :
    refinedObjective r β κ lam S (S.filter fun i => lam * κ i ≤ β i) ≤
      refinedObjective r β κ lam S T := by
  set G := S.filter fun i => lam * κ i ≤ β i
  set f : I → ℝ := fun i => lam * κ i - β i
  have key : ∑ i ∈ G, f i ≤ ∑ i ∈ T, f i := by
    rw [← sum_inter_add_sum_sdiff G T f, ← sum_inter_add_sum_sdiff T G f, inter_comm]
    have h1 : ∑ i ∈ G \ T, f i ≤ 0 := sum_nonpos fun i hi => by
      have := (mem_filter.mp (mem_sdiff.mp hi).1).2
      simp only [f]; linarith
    have h2 : 0 ≤ ∑ i ∈ T \ G, f i := sum_nonneg fun i hi => by
      have hiS : i ∈ S := hT (mem_sdiff.mp hi).1
      have : ¬ lam * κ i ≤ β i := fun h => (mem_sdiff.mp hi).2 (mem_filter.mpr ⟨hiS, h⟩)
      simp only [f]; linarith
    linarith
  simp only [refinedObjective, f, sum_sub_distrib, ← mul_sum] at key ⊢
  linarith

omit [DecidableEq I] in
/-- **Floor.** If every glyph's risk is at least its floor `ρ i`, the bound
is at least the sum of floors; a target below it is unreachable. -/
theorem bound_ge_floor (S : Finset I) (r ρ : I → ℝ) (h : ∀ i ∈ S, ρ i ≤ r i) :
    ∑ i ∈ S, ρ i ≤ ∑ i ∈ S, r i :=
  sum_le_sum h

omit [DecidableEq I] in
/-- **Length limit.** With a uniform floor `ρ`, a bound at most `δ` forces
`|S| · ρ ≤ δ`. -/
theorem length_limit (S : Finset I) (r : I → ℝ) (ρ δ : ℝ) (h : ∀ i ∈ S, ρ ≤ r i)
    (hδ : ∑ i ∈ S, r i ≤ δ) : S.card * ρ ≤ δ := by
  have := bound_ge_floor S r (fun _ => ρ) h
  simp only [sum_const, nsmul_eq_mul] at this
  linarith

/-- **Decision-relative risk is tighter.** With most probable mass `m` inside
the decision's classes of total mass `s ≤ 1`, the restricted risk
`1 − m / s` is at most the unrestricted risk `1 − m`. -/
theorem restricted_risk_le {m s : ℝ} (hm : 0 ≤ m) (hs : 0 < s) (hs1 : s ≤ 1) :
    1 - m / s ≤ 1 - m := by
  have : m ≤ m / s := by
    rw [le_div_iff₀ hs]
    nlinarith
  linarith

/-- The mass outside the chosen group gives the same conditional risk. -/
theorem risk_as_alternative_mass (chosen alternative : ℝ)
    (h : chosen + alternative ≠ 0) :
    1 - chosen / (chosen + alternative) = alternative / (chosen + alternative) := by
  have hsum : chosen / (chosen + alternative) + alternative / (chosen + alternative) = 1 := by
    rw [← add_div, div_self h]
  linarith

/-- Grouping a finite class distribution preserves its total mass. -/
theorem grouped_mass_sum {C G : Type} [Fintype C] [Fintype G] [DecidableEq G]
    (p : C → ℝ) (group : C → G) :
    ∑ g, ∑ c ∈ Finset.univ.filter (fun c => group c = g), p c = ∑ c, p c := by
  classical
  simp_rw [Finset.sum_filter]
  rw [Finset.sum_comm]
  simp

/-- Each grouped mass of a nonnegative class distribution is nonnegative. -/
theorem grouped_mass_nonneg {C G : Type} [Fintype C] [DecidableEq G]
    (p : C → ℝ) (group : C → G) (hp : ∀ c, 0 ≤ p c) (g : G) :
    0 ≤ ∑ c ∈ Finset.univ.filter (fun c => group c = g), p c := by
  classical
  exact Finset.sum_nonneg fun c _ => hp c

/-- Priorities may be stale: normalizing them allocates the current risk exactly. -/
theorem priority_allocation_sum (h : X → ℝ) (R : ℝ)
    (hH : (∑ x, h x) ≠ 0) :
    ∑ x, R * h x / (∑ y, h y) = R := by
  simp_rw [div_eq_mul_inv, mul_assoc]
  rw [← mul_sum, ← sum_mul, mul_inv_cancel₀ hH, mul_one]

/-- Nonnegative priorities allocate nonnegative charges. -/
theorem priority_allocation_nonneg (h : X → ℝ) (R : ℝ)
    (hh : ∀ x, 0 ≤ h x) (hR : 0 ≤ R) (x : X) :
    0 ≤ R * h x / (∑ y, h y) :=
  div_nonneg (mul_nonneg hR (hh x)) (sum_nonneg fun y _ => hh y)

/-- Filling a certified shortfall makes the total allocation cover the bound. -/
theorem priority_allocation_cover (R lower actual added : ℝ)
    (hlower : lower ≤ actual) (hadded : R - lower ≤ added) : R ≤ actual + added := by
  linarith

/-- Per-item upper bounds preserve allocation coverage when risks are combined. -/
theorem combined_allocation_cover (R : ℝ) (share within charge : X → ℝ)
    (hshare : R ≤ ∑ x, share x)
    (hcharge : ∀ x, share x + within x ≤ charge x) :
    R + ∑ x, within x ≤ ∑ x, charge x := by
  have hsum : (∑ x, (share x + within x)) ≤ ∑ x, charge x :=
    Finset.sum_le_sum fun x _ => hcharge x
  rw [Finset.sum_add_distrib] at hsum
  linarith

/-- A revision identifies all inputs to a cached deterministic quantity. -/
theorem revision_cache_eq {V Y : Type} (f : V → Y) {old current : V}
    (h : current = old) : f current = f old := congrArg f h

/-- Every retained entry agrees with the deterministic computation. -/
def CacheSound {K V : Type} (f : K → V) (cache : K → Option V) : Prop :=
  ∀ k v, cache k = some v → v = f k

/-- A hit or a recomputation returns the same value. -/
theorem cache_lookup_correct {K V : Type} (f : K → V) (cache : K → Option V)
    (sound : CacheSound f cache) (k : K) :
    (cache k).getD (f k) = f k := by
  cases h : cache k with
  | none => simp
  | some value => simpa [h] using sound k value h

/-- Evicting any set of entries preserves cache soundness. -/
theorem cache_evict_sound {K V : Type} (f : K → V) (cache : K → Option V)
    (sound : CacheSound f cache) (keep : K → Bool) :
    CacheSound f (fun k => if keep k then cache k else none) := by
  intro k v h
  cases hk : keep k <;> simp [hk] at h
  exact sound k v h

/-- Reinserting the computed value preserves cache soundness. -/
theorem cache_store_sound {K V : Type} [DecidableEq K] (f : K → V)
    (cache : K → Option V) (sound : CacheSound f cache) (target : K) :
    CacheSound f (fun k => if k = target then some (f target) else cache k) := by
  intro k v h
  by_cases hk : k = target
  · subst k
    simpa using h.symm
  · simp [hk] at h
    exact sound k v h

/-- A certified upper envelope absorbs numerical underestimation before selection. -/
theorem selective_risk_le_approx (p q b reported allowance : X → ℝ) (δ : ℝ)
    (hp : ∀ x, 0 ≤ p x) (hq : ∀ x, q x ≤ b x)
    (hround : ∀ x, b x ≤ reported x + allowance x) :
    ∑ x ∈ univ.filter (fun x => reported x + allowance x ≤ δ), p x * q x ≤
      δ * ∑ x ∈ univ.filter (fun x => reported x + allowance x ≤ δ), p x :=
  selective_risk_le p q (fun x => reported x + allowance x) δ hp
    (fun x => (hq x).trans (hround x))

/-- Threshold decisions are stable outside the numerical uncertainty margin. -/
theorem threshold_stable {reference reported allowance δ : ℝ}
    (herror : |reported - reference| ≤ allowance)
    (hmargin : reference + allowance ≤ δ ∨ δ + allowance < reference) :
    (reported ≤ δ ↔ reference ≤ δ) := by
  have hlo := (abs_le.mp herror).1
  have hhi := (abs_le.mp herror).2
  have hnonneg : 0 ≤ allowance := (abs_nonneg _).trans herror
  rcases hmargin with h | h
  · constructor <;> intro hsel <;> linarith
  · constructor <;> intro hsel <;> linarith

/-- Normalizing row log weights subtracts the same sum from every sequence. -/
theorem sum_row_shift (scores shifts : X → ℝ) :
    ∑ x, (scores x - shifts x) = (∑ x, scores x) - ∑ x, shifts x := by
  rw [Finset.sum_sub_distrib]

/-- A common log-score shift preserves the maximizing order. -/
theorem row_shift_order (a b shift : ℝ) : a - shift ≤ b - shift ↔ a ≤ b := by
  constructor <;> intro h <;> linarith

end NCA
