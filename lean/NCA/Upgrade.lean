import Mathlib.Logic.Function.Basic
import NCA.Check
import NCA.Routing

/-!
# Explicit route upgrades

Stable routing never changes a covered task's route on installation, so
better routes must be adopted explicitly. A router holds *pins*: per-goal
routes that override layered planning. An upgrade pins a checked plan for one
goal. Upgrades are local, reversible, and keep the router sound and stable.
-/

namespace NCA

variable {Ty : Type} [DecidableEq Ty] [SeqTypes Ty]

/-- Per-goal pinned routes. -/
abbrev Pins (Ty : Type) := Ty → Option (Plan Ty)

/-- The route for `t`: its pin if any, otherwise layered planning. -/
def route (pins : Pins Ty) (lib : List (Contract Ty)) (avail : List Ty) (n : Nat) (t : Ty) :
    Option (Plan Ty) :=
  (pins t).orElse fun _ => planStable lib avail n t

/-- Every pin is a well-typed plan for its goal. -/
def PinsValid (pins : Pins Ty) (lib : List (Contract Ty)) (avail : List Ty) : Prop :=
  ∀ t p, pins t = some p → WellTyped lib avail p t

/-- Pin `p` for goal `t` if it type-checks as producing `t`. -/
def upgrade (pins : Pins Ty) (lib : List (Contract Ty)) (avail : List Ty) (t : Ty)
    (p : Plan Ty) : Option (Pins Ty) :=
  if infer lib avail p = some t then some (Function.update pins t (some p)) else none

/-- **Router soundness.** With valid pins, every route is well-typed. -/
theorem route_sound {pins : Pins Ty} {lib : List (Contract Ty)} {avail : List Ty} {n : Nat}
    {t : Ty} {p : Plan Ty} (hpins : PinsValid pins lib avail)
    (h : route pins lib avail n t = some p) : WellTyped lib avail p t := by
  unfold route at h
  cases hp : pins t with
  | some q =>
    rw [hp] at h
    cases h
    exact hpins t _ hp
  | none =>
    rw [hp] at h
    exact planStable_sound h

/-- **Upgrades preserve validity.** -/
theorem upgrade_valid {pins pins' : Pins Ty} {lib : List (Contract Ty)} {avail : List Ty}
    {t : Ty} {p : Plan Ty} (hpins : PinsValid pins lib avail)
    (h : upgrade pins lib avail t p = some pins') : PinsValid pins' lib avail := by
  unfold upgrade at h
  split at h
  next hinfer =>
    cases h
    intro t' q hq
    by_cases ht : t' = t
    · subst ht
      simp at hq
      subst hq
      exact infer_sound lib avail _ _ hinfer
    · rw [Function.update_of_ne ht] at hq
      exact hpins t' q hq
  next => cases h

/-- **Upgrades take effect.** The upgraded goal is routed through the pin. -/
theorem upgrade_target {pins pins' : Pins Ty} {lib : List (Contract Ty)} {avail : List Ty}
    {n : Nat} {t : Ty} {p : Plan Ty} (h : upgrade pins lib avail t p = some pins') :
    route pins' lib avail n t = some p := by
  unfold upgrade at h
  split at h
  next =>
    cases h
    simp [route]
  next => cases h

/-- **Upgrades are local.** Every other goal keeps its route. -/
theorem upgrade_local {pins pins' : Pins Ty} {lib : List (Contract Ty)} {avail : List Ty}
    {n : Nat} {t t' : Ty} {p : Plan Ty} (h : upgrade pins lib avail t p = some pins')
    (ht : t' ≠ t) : route pins' lib avail n t' = route pins lib avail n t' := by
  unfold upgrade at h
  split at h
  next =>
    cases h
    simp [route, Function.update_of_ne ht]
  next => cases h

/-- **Rollback.** Restoring the previous pin of the upgraded goal restores the
router exactly, for every goal. -/
theorem upgrade_rollback {pins pins' : Pins Ty} {lib : List (Contract Ty)} {avail : List Ty}
    {t : Ty} {p : Plan Ty} (h : upgrade pins lib avail t p = some pins') :
    Function.update pins' t (pins t) = pins := by
  unfold upgrade at h
  split at h
  next =>
    cases h
    simp
  next => cases h

/-- **Stability with pins.** Installing modules never changes the route of a
goal that already had one. -/
theorem route_append {pins : Pins Ty} {lib : List (Contract Ty)} (extra : List (Contract Ty))
    {avail : List Ty} {n : Nat} {t : Ty} (h : (route pins lib avail n t).isSome) :
    route pins (lib ++ extra) avail n t = route pins lib avail n t := by
  unfold route at h ⊢
  cases hp : pins t with
  | some q => rfl
  | none =>
    rw [hp] at h
    simp only [Option.orElse] at h ⊢
    exact planStable_append extra h

omit [DecidableEq Ty] in
/-- Pins stay valid when modules are installed. -/
theorem PinsValid.append {pins : Pins Ty} {lib : List (Contract Ty)} {avail : List Ty}
    (extra : List (Contract Ty)) (h : PinsValid pins lib avail) :
    PinsValid pins (lib ++ extra) avail :=
  fun t p hp => WellTyped.mono (fun _ hc => List.mem_append_left _ hc) (h t p hp)

end NCA
