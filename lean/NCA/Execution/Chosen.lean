import Mathlib.Algebra.Order.BigOperators.Ring.Finset
import Mathlib.Probability.Moments.SubGaussian
import Mathlib.Tactic

/-! Choosing between readings by the payments they foretold (chapter 71). -/
namespace NCA

section Scores

variable {M I K : Type} [Field K] [LinearOrder K] [IsStrictOrderedRing K]

/-- A member's score on a stretch of presses: its losses there, added. -/
def scoreOn (loss : M → I → K) (s : Finset I) (m : M) : K := ∑ t ∈ s, loss m t

/-- A member leads on a stretch when no member's score there is lower. -/
def Leads (loss : M → I → K) (s : Finset I) (m : M) : Prop :=
  ∀ n, scoreOn loss s m ≤ scoreOn loss s n

omit [IsStrictOrderedRing K] in
/-- 71.1: among finitely many members one leads on any stretch. -/
theorem leader_exists [Finite M] [Nonempty M] (loss : M → I → K) (s : Finset I) :
    ∃ m, Leads loss s m :=
  Finite.exists_min (scoreOn loss s)

/-- 71.1: the leader's score is no more than any mix of the members' scores. -/
theorem leader_le_mix [Fintype M] (loss : M → I → K) (s : Finset I) (m : M)
    (leads : Leads loss s m) (share : M → K) (nonneg : ∀ n, 0 ≤ share n)
    (whole : ∑ n, share n = 1) : scoreOn loss s m ≤ ∑ n, share n * scoreOn loss s n := by
  calc scoreOn loss s m = ∑ n, share n * scoreOn loss s m := by
        rw [← Finset.sum_mul, whole, one_mul]
    _ ≤ ∑ n, share n * scoreOn loss s n :=
      Finset.sum_le_sum fun n _ => mul_le_mul_of_nonneg_left (leads n) (nonneg n)

/-- 71.1: over several stretches, each with its own leader, the leaders' scores together are no more
than any one member's over the same stretches. -/
theorem leaders_le_member {J : Type} (loss : M → I → K) (stretch : J → Finset I) (chosen : J → M)
    (leads : ∀ j, Leads loss (stretch j) (chosen j)) (js : Finset J) (n : M) :
    ∑ j ∈ js, scoreOn loss (stretch j) (chosen j) ≤ ∑ j ∈ js, scoreOn loss (stretch j) n :=
  Finset.sum_le_sum fun j _ => leads j n

omit [IsStrictOrderedRing K] in
/-- 71.3: a member whose score is strictly the lowest on every stretch scored from some press on is
chosen at every press from then on. -/
theorem strict_leader_chosen (loss : M → I → K) (stretch : Nat → Finset I) (chosen : Nat → M)
    (leads : ∀ t, Leads loss (stretch t) (chosen t)) (m : M) (from_ : Nat)
    (ahead : ∀ t, from_ ≤ t → ∀ n, n ≠ m →
      scoreOn loss (stretch t) m < scoreOn loss (stretch t) n)
    (t : Nat) (late : from_ ≤ t) : chosen t = m := by
  by_contra other
  exact absurd (leads t m) (not_le.2 (ahead t late _ other))

omit [IsStrictOrderedRing K] in
/-- 71.3: so the presses chosen by another member are no more than the presses before. -/
theorem others_chosen_le [DecidableEq M] (loss : M → I → K) (stretch : Nat → Finset I)
    (chosen : Nat → M) (leads : ∀ t, Leads loss (stretch t) (chosen t)) (m : M) (from_ : Nat)
    (ahead : ∀ t, from_ ≤ t → ∀ n, n ≠ m →
      scoreOn loss (stretch t) m < scoreOn loss (stretch t) n) (upTo : Nat) :
    ((Finset.range upTo).filter fun t => chosen t ≠ m).card ≤ from_ := by
  have early : ((Finset.range upTo).filter fun t => chosen t ≠ m) ⊆ Finset.range from_ := by
    intro t tIn
    rw [Finset.mem_filter] at tIn
    rw [Finset.mem_range]
    by_contra late
    exact tIn.2 (strict_leader_chosen loss stretch chosen leads m from_ ahead t (not_lt.1 late))
  simpa using Finset.card_le_card early

