import NCA.Execution.Newest

/-! Putting out or thinking on (chapter 76). At a step the risk of putting out now and the risk of going on are
weighed; a trial is a run of steps, soonest first, and what a way of putting out is paid over it is the read
of chapter 75 with the steps as its items. -/
namespace NCA

section Thinking

/-- 76.1: putting out with any chance at a step risks at least the smaller of the two risks. -/
theorem least_risk_le (out act wait : ℝ) (low : 0 ≤ out) (high : out ≤ 1) :
    min act wait ≤ out * act + (1 - out) * wait := by
  have first := min_le_left act wait
  have second := min_le_right act wait
  nlinarith [mul_le_mul_of_nonneg_left first low, mul_le_mul_of_nonneg_left second (sub_nonneg.mpr high)]

/-- 76.1: putting out where the risk of going on is at least the risk of putting out now, and going on
otherwise, risks the smaller of the two. -/
theorem rule_risks_least (act wait : ℝ) : (if act ≤ wait then act else wait) = min act wait := by
  by_cases h : act ≤ wait
  · simp [h]
  · simp [h, min_eq_right (le_of_lt (not_le.mp h))]

/-- 76.2: the rule applied to risks that are each read within `off` of the true ones risks at most twice
`off` more than the smaller true risk. -/
theorem read_risks_cost_little (act wait readAct readWait off : ℝ) (nearAct : |readAct - act| ≤ off)
    (nearWait : |readWait - wait| ≤ off) :
    (if readAct ≤ readWait then act else wait) ≤ min act wait + 2 * off := by
  have a := abs_le.mp nearAct
  have w := abs_le.mp nearWait
  by_cases h : readAct ≤ readWait
  · simp only [h, if_true]
    rcases le_total act wait with le | ge
    · rw [min_eq_left le]; linarith
    · rw [min_eq_right ge]; linarith
  · have lt := not_le.mp h
    simp only [h, if_false]
    rcases le_total act wait with le | ge
    · rw [min_eq_left le]; linarith
    · rw [min_eq_right ge]; linarith

/-- 76.2: with a threshold on the quotient of the risks that is at most one, the rule risks at most the
smaller risk and what the threshold lacks of one, times the risk of putting out now. -/
theorem threshold_costs_little (act wait threshold : ℝ) (nonneg : 0 ≤ act) (high : threshold ≤ 1) :
    (if threshold * act ≤ wait then act else wait) ≤ min act wait + (1 - threshold) * act := by
  have slack : 0 ≤ (1 - threshold) * act := mul_nonneg (sub_nonneg.mpr high) nonneg
  by_cases h : threshold * act ≤ wait
  · simp only [h, if_true]
    rcases le_total act wait with le | ge
    · rw [min_eq_left le]; linarith
    · rw [min_eq_right ge]; nlinarith
  · have lt := not_le.mp h
    simp only [h, if_false]
    rcases le_total act wait with le | ge
    · rw [min_eq_left le]; nlinarith
    · rw [min_eq_right ge]; linarith

/-- 76.1: one number says where the risk lies, the share of the two risks that is in putting out now; the rule
with a threshold on the quotient puts out exactly where that share is at most one in one and the threshold. -/
theorem share_le_iff (act wait threshold : ℝ) (nonneg : 0 ≤ threshold) (some : 0 < act + wait) :
    act / (act + wait) ≤ 1 / (1 + threshold) ↔ threshold * act ≤ wait := by
  rw [div_le_div_iff₀ some (by linarith)]
  constructor <;> intro h <;> nlinarith

/-- The best a trial can be paid from here on: the largest chance of a step left, nought where none is. -/
def bestBy : List ℝ → ℝ
  | [] => 0
  | paid :: later => max paid (bestBy later)

/-- The steps as items: each a chance of putting out and the chance an output there is paid. Putting out
where the step's chance is at least the best of the steps after it, and going on otherwise. -/
noncomputable def outWhereBest : List ℝ → List (ℝ × ℝ)
  | [] => []
  | paid :: later => ((if bestBy later ≤ paid then 1 else 0), paid) :: outWhereBest later

/-- At one step, no chance of putting out is paid more than the better of putting out and going on. -/
theorem out_or_on (out paid waited : ℝ) (low : 0 ≤ out) (high : out ≤ 1) :
    out * paid + (1 - out) * waited ≤ max paid waited := by
  have first := le_max_left paid waited
  have second := le_max_right paid waited
  nlinarith [mul_le_mul_of_nonneg_left first low, mul_le_mul_of_nonneg_left second (sub_nonneg.mpr high)]

