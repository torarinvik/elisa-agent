import Mathlib.Algebra.Group.Basic
import Mathlib.Data.Fintype.Card
import Mathlib.Data.Fintype.Sum
import Mathlib.Data.List.Basic
import Mathlib.Tactic.Abel

/-! Machines that read a sequence and answer from their final state: what a table of
answers to chosen sequences says about the states any such machine needs. -/

namespace NCA

/-- Theorem 51.1: prefixes whose answers differ after a common suffix end in different states. -/
theorem distinguished_prefixes_need_states {A Q O : Type} (step : Q → A → Q) (start : Q) (out : Q → O)
    (s t e : List A)
    (differ : out ((s ++ e).foldl step start) ≠ out ((t ++ e).foldl step start)) :
    s.foldl step start ≠ t.foldl step start := by
  intro same
  apply differ
  rw [List.foldl_append, List.foldl_append, same]

/-- Theorem 51.2: a machine giving `n` sequences pairwise distinct answers has at least `n` states. -/
theorem distinct_answers_need_states {A Q O : Type} [Fintype Q] (step : Q → A → Q) (start : Q)
    (out : Q → O) {n : ℕ} (word : Fin n → List A)
    (distinct : Function.Injective fun i => out ((word i).foldl step start)) :
    n ≤ Fintype.card Q := by
  have states : Function.Injective fun i => (word i).foldl step start :=
    fun i j same => distinct (congrArg out same)
  simpa using Fintype.card_le_of_injective _ states

/-- Theorem 51.3: adding one-step differences along a sequence rebuilds the answer. -/
theorem differences_rebuild {A G : Type} [AddCommGroup G] (f : List A → G) (p w : List A) :
    w.foldl (fun (s : List A × G) a => (s.1 ++ [a], s.2 + (f (s.1 ++ [a]) - f s.1))) (p, f p)
      = (p ++ w, f (p ++ w)) := by
  induction w generalizing p with
  | nil => simp
  | cons a w ih =>
    have step : f p + (f (p ++ [a]) - f p) = f (p ++ [a]) := by abel
    simp only [List.foldl_cons, step]
    rw [ih (p ++ [a])]
    simp

/-- Theorem 51.4: where transitions add to a register, the change made by one more symbol is
fixed by the control state reached and that symbol. -/
theorem counter_differences_follow_control {A Q G : Type} [AddCommGroup G] (step : Q → A → Q)
    (gain : Q → A → G) (start : Q) (base : G) (w : List A) (a : A) :
    ((w ++ [a]).foldl (fun (s : Q × G) x => (step s.1 x, s.2 + gain s.1 x)) (start, base)).2
      - (w.foldl (fun (s : Q × G) x => (step s.1 x, s.2 + gain s.1 x)) (start, base)).2
      = gain (w.foldl (fun (s : Q × G) x => (step s.1 x, s.2 + gain s.1 x)) (start, base)).1 a := by
  simp [List.foldl_append]

/-- The answers a state gives to the sequences of at most `k` symbols, and nothing for the longer ones. -/
noncomputable def answersTo {A Q O : Type} (step : Q → A → Q) (out : Q → O) (k : ℕ) (q : Q) :
    List A → Option O :=
  fun w => if w.length ≤ k then some (out (w.foldl step q)) else none

private theorem answersTo_succ {A Q O : Type} (step : Q → A → Q) (out : Q → O) (k : ℕ) (q q' : Q) :
    answersTo step out (k + 1) q = answersTo step out (k + 1) q' ↔
      out q = out q' ∧ ∀ a, answersTo step out k (step q a) = answersTo step out k (step q' a) := by
  constructor
  · intro same
    refine ⟨by simpa [answersTo] using congrFun same [], fun a => funext fun w => ?_⟩
    have longer := congrFun same (a :: w)
    by_cases short : w.length ≤ k
    · simpa [answersTo, short] using longer
    · simp [answersTo, short]
  · rintro ⟨here, after⟩
    funext w
    cases w with
    | nil => simp [answersTo, here]
    | cons a w =>
      have shorter := congrFun (after a) w
      by_cases short : w.length ≤ k
      · simpa [answersTo, short] using shorter
      · simp [answersTo, short]

