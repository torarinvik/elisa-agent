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

/-- Variable `n` occurs in a term. -/
inductive Occurs (n : Nat) : Term → Prop
  | var : Occurs n (.var n)
  | app {f : String} {ts : List Term} {t : Term} : t ∈ ts → Occurs n t → Occurs n (.app f ts)

/-- Substitutions that agree on a term agree on every variable occurring in it. -/
theorem subst_agree {σ τ : Nat → Term} {n : Nat} :
    {t : Term} → Occurs n t → subst σ t = subst τ t → σ n = τ n
  | _, .var, h => by
    rw [subst, subst] at h
    exact h
  | _, .app (ts := ts) ht hn, h => by
    rw [subst_app, subst_app] at h
    injection h with _ hmap
    exact subst_agree hn (List.map_inj_left.mp hmap _ ht)

/-- Substitutions that agree on every variable of a term agree on the term. -/
theorem subst_congr (σ τ : Nat → Term) :
    (t : Term) → (∀ n, Occurs n t → σ n = τ n) → subst σ t = subst τ t
  | .var n, h => by
    rw [subst, subst]
    exact h n .var
  | .app f ts, h => by
    rw [subst_app, subst_app]
    congr 1
    exact List.map_congr_left fun t ht => subst_congr σ τ t fun n hn => h n (.app ht hn)

/-- Substituting twice is substituting once with the composite. -/
theorem subst_subst (σ τ : Nat → Term) :
    (t : Term) → subst σ (subst τ t) = subst (fun n => subst σ (τ n)) t
  | .var n => by rw [subst, subst]
  | .app f ts => by
    rw [subst_app, subst_app, subst_app, List.map_map]
    congr 1
    exact List.map_congr_left fun t _ => subst_subst σ τ t

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

/-- Every variable of the inputs occurs in the output. -/
def Contract.RangeRestricted (c : Contract Term) : Prop :=
  ∀ n, (∃ t ∈ c.inputs, Term.Occurs n t) → Term.Occurs n c.output

/-- **Instances are determined by their output.** Two instances of a
range-restricted contract with the same output are the same instance, so a
ground goal selects at most one instance of each contract. -/
theorem Contract.subst_determined {σ τ : Nat → Term} (c : Contract Term)
    (hc : c.RangeRestricted) (h : Term.subst σ c.output = Term.subst τ c.output) :
    Contract.subst σ c = Contract.subst τ c := by
  have agree : ∀ n, Term.Occurs n c.output → σ n = τ n := fun n hn => Term.subst_agree hn h
  unfold Contract.subst
  rw [h]
  congr 1
  exact List.map_congr_left fun t ht => Term.subst_congr σ τ t fun n hn => agree n (hc n ⟨t, ht, hn⟩)

theorem Contract.subst_subst (σ τ : Nat → Term) (c : Contract Term) :
    Contract.subst σ (Contract.subst τ c) = Contract.subst (fun n => Term.subst σ (τ n)) c := by
  simp only [Contract.subst, List.map_map]
  congr 1
  · exact List.map_congr_left fun t _ => Term.subst_subst σ τ t
  · exact Term.subst_subst σ τ c.output

/-- `c` is an instance of a contract in `lib`. -/
def InstanceOf (lib : List (Contract Term)) (c : Contract Term) : Prop :=
  ∃ d ∈ lib, ∃ τ : Nat → Term, c = Contract.subst τ d

/-- Instances of instances are instances. -/
theorem InstanceOf.subst {lib : List (Contract Term)} {c : Contract Term}
    (h : InstanceOf lib c) (σ : Nat → Term) : InstanceOf lib (Contract.subst σ c) := by
  obtain ⟨d, hd, τ, rfl⟩ := h
  exact ⟨d, hd, _, Contract.subst_subst σ τ d⟩

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

/-- **Answers are instances.** A plan well-typed over instances of library
contracts stays well-typed, over instances of library contracts, when an
answer substitution is applied: pattern search is sound however its
unifiers are computed. -/
theorem answer_sound {lib inst : List (Contract Term)} (hinst : ∀ c ∈ inst, InstanceOf lib c)
    (σ : Nat → Term) {avail : List Term} {p : Plan Term} {t : Term}
    (h : WellTyped inst avail p t) :
    (∀ c ∈ inst.map (Contract.subst σ), InstanceOf lib c) ∧
      WellTyped (inst.map (Contract.subst σ)) (avail.map (Term.subst σ)) (Plan.subst σ p)
        (Term.subst σ t) := by
  refine ⟨fun c hc => ?_, WellTyped.subst σ h⟩
  obtain ⟨d, hd, rfl⟩ := List.mem_map.mp hc
  exact (hinst d hd).subst σ

end NCA