/-- 76.3: no way of putting out is paid more than the best chance of a step. -/
theorem paid_le_best (items : List (ℝ × ℝ)) (unit : ∀ item ∈ items, 0 ≤ item.1 ∧ item.1 ≤ 1) :
    readBy items ≤ bestBy (items.map Prod.snd) := by
  induction items with
  | nil => simp [readBy, bestBy]
  | cons item later ih =>
    have here := unit item (List.mem_cons_self ..)
    have rest := ih (fun x hx => unit x (List.mem_cons_of_mem _ hx))
    simp only [readBy, List.map_cons, bestBy]
    calc item.1 * item.2 + (1 - item.1) * readBy later
        ≤ item.1 * item.2 + (1 - item.1) * bestBy (later.map Prod.snd) := by
          nlinarith [mul_le_mul_of_nonneg_left rest (sub_nonneg.mpr here.2)]
      _ ≤ max item.2 (bestBy (later.map Prod.snd)) := out_or_on _ _ _ here.1 here.2

/-- 76.3: putting out where a step's chance is at least the best of those after it is paid the best chance. -/
theorem out_where_best_paid (steps : List ℝ) : readBy (outWhereBest steps) = bestBy steps := by
  induction steps with
  | nil => simp [outWhereBest, readBy, bestBy]
  | cons paid later ih =>
    simp only [outWhereBest, readBy, bestBy, ih]
    by_cases better : bestBy later ≤ paid
    · simp [better]
    · have worse : paid ≤ bestBy later := le_of_lt (not_le.mp better)
      simp [better, max_eq_right worse]

/-- 76.4: a learner that never puts out is never paid. -/
theorem never_out_unpaid (items : List (ℝ × ℝ)) (never : ∀ item ∈ items, item.1 = 0) : readBy items = 0 := by
  induction items with
  | nil => simp [readBy]
  | cons item later ih =>
    simp [readBy, never item (List.mem_cons_self ..), ih (fun x hx => never x (List.mem_cons_of_mem _ hx))]

/-- 76.4: putting out more surely at a step where an output is paid at least as often as going on from there
does not lower what the way of putting out is paid, whatever is done at the steps before. -/
theorem out_more_pays (before after : List (ℝ × ℝ)) (out more paid : ℝ) (raised : out ≤ more)
    (worth : readBy after ≤ paid) (unit : ∀ item ∈ before, 0 ≤ item.1 ∧ item.1 ≤ 1) :
    readBy (before ++ (out, paid) :: after) ≤ readBy (before ++ (more, paid) :: after) := by
  have left := left_between (before.map Prod.fst) (by
    intro m hm
    obtain ⟨item, within, rfl⟩ := List.mem_map.mp hm
    exact unit item within)
  rw [read_append, read_append]
  simp only [readBy]
  nlinarith [mul_nonneg left.1 (mul_nonneg (sub_nonneg.mpr raised) (sub_nonneg.mpr worth))]

/-- What thinking costs where each concept is asked only if no earlier one settled the step: each concept's
cost times the chance it is reached, soonest first. An item is that chance and the cost. -/
def costBy : List (ℝ × ℝ) → ℝ
  | [] => 0
  | concept :: later => concept.1 * concept.2 + costBy later

/-- 76.5: asking each concept only when it is reached costs no more than asking them all. -/
theorem cost_le_all (concepts : List (ℝ × ℝ)) (unit : ∀ c ∈ concepts, 0 ≤ c.1 ∧ c.1 ≤ 1)
    (costly : ∀ c ∈ concepts, 0 ≤ c.2) : costBy concepts ≤ (concepts.map Prod.snd).sum := by
  induction concepts with
  | nil => simp [costBy]
  | cons c later ih =>
    have here := unit c (List.mem_cons_self ..)
    have cost := costly c (List.mem_cons_self ..)
    have rest := ih (fun x hx => unit x (List.mem_cons_of_mem _ hx)) (fun x hx => costly x (List.mem_cons_of_mem _ hx))
    simp only [costBy, List.map_cons, List.sum_cons]
    nlinarith [mul_le_mul_of_nonneg_right here.2 cost]

