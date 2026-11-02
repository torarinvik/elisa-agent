import NCA.Types.Contract

/-!
# Refinement and subsumption

A declared refinement `R s t` claims that every value of `s` is a value of
`t`. Typing with subsumption (`WellTypedSub`) adds the rule that a plan of
type `s` also has type `t` when `R s t`. Each refinement is realized by an
upcast adapter with contract `[s] → t`; erasure (`Plan.erase`) removes
upcast applications.

Every plan typed with subsumption is the erasure of an ordinary well-typed
plan over the library followed by the upcasts (`WellTypedSub.coerce`), so
the planner needs no subtyping rule. If upcasts compute the identity, a
plan and its erasure evaluate equally (`Plan.eval_erase`), so all ways of
inserting upcasts agree.
-/

namespace NCA

variable {Ty : Type}

section Typing
variable [SeqTypes Ty]
open SeqTypes

mutual
/-- Typing with subsumption along the declared refinements `R`. -/
inductive WellTypedSub (R : Ty → Ty → Prop) (lib : List (Contract Ty)) :
    List Ty → Plan Ty → Ty → Prop
  | given {avail : List Ty} {t : Ty} : t ∈ avail → WellTypedSub R lib avail (.given t) t
  | apply {avail : List Ty} {c : Contract Ty} {ps : List (Plan Ty)} :
      c ∈ lib → WellTypedSubArgs R lib avail ps c.inputs →
      WellTypedSub R lib avail (.apply c ps) c.output
  | map {avail : List Ty} {a e : Ty} {body src : Plan Ty} :
      WellTypedSub R lib [a] body e → WellTypedSub R lib avail src (seq a) →
      WellTypedSub R lib avail (.map a body src) (seq e)
  | sub {avail : List Ty} {p : Plan Ty} {s t : Ty} :
      WellTypedSub R lib avail p s → R s t → WellTypedSub R lib avail p t

/-- Pointwise `WellTypedSub` for argument lists. -/
inductive WellTypedSubArgs (R : Ty → Ty → Prop) (lib : List (Contract Ty)) :
    List Ty → List (Plan Ty) → List Ty → Prop
  | nil {avail : List Ty} : WellTypedSubArgs R lib avail [] []
  | cons {avail : List Ty} {p : Plan Ty} {ps : List (Plan Ty)} {t : Ty} {ts : List Ty} :
      WellTypedSub R lib avail p t → WellTypedSubArgs R lib avail ps ts →
      WellTypedSubArgs R lib avail (p :: ps) (t :: ts)
end

mutual
/-- `p` without upcast applications: an upcast applied to one argument is
replaced by that argument. -/
def Plan.erase [DecidableEq Ty] (ups : List (Contract Ty)) : Plan Ty → Plan Ty
  | .given t => .given t
  | .apply c ps =>
    if c ∈ ups then
      match Plan.eraseList ups ps with
      | [q] => q
      | qs => .apply c qs
    else .apply c (Plan.eraseList ups ps)
  | .map a body src => .map a (Plan.erase ups body) (Plan.erase ups src)

def Plan.eraseList [DecidableEq Ty] (ups : List (Contract Ty)) : List (Plan Ty) → List (Plan Ty)
  | [] => []
  | p :: ps => Plan.erase ups p :: Plan.eraseList ups ps
end

section
variable [DecidableEq Ty] {R : Ty → Ty → Prop} {lib ups : List (Contract Ty)}

mutual
/-- **Subsumption is coercion.** With an upcast for every refinement and no
installed module an upcast, every plan typed with subsumption is the
erasure of a plan well-typed over the library and the upcasts. -/
theorem WellTypedSub.coerce
    (hup : ∀ s t, R s t → ∃ c, c ∈ ups ∧ c.inputs = [s] ∧ c.output = t)
    (hdis : ∀ c, c ∈ lib → c ∉ ups) :
    {avail : List Ty} → {p : Plan Ty} → {t : Ty} → WellTypedSub R lib avail p t →
    ∃ q, WellTyped (lib ++ ups) avail q t ∧ q.erase ups = p
  | _, _, _, .given h => ⟨.given _, .given h, by simp [Plan.erase]⟩
  | _, _, _, .apply (c := c) hc hargs => by
    obtain ⟨qs, hqs, hqe⟩ := WellTypedSubArgs.coerce hup hdis hargs
    refine ⟨.apply c qs, .apply (List.mem_append_left _ hc) hqs, ?_⟩
    simp [Plan.erase, hdis c hc, hqe]
  | _, _, _, .map hbody hsrc => by
    obtain ⟨b, hb, hbe⟩ := WellTypedSub.coerce hup hdis hbody
    obtain ⟨s, hs, hse⟩ := WellTypedSub.coerce hup hdis hsrc
    exact ⟨.map _ b s, .map hb hs, by simp [Plan.erase, hbe, hse]⟩
  | _, _, _, .sub (s := s) (t := t) hp hst => by
    obtain ⟨q, hq, hqe⟩ := WellTypedSub.coerce hup hdis hp
    obtain ⟨c, hc, hin, hout⟩ := hup s t hst
    refine ⟨.apply c [q], ?_, ?_⟩
    · have h := WellTyped.apply (lib := lib ++ ups) (avail := _) (ps := [q])
        (List.mem_append_right _ hc) (by rw [hin]; exact .cons hq .nil)
      rwa [hout] at h
    · simp [Plan.erase, Plan.eraseList, hc, hqe]

