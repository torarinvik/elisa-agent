import NCA.Planning.Routing

/-!
# Promotion is substitution

Planning reads contracts only through their inputs and output. So if `σ`
maps every contract to one with the same inputs and output, planning over
`lib.map σ` returns the plan found over `lib` with `σ` applied to each of
its contracts (`plan_rename`, `planShallow_rename`,
`planShallowStable_rename`), and renaming keeps plans well-typed
(`WellTyped.rename`). Promoting a challenger over an incumbent exchanges
the two, a signature-preserving `σ` that is its own inverse.
-/

namespace NCA

variable {α β Ty : Type}

mutual
/-- `p` with `σ` applied to every contract it applies. -/
def Plan.rename (σ : Contract Ty → Contract Ty) : Plan Ty → Plan Ty
  | .given t => .given t
  | .apply c ps => .apply (σ c) (Plan.renameList σ ps)
  | .map a body src => .map a (Plan.rename σ body) (Plan.rename σ src)

def Plan.renameList (σ : Contract Ty → Contract Ty) : List (Plan Ty) → List (Plan Ty)
  | [] => []
  | p :: ps => Plan.rename σ p :: Plan.renameList σ ps
end

theorem Plan.renameList_eq_map (σ : Contract Ty → Contract Ty) :
    ∀ ps : List (Plan Ty), Plan.renameList σ ps = ps.map (Plan.rename σ)
  | [] => rfl
  | p :: ps => by simp [Plan.renameList, Plan.renameList_eq_map σ ps]

theorem firstSome_map_list (f : β → Option γ) (g : α → β) :
    ∀ l : List α, firstSome f (l.map g) = firstSome (f ∘ g) l
  | [] => rfl
  | a :: as => by
    simp only [List.map_cons, firstSome, Function.comp]
    cases f (g a) <;> simp [firstSome_map_list f g as]

theorem firstSome_map_option (f : α → Option β) (r : β → γ) :
    ∀ l : List α, firstSome (fun a => (f a).map r) l = (firstSome f l).map r
  | [] => rfl
  | a :: as => by
    simp only [firstSome]
    cases f a <;> simp [firstSome_map_option f r as]

theorem orElse_map (x : Option β) (f : Unit → Option γ) (g : Unit → Option β) (r : β → γ)
    (h : f () = (g ()).map r) : (x.map r).orElse f = (x.orElse g).map r := by
  cases x <;> simp [Option.orElse, h]

theorem traverse_map_option (f : α → Option β) (r : β → γ) :
    ∀ l : List α, traverse (fun a => (f a).map r) l = (traverse f l).map (List.map r)
  | [] => rfl
  | a :: as => by
    simp only [traverse, traverse_map_option f r as]
    cases f a <;> cases traverse f as <;> simp

variable [SeqTypes Ty]
open SeqTypes

section
variable [DecidableEq Ty]
variable {σ : Contract Ty → Contract Ty}
  (hin : ∀ c, (σ c).inputs = c.inputs) (hout : ∀ c, (σ c).output = c.output)
include hin hout

omit [DecidableEq Ty] hin in
theorem elemCandidates_rename (lib : List (Contract Ty)) (avail : List Ty) :
    elemCandidates (lib.map σ) avail = elemCandidates lib avail := by
  simp [elemCandidates, List.map_map, Function.comp_def, hout]

/-- **Planning commutes with substitution.** -/
theorem plan_rename (lib : List (Contract Ty)) :
    ∀ (n : Nat) (avail : List Ty) (t : Ty),
    plan (lib.map σ) avail n t = (plan lib avail n t).map (Plan.rename σ)
  | 0, _, _ => by simp [plan]
  | n + 1, avail, t => by
    have ih := plan_rename lib n
    by_cases ht : t ∈ avail
    · simp [plan, ht, Plan.rename]
    · simp only [plan, ht, if_false]
      rw [firstSome_map_list]
      have happly : ∀ c : Contract Ty,
          ((fun c : Contract Ty => if c.output = t then
              (traverse (plan (lib.map σ) avail n) c.inputs).map (.apply c) else none) ∘ σ) c =
          (if c.output = t then (traverse (plan lib avail n) c.inputs).map (.apply c)
            else none).map (Plan.rename σ) := by
        intro c
        simp only [Function.comp, hout, hin]
        split
        · rw [show plan (lib.map σ) avail n = fun u => (plan lib avail n u).map (Plan.rename σ)
            from funext (ih avail), traverse_map_option]
          cases traverse (plan lib avail n) c.inputs <;>
            simp [Plan.rename, Plan.renameList_eq_map]
        · rfl
      rw [firstSome_congr (fun c _ => happly c), firstSome_map_option]
      refine orElse_map _ _ _ _ ?_
      cases elem? t with
      | none => rfl
      | some e =>
        rw [elemCandidates_rename hout]
        rw [← firstSome_map_option]
        apply firstSome_congr
        intro a _
        rw [ih [a] e, ih avail (seq a)]
        cases plan lib [a] n e <;> cases plan lib avail n (seq a) <;> simp [Plan.rename]

theorem planShallow_rename (lib : List (Contract Ty)) (avail : List Ty) (n : Nat) (t : Ty) :
    planShallow (lib.map σ) avail n t = (planShallow lib avail n t).map (Plan.rename σ) := by
  simp only [planShallow, plan_rename hin hout, firstSome_map_option]

/-- **Stable planning commutes with substitution**, so promotion replaces
the incumbent by the challenger in every route and changes nothing else. -/
theorem planShallowStable_rename (lib : List (Contract Ty)) (avail : List Ty) (n : Nat)
    (t : Ty) :
    planShallowStable (lib.map σ) avail n t =
      (planShallowStable lib avail n t).map (Plan.rename σ) := by
  simp only [planShallowStable, List.length_map, ← List.map_take,
    planShallow_rename hin hout, firstSome_map_option]

end

mutual
/-- Renaming by a signature-preserving `σ` keeps a plan well-typed. -/
theorem WellTyped.rename {σ : Contract Ty → Contract Ty}
    (hin : ∀ c, (σ c).inputs = c.inputs) (hout : ∀ c, (σ c).output = c.output)
    {lib : List (Contract Ty)} :
    {avail : List Ty} → {p : Plan Ty} → {t : Ty} → WellTyped lib avail p t →
    WellTyped (lib.map σ) avail (p.rename σ) t
  | _, _, _, .given h => .given h
  | _, _, _, .apply (c := c) hc hargs => by
    have h := WellTyped.apply (List.mem_map_of_mem hc)
      (by rw [hin]; exact WellTypedArgs.rename hin hout hargs)
    rw [hout] at h
    exact h
  | _, _, _, .map hbody hsrc =>
    .map (WellTyped.rename hin hout hbody) (WellTyped.rename hin hout hsrc)

theorem WellTypedArgs.rename {σ : Contract Ty → Contract Ty}
    (hin : ∀ c, (σ c).inputs = c.inputs) (hout : ∀ c, (σ c).output = c.output)
    {lib : List (Contract Ty)} :
    {avail : List Ty} → {ps : List (Plan Ty)} → {ts : List Ty} →
    WellTypedArgs lib avail ps ts → WellTypedArgs (lib.map σ) avail (Plan.renameList σ ps) ts
  | _, _, _, .nil => .nil
  | _, _, _, .cons h hs =>
    .cons (WellTyped.rename hin hout h) (WellTypedArgs.rename hin hout hs)
end

end NCA
