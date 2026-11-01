import NCA.Contract

/-!
# Type terms and substitution

Semantic types as first-order terms: type variables and applications of named
constructors. `seq` is the unary constructor named `"seq"`, so terms are an
instance of `SeqTypes`. A substitution replaces variables by terms; it acts on
contracts and plans pointwise, and typing is stable under it
(`WellTyped.subst`): a composition over type variables is valid at every
instantiation.
-/

namespace NCA

/-- Type terms: variables and constructor applications. -/
inductive Term where
  | var : Nat → Term
  | app : String → List Term → Term

namespace Term

/-- Replace every variable `n` by `σ n`. -/
def subst (σ : Nat → Term) : Term → Term
  | .var n => σ n
  | .app f ts => .app f (ts.attach.map fun ⟨t, _⟩ => subst σ t)

theorem subst_app (σ : Nat → Term) (f : String) (ts : List Term) :
    subst σ (.app f ts) = .app f (ts.map (subst σ)) := by
  rw [subst]
  congr 1
  conv => rhs; rw [← List.attach_map_subtype_val ts]
  rw [List.map_map]
  rfl

end Term

/-- The argument of a `seq` term. -/
def Term.elem? : Term → Option Term
  | .app f [t] => if f = "seq" then some t else none
  | _ => none

theorem Term.elem?_eq_some {u t : Term} : Term.elem? u = some t ↔ u = .app "seq" [t] := by
  constructor
  · intro h
    match u, h with
    | .var _, h => simp [Term.elem?] at h
    | .app f [t'], h =>
      by_cases hf : f = "seq"
      · simp [Term.elem?, hf] at h
        rw [hf, h]
      · simp [Term.elem?, hf] at h
    | .app _ [], h => simp [Term.elem?] at h
    | .app _ (_ :: _ :: _), h => simp [Term.elem?] at h
  · rintro rfl
    simp [Term.elem?]

instance : SeqTypes Term where
  seq t := .app "seq" [t]
  elem? := Term.elem?
  elem?_eq_some := Term.elem?_eq_some

open SeqTypes

theorem Term.subst_seq (σ : Nat → Term) (a : Term) :
    Term.subst σ (seq a) = seq (Term.subst σ a) := by
  show Term.subst σ (.app "seq" [a]) = .app "seq" [Term.subst σ a]
  rw [Term.subst_app]
  rfl

/-- A contract with its types substituted. -/
def Contract.subst (σ : Nat → Term) (c : Contract Term) : Contract Term :=
  { id := c.id, inputs := c.inputs.map (Term.subst σ), output := Term.subst σ c.output }

/-- A plan with every type in it substituted. -/
def Plan.subst (σ : Nat → Term) : Plan Term → Plan Term
  | .given t => .given (Term.subst σ t)
  | .apply c ps => .apply (Contract.subst σ c) (ps.attach.map fun ⟨p, _⟩ => Plan.subst σ p)
  | .map a body src => .map (Term.subst σ a) (Plan.subst σ body) (Plan.subst σ src)

theorem Plan.subst_apply (σ : Nat → Term) (c : Contract Term) (ps : List (Plan Term)) :
    Plan.subst σ (.apply c ps) = .apply (Contract.subst σ c) (ps.map (Plan.subst σ)) := by
  rw [Plan.subst]
  congr 1
  conv => rhs; rw [← List.attach_map_subtype_val ps]
  rw [List.map_map]
  rfl

mutual
/-- **Typing is stable under substitution.** A well-typed plan stays
well-typed when a substitution is applied to its library, inputs, plan and
type. -/
theorem WellTyped.subst (σ : Nat → Term) {lib : List (Contract Term)} :
    {avail : List Term} → {p : Plan Term} → {t : Term} →
    WellTyped lib avail p t →
    WellTyped (lib.map (Contract.subst σ)) (avail.map (Term.subst σ)) (Plan.subst σ p)
      (Term.subst σ t)
  | _, _, _, .given h => by
    rw [Plan.subst]
    exact .given (List.mem_map_of_mem h)
  | _, _, _, .apply (c := c) hc hargs => by
    rw [Plan.subst_apply]
    exact .apply (c := Contract.subst σ c) (List.mem_map_of_mem hc) (WellTypedArgs.subst σ hargs)
  | _, _, _, .map hbody hsrc => by
    rw [Plan.subst, Term.subst_seq]
    have hsrc' := WellTyped.subst σ hsrc
    rw [Term.subst_seq] at hsrc'
    exact .map (WellTyped.subst σ hbody) hsrc'

theorem WellTypedArgs.subst (σ : Nat → Term) {lib : List (Contract Term)} :
    {avail : List Term} → {ps : List (Plan Term)} → {ts : List Term} →
    WellTypedArgs lib avail ps ts →
    WellTypedArgs (lib.map (Contract.subst σ)) (avail.map (Term.subst σ))
      (ps.map (Plan.subst σ)) (ts.map (Term.subst σ))
  | _, _, _, .nil => .nil
  | _, _, _, .cons h hs => .cons (WellTyped.subst σ h) (WellTypedArgs.subst σ hs)
end

end NCA