/-- 76.8: in a contest of shares, lowering one amount raises the share of any other: what one hypothesis
loses is given to the others, one that was never judged among them. -/
theorem share_rises (amount whole less : ℝ) (pos : 0 < amount) (some : 0 < less) (left : less < whole) :
    amount / whole < amount / (whole - less) := by
  have small : 1 / whole < 1 / (whole - less) := one_div_lt_one_div_of_lt (by linarith) (by linarith)
  calc amount / whole = amount * (1 / whole) := by ring
    _ < amount * (1 / (whole - less)) := mul_lt_mul_of_pos_left small pos
    _ = amount / (whole - less) := by ring

/-- 76.8: and every other share is raised by one and the same factor, so the loss is given to the others
as they stand, whatever was learned of them. -/
theorem shares_rise_alike (first second whole less : ℝ) (one : first ≠ 0) (other : second ≠ 0) :
    first / (whole - less) / (first / whole) = second / (whole - less) / (second / whole) := by
  have each : ∀ x : ℝ, x ≠ 0 → x / (whole - less) / (x / whole) = whole / (whole - less) := by
    intro x nonzero
    rw [div_div_div_comm, div_self nonzero, one_div_div]
  rw [each first one, each second other]

/-- 76.9: over any trials, the larger of two readings sums to at least the larger of the two sums: the
largest reading of a trial overrates what either reading is worth on the whole. -/
theorem largest_overrates (reads : List (ℝ × ℝ)) :
    max (reads.map Prod.fst).sum (reads.map Prod.snd).sum ≤ (reads.map fun read => max read.1 read.2).sum :=
  max_le (List.sum_le_sum fun read _ => le_max_left read.1 read.2)
    (List.sum_le_sum fun read _ => le_max_right read.1 read.2)

/-- 76.10: where a concept gives its best hypothesis at least `sure`, no further concept can raise what
taking a hypothesis is paid by more than what `sure` lacks of one. -/
theorem sure_costs_little (chance better sure : ℝ) (held : sure ≤ chance) (most : better ≤ 1) :
    better - chance ≤ 1 - sure := by
  linarith

/-- 76.10: where a concept gives every hypothesis at most `low`, the chances of all of them together, which
bound the chance that any one of them is paid, come to at most `low` for each. -/
theorem settled_costs_little (chances : List ℝ) (low : ℝ) (each : ∀ chance ∈ chances, chance ≤ low) :
    chances.sum ≤ chances.length * low := by
  induction chances with
  | nil => simp
  | cons chance rest ih =>
    have here := each chance (List.mem_cons_self ..)
    have later := ih (fun x hx => each x (List.mem_cons_of_mem _ hx))
    simp only [List.sum_cons, List.length_cons, Nat.cast_add, Nat.cast_one]
    linarith

/-- 76.10: a dearer concept asked at a share of the steps costs, with the cheaper one asked at all of them,
no more than both asked at every step. -/
theorem unsure_costs_less (cheap dear share : ℝ) (costly : 0 ≤ dear) (part : share ≤ 1) :
    cheap + share * dear ≤ cheap + dear := by
  nlinarith

/-- 76.11: where going on shows nothing new, what it is worth less a share for each step is below what
putting out now is worth, however small the share, so the rule puts out. -/
theorem charged_tie_puts_out (chance lost : ℝ) (steps : ℕ) (some : 0 < chance) (charged : 0 < lost)
    (share : lost ≤ 1) (later : 1 ≤ steps) : (1 - lost) ^ steps * chance < chance := by
  have below : (1 - lost) ^ steps ≤ (1 - lost) ^ 1 :=
    pow_le_pow_of_le_one (by linarith) (by linarith) later
  nlinarith [pow_one (1 - lost)]

/-- 76.11: where the rule puts out now because what a later step is worth, less a share for each step to
it, does not pass what now is worth, it gives up at most that share of the later worth for each step. -/
theorem charge_costs_little (chance later lost : ℝ) (steps : ℕ) (worth : 0 ≤ later) (share : lost ≤ 1)
    (put : (1 - lost) ^ steps * later ≤ chance) : later - chance ≤ steps * lost * later := by
  have bernoulli := one_add_mul_le_pow (a := -lost) (by linarith) steps
  have kept : (1 - steps * lost) * later ≤ (1 - lost) ^ steps * later := by
    apply mul_le_mul_of_nonneg_right _ worth
    have same : (1 : ℝ) + -lost = 1 - lost := by ring
    rw [same] at bernoulli
    linarith
  linarith

