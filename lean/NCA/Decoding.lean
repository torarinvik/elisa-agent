import Mathlib.Algebra.BigOperators.Ring.List
import NCA.Detection

/-!
# Decoding by the format

`NCA.Detection` uses the prefix format to *detect* errors: a reading whose
arities do not parse is refused. The format can also *correct* them. The
arity sequences of formulas are exactly the words a counter automaton
accepts (`accepts_iff_codes`), so the most probable parseable arity
sequence, and the total probability of all parseable ones, are computed by
dynamic programs over the automaton's states.

The dynamic programs are stated for any deterministic automaton and any
position-wise weights: `dpSum` is the sum, and `dpMax` the maximum, of
`score` over all sequences of the given length (`dpSum_eq`, `dpMax_ge`,
`dpMax_attained`). With per-word arity probabilities as weights, `dpMax` is
the probability of the decoded sequence and `dpSum` the normalizer `Z`; the
decoded sequence is wrong with posterior probability `1 − dpMax / dpSum`,
which never exceeds the union bound (`exact_risk_le_union`).
-/

namespace NCA

/-- Restricting a sum to a known support interval removes only zero terms. -/
theorem sum_filter_support (xs : List ℕ) (f : ℕ → ℝ) (first last : ℕ)
    (outside : ∀ n ∈ xs, (n < first ∨ last < n) → f n = 0) :
    (xs.map f).sum = ((xs.filter fun n => first ≤ n ∧ n ≤ last).map f).sum := by
  induction xs with
  | nil => simp
  | cons x xs ih =>
    have rest : ∀ n ∈ xs, (n < first ∨ last < n) → f n = 0 := by
      intro n hn h
      exact outside n (List.mem_cons_of_mem _ hn) h
    by_cases h : first ≤ x ∧ x ≤ last
    · simp [h, ih rest]
    · have hz : f x = 0 := outside x List.mem_cons_self (by omega)
      simp [h, hz, ih rest]

/-- Restricting a nonnegative maximum to its support removes only zero terms. -/
theorem max_filter_support (xs : List ℕ) (f : ℕ → ℝ) (first last : ℕ)
    (outside : ∀ n ∈ xs, (n < first ∨ last < n) → f n = 0) :
    (xs.map f).foldr max 0 =
      ((xs.filter fun n => first ≤ n ∧ n ≤ last).map f).foldr max 0 := by
  have nonneg : ∀ ys : List ℝ, 0 ≤ ys.foldr max 0 := by
    intro ys
    induction ys with
    | nil => simp
    | cons y ys ih => exact le_trans ih (le_max_right y _)
  induction xs with
  | nil => simp
  | cons x xs ih =>
    have rest : ∀ n ∈ xs, (n < first ∨ last < n) → f n = 0 := by
      intro n hn h
      exact outside n (List.mem_cons_of_mem _ hn) h
    by_cases h : first ≤ x ∧ x ≤ last
    · simp [h, ih rest]
    · have hz : f x = 0 := outside x List.mem_cons_self (by omega)
      simp [h, hz, ih rest, max_eq_right (nonneg _)]

/-- A successor support interval translates to bounds on the source state. -/
theorem support_shift_bounds (n arity first last : ℤ) :
    (first ≤ n - 1 + arity ∧ n - 1 + arity ≤ last) ↔
      (first + 1 - arity ≤ n ∧ n ≤ last + 1 - arity) := by
  omega

/-- A scored transition must lie in both the prefix and shifted suffix support. -/
theorem split_support_intersection (n arity left_first left_last right_first right_last : ℤ) :
    (left_first ≤ n ∧ n ≤ left_last ∧
      right_first ≤ n - 1 + arity ∧ n - 1 + arity ≤ right_last) ↔
    (max left_first (right_first + 1 - arity) ≤ n ∧
      n ≤ min left_last (right_last + 1 - arity)) := by
  simp only [max_le_iff, le_min_iff]
  omega

/-- Increasing an arity cannot restore a predecessor below the allowed interval. -/
theorem trace_predecessor_monotone (before lower arity later : ℤ)
    (ordered : arity ≤ later) (outside : before + 1 - arity < lower) :
    before + 1 - later < lower := by
  omega