/-- 71.3: and whatever each press can cost at most, the presses chosen by another member cost at
most that for each press before. -/
theorem others_cost_le [DecidableEq M] (loss : M → I → K) (stretch : Nat → Finset I)
    (chosen : Nat → M) (leads : ∀ t, Leads loss (stretch t) (chosen t)) (m : M) (from_ : Nat)
    (ahead : ∀ t, from_ ≤ t → ∀ n, n ≠ m →
      scoreOn loss (stretch t) m < scoreOn loss (stretch t) n)
    (cost : Nat → K) (b : K) (most : ∀ t, cost t ≤ b) (nonneg : 0 ≤ b) (upTo : Nat) :
    ∑ t ∈ (Finset.range upTo).filter (fun t => chosen t ≠ m), cost t ≤ from_ * b := by
  have few := others_chosen_le loss stretch chosen leads m from_ ahead upTo
  calc ∑ t ∈ (Finset.range upTo).filter (fun t => chosen t ≠ m), cost t
      ≤ ((Finset.range upTo).filter fun t => chosen t ≠ m).card • b :=
        Finset.sum_le_card_nsmul _ _ _ fun t _ => most t
    _ ≤ from_ * b := by
        rw [nsmul_eq_mul]
        exact mul_le_mul_of_nonneg_right (Nat.cast_le.2 few) nonneg

end Scores

section Taught

variable {M X : Type} {St : M → Type}

/-- What a member has learned from some presses, the newest first. -/
def taughtOn (teach : ∀ m, St m → X → St m) (start : ∀ m, St m) (m : M) : List X → St m
  | [] => start m
  | x :: before => teach m (taughtOn teach start m before) x

/-- A play of so many presses: one member chooses, what its press shows is settled by who chose,
by what the members have learned and by the presses before, and every member is taught on it. Given
are what every member has learned and the presses, the newest first. -/
def playedTo (teach : ∀ m, St m → X → St m) (start : ∀ m, St m)
    (next : M → (∀ m, St m) → List X → X) (who : (∀ m, St m) → List X → M) :
    Nat → (∀ m, St m) × List X
  | 0 => (start, [])
  | n + 1 =>
    let now := playedTo teach start next who n
    let x := next (who now.1 now.2) now.1 now.2
    (fun m => teach m (now.1 m) x, x :: now.2)

/-- 71.2: the choice costs no presses: after a play every member has been taught on every press. -/
theorem presses_all_taught (teach : ∀ m, St m → X → St m) (start : ∀ m, St m)
    (next : M → (∀ m, St m) → List X → X) (who : (∀ m, St m) → List X → M) (n : Nat) :
    (playedTo teach start next who n).2.length = n := by
  induction n with
  | zero => rfl
  | succ k ih => simp [playedTo, ih]

/-- 71.2: what a member has learned in a play is what the presses of the play teach it, whoever
chose them. -/
theorem learned_from_presses (teach : ∀ m, St m → X → St m) (start : ∀ m, St m)
    (next : M → (∀ m, St m) → List X → X) (who : (∀ m, St m) → List X → M) (n : Nat) (m : M) :
    (playedTo teach start next who n).1 m
      = taughtOn teach start m (playedTo teach start next who n).2 := by
  induction n with
  | zero => rfl
  | succ k ih => simp [playedTo, taughtOn, ih]