/-- 76.12: where going on shows what is shown now, what it is worth after any number of steps is at most what
the last concept gives its best hypothesis, less the share once. -/
theorem still_worth_within (chance lost : ℝ) (steps : ℕ) (worth : 0 ≤ chance) (low : 0 ≤ lost) (share : lost ≤ 1)
    (later : 1 ≤ steps) : (1 - lost) ^ steps * chance ≤ (1 - lost) * chance := by
  have below : (1 - lost) ^ steps ≤ (1 - lost) ^ 1 :=
    pow_le_pow_of_le_one (by linarith) (by linarith) later
  rw [pow_one] at below
  exact mul_le_mul_of_nonneg_right below worth

/-- 76.12: with the chance of going on held to the smaller of what was read and what the last concept gives
its best hypothesis less the share, the risk of going on is above the risk of putting out, whatever was read. -/
theorem held_to_last_puts_out (read chance lost : ℝ) (some : 0 < chance) (charged : 0 < lost) :
    1 - chance < 1 - min read ((1 - lost) * chance) := by
  have held : min read ((1 - lost) * chance) ≤ (1 - lost) * chance := min_le_right _ _
  have less : (1 - lost) * chance < chance := by nlinarith [mul_pos charged some]
  linarith

/-- 76.13: whatever chance of answering a way of deciding gives a place, it has there at most the larger of
the answer's chance and what the asking is worth. -/
theorem taking_the_larger_is_best (out chance asking : ℝ) (low : 0 ≤ out) (high : out ≤ 1) :
    out * chance + (1 - out) * asking ≤ max chance asking := by
  have answered := mul_le_mul_of_nonneg_left (le_max_left chance asking) low
  have asked := mul_le_mul_of_nonneg_left (le_max_right chance asking) (by linarith : (0 : ℝ) ≤ 1 - out)
  linarith

/-- 76.13: an asking charged the larger share, leading to where no more is had, is worth no more. -/
theorem dearer_worth_no_more (had less lost more : ℝ) (worth : 0 ≤ less) (fewer : less ≤ had) (low : lost ≤ more)
    (share : more ≤ 1) : (1 - more) * less ≤ (1 - lost) * had := by
  have charged : (1 - more) * less ≤ (1 - lost) * less := mul_le_mul_of_nonneg_right (by linarith) worth
  have later : (1 - lost) * less ≤ (1 - lost) * had := mul_le_mul_of_nonneg_left fewer (by linarith)
  linarith

/-- 76.13: where no more is had at each later place, the mean over them, by weights that are not negative,
is no more. -/
theorem mean_had_no_more {ι : Type*} (s : Finset ι) (weight less had : ι → ℝ) (some : ∀ i ∈ s, 0 ≤ weight i)
    (fewer : ∀ i ∈ s, less i ≤ had i) : ∑ i ∈ s, weight i * less i ≤ ∑ i ∈ s, weight i * had i :=
  Finset.sum_le_sum fun i here => mul_le_mul_of_nonneg_left (fewer i here) (some i here)

/-- 76.13: so no more is had at a place under the dearer charge: the larger of the answer's chance and the
asking's worth is no larger. -/
theorem dearer_has_no_more (chance had less lost more : ℝ) (worth : 0 ≤ less) (fewer : less ≤ had)
    (low : lost ≤ more) (share : more ≤ 1) : max chance ((1 - more) * less) ≤ max chance ((1 - lost) * had) :=
  max_le_max le_rfl (dearer_worth_no_more had less lost more worth fewer low share)

/-- 76.13: where the rule answers under one charge, the asking being worth no more than the answer's chance,
it answers under every dearer charge. -/
theorem dearer_puts_out (chance had less lost more : ℝ) (worth : 0 ≤ less) (fewer : less ≤ had) (low : lost ≤ more)
    (share : more ≤ 1) (put : (1 - lost) * had ≤ chance) : (1 - more) * less ≤ chance :=
  le_trans (dearer_worth_no_more had less lost more worth fewer low share) put

/-- 76.14: an asking tried where the best chance does not fall in the mean gives up at most the charge
against answering at once. -/
theorem try_costs_charge (before after lost : ℝ) (rises : before ≤ after) (most : after ≤ 1) (low : 0 ≤ lost) :
    before - (1 - lost) * after ≤ lost := by
  nlinarith [mul_le_mul_of_nonneg_left most low]

