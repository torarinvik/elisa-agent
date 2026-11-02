import NCA.Routing

/-!
# Composite experts

A package is an expert or an ordered list of packages. Installing a
transparent package appends its flattened contracts, so every stability
result for appended libraries applies (`install_stable`), and flattening
respects concatenation (`flattenList_append`).

An exporting package offers a contract `c` implemented by a plan `impl` over
its members and the surrounding library. Replacing every application of `c`
in a plan by `impl` with its inputs instantiated by the application's
arguments (`Plan.inline`) preserves typing (`WellTyped.inline`): a plan that
uses a package as an expert is a plan over the package's members. Map bodies
read only their element, so instantiation leaves them unchanged.
-/

namespace NCA

/-- An expert, or an ordered list of packages. -/
inductive Pkg (Ty : Type) where
  | expert : Contract Ty → Pkg Ty
  | composite : List (Pkg Ty) → Pkg Ty

mutual
/-- The contracts of a package in member order. -/
def Pkg.flatten {Ty : Type} : Pkg Ty → List (Contract Ty)
  | .expert c => [c]
  | .composite ps => Pkg.flattenList ps

def Pkg.flattenList {Ty : Type} : List (Pkg Ty) → List (Contract Ty)
  | [] => []
  | p :: ps => p.flatten ++ Pkg.flattenList ps
end

theorem Pkg.flattenList_append {Ty : Type} :
    ∀ ps qs : List (Pkg Ty), Pkg.flattenList (ps ++ qs) = Pkg.flattenList ps ++ Pkg.flattenList qs
  | [], _ => rfl
  | p :: ps, qs => by
    simp only [List.cons_append, Pkg.flattenList, Pkg.flattenList_append ps qs, List.append_assoc]

section
variable {Ty : Type} [SeqTypes Ty]

/-- **Installing a package keeps every route.** A task the library already
solves keeps its route when a package's contracts are appended. -/
theorem install_stable [DecidableEq Ty] {lib : List (Contract Ty)} (p : Pkg Ty) {avail : List Ty} {n : Nat}
    {t : Ty} (h : (planShallowStable lib avail n t).isSome) :
    planShallowStable (lib ++ p.flatten) avail n t = planShallowStable lib avail n t :=
  planShallowStable_append _ h

end

section
variable {Ty : Type} [SeqTypes Ty]

/-- The argument for the first input of type `t`. -/
def lookupArg [DecidableEq Ty] (t : Ty) : List Ty → List (Plan Ty) → Option (Plan Ty)
  | u :: us, p :: ps => if u = t then some p else lookupArg t us ps
  | _, _ => none

theorem lookupArg_typed [DecidableEq Ty] {M : List (Contract Ty)} {avail : List Ty} {t : Ty} :
    {args : List (Plan Ty)} → {ins : List Ty} → WellTypedArgs M avail args ins → t ∈ ins →
    ∃ p, lookupArg t ins args = some p ∧ WellTyped M avail p t
  | _, _, .nil, h => by simp at h
  | _, _, .cons (t := u) (ts := us) hp hps, h => by
    by_cases hu : u = t
    · subst hu
      exact ⟨_, by simp [lookupArg], hp⟩
    · have ht : t ∈ us := by
        rcases List.mem_cons.mp h with h | h
        · exact absurd h.symm hu
        · exact h
      obtain ⟨q, hq, hqt⟩ := lookupArg_typed hps ht
      exact ⟨q, by simp [lookupArg, hu, hq], hqt⟩

mutual
/-- `p` with each input, read by type from `ins`, replaced by its argument. -/
def Plan.instantiate [DecidableEq Ty] (ins : List Ty) (args : List (Plan Ty)) : Plan Ty → Plan Ty
  | .given t => (lookupArg t ins args).getD (.given t)
  | .apply c ps => .apply c (Plan.instantiateList ins args ps)
  | .map a body src => .map a body (Plan.instantiate ins args src)

def Plan.instantiateList [DecidableEq Ty] (ins : List Ty) (args : List (Plan Ty)) :
    List (Plan Ty) → List (Plan Ty)
  | [] => []
  | p :: ps => Plan.instantiate ins args p :: Plan.instantiateList ins args ps
end

