import Mathlib.Data.Finset.Card
import Mathlib.Data.Fintype.Card
import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Algebra.Order.Chebyshev
import Mathlib.Data.Fintype.BigOperators
import Mathlib.Data.Fintype.Sum
import Mathlib.Data.List.Basic
import Mathlib.Tactic.Ring

/-! Teaching by takeover: what one correction establishes about the machine being taught, and
how many corrections a learner can need. -/

namespace NCA

/-- Theorem 52.1: where a conjecture answers a history differently from the target, some cut of
that history has a suffix on which the target separates two histories the conjecture merged. -/
theorem takeover_exposes_merged_histories {A Q O : Type} (step : Q → A → Q) (start : Q) (out : Q → O)
    (f : List A → O) (access : Q → List A) (anchored : access start = [])
    (answers : ∀ q, out q = f (access q)) (w : List A) (wrong : out (w.foldl step start) ≠ f w) :
    ∃ u a v, w = u ++ a :: v ∧
      f (access (u.foldl step start) ++ a :: v) ≠ f (access (step (u.foldl step start) a) ++ v) := by
  have general : ∀ (w : List A) (q : Q), f (access q ++ w) ≠ out (w.foldl step q) →
      ∃ u a v, w = u ++ a :: v ∧
        f (access (u.foldl step q) ++ a :: v) ≠ f (access (step (u.foldl step q) a) ++ v) := by
    intro w
    induction w with
    | nil =>
      intro q differ
      exact absurd (by simpa using (answers q).symm) differ
    | cons a w ih =>
      intro q differ
      by_cases same : f (access q ++ a :: w) = f (access (step q a) ++ w)
      · obtain ⟨u, b, v, split, separated⟩ := ih (step q a) (by simpa [same] using differ)
        exact ⟨a :: u, b, v, by simp [split], by simpa using separated⟩
      · exact ⟨[], a, w, rfl, by simpa using same⟩
  exact general w start (by simpa [anchored] using wrong.symm)

/-- Theorem 52.2: a history that the table gave the row of `t`, and that a new suffix separates
from `t`, is separated from every history the table holds. -/
theorem takeover_adds_a_state {A O : Type} (f : List A → O) (held : Finset (List A))
    (suffixes : Set (List A)) (p t v : List A)
    (row : ∀ e ∈ suffixes, f (p ++ e) = f (t ++ e))
    (apart : ∀ s ∈ held, s ≠ t → ∃ e ∈ suffixes, f (s ++ e) ≠ f (t ++ e))
    (separated : f (p ++ v) ≠ f (t ++ v)) :
    ∀ s ∈ held, ∃ e, f (p ++ e) ≠ f (s ++ e) := by
  intro s inside
  by_cases same : s = t
  · exact ⟨v, by simpa [same] using separated⟩
  · obtain ⟨e, known, differ⟩ := apart s inside same
    exact ⟨e, by rw [row e known]; exact fun equal => differ equal.symm⟩

/-- Theorem 52.3: histories that the target separates pairwise number at most the states of any
machine computing it, so `k` takeovers that each add one need `k + 1` states. -/
theorem separated_histories_bound {A Q O : Type} [Fintype Q] (step : Q → A → Q) (start : Q)
    (out : Q → O) (f : List A → O) (computes : ∀ w, out (w.foldl step start) = f w)
    (held : Finset (List A))
    (apart : ∀ s ∈ held, ∀ t ∈ held, s ≠ t → ∃ e, f (s ++ e) ≠ f (t ++ e)) :
    held.card ≤ Fintype.card Q := by
  have injective : Set.InjOn (fun s : List A => s.foldl step start) held := by
    intro s inS t inT same
    by_contra differ
    obtain ⟨e, separated⟩ := apart s inS t inT differ
    apply separated
    rw [← computes, ← computes, List.foldl_append, List.foldl_append]
    exact congrArg (fun q => out (e.foldl step q)) same
  simpa using Finset.card_le_card_of_injOn (t := Finset.univ) _ (fun _ _ => Finset.mem_univ _) injective

/-- Theorem 52.4: a wrong answer shared by at least as many candidates as any other answer leaves
at most half the candidates agreeing with the truth. -/
theorem wrong_majority_halves {H X O : Type} [DecidableEq H] [DecidableEq O] (candidates : Finset H) (answer : H → X → O)
    (x : X) (guess truth : O) (wrong : guess ≠ truth)
    (majority : (candidates.filter fun h => answer h x = truth).card
      ≤ (candidates.filter fun h => answer h x = guess).card) :
    2 * (candidates.filter fun h => answer h x = truth).card ≤ candidates.card := by
  have disjoint : Disjoint (candidates.filter fun h => answer h x = truth)
      (candidates.filter fun h => answer h x = guess) := by
    rw [Finset.disjoint_filter]
    intro h _ isTruth isGuess
    exact wrong (isGuess.symm.trans isTruth)
  have inside : (candidates.filter fun h => answer h x = truth) ∪
      (candidates.filter fun h => answer h x = guess) ⊆ candidates :=
    Finset.union_subset (Finset.filter_subset _ _) (Finset.filter_subset _ _)
  have total := Finset.card_le_card inside
  rw [Finset.card_union_of_disjoint disjoint] at total
  omega