theorem WellTypedSubArgs.coerce
    (hup : ∀ s t, R s t → ∃ c, c ∈ ups ∧ c.inputs = [s] ∧ c.output = t)
    (hdis : ∀ c, c ∈ lib → c ∉ ups) :
    {avail : List Ty} → {ps : List (Plan Ty)} → {ts : List Ty} →
    WellTypedSubArgs R lib avail ps ts →
    ∃ qs, WellTypedArgs (lib ++ ups) avail qs ts ∧ Plan.eraseList ups qs = ps
  | _, _, _, .nil => ⟨[], .nil, by simp [Plan.eraseList]⟩
  | _, _, _, .cons h hs => by
    obtain ⟨q, hq, hqe⟩ := WellTypedSub.coerce hup hdis h
    obtain ⟨qs, hqs, hqse⟩ := WellTypedSubArgs.coerce hup hdis hs
    exact ⟨q :: qs, .cons hq hqs, by simp [Plan.eraseList, hqe, hqse]⟩
end

end

end Typing

mutual
/-- A plan's value: `app` gives each module's output from its arguments'
values, a map applies its body to each element through `mapv`, and inside
a body the element is the only available value. -/
def Plan.eval {V : Type} (app : Contract Ty → List V → V) (mapv : (V → V) → V → V)
    (env : Ty → V) : Plan Ty → V
  | .given t => env t
  | .apply c ps => app c (Plan.evalList app mapv env ps)
  | .map _ body src => mapv (fun v => Plan.eval app mapv (fun _ => v) body)
      (Plan.eval app mapv env src)

def Plan.evalList {V : Type} (app : Contract Ty → List V → V) (mapv : (V → V) → V → V)
    (env : Ty → V) : List (Plan Ty) → List V
  | [] => []
  | p :: ps => Plan.eval app mapv env p :: Plan.evalList app mapv env ps
end

section
variable [DecidableEq Ty] {V : Type} {app : Contract Ty → List V → V} {mapv : (V → V) → V → V}
  {ups : List (Contract Ty)}

mutual
/-- **Coherence.** If every upcast returns its argument, erasure does not
change a plan's value. -/
theorem Plan.eval_erase (hid : ∀ c, c ∈ ups → ∀ v, app c [v] = v) :
    (env : Ty → V) → (p : Plan Ty) → (p.erase ups).eval app mapv env = p.eval app mapv env
  | _, .given _ => by simp [Plan.erase, Plan.eval]
  | env, .apply c ps => by
    have hl := Plan.evalList_erase hid env ps
    by_cases hc : c ∈ ups
    · simp only [Plan.erase, if_pos hc]
      split
      · next q hq =>
        rw [hq] at hl
        simp only [Plan.eval, ← hl, Plan.evalList, hid c hc]
      · simp only [Plan.eval, hl]
    · simp only [Plan.erase, if_neg hc, Plan.eval, hl]
  | env, .map _ body src => by
    simp only [Plan.erase, Plan.eval, Plan.eval_erase hid env src,
      fun v => Plan.eval_erase hid (fun _ => v) body]

theorem Plan.evalList_erase (hid : ∀ c, c ∈ ups → ∀ v, app c [v] = v) :
    (env : Ty → V) → (ps : List (Plan Ty)) →
    Plan.evalList app mapv env (Plan.eraseList ups ps) = Plan.evalList app mapv env ps
  | _, [] => by simp [Plan.eraseList, Plan.evalList]
  | env, p :: ps => by
    simp only [Plan.eraseList, Plan.evalList, Plan.eval_erase hid env p,
      Plan.evalList_erase hid env ps]
end

end

end NCA
