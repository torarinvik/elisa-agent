import Mathlib.Data.Nat.Find
import Mathlib.Data.Rat.Defs
import Mathlib.Order.Basic
import Mathlib.Tactic.Linarith

/-! Sub-goals counted from paid trials (chapter 67). -/
namespace NCA

variable {S A : Type}

/-- Payment can be had from a state in exactly this many presses. -/
def Way (step : S → A → S) (paid : S → Prop) : Nat → S → Prop
  | 0, s => paid s
  | n + 1, s => ∃ a, Way step paid n (step s a)

theorem way_succ (step : S → A → S) (paid : S → Prop) (n : Nat) (s : S) :
    Way step paid (n + 1) s ↔ ∃ a, Way step paid n (step s a) := Iff.rfl

/-- The least number of presses in which payment can be had from a state. -/
def Least (step : S → A → S) (paid : S → Prop) (n : Nat) (s : S) : Prop :=
  Way step paid n s ∧ ∀ k, Way step paid k s → n ≤ k

/-- Where a run of presses leads. -/
def led (step : S → A → S) : S → List A → S
  | s, [] => s
  | s, a :: rest => led step (step s a) rest

/-- 67.1: what a paid trial had left when it showed a state is a way from that state. -/
theorem trial_gives_way (step : S → A → S) (paid : S → Prop) (presses : List A) (s : S)
    (ended : paid (led step s presses)) : Way step paid presses.length s := by
  induction presses generalizing s with
  | nil => exact ended
  | cons a rest ih => exact (way_succ step paid rest.length s).2 ⟨a, ih (step s a) ended⟩

/-- 67.1: so the least number of presses from a state is at most what any paid trial had left there. -/
theorem least_le_trial (step : S → A → S) (paid : S → Prop) (presses : List A) (s : S) (n : Nat)
    (least : Least step paid n s) (ended : paid (led step s presses)) : n ≤ presses.length :=
  least.2 _ (trial_gives_way step paid presses s ended)

/-- 67.2: a press from a state `k + 1` from payment to one with a way of `k` leads to a state exactly
`k` from payment. -/
theorem reached_is_least (step : S → A → S) (paid : S → Prop) (k : Nat) (s : S) (a : A)
    (least : Least step paid (k + 1) s) (way : Way step paid k (step s a)) :
    Least step paid k (step s a) := by
  refine ⟨way, fun j shorter => ?_⟩
  have longer := least.2 (j + 1) ((way_succ step paid j s).2 ⟨a, shorter⟩)
  omega

/-- 67.3: where the least numbers are known at both states, a press begins a shortest way exactly when
the number falls by one over it. -/
theorem falls_iff_begins_shortest (step : S → A → S) (paid : S → Prop) (n m : Nat) (s : S) (a : A)
    (here : Least step paid (n + 1) s) (there : Least step paid m (step s a)) :
    m = n ↔ Way step paid n (step s a) := by
  constructor
  · intro same
    subst same
    exact there.1
  · intro way
    have upper := there.2 n way
    have lower := here.2 (m + 1) ((way_succ step paid m s).2 ⟨a, there.1⟩)
    omega

/-- 67.3: a count that is right at both states marks a press exactly when it begins a shortest way. -/
theorem marked_iff_begins_shortest (step : S → A → S) (paid : S → Prop) (count : S → Nat) (n : Nat)
    (s : S) (a : A) (here : Least step paid (n + 1) s) (right : count s = n + 1)
    (there : Least step paid (count (step s a)) (step s a)) :
    count (step s a) + 1 = count s ↔ Way step paid n (step s a) := by
  rw [right, ← falls_iff_begins_shortest step paid n (count (step s a)) s a here there]
  omega

/-- 67.4: where the least numbers are known at both states, a press leaves the shortest ways exactly when
the number does not fall over it. -/
theorem stays_iff_leaves_shortest (step : S → A → S) (paid : S → Prop) (n m : Nat) (s : S) (a : A)
    (here : Least step paid (n + 1) s) (there : Least step paid m (step s a)) :
    n + 1 ≤ m ↔ ¬ Way step paid n (step s a) := by
  rw [← falls_iff_begins_shortest step paid n m s a here there]
  have lower := here.2 (m + 1) ((way_succ step paid m s).2 ⟨a, there.1⟩)
  omega

/-- A press begins a shortest way from a state. -/
def Shortest (step : S → A → S) (paid : S → Prop) (s : S) (a : A) : Prop :=
  ∃ k, Least step paid (k + 1) s ∧ Way step paid k (step s a)

/-- A state with a way has a least number of presses to payment. -/
theorem least_exists (step : S → A → S) (paid : S → Prop) (k : Nat) (s : S) (way : Way step paid k s) :
    ∃ n, Least step paid n s := by
  classical
  have some : ∃ n, Way step paid n s := ⟨k, way⟩
  exact ⟨Nat.find some, Nat.find_spec some, fun _ shorter => Nat.find_min' some shorter⟩

/-- 67.5: a paid trial of more presses than the least from where it began holds a press that did not begin a
shortest way from where it was made. -/
theorem long_trial_holds_wasted (step : S → A → S) (paid : S → Prop) (presses : List A) :
    ∀ (s : S) (n : Nat), Least step paid n s → paid (led step s presses) → n < presses.length →
      ∃ before a after, presses = before ++ a :: after ∧ ¬ Shortest step paid (led step s before) a := by
  induction presses with
  | nil =>
    intro s n _ _ longer
    simp at longer
  | cons a rest ih =>
    intro s n least ended longer
    have way := trial_gives_way step paid rest (step s a) ended
    obtain ⟨m, there⟩ := least_exists step paid rest.length (step s a) way
    by_cases same : m + 1 = n
    · have shorter : m < rest.length := by
        simp at longer
        omega
      obtain ⟨before, b, after, split, wasted⟩ := ih (step s a) m there ended shorter
      exact ⟨a :: before, b, after, by simp [split], wasted⟩
    · refine ⟨[], a, rest, rfl, ?_⟩
      rintro ⟨k, here, nearer⟩
      have upper := least.2 _ here.1
      have lower := here.2 _ least.1
      have reached := there.2 k nearer
      have through := least.2 (m + 1) ((way_succ step paid m s).2 ⟨a, there.1⟩)
      omega

/-- 67.6: of two presses, shares that sum to at most one give one at most a half. -/
theorem shares_halve (p q : ℚ) (sum : p + q ≤ 1) : p ≤ 1 / 2 ∨ q ≤ 1 / 2 := by
  rcases le_or_gt p (1 / 2) with low | high
  · exact Or.inl low
  · exact Or.inr (by linarith)

end NCA