/-- Theorem 52.5: if each of `k` corrections at least halves the candidates and one remains,
then `2 ^ k` is at most the number of candidates at the start. -/
theorem halving_corrections_bounded {H : Type} (remaining : ℕ → Finset H) (k : ℕ)
    (halves : ∀ i < k, 2 * (remaining (i + 1)).card ≤ (remaining i).card)
    (survivor : (remaining k).Nonempty) : 2 ^ k ≤ (remaining 0).card := by
  have scaled : ∀ i ≤ k, 2 ^ i * (remaining i).card ≤ (remaining 0).card := by
    intro i
    induction i with
    | zero => intro _; simp
    | succ i ih =>
      intro within
      have earlier := ih (by omega)
      have step := halves i (by omega)
      calc 2 ^ (i + 1) * (remaining (i + 1)).card = 2 ^ i * (2 * (remaining (i + 1)).card) := by ring
        _ ≤ 2 ^ i * (remaining i).card := Nat.mul_le_mul_left _ step
        _ ≤ (remaining 0).card := earlier
  have positive : 1 ≤ (remaining k).card := Finset.card_pos.mpr survivor
  calc 2 ^ k = 2 ^ k * 1 := by ring
    _ ≤ 2 ^ k * (remaining k).card := Nat.mul_le_mul_left _ positive
    _ ≤ (remaining 0).card := scaled k le_rfl

/-- Theorem 52.6: the machines on given states whose actions are fixed actions or one of the
helpers number `n ^ (n * |A|) * (|O| + m) ^ n`. -/
theorem candidates_with_helpers (Q A O ι : Type) [Fintype Q] [DecidableEq Q] [Fintype A] [DecidableEq A]
    [Fintype O] [Fintype ι] :
    Fintype.card ((Q × A → Q) × (Q → O ⊕ ι))
      = Fintype.card Q ^ (Fintype.card Q * Fintype.card A)
        * (Fintype.card O + Fintype.card ι) ^ Fintype.card Q := by
  rw [Fintype.card_prod, Fintype.card_fun, Fintype.card_fun, Fintype.card_prod, Fintype.card_sum]

/-- Theorem 52.7: if the teacher takes over at most `unjudged` steps after the first wrong
action, every step more than `unjudged` before the takeover precedes that action. -/
theorem judged_actions_are_right (wrong delay taken unjudged step : ℕ) (takeover : taken = wrong + delay)
    (bounded : delay ≤ unjudged) (judged : step + unjudged < taken) : step < wrong := by
  omega

/-- Theorem 52.8: where the good actions depend on the state alone, an action accepted after one
history and rejected after another shows that the two histories end in different states. -/
theorem conflicting_judgements_separate {A Q O : Type} (step : Q → A → Q) (start : Q) (good : Q → Set O)
    (s t : List A) (a : O) (accepted : a ∈ good (s.foldl step start))
    (rejected : a ∉ good (t.foldl step start)) : s.foldl step start ≠ t.foldl step start := by
  intro same
  exact rejected (same ▸ accepted)

/-- Theorem 52.9: if every candidate holds some action good, one action is held good by at least
a share `1 / |O|` of the candidates. -/
theorem popular_action_share {H O : Type} [Fintype O] [DecidableEq O] [Nonempty O] (candidates : Finset H)
    (good : H → Finset O) (some : ∀ h ∈ candidates, (good h).Nonempty) :
    ∃ a, candidates.card ≤ Fintype.card O * (candidates.filter fun h => a ∈ good h).card := by
  have counted : candidates.card ≤ ∑ a : O, (candidates.filter fun h => a ∈ good h).card := by
    have swap : ∑ a : O, (candidates.filter fun h => a ∈ good h).card = ∑ h ∈ candidates, (good h).card := by
      simp only [Finset.card_filter]
      rw [Finset.sum_comm]
      refine Finset.sum_congr rfl fun h _ => ?_
      simp
    rw [swap]
    calc candidates.card = ∑ _h ∈ candidates, 1 := by simp
      _ ≤ ∑ h ∈ candidates, (good h).card :=
        Finset.sum_le_sum fun h inside => Finset.card_pos.mpr (some h inside)
  by_contra none
  have none' : ∀ a : O, Fintype.card O * (candidates.filter fun h => a ∈ good h).card < candidates.card :=
    fun a => not_le.mp fun enough => none ⟨a, enough⟩
  have below : ∑ a : O, Fintype.card O * (candidates.filter fun h => a ∈ good h).card
      < ∑ _a : O, candidates.card :=
    Finset.sum_lt_sum_of_nonempty Finset.univ_nonempty fun a _ => none' a
  have total : ∑ a : O, Fintype.card O * (candidates.filter fun h => a ∈ good h).card
      = Fintype.card O * ∑ a : O, (candidates.filter fun h => a ∈ good h).card :=
    (Finset.mul_sum _ _ _).symm
  rw [total, Finset.sum_const, Finset.card_univ] at below
  have plain : Fintype.card O • candidates.card = Fintype.card O * candidates.card := rfl
  rw [plain] at below
  exact absurd (Nat.lt_of_mul_lt_mul_left below) (not_lt.mpr counted)

