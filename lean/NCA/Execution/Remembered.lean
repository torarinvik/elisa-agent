import Mathlib.Algebra.BigOperators.Field
import Mathlib.Algebra.Order.BigOperators.Ring.Finset
import Mathlib.Data.Fintype.BigOperators
import Mathlib.Data.Finset.Powerset
import Mathlib.Data.Fintype.Pi
import Mathlib.Order.Interval.Finset.Nat
import Mathlib.Tactic
import NCA.Execution.Ahead
import NCA.Execution.Memory

/-! What a working memory has to hold, find and follow (chapter 73). -/
namespace NCA


section Holding

variable {ι X A : Type}

/-- A choice turns on a set of steps: two histories alike at those steps are chosen for alike. -/
def TurnsOn (best : (ι → X) → A) (D : Set ι) : Prop :=
  ∀ h h' : ι → X, (∀ i ∈ D, h i = h' i) → best h = best h'

/-- A choice that turns on some steps turns on any more. -/
theorem turnsOn_more (best : (ι → X) → A) (D K : Set ι) (sub : D ⊆ K) (turns : TurnsOn best D) :
    TurnsOn best K :=
  fun h h' alike => turns h h' (fun i inD => alike i (sub inD))

/-- 73.1: a learner that holds the steps a choice turns on, and any others, can choose from what it holds
exactly as one that holds the whole history. -/
theorem held_chooses_as_whole [Inhabited X] (best : (ι → X) → A) (D K : Set ι) (sub : D ⊆ K)
    (turns : TurnsOn best D) : ∃ choose : (K → X) → A, ∀ h : ι → X, choose (fun i : K => h i) = best h := by
  classical
  refine ⟨fun g => best (fun i => if inK : i ∈ K then g ⟨i, inK⟩ else default), fun h => ?_⟩
  apply turns
  intro i inD
  simp [sub inD]