private theorem answersTo_settled {A Q O : Type} (step : Q → A → Q) (out : Q → O) (k : ℕ)
    (settled : ∀ q q', answersTo step out k q = answersTo step out k q' →
      answersTo step out (k + 1) q = answersTo step out (k + 1) q') (j : ℕ) :
    ∀ q q', answersTo step out k q = answersTo step out k q' →
      answersTo step out (k + j) q = answersTo step out (k + j) q' := by
  induction j with
  | zero => exact fun _ _ same => same
  | succ j further =>
    intro q q' same
    obtain ⟨here, after⟩ := (answersTo_succ step out k q q').mp (settled q q' same)
    exact (answersTo_succ step out (k + j) q q').mpr ⟨here, fun a => further _ _ (after a)⟩

open Classical in
/-- **Theorem 51.5 (short sequences settle it).** Two states of a machine of `N` states that answer alike every
sequence of at most `N - 1` symbols answer alike every sequence. -/
theorem answers_to_depth_settle {A Q O : Type} [Fintype Q] (step : Q → A → Q) (out : Q → O) (q q' : Q)
    (same : ∀ w : List A, w.length ≤ Fintype.card Q - 1 → out (w.foldl step q) = out (w.foldl step q'))
    (w : List A) : out (w.foldl step q) = out (w.foldl step q') := by
  let classes : ℕ → ℕ := fun k => (Finset.univ.image (answersTo step out k)).card
  let cut : ℕ → (List A → Option O) → List A → Option O := fun k f w => if w.length ≤ k then f w else none
  have cuts : ∀ k (s : Q), cut k (answersTo step out (k + 1) s) = answersTo step out k s := by
    intro k s
    funext v
    by_cases short : v.length ≤ k
    · simp [cut, answersTo, short, Nat.le_succ_of_le short]
    · simp [cut, answersTo, short]
  have image : ∀ k, Finset.univ.image (answersTo step out k)
      = (Finset.univ.image (answersTo step out (k + 1))).image (cut k) := by
    intro k
    rw [Finset.image_image]
    exact Finset.image_congr fun s _ => (cuts k s).symm
  have grows : ∀ k, classes k ≤ classes (k + 1) := by
    intro k
    show (Finset.univ.image (answersTo step out k)).card ≤ _
    rw [image k]
    exact Finset.card_image_le
  have stops : ∃ k, k < Fintype.card Q ∧ classes k = classes (k + 1) := by
    by_contra never
    have strict : ∀ k, k ≤ Fintype.card Q → k + 1 ≤ classes k := by
      intro k
      induction k with
      | zero =>
        intro _
        exact Finset.card_pos.mpr ⟨_, Finset.mem_image_of_mem _ (Finset.mem_univ q)⟩
      | succ k before =>
        intro within
        have less : classes k < classes (k + 1) :=
          lt_of_le_of_ne (grows k) fun equal => never ⟨k, within, equal⟩
        have earlier := before (Nat.le_of_succ_le within)
        omega
    have most : classes (Fintype.card Q) ≤ Fintype.card Q := by
      show (Finset.univ.image (answersTo step out (Fintype.card Q))).card ≤ _
      exact Finset.card_image_le.trans (le_of_eq Finset.card_univ)
    have least := strict (Fintype.card Q) le_rfl
    omega
  obtain ⟨k, within, equal⟩ := stops
  have injective : Set.InjOn (cut k) (Finset.univ.image (answersTo step out (k + 1)) : Finset _) := by
    apply Finset.card_image_iff.mp
    rw [← image k]
    exact equal
  have settled : ∀ s s', answersTo step out k s = answersTo step out k s' →
      answersTo step out (k + 1) s = answersTo step out (k + 1) s' := by
    intro s s' alike
    apply injective (Finset.mem_coe.mpr (Finset.mem_image_of_mem _ (Finset.mem_univ s)))
      (Finset.mem_coe.mpr (Finset.mem_image_of_mem _ (Finset.mem_univ s')))
    rw [cuts k s, cuts k s', alike]
  have first : answersTo step out k q = answersTo step out k q' := by
    funext v
    by_cases short : v.length ≤ k
    · simp [answersTo, short, same v (by omega)]
    · simp [answersTo, short]
  have all := congrFun (answersTo_settled step out k settled w.length q q' first) w
  simpa [answersTo] using all

/-- **Theorem 51.6 (two machines agree if they agree on short sequences).** Machines of `n` and `m` states that
give the same answer to every sequence of at most `n + m - 1` symbols give the same answer to every sequence. -/
theorem machines_agreeing_to_depth_agree {A Q₁ Q₂ O : Type} [Fintype Q₁] [Fintype Q₂]
    (step₁ : Q₁ → A → Q₁) (step₂ : Q₂ → A → Q₂) (out₁ : Q₁ → O) (out₂ : Q₂ → O) (start₁ : Q₁) (start₂ : Q₂)
    (same : ∀ w : List A, w.length ≤ Fintype.card Q₁ + Fintype.card Q₂ - 1 →
      out₁ (w.foldl step₁ start₁) = out₂ (w.foldl step₂ start₂))
    (w : List A) : out₁ (w.foldl step₁ start₁) = out₂ (w.foldl step₂ start₂) := by
  let step : Q₁ ⊕ Q₂ → A → Q₁ ⊕ Q₂ := fun s a => Sum.map (fun x => step₁ x a) (fun y => step₂ y a) s
  have left : ∀ (v : List A) (s : Q₁), v.foldl step (Sum.inl s) = Sum.inl (v.foldl step₁ s) := by
    intro v
    induction v with
    | nil => exact fun _ => rfl
    | cons a v after => exact fun s => after (step₁ s a)
  have right : ∀ (v : List A) (s : Q₂), v.foldl step (Sum.inr s) = Sum.inr (v.foldl step₂ s) := by
    intro v
    induction v with
    | nil => exact fun _ => rfl
    | cons a v after => exact fun s => after (step₂ s a)
  have joined := answers_to_depth_settle step (Sum.elim out₁ out₂) (Sum.inl start₁) (Sum.inr start₂)
    (fun v short => by
      rw [left, right]
      exact same v (by simpa [Fintype.card_sum] using short)) w
  rw [left, right] at joined
  exact joined

end NCA