/-- Theorem 52.10: if each of `k` corrections leaves at most a share `d / (d + 1)` of the
candidates and one remains, then `(d + 1) ^ k ≤ d ^ k * |candidates|`. -/
theorem share_corrections_bounded {H : Type} (remaining : ℕ → Finset H) (d k : ℕ)
    (shrinks : ∀ i < k, (d + 1) * (remaining (i + 1)).card ≤ d * (remaining i).card)
    (survivor : (remaining k).Nonempty) : (d + 1) ^ k ≤ d ^ k * (remaining 0).card := by
  have scaled : ∀ i ≤ k, (d + 1) ^ i * (remaining i).card ≤ d ^ i * (remaining 0).card := by
    intro i
    induction i with
    | zero => intro _; simp
    | succ i ih =>
      intro within
      have earlier := ih (by omega)
      have step := shrinks i (by omega)
      calc (d + 1) ^ (i + 1) * (remaining (i + 1)).card
          = (d + 1) ^ i * ((d + 1) * (remaining (i + 1)).card) := by ring
        _ ≤ (d + 1) ^ i * (d * (remaining i).card) := Nat.mul_le_mul_left _ step
        _ = d * ((d + 1) ^ i * (remaining i).card) := by ring
        _ ≤ d * (d ^ i * (remaining 0).card) := Nat.mul_le_mul_left _ earlier
        _ = d ^ (i + 1) * (remaining 0).card := by ring
  have positive : 1 ≤ (remaining k).card := Finset.card_pos.mpr survivor
  calc (d + 1) ^ k = (d + 1) ^ k * 1 := by ring
    _ ≤ (d + 1) ^ k * (remaining k).card := Nat.mul_le_mul_left _ positive
    _ ≤ d ^ k * (remaining 0).card := scaled k le_rfl

/-- Theorem 52.11: sort the candidates into `K` classes. Summed over the candidates, the number
sharing a candidate's class is at least `|candidates|² / K`: a candidate drawn at random shares
its class with at least a share `1 / K` of them on average. -/
theorem random_candidate_agreement {H κ : Type} [Fintype κ] [DecidableEq κ] (candidates : Finset H)
    (cls : H → κ) :
    candidates.card ^ 2
      ≤ Fintype.card κ * ∑ c ∈ candidates, (candidates.filter fun h => cls h = cls c).card := by
  have fibers : candidates.card = ∑ k : κ, (candidates.filter fun h => cls h = k).card :=
    Finset.card_eq_sum_card_fiberwise fun _ _ => Finset.mem_univ _
  have squares : ∑ c ∈ candidates, (candidates.filter fun h => cls h = cls c).card
      = ∑ k : κ, (candidates.filter fun h => cls h = k).card ^ 2 := by
    rw [← Finset.sum_fiberwise candidates cls]
    refine Finset.sum_congr rfl fun k _ => ?_
    rw [Finset.sum_congr rfl (g := fun _ => (candidates.filter fun h => cls h = k).card)]
    · rw [Finset.sum_const, smul_eq_mul, sq]
    · intro c inside
      rw [(Finset.mem_filter.mp inside).2]
  rw [squares, fibers]
  simpa [Finset.card_univ] using
    sq_sum_le_card_mul_sum_sq (s := (Finset.univ : Finset κ))
      (f := fun k => (candidates.filter fun h => cls h = k).card)

