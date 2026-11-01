import NCA.Planner

/-!
# Routing stability

Installing a module should not silently change how previously solved tasks
are solved (the add-and-freeze protocol). The plain planner does not have this
property; the generation-layered planner does, while remaining sound and
complete.
-/

namespace NCA

section Counterexample

/-- Types are naturals; odd numbers `2t + 1` encode `seq t`. -/
private instance : SeqTypes Nat where
  seq t := 2 * t + 1
  elem? u := if u % 2 = 1 then some (u / 2) else none
  elem?_eq_some := by
    intro u t
    split <;> simp <;> omega

private def need1 : Contract Nat := ⟨0, [2], 0⟩
private def from2 : Contract Nat := ⟨1, [4], 0⟩
private def make1 : Contract Nat := ⟨2, [4], 2⟩

/-- **Instability of the plain planner.** Installing `make1` makes the
higher-priority `need1` applicable, so the route to goal `0` changes even
though the old route is still valid. -/
theorem plan_not_stable :
    plan [need1, from2] [4] 3 0 = some (.apply from2 [.given 4]) ∧
    plan [need1, from2, make1] [4] 3 0 =
      some (.apply need1 [.apply make1 [.given 4]]) := by
  constructor <;> rfl

end Counterexample

variable {Ty : Type} [DecidableEq Ty] [SeqTypes Ty]

/-- Generation-layered planning: use only the first `k` installed contracts,
for the smallest `k` that succeeds. -/
def planStable (lib : List (Contract Ty)) (avail : List Ty) (n : Nat) (t : Ty) :
    Option (Plan Ty) :=
  firstSome (fun k => plan (lib.take k) avail n t) (List.range (lib.length + 1))

theorem firstSome_append_of_isSome {α β : Type} {f : α → Option β} {l₁ : List α}
    (l₂ : List α) (h : (firstSome f l₁).isSome) :
    firstSome f (l₁ ++ l₂) = firstSome f l₁ := by
  induction l₁ with
  | nil => simp [firstSome] at h
  | cons a as ih =>
    cases ha : f a with
    | some b => simp [firstSome, ha]
    | none =>
      simp only [List.cons_append, firstSome, ha] at h ⊢
      exact ih h

theorem firstSome_congr {α β : Type} {f g : α → Option β} :
    ∀ {l : List α}, (∀ a ∈ l, f a = g a) → firstSome f l = firstSome g l
  | [], _ => rfl
  | a :: as, h => by
    simp only [firstSome, h a List.mem_cons_self,
      firstSome_congr fun x hx => h x (List.mem_cons_of_mem _ hx)]

/-- **Soundness** of layered planning. -/
theorem planStable_sound {lib : List (Contract Ty)} {avail : List Ty} {n : Nat}
    {t : Ty} {p : Plan Ty} (h : planStable lib avail n t = some p) :
    WellTyped lib avail p t := by
  obtain ⟨k, _, hk⟩ := firstSome_spec h
  exact WellTyped.mono (fun _ hc => List.mem_of_mem_take hc)
    (plan_sound _ n avail t p hk)

/-- **Completeness** of layered planning. -/
theorem planStable_complete {lib : List (Contract Ty)} {avail : List Ty} {n : Nat}
    {t : Ty} (h : Derivable lib avail n t) : (planStable lib avail n t).isSome := by
  apply firstSome_isSome (a := lib.length) (by simp)
  simpa using plan_complete h

/-- **Stability.** Installing new modules never changes the route of a task
that was already solvable. -/
theorem planStable_append {lib : List (Contract Ty)} (extra : List (Contract Ty))
    {avail : List Ty} {n : Nat} {t : Ty} (h : (planStable lib avail n t).isSome) :
    planStable (lib ++ extra) avail n t = planStable lib avail n t := by
  unfold planStable at h ⊢
  have hrange : List.range ((lib ++ extra).length + 1) =
      List.range (lib.length + 1) ++
        (List.range extra.length).map (lib.length + 1 + ·) := by
    rw [show (lib ++ extra).length + 1 = (lib.length + 1) + extra.length by
      simp; omega, List.range_add]
  rw [hrange, firstSome_append_of_isSome _ (by
    rwa [firstSome_congr fun k hk => by
      rw [List.take_append_of_le_length (by simp at hk; omega)]])]
  exact firstSome_congr fun k hk => by
    rw [List.take_append_of_le_length (by simp at hk; omega)]

/-- Search depth limits in increasing order, preserving contract order at each depth. -/
def planShallow (lib : List (Contract Ty)) (avail : List Ty) (n : Nat) (t : Ty) :
    Option (Plan Ty) :=
  firstSome (fun depth => plan lib avail depth t) (List.range (n + 1))

theorem planShallow_sound {lib : List (Contract Ty)} {avail : List Ty} {n : Nat}
    {t : Ty} {p : Plan Ty} (h : planShallow lib avail n t = some p) :
    WellTyped lib avail p t := by
  obtain ⟨depth, _, hd⟩ := firstSome_spec h
  exact plan_sound _ depth avail t p hd

theorem planShallow_complete {lib : List (Contract Ty)} {avail : List Ty} {n : Nat}
    {t : Ty} (h : Derivable lib avail n t) : (planShallow lib avail n t).isSome := by
  apply firstSome_isSome (a := n) (by simp)
  exact plan_complete h

/-- Prefer the earliest successful library prefix, then the shallowest depth. -/
def planShallowStable (lib : List (Contract Ty)) (avail : List Ty) (n : Nat) (t : Ty) :
    Option (Plan Ty) :=
  firstSome (fun k => planShallow (lib.take k) avail n t) (List.range (lib.length + 1))

theorem planShallowStable_sound {lib : List (Contract Ty)} {avail : List Ty} {n : Nat}
    {t : Ty} {p : Plan Ty} (h : planShallowStable lib avail n t = some p) :
    WellTyped lib avail p t := by
  obtain ⟨k, _, hk⟩ := firstSome_spec h
  exact WellTyped.mono (fun _ hc => List.mem_of_mem_take hc) (planShallow_sound hk)

theorem planShallowStable_complete {lib : List (Contract Ty)} {avail : List Ty} {n : Nat}
    {t : Ty} (h : Derivable lib avail n t) : (planShallowStable lib avail n t).isSome := by
  apply firstSome_isSome (a := lib.length) (by simp)
  simpa using planShallow_complete h

theorem planShallowStable_append {lib : List (Contract Ty)} (extra : List (Contract Ty))
    {avail : List Ty} {n : Nat} {t : Ty} (h : (planShallowStable lib avail n t).isSome) :
    planShallowStable (lib ++ extra) avail n t = planShallowStable lib avail n t := by
  unfold planShallowStable at h ⊢
  have hrange : List.range ((lib ++ extra).length + 1) =
      List.range (lib.length + 1) ++
        (List.range extra.length).map (lib.length + 1 + ·) := by
    rw [show (lib ++ extra).length + 1 = (lib.length + 1) + extra.length by
      simp; omega, List.range_add]
  rw [hrange, firstSome_append_of_isSome _ (by
    rwa [firstSome_congr fun k hk => by
      rw [List.take_append_of_le_length (by simp at hk; omega)]])]
  exact firstSome_congr fun k hk => by
    rw [List.take_append_of_le_length (by simp at hk; omega)]

end NCA