/-- 76.14: so tries that each give up at most the charge give up, all together, at most the charge for
each. -/
theorem tries_cost_at_most {ι : Type*} (tries : Finset ι) (given : ι → ℝ) (lost : ℝ)
    (each : ∀ i ∈ tries, given i ≤ lost) : ∑ i ∈ tries, given i ≤ tries.card * lost := by
  have summed := Finset.sum_le_card_nsmul tries given lost each
  simpa [nsmul_eq_mul] using summed

/-- 76.15: with more askings open, each worth what it is worth, no less is had at a place. -/
theorem more_askings_have_no_less {ι : Type*} (fewer more : Finset ι) (worth : ι → ℝ) (chance : ℝ)
    (within : fewer ⊆ more) (some : fewer.Nonempty) :
    max chance (fewer.sup' some worth) ≤ max chance (more.sup' (some.mono within) worth) :=
  max_le_max le_rfl (Finset.sup'_mono worth within some)

/-- 76.15: one asking made dearer, the best of the others as it was or no better, leaves no more to be
had. -/
theorem one_dearer_has_no_more (chance other rest had less lost more : ℝ) (worth : 0 ≤ less) (fewer : less ≤ had)
    (low : lost ≤ more) (share : more ≤ 1) (others : other ≤ rest) :
    max chance (max other ((1 - more) * less)) ≤ max chance (max rest ((1 - lost) * had)) :=
  max_le_max le_rfl (max_le_max others (dearer_worth_no_more had less lost more worth fewer low share))

/-- 76.16: a chance that is the mean of what it becomes does not drift: over what an asking may give, the
changes weighted by their chances sum to nought. -/
theorem right_chance_does_not_drift {ι : Type*} (s : Finset ι) (weight after : ι → ℝ) (before : ℝ)
    (whole : ∑ i ∈ s, weight i = 1) (mean : ∑ i ∈ s, weight i * after i = before) :
    ∑ i ∈ s, weight i * (after i - before) = 0 := by
  simp only [mul_sub, Finset.sum_sub_distrib, ← Finset.sum_mul, whole, mean, one_mul, sub_self]

/-- 76.16: a stated chance that is a concave reading of the true one falls in the mean over an asking. -/
theorem too_sure_falls {ι : Type*} (s : Finset ι) (weight after : ι → ℝ) (met : Set ℝ) (read : ℝ → ℝ)
    (concave : ConcaveOn ℝ met read) (some : ∀ i ∈ s, 0 ≤ weight i) (whole : ∑ i ∈ s, weight i = 1)
    (within : ∀ i ∈ s, after i ∈ met) :
    ∑ i ∈ s, weight i * read (after i) ≤ read (∑ i ∈ s, weight i * after i) := by
  simpa [smul_eq_mul] using concave.le_map_sum some whole within

/-- 76.16: and one that is a convex reading rises. -/
theorem too_modest_rises {ι : Type*} (s : Finset ι) (weight after : ι → ℝ) (met : Set ℝ) (read : ℝ → ℝ)
    (convex : ConvexOn ℝ met read) (some : ∀ i ∈ s, 0 ≤ weight i) (whole : ∑ i ∈ s, weight i = 1)
    (within : ∀ i ∈ s, after i ∈ met) :
    read (∑ i ∈ s, weight i * after i) ≤ ∑ i ∈ s, weight i * read (after i) := by
  simpa [smul_eq_mul] using convex.map_sum_le some whole within

/-- 76.17: where asking the dear source is independent of which answer is right, the share right among
the standings asked at is the share right among all. -/
theorem asked_from_the_standing_names_fairly (right asked both : ℝ) (apart : both = right * asked)
    (some : 0 < asked) : both / asked = right := by
  rw [apart, mul_div_assoc, div_self (ne_of_gt some), mul_one]

/-- 76.17: two sources each right with the same chance, the dear source asked where they disagree: among
those trials each is right half the time, whatever that chance. -/
theorem counted_where_asked_is_a_half (p : ℝ) (low : 0 < p) (high : p < 1) :
    p * (1 - p) / (p * (1 - p) + (1 - p) * p) = 1 / 2 := by
  have within : p * (1 - p) ≠ 0 := ne_of_gt (mul_pos low (sub_pos.mpr high))
  have twice : p * (1 - p) + (1 - p) * p = 2 * (p * (1 - p)) := by ring
  rw [twice, div_eq_iff (mul_ne_zero two_ne_zero within)]
  ring

/-- 76.17: over the dear asking a chance goes to one where its answer was right and to nought where not,
so its mean change is the share right less the chance stated. -/
theorem named_change_is_the_gap (right stated : ℝ) :
    right * (1 - stated) + (1 - right) * (0 - stated) = right - stated := by
  ring

/-- 76.18: an asking weighed at its charge and a price is weighed at what it is paid less the price's
share of what is had after it. -/
theorem price_takes_its_share (charge price had : ℝ) :
    (1 - charge - price) * had = (1 - charge) * had - price * had := by
  ring

/-- 76.18: a way that is best once a price is put on what passes through an asking, with the price nought
unless the limit is met, is paid no less than any way that keeps the limit. -/
theorem kept_by_a_price_is_best_within (paid through other otherThrough limit price : ℝ)
    (best : other - price * otherThrough ≤ paid - price * through) (within : otherThrough ≤ limit)
    (worth : 0 ≤ price) (slack : price * (limit - through) = 0) : other ≤ paid := by
  nlinarith [mul_le_mul_of_nonneg_left within worth]

/-- 76.19: where what is had at a place is what its asking leads on to, less the charge, in the shares
with which it does lead on, what is had does not drift over the asking. -/
theorem right_promise_does_not_drift {ι : Type*} (s : Finset ι) (weight after : ι → ℝ) (had left : ℝ)
    (whole : ∑ i ∈ s, weight i = 1) (right : had = left * ∑ i ∈ s, weight i * after i) :
    ∑ i ∈ s, weight i * (left * after i - had) = 0 := by
  have apart : ∑ i ∈ s, weight i * (left * after i - had)
      = left * ∑ i ∈ s, weight i * after i - (∑ i ∈ s, weight i) * had := by
    rw [Finset.mul_sum, Finset.sum_mul, ← Finset.sum_sub_distrib]
    exact Finset.sum_congr rfl fun i _ => by ring
  rw [apart, whole, ← right]
  ring

/-- 76.19: the best of two askings as counted on each of two halves is, summed, no less than the best of
their sums: a record that takes the best of scattered counts promises at least what the best is worth. -/
theorem best_of_counts_flatters (a b c d : ℝ) : max (a + b) (c + d) ≤ max a c + max b d :=
  max_le (add_le_add (le_max_left a c) (le_max_left b d)) (add_le_add (le_max_right a c) (le_max_right b d))

/-- 76.20: a share right among the answers judged, pulled toward the chance stated with the weight of
some answers, lies between the two. -/
theorem pulled_share_lies_between (right judged weight stated : ℝ) (some : 0 < judged) (pull : 0 < weight) :
    min (right / judged) stated ≤ (right + weight * stated) / (judged + weight) ∧
      (right + weight * stated) / (judged + weight) ≤ max (right / judged) stated := by
  have whole : 0 < judged + weight := add_pos some pull
  have share : right = judged * (right / judged) := by field_simp
  constructor
  · rw [le_div_iff₀ whole]
    nlinarith [min_le_left (right / judged) stated, min_le_right (right / judged) stated]
  · rw [div_le_iff₀ whole]
    nlinarith [le_max_left (right / judged) stated, le_max_right (right / judged) stated]

/-- 76.21: an asking after which, with the chance `ended`, nothing is had is worth what is had where the
inquiry goes on, less that share of it. -/
theorem ended_share_is_a_charge (ended had : ℝ) : ended * 0 + (1 - ended) * had = (1 - ended) * had := by
  ring

/-- 76.21: such an asking is worth more than answering now exactly where the share of times it comes too
late is under the share of what it adds. -/
theorem thought_pays_where_gain_exceeds_hazard (ended now after : ℝ) (some : 0 < after) :
    now < (1 - ended) * after ↔ ended < (after - now) / after := by
  rw [lt_div_iff₀ some]
  constructor <;> intro h <;> nlinarith

/-- 76.22: a step that keeps the order, begun where one step does not lower, does not lower at the next
step either: what is had by asking at most once more is no less. -/
theorem asking_once_more_has_no_less {α : Type*} [Preorder α] (step : α → α) (keeps : Monotone step) (had : α)
    (rises : had ≤ step had) : step had ≤ step (step had) :=
  keeps rises

/-- 76.22: an asking that leads back to where the inquiry stood, uncharged, is worth what is had there; where
that is the answer's value the larger of the two is the answer's value, a tie. -/
theorem back_to_where_it_stood_ties (answer : ℝ) : max answer (1 * answer) = answer := by
  rw [one_mul, max_self]

end Thinking

end NCA
