/-!
# Contracts and well-typed composition

The mathematical model of the Cognitive ABI's composition rule: a module is
known only by its contract, and a composition graph is valid when every edge
connects equal semantic types. Sequence types let one composition be applied
elementwise to a sequence.
-/

namespace NCA

/-- Semantic types with a sequence former `seq t`, recognisable by `elem?`. -/
class SeqTypes (Ty : Type) where
  seq : Ty → Ty
  elem? : Ty → Option Ty
  elem?_eq_some {u t : Ty} : elem? u = some t ↔ u = seq t

/-- A module's contract: input types and output type. `id` distinguishes
modules that share a signature. -/
structure Contract (Ty : Type) where
  id : Nat
  inputs : List Ty
  output : Ty
  deriving DecidableEq

/-- A composition graph. `map a body src` runs `body` on each element of the
sequence produced by `src`; inside `body` the element (of type `a`) is the
only available input. -/
inductive Plan (Ty : Type) where
  | given : Ty → Plan Ty
  | apply : Contract Ty → List (Plan Ty) → Plan Ty
  | map : Ty → Plan Ty → Plan Ty → Plan Ty

variable {Ty : Type} [SeqTypes Ty]
open SeqTypes

mutual
/-- `WellTyped lib avail p t`: plan `p` uses only installed contracts `lib`,
only available inputs `avail`, and produces type `t`. -/
inductive WellTyped (lib : List (Contract Ty)) : List Ty → Plan Ty → Ty → Prop
  | given {avail : List Ty} {t : Ty} : t ∈ avail → WellTyped lib avail (.given t) t
  | apply {avail : List Ty} {c : Contract Ty} {ps : List (Plan Ty)} :
      c ∈ lib → WellTypedArgs lib avail ps c.inputs →
      WellTyped lib avail (.apply c ps) c.output
  | map {avail : List Ty} {a e : Ty} {body src : Plan Ty} :
      WellTyped lib [a] body e → WellTyped lib avail src (seq a) →
      WellTyped lib avail (.map a body src) (seq e)

/-- Pointwise `WellTyped` for argument lists. -/
inductive WellTypedArgs (lib : List (Contract Ty)) :
    List Ty → List (Plan Ty) → List Ty → Prop
  | nil {avail : List Ty} : WellTypedArgs lib avail [] []
  | cons {avail : List Ty} {p : Plan Ty} {ps : List (Plan Ty)} {t : Ty} {ts : List Ty} :
      WellTyped lib avail p t → WellTypedArgs lib avail ps ts →
      WellTypedArgs lib avail (p :: ps) (t :: ts)
end

mutual
/-- Installing modules never invalidates an existing well-typed plan. -/
theorem WellTyped.mono {lib lib' : List (Contract Ty)}
    (hsub : ∀ c, c ∈ lib → c ∈ lib') :
    {avail : List Ty} → {p : Plan Ty} → {t : Ty} →
    WellTyped lib avail p t → WellTyped lib' avail p t
  | _, _, _, .given h => .given h
  | _, _, _, .apply hc hargs => .apply (hsub _ hc) (WellTypedArgs.mono hsub hargs)
  | _, _, _, .map hbody hsrc => .map (WellTyped.mono hsub hbody) (WellTyped.mono hsub hsrc)

theorem WellTypedArgs.mono {lib lib' : List (Contract Ty)}
    (hsub : ∀ c, c ∈ lib → c ∈ lib') :
    {avail : List Ty} → {ps : List (Plan Ty)} → {ts : List Ty} →
    WellTypedArgs lib avail ps ts → WellTypedArgs lib' avail ps ts
  | _, _, _, .nil => .nil
  | _, _, _, .cons h hs => .cons (WellTyped.mono hsub h) (WellTypedArgs.mono hsub hs)
end

end NCA