/-- 71.2: so two plays of the same presses leave every member the same, though the members that
chose, and the rules by which they were chosen, differ. -/
theorem same_presses_same_learned (teach : ∀ m, St m → X → St m) (start : ∀ m, St m)
    (next next' : M → (∀ m, St m) → List X → X) (who who' : (∀ m, St m) → List X → M)
    (n n' : Nat)
    (same : (playedTo teach start next who n).2 = (playedTo teach start next' who' n').2)
    (m : M) :
    (playedTo teach start next who n).1 m = (playedTo teach start next' who' n').1 m := by
  rw [learned_from_presses, learned_from_presses, same]

end Taught

section Crossing

variable {K : Type} [Field K] [LinearOrder K] [IsStrictOrderedRing K]

/-- Losses of two members whose lead changes at a press: the first loses nothing before it and one
at every press from it on, the second the reverse. -/
def crossing (turn : Nat) (first : Bool) (t : Nat) : K :=
  if decide (t < turn) = first then 0 else 1

/-- The losses lie between nought and one. -/
theorem crossing_bounded (turn : Nat) (first : Bool) (t : Nat) :
    (0 : K) ≤ crossing turn first t ∧ crossing turn first t ≤ (1 : K) := by
  unfold crossing
  split <;> simp

/-- 71.4: scores can cross. On every stretch before the turn the first member's score is strictly
the lower, and on every stretch from the turn on strictly the higher. -/
theorem lead_can_end (turn : Nat) (s : Finset Nat) (some : s.Nonempty) :
    ((∀ t ∈ s, t < turn) →
        scoreOn (crossing (K := K) turn) s true < scoreOn (crossing (K := K) turn) s false)
      ∧ ((∀ t ∈ s, turn ≤ t) →
        scoreOn (crossing (K := K) turn) s false < scoreOn (crossing (K := K) turn) s true) := by
  constructor
  · intro before
    refine Finset.sum_lt_sum_of_nonempty some fun t ts => ?_
    simp [crossing, before t ts]
  · intro after
    refine Finset.sum_lt_sum_of_nonempty some fun t ts => ?_
    simp [crossing, not_lt.2 (after t ts)]

end Crossing

section Adverse

variable {K : Type} [Field K]

/-- The members a rule chooses, the newest first, when at every press the member it chose is the
one that loses. -/
def adversePast (rule : List Bool → Bool) : Nat → List Bool
  | 0 => []
  | t + 1 => rule (adversePast rule t) :: adversePast rule t

/-- Losses made against a rule that chooses by what went before: at every press the member the
rule chooses loses one and the other nothing. -/
def adverse (rule : List Bool → Bool) (member : Bool) (t : Nat) : K :=
  if rule (adversePast rule t) = member then 1 else 0

/-- 71.5: against any rule that chooses by the losses before there are losses under which the
member chosen is at every press the one that loses. -/
theorem chooser_always_worse (rule : List Bool → Bool) (t : Nat) :
    adverse (K := K) rule (rule (adversePast rule t)) t = 1
      ∧ adverse (K := K) rule (!rule (adversePast rule t)) t = 0 := by
  simp [adverse]

/-- 71.5: while the two members' losses together are one for each press, so that one of them loses
at no more than half of the presses. -/
theorem members_share_loss (rule : List Bool → Bool) (upTo : Nat) :
    ∑ t ∈ Finset.range upTo, adverse (K := K) rule true t
      + ∑ t ∈ Finset.range upTo, adverse (K := K) rule false t = upTo := by
  rw [← Finset.sum_add_distrib]
  have one : ∀ t ∈ Finset.range upTo,
      adverse (K := K) rule true t + adverse (K := K) rule false t = 1 := by
    intro t _
    unfold adverse
    cases rule (adversePast rule t) <;> simp
  rw [Finset.sum_congr rfl one]
  simp

end Adverse

section Settling

open MeasureTheory ProbabilityTheory

variable {Ω : Type} [MeasurableSpace Ω]

/-- 71.6 (Hoeffding 1963): let `more t` be by how much the member with the lower expected loss
lost more than the other at new press `t`. If these are independent, lie within `b` of nought and
are expected to be at most `-gap`, the other member has the score no higher on `n` new presses
with chance at most `exp (-n gap² / 2 b²)`. -/
theorem wrong_chosen_le (μ : Measure Ω) [IsProbabilityMeasure μ] (more : Nat → Ω → ℝ)
    (b gap : ℝ) (wide : 0 < b) (apart : 0 ≤ gap) (independent : iIndepFun more μ)
    (seen : ∀ t, AEMeasurable (more t) μ)
    (bounded : ∀ t, ∀ᵐ ω ∂μ, more t ω ∈ Set.Icc (-b) b)
    (expected : ∀ t, μ[more t] ≤ -gap) (n : Nat) :
    μ.real {ω | 0 ≤ ∑ t ∈ Finset.range n, more t ω}
      ≤ Real.exp (-(n * gap ^ 2) / (2 * b ^ 2)) := by
  rcases Nat.eq_zero_or_pos n with none | some
  · subst none
    simp
  have centred : iIndepFun (fun t ω => more t ω - μ[more t]) μ := by
    have moved := independent.comp (fun t (x : ℝ) => x - ∫ ω, more t ω ∂μ)
      fun t => measurable_sub_const _
    exact moved
  have narrow : ∀ t < n, HasSubgaussianMGF (fun ω => more t ω - μ[more t])
      ((‖b - -b‖₊ / 2) ^ 2) μ :=
    fun t _ => hasSubgaussianMGF_of_mem_Icc (seen t) (bounded t)
  have far : (0 : ℝ) ≤ n * gap := mul_nonneg (Nat.cast_nonneg n) apart
  have tail := HasSubgaussianMGF.measure_sum_range_ge_le_of_iIndepFun centred narrow far
  have within : {ω | 0 ≤ ∑ t ∈ Finset.range n, more t ω}
      ⊆ {ω | n * gap ≤ ∑ t ∈ Finset.range n, (more t ω - μ[more t])} := by
    intro ω least
    change 0 ≤ ∑ t ∈ Finset.range n, more t ω at least
    change n * gap ≤ ∑ t ∈ Finset.range n, (more t ω - μ[more t])
    rw [Finset.sum_sub_distrib]
    have means : ∑ t ∈ Finset.range n, μ[more t] ≤ ∑ _t ∈ Finset.range n, -gap :=
      Finset.sum_le_sum fun t _ => expected t
    rw [Finset.sum_const, Finset.card_range, nsmul_eq_mul] at means
    linarith
  refine (measureReal_mono within).trans (tail.trans_eq ?_)
  have width : ((‖b - -b‖₊ / 2) ^ 2 : NNReal) = (b ^ 2 : ℝ) := by
    push_cast
    rw [Real.norm_eq_abs, abs_of_pos (by linarith)]
    ring
  rw [width]
  congr 1
  have count : (n : ℝ) ≠ 0 := Nat.cast_ne_zero.2 some.ne'
  field_simp

end Settling

end NCA