/-- **Theorem 52.12 (what belief takes).** Marks against an action are believed on a transition while
they exceed the share `num / den` of its `b` marks and `g` good judgements there. They then outweigh
the good judgements in the proportion the share fixes: with a quarter, `g < 3 b`. -/
theorem believed_mark_outweighs (num den b g : ℕ) (believed : num * (b + g) < den * b) :
    num * g < (den - num) * b := by
  rw [Nat.sub_mul]
  rw [Nat.mul_add, Nat.add_comm] at believed
  exact Nat.lt_sub_of_add_lt believed

/-- **Theorem 52.13 (misfiled marks are bounded by changes).** The steps that contain a change of observation are the
image of the changes under the step each falls in, so there are no more of them than changes. -/
theorem steps_with_change_le_changes {ι κ : Type*} [DecidableEq κ] (changes : Finset ι) (step : ι → κ) :
    (changes.image step).card ≤ changes.card :=
  Finset.card_image_le

/-- What a choice gives after a history: a fixed action, or the answer of the part it names. -/
def choiceAnswer {H A ι : Type*} (parts : ι → H → A) (h : H) : A ⊕ ι → A
  | Sum.inl a => a
  | Sum.inr i => parts i h

/-- **Proposition 52.16 (a certificate does not travel).** Whatever a part answers, and on whatever histories it
was found right, a history outside them admits a target that agrees with the part on all of those and differs
from it there. -/
theorem certificate_does_not_travel {H A : Type*} [DecidableEq H] (part : H → A) (drawn : Set H) (h : H)
    (outside : h ∉ drawn) (a : A) (differs : a ≠ part h) :
    ∃ target : H → A, (∀ x ∈ drawn, part x = target x) ∧ part h ≠ target h := by
  refine ⟨Function.update part h a, fun x inside => ?_, ?_⟩
  · have other : x ≠ h := fun same => outside (by rw [← same]; exact inside)
    rw [Function.update_of_ne other]
  · rw [Function.update_self]
    exact fun same => differs same.symm

/-- **Proposition 52.17 (an erring part is told apart).** Let a machine give the right action after every history.
A history at which a part errs is in another state than any history whose state holds that part as its choice. -/
theorem erring_part_is_not_the_choice {H A ι S : Type*} (parts : ι → H → A) (right : H → A) (state : H → S)
    (choice : S → A ⊕ ι) (consistent : ∀ h, choiceAnswer parts h (choice (state h)) = right h) (i : ι) (h h' : H)
    (errs : parts i h ≠ right h) (held : choice (state h') = Sum.inr i) : state h ≠ state h' := by
  intro same
  have given := consistent h
  rw [same, held] at given
  exact errs given

/-- **Proposition 52.18 (amended parts keep the rule).** Let the right action be given by a rule that chooses among
target parts. If each part agrees with its target wherever the rule chooses it, the rule gives the right action
with the parts as they are: no machine larger than the rule is needed. -/
theorem amended_parts_keep_the_rule {H A ι S : Type*} (parts targets : ι → H → A) (state : H → S)
    (choice : S → A ⊕ ι)
    (amended : ∀ h i, choice (state h) = Sum.inr i → parts i h = targets i h) (h : H) :
    choiceAnswer parts h (choice (state h)) = choiceAnswer targets h (choice (state h)) := by
  cases held : choice (state h) with
  | inl a => rfl
  | inr i => exact amended h i held

/-- **Proposition 52.19 (practice reaches every history).** Of the sequences of `l + r` observations, those that
begin with a given `l` number `|O| ^ r`: where observations are drawn evenly, every history of `l` observations
begins an episode with the same chance `|O| ^ l` to one. -/
theorem sequences_beginning_alike {O : Type} [Fintype O] [DecidableEq O] (l r : ℕ) (start : Fin l → O) :
    (Finset.univ.filter fun word : Fin (l + r) → O => ∀ i : Fin l, word (Fin.castAdd r i) = start i).card
      = Fintype.card O ^ r := by
  have count : (Finset.univ.filter fun word : Fin (l + r) → O =>
      ∀ i : Fin l, word (Fin.castAdd r i) = start i).card = (Finset.univ : Finset (Fin r → O)).card := by
    refine Finset.card_nbij' (fun word j => word (Fin.natAdd l j)) (fun rest => Fin.append start rest) ?_ ?_ ?_ ?_
    · intro word _
      exact Finset.mem_coe.mpr (Finset.mem_univ _)
    · intro rest _
      simp [Fin.append_left]
    · intro word inside
      have begins := (Finset.mem_filter.mp (Finset.mem_coe.mp inside)).2
      funext x
      refine Fin.addCases (fun i => ?_) (fun j => ?_) x
      · simp [Fin.append_left, begins i]
      · simp [Fin.append_right]
    · intro rest _
      funext j
      simp [Fin.append_right]
  rw [count, Finset.card_univ, Fintype.card_fun, Fintype.card_fin]

end NCA