/-- Increasing an arity cannot restore a successor above the allowed interval. -/
theorem trace_successor_monotone (after upper arity later : ℤ)
    (ordered : arity ≤ later) (outside : upper < after - 1 + arity) :
    upper < after - 1 + later := by
  omega

/-- Once an ordered arity exceeds the destination envelope, later ones do too. -/
theorem ordered_arity_exceeds_envelope (source minimum upper arity later : ℤ)
    (source_bound : minimum ≤ source) (ordered : arity ≤ later)
    (outside : upper + 1 - minimum < arity) : upper < source - 1 + later := by
  omega

/-- Keep the earlier alphabet index when two candidates have equal score. -/
def tiedChoice (current candidate : ℕ) : ℕ :=
  if candidate < current then candidate else current

/-- The tie rule chooses the minimum index, independently of encounter order. -/
theorem tiedChoice_eq_min (current candidate : ℕ) :
    tiedChoice current candidate = min current candidate := by
  unfold tiedChoice
  split <;> omega

theorem tiedChoice_comm (a b : ℕ) : tiedChoice a b = tiedChoice b a := by
  simp [tiedChoice_eq_min, min_comm]

/-- Choose the larger score, breaking ties by the smaller original index. -/
noncomputable def scoredChoice (a b : ℝ × ℕ) : ℝ × ℕ :=
  if a.1 < b.1 then b else if b.1 < a.1 then a else (a.1, min a.2 b.2)

/-- The score and original-index tie rule is independent of encounter order. -/
theorem scoredChoice_comm (a b : ℝ × ℕ) : scoredChoice a b = scoredChoice b a := by
  rcases a with ⟨x, i⟩
  rcases b with ⟨y, j⟩
  by_cases hxy : x < y
  · have hyx : ¬y < x := not_lt_of_ge (le_of_lt hxy)
    simp [scoredChoice, hxy, hyx]
  · by_cases hyx : y < x
    · simp [scoredChoice, hxy, hyx]
    · have h : x = y := le_antisymm (le_of_not_gt hyx) (le_of_not_gt hxy)
      subst y
      simp [scoredChoice, min_comm]

/-- Grouping candidates does not change the selected score and tie index. -/
theorem scoredChoice_assoc (a b c : ℝ × ℕ) :
    scoredChoice (scoredChoice a b) c = scoredChoice a (scoredChoice b c) := by
  rcases a with ⟨x, i⟩
  rcases b with ⟨y, j⟩
  rcases c with ⟨z, k⟩
  simp only [scoredChoice]
  split_ifs <;> simp_all [min_comm, min_left_comm] <;> try linarith

/-- A transition with arity beyond the next row cannot enter that row. -/
theorem arity_exceeds_state_bound (state arity bound : ℕ) (h : bound < arity) :
    bound < state - 1 + arity := by
  omega

/-- A step with arity at most `growth + 1` increases the counter bound by at most `growth`. -/
theorem counter_growth_bound (state k arity growth : ℕ) (positive : 1 ≤ state)
    (before : state ≤ 1 + k * growth) (arity_bound : arity ≤ growth + 1) :
    state - 1 + arity ≤ 1 + (k + 1) * growth := by
  simp only [Nat.add_mul, Nat.one_mul]
  omega

/-- A path's total log weight is bounded by the sum of per-step budgets. -/
theorem log_weight_sum_bound (budget : ℝ) : ∀ weights : List ℝ,
    (∀ x ∈ weights, |x| ≤ budget) → |weights.sum| ≤ weights.length * budget
  | [], _ => by simp
  | x :: xs, h => by
    have hx := h x List.mem_cons_self
    have ih := log_weight_sum_bound budget xs (fun y hy => h y (List.mem_cons_of_mem _ hy))
    simp only [List.sum_cons, List.length_cons, Nat.cast_succ]
    calc |x + xs.sum| ≤ |x| + |xs.sum| := abs_add_le _ _
      _ ≤ budget + xs.length * budget := add_le_add hx ih
      _ = (xs.length + 1) * budget := by ring

section Automaton

variable {σ α : Type} (δ : σ → α → σ) (F : σ → Prop) [DecidablePred F] (as : List α)

/-- Every sequence of length `m` over the alphabet `as`. -/
def words : ℕ → List (List α)
  | 0 => [[]]
  | m + 1 => (as.map fun a => (words m).map (a :: ·)).flatten