mutual
/-- Instantiating a plan's inputs with well-typed arguments keeps its type. -/
theorem WellTyped.instantiate [DecidableEq Ty] {L M : List (Contract Ty)} {avail ins : List Ty}
    {args : List (Plan Ty)} (hsub : ∀ c, c ∈ L → c ∈ M)
    (hargs : WellTypedArgs M avail args ins) :
    {p : Plan Ty} → {t : Ty} → WellTyped L ins p t →
    WellTyped M avail (p.instantiate ins args) t
  | _, _, .given h => by
    obtain ⟨q, hq, hqt⟩ := lookupArg_typed hargs h
    simp only [Plan.instantiate, hq, Option.getD_some]
    exact hqt
  | _, _, .apply hc hps => by
    simp only [Plan.instantiate]
    exact .apply (hsub _ hc) (WellTypedArgs.instantiate hsub hargs hps)
  | _, _, .map hbody hsrc => by
    simp only [Plan.instantiate]
    exact .map (WellTyped.mono hsub hbody) (WellTyped.instantiate hsub hargs hsrc)

theorem WellTypedArgs.instantiate [DecidableEq Ty] {L M : List (Contract Ty)} {avail ins : List Ty}
    {args : List (Plan Ty)} (hsub : ∀ c, c ∈ L → c ∈ M)
    (hargs : WellTypedArgs M avail args ins) :
    {ps : List (Plan Ty)} → {ts : List Ty} → WellTypedArgs L ins ps ts →
    WellTypedArgs M avail (Plan.instantiateList ins args ps) ts
  | _, _, .nil => by
    simp only [Plan.instantiateList]
    exact .nil
  | _, _, .cons h hs => by
    simp only [Plan.instantiateList]
    exact .cons (WellTyped.instantiate hsub hargs h) (WellTypedArgs.instantiate hsub hargs hs)
end

mutual
/-- `q` with every application of `c` replaced by `impl` on its arguments. -/
def Plan.inline [DecidableEq Ty] (c : Contract Ty) (impl : Plan Ty) : Plan Ty → Plan Ty
  | .given t => .given t
  | .apply d ps =>
    if d = c then impl.instantiate c.inputs (Plan.inlineList c impl ps)
    else .apply d (Plan.inlineList c impl ps)
  | .map a body src => .map a (Plan.inline c impl body) (Plan.inline c impl src)

def Plan.inlineList [DecidableEq Ty] (c : Contract Ty) (impl : Plan Ty) : List (Plan Ty) → List (Plan Ty)
  | [] => []
  | p :: ps => Plan.inline c impl p :: Plan.inlineList c impl ps
end

mutual
/-- **Packages are experts.** If an exported contract `c` is implemented by
`impl` over the package's members `inner` and the library, every plan using
`c` as an expert inlines to a plan over `inner ++ lib` of the same type. -/
theorem WellTyped.inline [DecidableEq Ty] {c : Contract Ty} {impl : Plan Ty} {inner lib : List (Contract Ty)}
    (himpl : WellTyped (inner ++ lib) c.inputs impl c.output) :
    {avail : List Ty} → {q : Plan Ty} → {t : Ty} → WellTyped (c :: lib) avail q t →
    WellTyped (inner ++ lib) avail (Plan.inline c impl q) t
  | _, _, _, .given h => by
    simp only [Plan.inline]
    exact .given h
  | _, _, _, .apply (c := d) hd hps => by
    have hargs := WellTypedArgs.inline himpl hps
    simp only [Plan.inline]
    by_cases hdc : d = c
    · subst hdc
      simp only [if_true]
      exact WellTyped.instantiate (fun _ h => h) hargs himpl
    · rw [if_neg hdc]
      exact .apply (List.mem_append_right _ ((List.mem_cons.mp hd).resolve_left hdc)) hargs
  | _, _, _, .map hbody hsrc => by
    simp only [Plan.inline]
    exact .map (WellTyped.inline himpl hbody) (WellTyped.inline himpl hsrc)

theorem WellTypedArgs.inline [DecidableEq Ty] {c : Contract Ty} {impl : Plan Ty}
    {inner lib : List (Contract Ty)}
    (himpl : WellTyped (inner ++ lib) c.inputs impl c.output) :
    {avail : List Ty} → {ps : List (Plan Ty)} → {ts : List Ty} →
    WellTypedArgs (c :: lib) avail ps ts →
    WellTypedArgs (inner ++ lib) avail (Plan.inlineList c impl ps) ts
  | _, _, _, .nil => by
    simp only [Plan.inlineList]
    exact .nil
  | _, _, _, .cons h hs => by
    simp only [Plan.inlineList]
    exact .cons (WellTyped.inline himpl h) (WellTypedArgs.inline himpl hs)
end

end

end NCA
