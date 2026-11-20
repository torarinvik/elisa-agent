import NCA.Execution.Counted

/-! Payment within so many presses, each level taught from the one below (chapter 70). -/
namespace NCA

variable {S A : Type}

/-- Payment can be had from a state in at most this many presses. -/
def WithinPresses (step : S → A → S) (paid : S → Prop) (k : Nat) (s : S) : Prop :=
  ∃ j, j ≤ k ∧ Way step paid j s

/-- Level nought is payment itself. -/
theorem within_zero (step : S → A → S) (paid : S → Prop) (s : S) :
    WithinPresses step paid 0 s ↔ paid s := by
  constructor
  · rintro ⟨j, small, way⟩
    have none : j = 0 := by omega
    subst none
    exact way
  · intro pays
    exact ⟨0, le_refl 0, pays⟩

/-- A level holds what every lower level holds. -/
theorem within_mono (step : S → A → S) (paid : S → Prop) (k m : Nat) (s : S) (le : k ≤ m)
    (within : WithinPresses step paid k s) : WithinPresses step paid m s := by
  obtain ⟨j, small, way⟩ := within
  exact ⟨j, by omega, way⟩

/-- 70.1: a state is within `k + 1` presses of payment exactly when it is paid or some press leads to a
state within `k`. So what a level is to say of a press is what the level below says of the state after. -/
theorem within_succ (step : S → A → S) (paid : S → Prop) (k : Nat) (s : S) :
    WithinPresses step paid (k + 1) s ↔ paid s ∨ ∃ a, WithinPresses step paid k (step s a) := by
  constructor
  · rintro ⟨j, small, way⟩
    cases j with
    | zero => exact Or.inl way
    | succ i =>
      obtain ⟨a, after⟩ := (way_succ step paid i s).1 way
      exact Or.inr ⟨a, i, by omega, after⟩
  · rintro (pays | ⟨a, i, small, after⟩)
    · exact ⟨0, by omega, pays⟩
    · exact ⟨i + 1, by omega, (way_succ step paid i s).2 ⟨a, after⟩⟩

/-- 70.2: with the least number of presses known, a level answers exactly from that number up. -/
theorem within_iff_least (step : S → A → S) (paid : S → Prop) (n k : Nat) (s : S)
    (least : Least step paid n s) : WithinPresses step paid k s ↔ n ≤ k := by
  constructor
  · rintro ⟨j, small, way⟩
    have lower := least.2 j way
    omega
  · intro le
    exact ⟨n, le, least.1⟩

/-- A press whose state after is within `n`, made at a state `n + 1` from payment, leads to a state with a
way of exactly `n`. -/
theorem within_gives_way (step : S → A → S) (paid : S → Prop) (n : Nat) (s : S) (a : A)
    (here : Least step paid (n + 1) s) (yes : WithinPresses step paid n (step s a)) :
    Way step paid n (step s a) := by
  obtain ⟨j, small, way⟩ := yes
  have lower := here.2 (j + 1) ((way_succ step paid j s).2 ⟨a, way⟩)
  have same : j = n := by omega
  subst same
  exact way

/-- 70.3: at a state `n + 1` from payment, a press for which level `n` answers at the state after begins a
shortest way. -/
theorem lowest_level_begins_shortest (step : S → A → S) (paid : S → Prop) (n : Nat) (s : S) (a : A)
    (here : Least step paid (n + 1) s) (yes : WithinPresses step paid n (step s a)) :
    Shortest step paid s a :=
  ⟨n, here, within_gives_way step paid n s a here yes⟩

/-- 70.3: and no level below it answers for any press there. -/
theorem lower_levels_silent (step : S → A → S) (paid : S → Prop) (n j : Nat) (s : S) (b : A)
    (here : Least step paid (n + 1) s) (lower : j < n) : ¬ WithinPresses step paid j (step s b) := by
  rintro ⟨i, small, way⟩
  have least := here.2 (i + 1) ((way_succ step paid i s).2 ⟨b, way⟩)
  omega

/-- Where a learner stands after so many presses, each chosen at the state it is made at. -/
def followedTo (step : S → A → S) (choose : S → A) : Nat → S → S
  | 0, s => s
  | n + 1, s => followedTo step choose n (step s (choose s))

/-- 70.4: a learner that at every state presses a port for which the lowest answering level answers is
paid after exactly the least number of presses. -/
theorem followed_is_paid (step : S → A → S) (paid : S → Prop) (choose : S → A)
    (lowest : ∀ t m, Least step paid (m + 1) t → WithinPresses step paid m (step t (choose t))) :
    ∀ (n : Nat) (s : S), Least step paid n s → paid (followedTo step choose n s) := by
  intro n
  induction n with
  | zero =>
    intro s least
    exact least.1
  | succ k ih =>
    intro s least
    have way := within_gives_way step paid k s (choose s) least (lowest s k least)
    exact ih (step s (choose s)) (reached_is_least step paid k s (choose s) least way)

/-- 70.5: after a press that left the shortest ways, a learner that follows the levels from the state
reached is paid in the least number of presses from there; so a trial with that many presses left is
still paid. -/
theorem mended_is_paid (step : S → A → S) (paid : S → Prop) (choose : S → A)
    (lowest : ∀ t m, Least step paid (m + 1) t → WithinPresses step paid m (step t (choose t)))
    (s : S) (wrong : A) (m : Nat) (after : Least step paid m (step s wrong)) :
    paid (followedTo step choose m (step s wrong)) :=
  followed_is_paid step paid choose lowest m (step s wrong) after

/-- 70.6: a press whose state after is no further from payment than the state after any other press
begins a shortest way. So a choice that ranks presses by how soon their levels answer need not know how
far the state itself is from payment. -/
theorem nearest_after_begins_shortest (step : S → A → S) (paid : S → Prop) (n : Nat) (s : S) (a : A)
    (far : A → Nat) (here : Least step paid (n + 1) s)
    (there : ∀ b, Way step paid n (step s b) → Least step paid (far b) (step s b))
    (known : Least step paid (far a) (step s a)) (nearest : ∀ b, far a ≤ far b) :
    Shortest step paid s a := by
  obtain ⟨b, way⟩ := (way_succ step paid n s).1 here.1
  have near := (there b way).2 n way
  have lower := here.2 (far a + 1) ((way_succ step paid (far a) s).2 ⟨a, known.1⟩)
  have same : far a = n := by
    have := nearest b
    omega
  exact ⟨n, here, same ▸ known.1⟩

end NCA