/-- Product of position-wise weights along a sequence. -/
def weightOf : List (α → ℝ) → List α → ℝ
  | w :: ws, a :: l => w a * weightOf ws l
  | _, _ => 1

/-- A sequence's weight if the automaton, started at `s`, accepts it, else 0. -/
def score (ws : List (α → ℝ)) (s : σ) (l : List α) : ℝ :=
  if F (l.foldl δ s) then weightOf ws l else 0

/-- Sum-product dynamic program over the automaton's states. -/
def dpSum : List (α → ℝ) → σ → ℝ
  | [], s => if F s then 1 else 0
  | w :: ws, s => (as.map fun a => w a * dpSum ws (δ s a)).sum

/-- Max-product dynamic program over the automaton's states. -/
def dpMax : List (α → ℝ) → σ → ℝ
  | [], s => if F s then 1 else 0
  | w :: ws, s => (as.map fun a => w a * dpMax ws (δ s a)).foldr max 0

theorem score_cons (w : α → ℝ) (ws : List (α → ℝ)) (s : σ) (a : α) (l : List α) :
    score δ F (w :: ws) s (a :: l) = w a * score δ F ws (δ s a) l := by
  unfold score
  by_cases h : F (l.foldl δ (δ s a))
  · rw [if_pos (show F ((a :: l).foldl δ s) from h), if_pos h]; rfl
  · rw [if_neg (show ¬F ((a :: l).foldl δ s) from h), if_neg h, mul_zero]

theorem score_nil (s : σ) : score δ F [] s [] = if F s then 1 else 0 := rfl

omit [DecidablePred F] in
theorem sum_flatten (L : List (List ℝ)) : L.flatten.sum = (L.map List.sum).sum := by
  induction L with
  | nil => rfl
  | cons l L ih => simp [List.sum_append, ih]

/-- **Sum-product.** The dynamic program sums the scores of all sequences. -/
theorem dpSum_eq : ∀ (ws : List (α → ℝ)) (s : σ),
    dpSum δ F as ws s = ((words as ws.length).map (score δ F ws s)).sum
  | [], s => by simp only [dpSum, words, List.map_cons, List.map_nil, List.sum_cons,
      List.sum_nil, add_zero, List.length_nil, score_nil]
  | w :: ws, s => by
    simp only [dpSum, words, List.length_cons, List.map_flatten, sum_flatten, List.map_map]
    congr 1
    refine List.map_congr_left fun a _ => ?_
    rw [dpSum_eq ws (δ s a), ← List.sum_map_mul_left]
    simp only [Function.comp_def, List.map_map, score_cons]

theorem le_foldr_max {l : List ℝ} {x : ℝ} (hx : x ∈ l) : x ≤ l.foldr max 0 := by
  induction l with
  | nil => simp at hx
  | cons y l ih =>
    rcases List.mem_cons.mp hx with rfl | hx
    · exact le_max_left _ _
    · exact (ih hx).trans (le_max_right _ _)

