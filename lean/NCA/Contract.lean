/-!
# Contracts and well-typed composition

The mathematical model of the Cognitive ABI's composition rule: a module is
known only by its contract, and a composition graph is valid when every edge
connects equal semantic types.
-/

namespace NCA

/-- A module's contract: input types and output type. `id` distinguishes
modules that share a signature. -/
structure Contract (Ty : Type) where
  id : Nat
  inputs : List Ty
  output : Ty
  deriving DecidableEq

/-- A composition graph: either a task input, or a module applied to
sub-plans producing its inputs. -/
inductive Plan (Ty : Type) where
  | given : Ty → Plan Ty
  | apply : Contract Ty → List (Plan Ty) → Plan Ty

variable {Ty : Type}

mutual
/-- `WellTyped lib avail p t`: plan `p` uses only installed contracts `lib`,
only available inputs `avail`, and produces type `t`. -/
inductive WellTyped (lib : List (Contract Ty)) (avail : List Ty) : Plan Ty → Ty → Prop
  | given {t : Ty} : t ∈ avail → WellTyped lib avail (.given t) t
  | apply {c : Contract Ty} {ps : List (Plan Ty)} :
      c ∈ lib → WellTypedArgs lib avail ps c.inputs →
      WellTyped lib avail (.apply c ps) c.output

/-- Pointwise `WellTyped` for argument lists. -/
inductive WellTypedArgs (lib : List (Contract Ty)) (avail : List Ty) :
    List (Plan Ty) → List Ty → Prop
  | nil : WellTypedArgs lib avail [] []
  | cons {p : Plan Ty} {ps : List (Plan Ty)} {t : Ty} {ts : List Ty} :
      WellTyped lib avail p t → WellTypedArgs lib avail ps ts →
      WellTypedArgs lib avail (p :: ps) (t :: ts)
end

mutual
/-- Installing modules never invalidates an existing well-typed plan. -/
theorem WellTyped.mono {lib lib' : List (Contract Ty)} {avail : List Ty}
    (hsub : ∀ c, c ∈ lib → c ∈ lib') :
    {p : Plan Ty} → {t : Ty} → WellTyped lib avail p t → WellTyped lib' avail p t
  | _, _, .given h => .given h
  | _, _, .apply hc hargs => .apply (hsub _ hc) (WellTypedArgs.mono hsub hargs)

theorem WellTypedArgs.mono {lib lib' : List (Contract Ty)} {avail : List Ty}
    (hsub : ∀ c, c ∈ lib → c ∈ lib') :
    {ps : List (Plan Ty)} → {ts : List Ty} →
    WellTypedArgs lib avail ps ts → WellTypedArgs lib' avail ps ts
  | _, _, .nil => .nil
  | _, _, .cons h hs => .cons (WellTyped.mono hsub h) (WellTypedArgs.mono hsub hs)
end

end NCA
