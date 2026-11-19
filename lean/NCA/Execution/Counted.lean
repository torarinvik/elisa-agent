import Mathlib.Order.Basic

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

end NCA