theorem foldr_max_mem (l : List ℝ) : l.foldr max 0 = 0 ∨ l.foldr max 0 ∈ l := by
  induction l with
  | nil => simp
  | cons y l ih =>
    simp only [List.foldr_cons, List.mem_cons]
    rcases le_total y (l.foldr max 0) with h | h
    · rw [max_eq_right h]; rcases ih with h' | h'
      · exact Or.inl h'
      · exact Or.inr (Or.inr h')
    · rw [max_eq_left h]; exact Or.inr (Or.inl rfl)

theorem dpMax_nonneg : ∀ (ws : List (α → ℝ)) (s : σ), 0 ≤ dpMax δ F as ws s
  | [], s => by unfold dpMax; split <;> norm_num
  | w :: ws, s => by
    show 0 ≤ (as.map fun a => w a * dpMax δ F as ws (δ s a)).foldr max 0
    induction (as.map fun a => w a * dpMax δ F as ws (δ s a)) with
    | nil => simp
    | cons y l ih => exact ih.trans (le_max_right _ _)

/-- **Max-product, upper bound.** With nonnegative weights, no sequence
scores more than the dynamic program. -/
theorem dpMax_ge : ∀ (ws : List (α → ℝ)), (∀ w ∈ ws, ∀ a, 0 ≤ w a) →
    ∀ (s : σ) (l : List α), l ∈ words as ws.length → score δ F ws s l ≤ dpMax δ F as ws s
  | [], _, s, l, hl => by
    simp only [List.length_nil, words, List.mem_singleton] at hl
    subst hl
    rw [score_nil]; rfl
  | w :: ws, hw, s, l, hl => by
    simp only [words, List.length_cons, List.mem_flatten, List.mem_map] at hl
    obtain ⟨_, ⟨a, ha, rfl⟩, hl⟩ := hl
    obtain ⟨l', hl', rfl⟩ := List.mem_map.mp hl
    rw [score_cons]
    have ih := dpMax_ge ws (fun v hv => hw v (List.mem_cons_of_mem _ hv)) (δ s a) l' hl'
    calc w a * score δ F ws (δ s a) l'
        ≤ w a * dpMax δ F as ws (δ s a) :=
          mul_le_mul_of_nonneg_left ih (hw w List.mem_cons_self a)
      _ ≤ _ := le_foldr_max (List.mem_map.mpr ⟨a, ha, rfl⟩)

/-- **Max-product, attained.** Unless every sequence scores at most 0, some
sequence of the right length scores exactly the dynamic program's value:
tracing the maximizing choices back decodes it. -/
theorem dpMax_attained : ∀ (ws : List (α → ℝ)) (s : σ),
    dpMax δ F as ws s = 0 ∨ ∃ l ∈ words as ws.length, score δ F ws s l = dpMax δ F as ws s
  | [], s => Or.inr ⟨[], by simp [words], by rw [score_nil]; rfl⟩
  | w :: ws, s => by
    rcases foldr_max_mem (as.map fun a => w a * dpMax δ F as ws (δ s a)) with h | h
    · exact Or.inl (by simpa [dpMax] using h)
    · obtain ⟨a, ha, hval⟩ := List.mem_map.mp h
      rcases dpMax_attained ws (δ s a) with h0 | ⟨l, hl, hs⟩
      · left
        simp only [dpMax]
        rw [← hval, h0, mul_zero]
      · right
        refine ⟨a :: l, ?_, ?_⟩
        · simp only [words, List.length_cons]
          exact List.mem_flatten.mpr ⟨_, List.mem_map.mpr ⟨a, ha, rfl⟩, List.mem_map.mpr ⟨l, hl, rfl⟩⟩
        · simp only [dpMax]
          rw [score_cons, hs, hval]

end Automaton

/-- One Bernoulli event extends an existing count distribution. -/
def bernoulliStep (mass : ℕ → ℝ) (p : ℝ) (k : ℕ) : ℝ :=
  (1 - p) * mass k + if k = 0 then 0 else p * mass (k - 1)

/-- Splitting a count's mass between failure and success preserves it. -/
theorem bernoulli_split_mass (mass p : ℝ) : (1 - p) * mass + p * mass = mass := by
  ring

/-- Upper bounds remain upper bounds through one nonnegative count update. -/
theorem bernoulli_step_upper (p q p' q' x y x' y' : ℝ)
    (hp : 0 ≤ p) (hq : 0 ≤ q) (hx' : 0 ≤ x') (hy' : 0 ≤ y')
    (hpp : p ≤ p') (hqq : q ≤ q') (hxx : x ≤ x') (hyy : y ≤ y') :
    q * x + p * y ≤ q' * x' + p' * y' := by
  calc
    q * x + p * y ≤ q * x' + p * y' :=
      add_le_add (mul_le_mul_of_nonneg_left hxx hq) (mul_le_mul_of_nonneg_left hyy hp)
    _ ≤ q' * x' + p' * y' :=
      add_le_add (mul_le_mul_of_nonneg_right hqq hx') (mul_le_mul_of_nonneg_right hpp hy')

/-- A bounded tail stays bounded when mass crosses its threshold. -/
theorem bernoulli_tail_step_upper (tail p mass tailUpper pUpper massUpper : ℝ)
    (hTail : tail ≤ tailUpper) (hP : p ≤ pUpper) (hMass : mass ≤ massUpper)
    (hMass0 : 0 ≤ mass) (hPUpper0 : 0 ≤ pUpper) :
    tail + p * mass ≤ tailUpper + pUpper * massUpper := by
  exact add_le_add hTail (mul_le_mul hP hMass hMass0 hPUpper0)

/-- The number of successes cannot exceed the number of Bernoulli events. -/
theorem bernoulli_count_le_length (events : List Bool) :
    events.count true ≤ events.length := by
  exact List.count_le_length

/-- A certain success shifts a positive count threshold down by one. -/
theorem certain_success_threshold (count threshold : ℕ) (h : 0 < threshold) :
    threshold ≤ count + 1 ↔ threshold - 1 ≤ count := by
  omega

theorem bernoulliStep_zero (mass : ℕ → ℝ) (p : ℝ) :
    bernoulliStep mass p 0 = (1 - p) * mass 0 := by
  simp [bernoulliStep]

/-- An impossible event leaves every count's mass unchanged. -/
theorem bernoulliStep_impossible (mass : ℕ → ℝ) (k : ℕ) :
    bernoulliStep mass 0 k = mass k := by
  simp [bernoulliStep]

/-- A certain event shifts the count distribution by one. -/
theorem bernoulliStep_certain_zero (mass : ℕ → ℝ) : bernoulliStep mass 1 0 = 0 := by
  simp [bernoulliStep]

theorem bernoulliStep_certain_succ (mass : ℕ → ℝ) (k : ℕ) :
    bernoulliStep mass 1 (k + 1) = mass k := by
  simp [bernoulliStep]

theorem bernoulliStep_succ (mass : ℕ → ℝ) (p : ℝ) (k : ℕ) :
    bernoulliStep mass p (k + 1) = (1 - p) * mass (k + 1) + p * mass k := by
  simp [bernoulliStep]

section Counter

/-- The counter automaton of prefix notation. The state is the number of
subformulas still to be read, `none` once the reading has ended early. A word
of arity `a` replaces one awaited subformula by `a` new ones. -/
def await : Option ℕ → ℕ → Option ℕ
  | some (n + 1), a => some (n + a)
  | _, _ => none

variable {ω : Type}

theorem await_code (f : Formula ω) : ∀ (n : ℕ) (l : List ℕ),
    (code f ++ l).foldl await (some (n + 1)) = l.foldl await (some n) := by
  induction f with
  | const _ _ => intro n l; simp [code, await]
  | not _ f ih => intro n l; simp only [code, List.cons_append, List.foldl_cons, await]; exact ih n l
  | bin _ _ f g ihf ihg =>
    intro n l
    simp only [code, List.cons_append, List.foldl_cons, await, List.append_assoc]
    rw [show n + 2 = (n + 1) + 1 by omega, ihf (n + 1), ihg n]

/-- Every formula's arity sequence is accepted: read from one awaited
subformula, it ends with none awaited. -/
theorem code_accepted (f : Formula ω) : (code f).foldl await (some 1) = some 0 := by
  simpa using await_code f 0 []

theorem foldl_await_none : ∀ l : List ℕ, l.foldl await none = none
  | [] => rfl
  | _ :: l => foldl_await_none l

/-- Every successful counter run conserves pending slots plus consumed words. -/
theorem await_balance : ∀ (l : List ℕ) (start finish : ℕ),
    l.foldl await (some start) = some finish → start + l.sum = finish + l.length
  | [], start, finish, h => by simpa using h
  | _ :: l, 0, _, h => by simp [await, foldl_await_none] at h
  | a :: l, start + 1, finish, h => by
    simp only [List.foldl_cons, await] at h
    have ih := await_balance l (start + a) finish h
    simp only [List.sum_cons, List.length_cons]
    omega

/-- A complete prefix sequence has exactly one fewer child edge than words. -/
theorem accepted_arity_sum (l : List ℕ) (h : l.foldl await (some 1) = some 0) :
    l.sum + 1 = l.length := by
  have balance := await_balance l 1 0 h
  omega

/-- No arity in a complete prefix can reach the number of words. -/
theorem accepted_arity_lt_length (l : List ℕ) (a : ℕ) (member : a ∈ l)
    (accepted : l.foldl await (some 1) = some 0) : a < l.length := by
  have bound := List.le_sum_of_mem member
  have total := accepted_arity_sum l accepted
  omega

/-- Concatenated arity sequences of `n` formulas are accepted from `n`
awaited subformulas. -/
theorem codes_accepted : ∀ fs : List (Formula ω),
    ((fs.map code).flatten).foldl await (some fs.length) = some 0
  | [] => rfl
  | f :: fs => by
    simp only [List.map_cons, List.flatten_cons, List.length_cons]
    rw [await_code]
    exact codes_accepted fs

/-- **Accepted sequences are exactly the codes.** A sequence of arities at
most 2, read from `n` awaited subformulas, ends with none awaited exactly
when it is the concatenated arity sequence of `n` formulas. -/
theorem accepts_iff_codes : ∀ (l : List ℕ), (∀ a ∈ l, a ≤ 2) → ∀ n : ℕ,
    (l.foldl await (some n) = some 0 ↔
      ∃ fs : List (Formula Unit), fs.length = n ∧ (fs.map code).flatten = l)
  | [], _, n => by
    constructor
    · intro h
      simp only [List.foldl_nil, Option.some.injEq] at h
      exact ⟨[], by simp [h], rfl⟩
    · rintro ⟨fs, rfl, hfl⟩
      rw [← hfl]
      exact codes_accepted fs
  | a :: l, hl, n => by
    have hl' : ∀ b ∈ l, b ≤ 2 := fun b hb => hl b (List.mem_cons_of_mem _ hb)
    have ha : a ≤ 2 := hl a List.mem_cons_self
    constructor
    · intro h
      obtain ⟨k, rfl⟩ : ∃ k, n = k + 1 := by
        cases n with
        | zero => simp [await, foldl_await_none] at h
        | succ k => exact ⟨k, rfl⟩
      simp only [List.foldl_cons, await] at h
      obtain ⟨fs, hlen, hfl⟩ := (accepts_iff_codes l hl' (k + a)).mp h
      rcases (by omega : a = 0 ∨ a = 1 ∨ a = 2) with rfl | rfl | rfl
      · exact ⟨.const () true :: fs, by simp [hlen], by simp [code, hfl]⟩
      · obtain ⟨f, fs, rfl⟩ : ∃ f fs', fs = f :: fs' := by
          cases fs with
          | nil => simp at hlen
          | cons f fs' => exact ⟨f, fs', rfl⟩
        exact ⟨.not () f :: fs, by simp at hlen ⊢; omega, by simp [code, ← hfl]⟩
      · obtain ⟨f, g, fs, rfl⟩ : ∃ f g fs', fs = f :: g :: fs' := by
          match fs with
          | f :: g :: fs' => exact ⟨f, g, fs', rfl⟩
          | [] => simp at hlen
          | [_] => simp at hlen
        exact ⟨.bin () .and f g :: fs, by simp at hlen ⊢; omega, by simp [code, ← hfl]⟩
    · rintro ⟨fs, rfl, hfl⟩
      rw [← hfl]
      exact codes_accepted fs

end Counter

theorem prod_le_one : ∀ l : List ℝ, (∀ p ∈ l, 0 ≤ p ∧ p ≤ 1) → l.prod ≤ 1
  | [], _ => by simp
  | p :: l, h => by
    have hp := h p List.mem_cons_self
    have ih := prod_le_one l fun q hq => h q (List.mem_cons_of_mem _ hq)
    have h0 : 0 ≤ l.prod := List.prod_nonneg fun q hq => (h q (List.mem_cons_of_mem _ hq)).1
    simp only [List.prod_cons]
    nlinarith

/-- 1 − Π pₖ ≤ Σ (1 − pₖ) for probabilities `pₖ`. -/
theorem one_sub_prod_le_sum : ∀ l : List ℝ, (∀ p ∈ l, 0 ≤ p ∧ p ≤ 1) →
    1 - l.prod ≤ (l.map (1 - ·)).sum
  | [], _ => by simp
  | p :: l, h => by
    have hp := h p List.mem_cons_self
    have hl := fun q hq => h q (List.mem_cons_of_mem _ hq)
    have ih := one_sub_prod_le_sum l hl
    have h0 : 0 ≤ l.prod := List.prod_nonneg fun q hq => (hl q hq).1
    have h1 : l.prod ≤ 1 := prod_le_one l hl
    simp only [List.prod_cons, List.map_cons, List.sum_cons]
    nlinarith

/-- **Correction is no worse than the union bound.** The decoded sequence's
posterior risk `1 − x / Z`, with `x` its weight and `0 < Z ≤ 1` the weight of all
parseable sequences, is at most `1 − x`; with `x` a product of per-word
probabilities, at most the sum of their complements (`one_sub_prod_le_sum`). -/
theorem exact_risk_le_union {x Z : ℝ} (hx : 0 ≤ x) (hZ : Z ≤ 1) (hZ0 : 0 < Z) :
    1 - x / Z ≤ 1 - x := by
  have : x ≤ x / Z := by rw [le_div_iff₀ hZ0]; nlinarith
  linarith

/-- Complete binary skeletons with optional unary negation at leaves. -/
inductive CompleteShape : ℕ → List ℕ → Prop
  | leaf : CompleteShape 0 [0]
  | negated : CompleteShape 0 [1, 0]
  | branch {d : ℕ} {left right : List ℕ} : CompleteShape d left →
      CompleteShape d right → CompleteShape (d + 1) (2 :: (left ++ right))

/-- The length interval used to identify a complete skeleton's depth. -/
theorem complete_shape_length {d : ℕ} {arities : List ℕ}
    (h : CompleteShape d arities) :
    2 ^ (d + 1) ≤ arities.length + 1 ∧ arities.length + 1 ≤ 3 * 2 ^ d := by
  induction h with
  | leaf => simp
  | negated => simp
  | branch hl hr ihl ihr =>
      simp only [List.length_cons, List.length_append]
      simp only [pow_succ] at *
      constructor <;> omega

/-- Prefix trees with unary and binary nodes, bounded by their height budget. -/
inductive BoundedShape : ℕ → List ℕ → Prop
  | leaf (d : ℕ) : BoundedShape d [0]
  | unary {d : ℕ} {child : List ℕ} : BoundedShape d child →
      BoundedShape (d + 1) (1 :: child)
  | branch {d : ℕ} {left right : List ℕ} : BoundedShape d left →
      BoundedShape d right → BoundedShape (d + 1) (2 :: (left ++ right))

/-- A complete unary/binary prefix tree has one more leaf than binary nodes. -/
theorem bounded_shape_leaf_binary_count {d : ℕ} {arities : List ℕ}
    (h : BoundedShape d arities) : arities.count 0 = arities.count 2 + 1 := by
  induction h with
  | leaf d => simp
  | unary h ih => simpa using ih
  | branch hl hr ihl ihr =>
      simp only [List.count_cons, List.count_append]
      simp at *
      omega

/-- Bounded binary trees have at most `2^(d+1)-1` nodes. -/
theorem bounded_shape_length {d : ℕ} {arities : List ℕ}
    (h : BoundedShape d arities) : arities.length + 1 ≤ 2 ^ (d + 1) := by
  induction h with
  | leaf d => simp; exact Nat.succ_le_of_lt (one_lt_pow₀ (by decide) (by omega))
  | unary h ih =>
      simp only [List.length_cons, pow_succ] at *
      omega
  | branch hl hr ihl ihr =>
      simp only [List.length_cons, List.length_append, pow_succ] at *
      omega

/-- One extra level accommodates optional negations at complete-tree leaves. -/
theorem complete_shape_bounded {d : ℕ} {arities : List ℕ}
    (h : CompleteShape d arities) : BoundedShape (d + 1) arities := by
  induction h with
  | leaf => exact BoundedShape.leaf 1
  | negated => exact BoundedShape.unary (BoundedShape.leaf 0)
  | branch hl hr ihl ihr => exact BoundedShape.branch ihl ihr

/-- Expected leaf-count recurrence when each positive-depth node stops with p. -/
def prunedLeaves (p : ℝ) : ℕ → ℝ
  | 0 => 1
  | d + 1 => p + 2 * (1 - p) * prunedLeaves p d

/-- Expected binary-branch recurrence for the same stopping rule. -/
def prunedBranches (p : ℝ) : ℕ → ℝ
  | 0 => 0
  | d + 1 => (1 - p) * (1 + 2 * prunedBranches p d)

/-- Binary branches remain leaves minus one under the expectation recurrences. -/
theorem pruned_branches_eq_leaves_sub_one (p : ℝ) (d : ℕ) :
    prunedBranches p d = prunedLeaves p d - 1 := by
  induction d with
  | zero => simp [prunedBranches, prunedLeaves]
  | succ d ih => simp only [prunedBranches, prunedLeaves, ih]; ring

end NCA