/-- 73.2: a step that is not held and on which the best choice turns alone, at two histories alike
elsewhere, is chosen wrongly at one of them, whatever the learner does with what it holds. -/
theorem unheld_step_errs (best : (ι → X) → A) (K : Set ι) (choose : (K → X) → A) (i : ι) (out : i ∉ K)
    (h h' : ι → X) (alike : ∀ j, j ≠ i → h j = h' j) (differ : best h ≠ best h') :
    choose (fun j : K => h j) ≠ best h ∨ choose (fun j : K => h' j) ≠ best h' := by
  have same : (fun j : K => h j) = (fun j : K => h' j) := by
    funext j
    exact alike j (fun eq => out (eq ▸ j.2))
  by_cases first : choose (fun j : K => h j) = best h
  · right
    intro second
    rw [same] at first
    exact differ (first.symm.trans second)
  · exact Or.inl first

end Holding

section Open

/-- The steps open at step `n`: written by then, with a choice judged later that turns on them. -/
def openAt (needs : Nat → Set Nat) (n : Nat) : Set Nat := {i | i ≤ n ∧ ∃ t, n < t ∧ i ∈ needs t}

/-- 73.3: a step a later choice turns on is open at every step from its own until that choice. -/
theorem needed_is_open (needs : Nat → Set Nat) (n t i : Nat) (written : i ≤ n) (later : n < t)
    (needed : i ∈ needs t) : i ∈ openAt needs n :=
  ⟨written, t, later, needed⟩

/-- 73.3: a step open at one step is the step just written or was open the step before: a learner that
holds the open steps never has to bring back a step it let go. -/
theorem open_carried (needs : Nat → Set Nat) (n i : Nat) (still : i ∈ openAt needs (n + 1)) :
    i = n + 1 ∨ i ∈ openAt needs n := by
  obtain ⟨le, t, later, needed⟩ := still
  by_cases new : i = n + 1
  · exact Or.inl new
  · exact Or.inr ⟨by omega, t, by omega, needed⟩

/-- 73.3: what a choice turns on is the step it is made at or was open the step before. -/
theorem open_holds_needed (needs : Nat → Set Nat) (n i : Nat) (past : i ≤ n + 1) (needed : i ∈ needs (n + 1)) :
    i = n + 1 ∨ i ∈ openAt needs n := by
  by_cases new : i = n + 1
  · exact Or.inl new
  · exact Or.inr ⟨by omega, n + 1, by omega, needed⟩

/-- 73.3: so a learner that holds the step it is at and the steps open the step before can choose there as
one that holds the whole history. -/
theorem open_steps_serve {X A : Type} [Inhabited X] (best : (Nat → X) → A) (needs : Nat → Set Nat) (n : Nat)
    (turns : TurnsOn best (needs (n + 1))) (past : ∀ i ∈ needs (n + 1), i ≤ n + 1) :
    ∃ choose : ((insert (n + 1) (openAt needs n) : Set Nat) → X) → A,
      ∀ h : Nat → X, choose (fun i : (insert (n + 1) (openAt needs n) : Set Nat) => h i) = best h := by
  refine held_chooses_as_whole best (needs (n + 1)) (insert (n + 1) (openAt needs n)) (fun i needed => ?_) turns
  rcases open_holds_needed needs n i (past i needed) needed with new | was
  · exact Set.mem_insert_iff.mpr (Or.inl new)
  · exact Set.mem_insert_iff.mpr (Or.inr was)

/-- 73.3: a step that is not open is turned on by no later choice, and may be let go. -/
theorem closed_never_needed (needs : Nat → Set Nat) (n t i : Nat) (written : i ≤ n)
    (closed : i ∉ openAt needs n) (later : n < t) : i ∉ needs t :=
  fun needed => closed ⟨written, t, later, needed⟩

end Open

section Counting

variable {ι X A : Type}

/-- 73.4: a memory with fewer states than there are histories some later question tells apart answers
wrongly at some history and question, whatever it keeps and however it keeps it. -/
theorem short_memory_errs {H M Q : Type} [Fintype H] [Fintype M] (best : H → Q → A) (mem : H → M)
    (choose : M → Q → A) (few : Fintype.card M < Fintype.card H)
    (apart : ∀ h h', h ≠ h' → ∃ q, best h q ≠ best h' q) : ∃ h q, choose (mem h) q ≠ best h q := by
  obtain ⟨h, h', ne, same⟩ := Fintype.exists_ne_map_eq_of_card_lt mem few
  obtain ⟨q, differ⟩ := apart h h' ne
  by_cases first : choose (mem h) q = best h q
  · refine ⟨h', q, fun second => differ ?_⟩
    rw [← first, same, second]
  · exact ⟨h, q, first⟩

/-- 73.4: with `n` steps open, each of which the question may ask for, a memory of fewer than `n` slots
answers wrongly at some history and question, whatever it writes in its slots. -/
theorem fewer_slots_err [Fintype X] [DecidableEq X] {n s : Nat} (two : 1 < Fintype.card X) (fewer : s < n)
    (mem : (Fin n → X) → (Fin s → X)) (choose : (Fin s → X) → Fin n → X) :
    ∃ h i, choose (mem h) i ≠ h i := by
  apply short_memory_errs (fun (h : Fin n → X) i => h i) mem choose
  · simp only [Fintype.card_fun, Fintype.card_fin]
    exact Nat.pow_lt_pow_right two fewer
  · intro h h' ne
    by_contra none
    push Not at none
    exact ne (funext none)

/-- 73.4: and `n` slots answer rightly at every history and question. -/
theorem enough_slots_serve {n : Nat} :
    ∃ (mem : (Fin n → X) → (Fin n → X)) (choose : (Fin n → X) → Fin n → X), ∀ h i, choose (mem h) i = h i :=
  ⟨id, fun kept i => kept i, fun _ _ => rfl⟩

/-- 73.5: which step is kept is itself a state of the memory. With two steps, entries of two kinds and one
slot that holds truly the entry of the step it names, a learner free to choose the step answers rightly
for both steps at every history: the bound of 73.4 is on states, not on slots. -/
theorem which_kept_tells :
    ∃ (mem : (Fin 2 → Bool) → Fin 2 × Bool) (choose : Fin 2 × Bool → Fin 2 → Bool),
      ∀ h i, (mem h).2 = h (mem h).1 ∧ choose (mem h) i = h i := by
  refine ⟨fun h => if h 0 = h 1 then (0, h 0) else (1, h 1),
    fun kept i => if kept.1 = 0 then kept.2 else if i = 1 then kept.2 else !kept.2, fun h i => ?_⟩
  cases first : h 0 <;> cases second : h 1 <;> fin_cases i <;> simp [first, second]

end Counting

section Writing

variable {ι X A : Type}

/-- 73.6: a step whose entry, put otherwise, changes the choice is a step the choice turns on: the test
marks no step that does not matter. -/
theorem changed_is_needed [DecidableEq ι] (best : (ι → X) → A) (D : Set ι) (turns : TurnsOn best D)
    (h : ι → X) (i : ι) (x : X) (changed : best (Function.update h i x) ≠ best h) : i ∈ D := by
  by_contra out
  apply changed
  apply turns
  intro j inD
  have other : j ≠ i := fun eq => out (eq ▸ inD)
  simp [Function.update, other]

/-- 73.6: and the test can miss a step that matters: here putting the first entry otherwise changes
nothing at this history, though the choice does not turn on the second alone. -/
theorem unchanged_may_be_needed :
    ∃ (best : (Bool → Bool) → Bool) (h : Bool → Bool) (x : Bool),
      best (Function.update h false x) = best h ∧ ¬ TurnsOn best {true} := by
  refine ⟨fun h => h false && h true, fun _ => false, true, by simp [Function.update], ?_⟩
  intro turns
  have same := turns (fun _ => true) (fun b => b) (by intro i inD; simp at inD; simp [inD])
  simp at same

/-- 73.7: whatever rule keeps at most `r` of `n` steps without knowing which will matter, by chance or
not, some step is kept with chance at most `r / n`. `w` is the chance of each way the rule can go and
`kept` what it then holds. -/
theorem some_step_kept_rarely {Ω : Type} [Fintype Ω] {n r : Nat} (some : 0 < n) (w : Ω → ℚ)
    (nonneg : ∀ ω, 0 ≤ w ω) (total : ∑ ω, w ω = 1) (kept : Ω → Finset (Fin n))
    (slots : ∀ ω, (kept ω).card ≤ r) :
    ∃ j : Fin n, ∑ ω, (if j ∈ kept ω then w ω else 0) ≤ (r : ℚ) / n := by
  by_contra none
  push Not at none
  have hn : (0 : ℚ) < n := by exact_mod_cast some
  have : Nonempty (Fin n) := ⟨⟨0, some⟩⟩
  have big : ∑ _j : Fin n, (r : ℚ) / n < ∑ j : Fin n, ∑ ω, (if j ∈ kept ω then w ω else 0) :=
    Finset.sum_lt_sum_of_nonempty Finset.univ_nonempty (fun j _ => none j)
  have left : ∑ _j : Fin n, (r : ℚ) / n = r := by
    simp
    field_simp
  have swap : ∑ j : Fin n, ∑ ω, (if j ∈ kept ω then w ω else 0) = ∑ ω, w ω * (kept ω).card := by
    rw [Finset.sum_comm]
    refine Finset.sum_congr rfl (fun ω _ => ?_)
    simp [Finset.sum_ite_mem, mul_comm]
  have bound : ∑ ω, w ω * (kept ω).card ≤ ∑ ω, w ω * r :=
    Finset.sum_le_sum (fun ω _ => mul_le_mul_of_nonneg_left (by exact_mod_cast slots ω) (nonneg ω))
  rw [← Finset.sum_mul, total, one_mul] at bound
  linarith

/-- 73.8: and for every `m` there are `m` steps that such a rule holds all together with chance at most
`C(r, m) / C(n, m)`: a choice that turns on several steps is rarely served by keeping blind. -/
theorem some_steps_kept_rarely {Ω : Type} [Fintype Ω] {n r m : Nat} (fits : m ≤ n) (w : Ω → ℚ)
    (nonneg : ∀ ω, 0 ≤ w ω) (total : ∑ ω, w ω = 1) (kept : Ω → Finset (Fin n))
    (slots : ∀ ω, (kept ω).card ≤ r) :
    ∃ D : Finset (Fin n), D.card = m ∧
      ∑ ω, (if D ⊆ kept ω then w ω else 0) ≤ (r.choose m : ℚ) / n.choose m := by
  by_contra none
  push Not at none
  have count : (Finset.powersetCard m (Finset.univ : Finset (Fin n))).card = n.choose m := by
    rw [Finset.card_powersetCard, Finset.card_univ, Fintype.card_fin]
  have pos : (0 : ℚ) < n.choose m := by exact_mod_cast Nat.choose_pos fits
  have nonempty : (Finset.powersetCard m (Finset.univ : Finset (Fin n))).Nonempty :=
    Finset.card_pos.mp (by rw [count]; exact Nat.choose_pos fits)
  have big : ∑ _D ∈ Finset.powersetCard m (Finset.univ : Finset (Fin n)), (r.choose m : ℚ) / n.choose m
      < ∑ D ∈ Finset.powersetCard m (Finset.univ : Finset (Fin n)),
        ∑ ω, (if D ⊆ kept ω then w ω else 0) :=
    Finset.sum_lt_sum_of_nonempty nonempty (fun D inside => none D (Finset.mem_powersetCard.mp inside).2)
  have left : ∑ _D ∈ Finset.powersetCard m (Finset.univ : Finset (Fin n)), (r.choose m : ℚ) / n.choose m
      = r.choose m := by
    rw [Finset.sum_const, count, nsmul_eq_mul]
    field_simp
  have swap : ∑ D ∈ Finset.powersetCard m (Finset.univ : Finset (Fin n)),
      ∑ ω, (if D ⊆ kept ω then w ω else 0) = ∑ ω, w ω * ((kept ω).card.choose m : ℚ) := by
    rw [Finset.sum_comm]
    refine Finset.sum_congr rfl (fun ω _ => ?_)
    rw [← Finset.sum_filter]
    have same : (Finset.powersetCard m (Finset.univ : Finset (Fin n))).filter (fun D => D ⊆ kept ω)
        = Finset.powersetCard m (kept ω) := by
      ext D
      simp only [Finset.mem_filter, Finset.mem_powersetCard, Finset.subset_univ, true_and]
      tauto
    rw [same, Finset.sum_const, Finset.card_powersetCard, nsmul_eq_mul, mul_comm]
  have bound : ∑ ω, w ω * ((kept ω).card.choose m : ℚ) ≤ ∑ ω, w ω * (r.choose m : ℚ) :=
    Finset.sum_le_sum (fun ω _ => mul_le_mul_of_nonneg_left
      (by exact_mod_cast Nat.choose_le_choose m (slots ω)) (nonneg ω))
  rw [← Finset.sum_mul, total, one_mul] at bound
  linarith

/-- The chance that `m` given steps among the first `r` since a mark, which are kept surely, are all still
in slots `d` steps after step `r`, under the rule of 64.6: a later step `n` is kept with chance `r / n`, and
then takes the place of one of the `m` with chance `m / r`. -/
def allKeptAtRandom (r m : Nat) : Nat → ℚ
  | 0 => 1
  | d + 1 => allKeptAtRandom r m d * (1 - (r : ℚ) / (r + d + 1 : Nat) * ((m : ℚ) / r))

/-- 73.8: keeping at random holds such `m` steps all together, after `n` steps, with chance exactly
`C(r, m) / C(n, m)`: it meets the bound that no rule passes. -/
theorem allKeptAtRandom_even {r m : Nat} (slots : 0 < r) (fits : m ≤ r) (d : Nat) :
    allKeptAtRandom r m d = (r.choose m : ℚ) / (r + d).choose m := by
  induction d with
  | zero =>
    have pos : (0 : ℚ) < r.choose m := by exact_mod_cast Nat.choose_pos fits
    simp [allKeptAtRandom, pos.ne']
  | succ d ih =>
    have hr : (r : ℚ) ≠ 0 := by exact_mod_cast slots.ne'
    have low : m ≤ r + d := by omega
    have c_pos : (0 : ℚ) < ((r + d).choose m : ℚ) := by exact_mod_cast Nat.choose_pos low
    have c'_pos : (0 : ℚ) < ((r + d + 1).choose m : ℚ) := by
      exact_mod_cast Nat.choose_pos (show m ≤ r + d + 1 by omega)
    have next : ((r + d + 1 : Nat) : ℚ) ≠ 0 := by exact_mod_cast Nat.succ_ne_zero (r + d)
    have cast : (((r + d + 1 - m : Nat)) : ℚ) = ((r + d + 1 : Nat) : ℚ) - m := by
      rw [Nat.cast_sub (by omega)]
    have key : ((r + d).choose m : ℚ) * ((r + d + 1 : Nat) : ℚ)
        = ((r + d + 1).choose m : ℚ) * (((r + d + 1 : Nat) : ℚ) - m) := by
      rw [← cast]
      exact_mod_cast Nat.choose_mul_succ_eq (r + d) m
    have frac : 1 - (r : ℚ) / ((r + d + 1 : Nat) : ℚ) * ((m : ℚ) / r)
        = (((r + d + 1 : Nat) : ℚ) - m) / ((r + d + 1 : Nat) : ℚ) := by
      field_simp
    have same : ((r + d).choose m : ℚ)
        = ((r + d + 1).choose m : ℚ) * (((r + d + 1 : Nat) : ℚ) - m) / ((r + d + 1 : Nat) : ℚ) := by
      rw [eq_div_iff next]
      exact key
    rw [allKeptAtRandom, ih, show r + (d + 1) = r + d + 1 by omega, frac, div_mul_eq_mul_div,
      div_eq_div_iff c_pos.ne' c'_pos.ne']
    rw [same]
    ring

end Writing

section Finding

variable {ι X A K : Type}

/-- 73.9: a question can be answered by a match on keys that finds exactly the steps `D` if and only if
no step of `D` has the key of a step outside it. -/
theorem parted_iff_found (key : ι → K) (D : Set ι) :
    (∀ i ∈ D, ∀ j, j ∉ D → key i ≠ key j) ↔ ∃ m : K → Prop, ∀ i, m (key i) ↔ i ∈ D := by
  constructor
  · intro parted
    refine ⟨fun k => ∃ i ∈ D, key i = k, fun j => ⟨?_, fun inD => ⟨j, inD, rfl⟩⟩⟩
    rintro ⟨i, inD, eq⟩
    by_contra out
    exact parted i inD j out eq
  · rintro ⟨m, finds⟩ i inD j out eq
    exact out ((finds j).1 (eq ▸ (finds i).2 inD))

/-- 73.10: a learner that reads the steps a match on keys finds, where the match finds every step the
choice turns on, can choose as one that holds the whole history; the steps found beside them do no harm. -/
theorem found_chooses_as_whole [Inhabited X] (best : (ι → X) → A) (D : Set ι) (key : ι → K) (m : K → Prop)
    (turns : TurnsOn best D) (finds : ∀ i ∈ D, m (key i)) :
    ∃ choose : ({i | m (key i)} → X) → A, ∀ h : ι → X, choose (fun i : {i | m (key i)} => h i) = best h :=
  held_chooses_as_whole best D {i | m (key i)} finds turns

/-- 73.10: a step the match does not find, on which the best choice turns alone at two histories alike
elsewhere, is chosen wrongly at one of them. -/
theorem missed_key_errs (best : (ι → X) → A) (key : ι → K) (m : K → Prop)
    (choose : ({j | m (key j)} → X) → A) (i : ι) (missed : ¬ m (key i)) (h h' : ι → X)
    (alike : ∀ j, j ≠ i → h j = h' j) (differ : best h ≠ best h') :
    choose (fun j : {j | m (key j)} => h j) ≠ best h ∨ choose (fun j : {j | m (key j)} => h' j) ≠ best h' :=
  unheld_step_errs best {j | m (key j)} choose i missed h h' alike differ

/-- 73.11: keys written under one reading and keys the present reading would write find the same steps
exactly when the match says the same of both at every step; the keys need not be the same. -/
theorem stale_keys_found_alike (old new : ι → K) (m : K → Prop) :
    {i | m (old i)} = {i | m (new i)} ↔ ∀ i, m (old i) ↔ m (new i) :=
  Set.ext_iff

end Finding

section Plans

variable {S T A : Type}

/-- Where a run of presses leads is where its end leads from where its beginning led. -/
theorem led_append (step : S → A → S) (s : S) (before rest : List A) :
    led step s (before ++ rest) = led step (led step s before) rest := by
  induction before generalizing s with
  | nil => rfl
  | cons a more ih => exact ih (step s a)

/-- 73.12: a run of presses the foretelling says ends paid, from a foretold state that stands for the
world's for as many presses as the run has, ends paid in the world: it can be pressed without looking
ahead again. -/
theorem plan_paid (step : S → A → S) (fore : T → A → T) (paid : S → Prop) (told : T → Prop)
    (stands : Nat → S → T → Prop)
    (reads : ∀ k s t, stands k s t → (paid s ↔ told t))
    (keeps : ∀ k s t a, stands (k + 1) s t → stands k (step s a) (fore t a)) :
    ∀ (plan : List A) (s : S) (t : T), stands plan.length s t → told (led fore t plan) →
      paid (led step s plan) := by
  intro plan
  induction plan with
  | nil =>
    intro s t st yes
    exact (reads 0 s t st).2 yes
  | cons a rest ih =>
    intro s t st yes
    exact ih (step s a) (fore t a) (keeps rest.length s t a st) yes

/-- 73.12: the rest of a run is paid from any point along it at which the foretold state stands for the
state that came, whatever was the case before. -/
theorem plan_taken_up (step : S → A → S) (fore : T → A → T) (paid : S → Prop) (told : T → Prop)
    (stands : Nat → S → T → Prop)
    (reads : ∀ k s t, stands k s t → (paid s ↔ told t))
    (keeps : ∀ k s t a, stands (k + 1) s t → stands k (step s a) (fore t a))
    (before rest : List A) (s : S) (t : T)
    (st : stands rest.length (led step s before) (led fore t before))
    (yes : told (led fore t (before ++ rest))) : paid (led step s (before ++ rest)) := by
  rw [led_append] at yes ⊢
  exact plan_paid step fore paid told stands reads keeps rest _ _ st yes

/-- 73.13: the least number of presses the foretelling finds is the least in the world, so a run found at
the first depth is paid in as few presses as any. -/
theorem foretold_least (step : S → A → S) (fore : T → A → T) (paid : S → Prop) (told : T → Prop)
    (stands : Nat → S → T → Prop)
    (reads : ∀ k s t, stands k s t → (paid s ↔ told t))
    (keeps : ∀ k s t a, stands (k + 1) s t → stands k (step s a) (fore t a))
    (shorter : ∀ k s t, stands (k + 1) s t → stands k s t) (n : Nat) (s : S) (t : T)
    (st : stands n s t) (least : Least fore told n t) : Least step paid n s := by
  refine ⟨(foretold_way step fore paid told stands reads keeps n s t st).2 least.1, fun k way => ?_⟩
  by_contra less
  have fewer := stands_fewer stands shorter n k s t (by omega) st
  have lower := least.2 k ((foretold_way step fore paid told stands reads keeps k s t fewer).1 way)
  omega

/-- 73.13: after the first press of a shortest run, what is left of it is a shortest run from the state
reached: looking ahead again there finds nothing shorter than what is held. -/
theorem rest_of_plan_shortest (step : S → A → S) (paid : S → Prop) (n : Nat) (s : S) (a : A)
    (rest : List A) (here : Least step paid (n + 1) s) (length : rest.length = n)
    (ended : paid (led step (step s a) rest)) : Least step paid n (step s a) :=
  reached_is_least step paid n s a here (length ▸ trial_gives_way step paid rest (step s a) ended)

/-- 73.14: a run the foretelling said ends paid and that did not, from a state the foretold state was like,
holds a first press at which the foretelling erred: at every point of the run up to it the foretold state
was like the state that came, and after it it was not. `like` is any likeness under which payment is told
alike. -/
theorem unpaid_plan_erred (step : S → A → S) (fore : T → A → T) (paid : S → Prop) (told : T → Prop)
    (like : S → T → Prop) (reads : ∀ s t, like s t → (paid s ↔ told t)) :
    ∀ (plan : List A) (s : S) (t : T), like s t → told (led fore t plan) → ¬ paid (led step s plan) →
      ∃ before a after, plan = before ++ a :: after ∧
        (∀ early later, before = early ++ later → like (led step s early) (led fore t early)) ∧
        ¬ like (step (led step s before) a) (fore (led fore t before) a) := by
  intro plan
  induction plan with
  | nil =>
    intro s t was yes no
    exact absurd ((reads s t was).2 yes) no
  | cons a rest ih =>
    intro s t was yes no
    by_cases next : like (step s a) (fore t a)
    · obtain ⟨before, b, after, split, good, bad⟩ := ih (step s a) (fore t a) next yes no
      refine ⟨a :: before, b, after, by simp [split], ?_, bad⟩
      intro early later whole
      cases early with
      | nil => exact was
      | cons e more =>
        rw [List.cons_append] at whole
        injection whole with same tail
        subst same
        exact good more later tail
    · refine ⟨[], a, rest, rfl, ?_, next⟩
      intro early later whole
      cases early with
      | nil => exact was
      | cons e more => exact absurd whole (by simp)

/-- 73.15: with `b ≥ 2` presses and `b ^ d` states foretold to look `d` presses ahead, looking ahead
again at every state of a run of `n` presses foretells fewer than twice what the first look did. -/
theorem searching_again_under_twice (b n : Nat) (two : 2 ≤ b) :
    ∑ d ∈ Finset.range (n + 1), b ^ d < 2 * b ^ n := by
  rw [Finset.sum_range_succ]
  have below := Nat.geomSum_lt two (s := Finset.range n) (n := n) (fun k inside => Finset.mem_range.mp inside)
  omega

end Plans

section Cost

/-- 73.16: a channel of capacity `c` holds at most `c` entries at any step. -/
theorem held_count_le (c n : Nat) : ((Finset.range (n + 1)).filter (fun i => n < i + c)).card ≤ c := by
  have sub : (Finset.range (n + 1)).filter (fun i => n < i + c) ⊆ Finset.Ico (n + 1 - c) (n + 1) := by
    intro i inside
    simp only [Finset.mem_filter, Finset.mem_range] at inside
    simp only [Finset.mem_Ico]
    omega
  calc ((Finset.range (n + 1)).filter (fun i => n < i + c)).card
      ≤ (Finset.Ico (n + 1 - c) (n + 1)).card := Finset.card_le_card sub
    _ ≤ c := by
      simp only [Nat.card_Ico]
      omega

/-- 73.16: a learner that reads what its channel holds, its slots and what a match finds reads at most the
sum of the three counts at a step, whatever the ages of the entries. -/
theorem read_at_most {ι : Type} [DecidableEq ι] (near slots found : Finset ι) (r s m : Nat)
    (reach : near.card ≤ r) (pinned : slots.card ≤ s) (matched : found.card ≤ m) :
    (near ∪ slots ∪ found).card ≤ r + s + m := by
  have first := Finset.card_union_le (near ∪ slots) found
  have second := Finset.card_union_le near slots
  omega

/-- 73.17: where the best choice is the same at histories whose entries, at the steps it turns on, a form
`f` gives alike, a learner that holds only that form of those entries can choose as one that holds the whole
history. -/
theorem held_form_serves {ι X F A : Type} [Inhabited A] (best : (ι → X) → A) (D : Set ι) (f : X → F)
    (turns : ∀ h h' : ι → X, (∀ i ∈ D, f (h i) = f (h' i)) → best h = best h') :
    ∃ choose : (D → F) → A, ∀ h : ι → X, choose (fun i : D => f (h i)) = best h := by
  classical
  refine ⟨fun g => if some : ∃ h : ι → X, ∀ i : D, f (h i) = g i then best (Classical.choose some) else default,
    fun h => ?_⟩
  have some : ∃ h' : ι → X, ∀ i : D, f (h' i) = f (h i) := ⟨h, fun _ => rfl⟩
  dsimp only
  rw [dif_pos some]
  exact turns _ _ (fun i inD => Classical.choose_spec some ⟨i, inD⟩)

/-- 73.17: a form that gives alike, at every step, the entries of two histories with different best choices
is chosen wrongly from at one of them, though every step is held. -/
theorem merged_form_errs {ι X F A : Type} (best : (ι → X) → A) (f : X → F) (choose : (ι → F) → A)
    (h h' : ι → X) (merged : ∀ i, f (h i) = f (h' i)) (differ : best h ≠ best h') :
    choose (fun i => f (h i)) ≠ best h ∨ choose (fun i => f (h' i)) ≠ best h' := by
  have same : (fun i => f (h i)) = (fun i => f (h' i)) := funext merged
  by_cases first : choose (fun i => f (h i)) = best h
  · right
    intro second
    rw [same] at first
    exact differ (first.symm.trans second)
  · exact Or.inl first

end Cost

end NCA
