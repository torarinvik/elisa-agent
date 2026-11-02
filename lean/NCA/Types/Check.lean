import NCA.Types.Contract

/-!
# Plan type checking

`infer` computes the type a plan produces, if it is well-typed. It decides
well-typedness: `infer lib avail p = some t ↔ WellTyped lib avail p t`. Plans
from outside the planner (hand-written pipelines, proposed upgrades) are
admitted only after checking.
-/

namespace NCA

variable {Ty : Type} [DecidableEq Ty] [SeqTypes Ty]
open SeqTypes

mutual
/-- The type produced by a plan, or `none` if it is not well-typed. -/
def infer (lib : List (Contract Ty)) : List Ty → Plan Ty → Option Ty
  | avail, .given t => if t ∈ avail then some t else none
  | avail, .apply c ps =>
    if c ∈ lib ∧ inferArgs lib avail ps = some c.inputs then some c.output else none
  | avail, .map a body src =>
    match infer lib [a] body, infer lib avail src with
    | some e, some u => if u = seq a then some (seq e) else none
    | _, _ => none

/-- Pointwise `infer` over argument lists. -/
def inferArgs (lib : List (Contract Ty)) : List Ty → List (Plan Ty) → Option (List Ty)
  | _, [] => some []
  | avail, p :: ps =>
    match infer lib avail p, inferArgs lib avail ps with
    | some t, some ts => some (t :: ts)
    | _, _ => none
end

mutual
theorem infer_sound (lib : List (Contract Ty)) :
    ∀ (avail : List Ty) (p : Plan Ty) (t : Ty), infer lib avail p = some t →
      WellTyped lib avail p t
  | avail, .given t', t, h => by
    unfold infer at h
    split at h
    next hm => cases h; exact .given hm
    next => cases h
  | avail, .apply c ps, t, h => by
    unfold infer at h
    split at h
    next hc =>
      cases h
      exact .apply hc.1 (inferArgs_sound lib avail ps c.inputs hc.2)
    next => cases h
  | avail, .map a body src, t, h => by
    unfold infer at h
    split at h
    next e u hb hs =>
      split at h
      next hu =>
        cases h
        subst hu
        exact .map (infer_sound lib [a] body e hb) (infer_sound lib avail src _ hs)
      next => cases h
    next => cases h

theorem inferArgs_sound (lib : List (Contract Ty)) :
    ∀ (avail : List Ty) (ps : List (Plan Ty)) (ts : List Ty),
      inferArgs lib avail ps = some ts → WellTypedArgs lib avail ps ts
  | avail, [], ts, h => by
    unfold inferArgs at h
    cases h
    exact .nil
  | avail, p :: ps, ts, h => by
    unfold inferArgs at h
    split at h
    next t ts' hp hps =>
      cases h
      exact .cons (infer_sound lib avail p t hp) (inferArgs_sound lib avail ps ts' hps)
    next => cases h
end

mutual
theorem infer_complete {lib : List (Contract Ty)} :
    {avail : List Ty} → {p : Plan Ty} → {t : Ty} →
    WellTyped lib avail p t → infer lib avail p = some t
  | _, _, _, .given h => by simp [infer, h]
  | _, _, _, .apply hc hargs => by
    simp [infer, hc, inferArgs_complete hargs]
  | _, _, _, .map hbody hsrc => by
    simp [infer, infer_complete hbody, infer_complete hsrc]

theorem inferArgs_complete {lib : List (Contract Ty)} :
    {avail : List Ty} → {ps : List (Plan Ty)} → {ts : List Ty} →
    WellTypedArgs lib avail ps ts → inferArgs lib avail ps = some ts
  | _, _, _, .nil => by simp [inferArgs]
  | _, _, _, .cons h hs => by
    simp [inferArgs, infer_complete h, inferArgs_complete hs]
end

/-- **Decidability.** The checker accepts exactly the well-typed plans. -/
theorem infer_iff {lib : List (Contract Ty)} {avail : List Ty} {p : Plan Ty} {t : Ty} :
    infer lib avail p = some t ↔ WellTyped lib avail p t :=
  ⟨infer_sound lib avail p t, infer_complete⟩

end NCA
