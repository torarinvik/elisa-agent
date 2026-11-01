import NCA.Upgrade

/-!
# Lazy loading and scalable discovery

Planning reads only contracts (module manifests); executing a plan needs only
the modules whose contracts occur in it. This file proves that the working
set of a task is contained in the library and is unaffected by installing
further modules, that planning success is monotone in the library (which
lets the layered planner binary-search its prefix), and that planning
through an index by output type computes the same plans as scanning the
whole library.
-/

namespace NCA

variable {Ty : Type} [DecidableEq Ty] [SeqTypes Ty]
open SeqTypes

mutual
/-- The contracts a plan invokes: its working set. -/
def Plan.contracts : Plan Ty → List (Contract Ty)
  | .given _ => []
  | .apply c ps => c :: Plan.contractsArgs ps
  | .map _ body src => body.contracts ++ src.contracts

/-- Working set of a list of plans. -/
def Plan.contractsArgs : List (Plan Ty) → List (Contract Ty)
  | [] => []
  | p :: ps => p.contracts ++ Plan.contractsArgs ps
end

omit [DecidableEq Ty] in
mutual
/-- **Working set ⊆ library.** A well-typed plan only invokes installed modules. -/
theorem WellTyped.contracts_subset {lib : List (Contract Ty)} :
    {avail : List Ty} → {p : Plan Ty} → {t : Ty} →
    WellTyped lib avail p t → ∀ c ∈ p.contracts, c ∈ lib
  | _, _, _, .given _ => by simp [Plan.contracts]
  | _, _, _, .apply hc hargs => by
    intro c' hmem
    simp only [Plan.contracts, List.mem_cons] at hmem
    rcases hmem with rfl | hmem
    · exact hc
    · exact WellTypedArgs.contracts_subset hargs c' hmem
  | _, _, _, .map hbody hsrc => by
    intro c' hmem
    simp only [Plan.contracts, List.mem_append] at hmem
    rcases hmem with hmem | hmem
    · exact WellTyped.contracts_subset hbody c' hmem
    · exact WellTyped.contracts_subset hsrc c' hmem

theorem WellTypedArgs.contracts_subset {lib : List (Contract Ty)} :
    {avail : List Ty} → {ps : List (Plan Ty)} → {ts : List Ty} →
    WellTypedArgs lib avail ps ts → ∀ c ∈ Plan.contractsArgs ps, c ∈ lib
  | _, _, _, .nil => by simp [Plan.contractsArgs]
  | _, _, _, .cons h hs => by
    intro c' hmem
    simp only [Plan.contractsArgs, List.mem_append] at hmem
    rcases hmem with hmem | hmem
    · exact WellTyped.contracts_subset h c' hmem
    · exact WellTypedArgs.contracts_subset hs c' hmem
end

/-- **Installation never grows a working set.** After installing `extra`, a
task that already had a route invokes exactly the same modules. -/
theorem route_contracts_append {pins : Pins Ty} {lib : List (Contract Ty)}
    (extra : List (Contract Ty)) {avail : List Ty} {n : Nat} {t : Ty}
    (h : (route pins lib avail n t).isSome) :
    (route pins (lib ++ extra) avail n t).map Plan.contracts =
      (route pins lib avail n t).map Plan.contracts := by
  rw [route_append extra h]

section Monotonicity

theorem traverse_forall {α β : Type} {f : α → Option β} {P : α → Prop}
    (hf : ∀ a b, f a = some b → P a) :
    ∀ {l : List α} {bs : List β}, traverse f l = some bs → ∀ a ∈ l, P a
  | [], _, _ => by simp
  | a :: as, bs, h => by
    cases ha : f a <;> cases hr : traverse f as <;> simp [traverse, ha, hr] at h
    intro x hx
    rcases List.mem_cons.mp hx with rfl | hx
    · exact hf _ _ ha
    · exact traverse_forall hf hr x hx

/-- A successful plan witnesses derivability at the same depth. -/
theorem plan_derivable (lib : List (Contract Ty)) :
    ∀ (n : Nat) (avail : List Ty) (t : Ty) (p : Plan Ty), plan lib avail n t = some p →
      Derivable lib avail n t
  | 0, _, _, _, h => by simp [plan] at h
  | n + 1, avail, t, p, h => by
    unfold plan at h
    split at h
    next ht => exact .given ht
    next =>
      cases hfs : firstSome (fun c =>
          if c.output = t then (traverse (plan lib avail n) c.inputs).map (Plan.apply c)
          else none) lib with
      | some q =>
        obtain ⟨c, hc, hf⟩ := firstSome_spec hfs
        split at hf
        next heq =>
          cases hr : traverse (plan lib avail n) c.inputs with
          | none => simp [hr] at hf
          | some ps =>
            subst heq
            exact .apply hc (traverse_forall
              (fun i q hq => plan_derivable lib n avail i q hq) hr)
        next => simp at hf
      | none =>
        rw [hfs] at h
        simp only [Option.orElse] at h
        cases he : elem? t with
        | none => simp [he] at h
        | some e =>
          simp only [he] at h
          obtain ⟨a, ha, hf⟩ := firstSome_spec h
          cases hb : plan lib [a] n e <;> cases hs : plan lib avail n (seq a) <;>
            simp [hb, hs] at hf
          rw [elem?_eq_some.mp he]
          exact .map ha (plan_derivable lib n [a] e _ hb)
            (plan_derivable lib n avail _ _ hs)

omit [DecidableEq Ty] in
theorem elemCandidates_mono {lib lib' : List (Contract Ty)} {avail : List Ty}
    (hsub : ∀ c, c ∈ lib → c ∈ lib') {a : Ty} (ha : a ∈ elemCandidates lib avail) :
    a ∈ elemCandidates lib' avail := by
  simp only [elemCandidates, List.mem_filterMap, List.mem_append, List.mem_map] at ha ⊢
  obtain ⟨u, hu, he⟩ := ha
  refine ⟨u, ?_, he⟩
  rcases hu with hu | ⟨c, hc, rfl⟩
  · exact Or.inl hu
  · exact Or.inr ⟨c, hsub c hc, rfl⟩

omit [DecidableEq Ty] in
theorem Derivable.mono {lib lib' : List (Contract Ty)} (hsub : ∀ c, c ∈ lib → c ∈ lib')
    {avail : List Ty} {n : Nat} {t : Ty} (h : Derivable lib avail n t) :
    Derivable lib' avail n t := by
  induction h with
  | given ht => exact .given ht
  | apply hc _ ih => exact .apply (hsub _ hc) ih
  | map ha _ _ ihb ihs => exact .map (elemCandidates_mono hsub ha) ihb ihs

/-- **Monotonicity.** Installing modules never makes a solvable goal unsolvable. -/
theorem plan_mono {lib lib' : List (Contract Ty)} (hsub : ∀ c, c ∈ lib → c ∈ lib')
    {avail : List Ty} {n : Nat} {t : Ty} (h : (plan lib avail n t).isSome) :
    (plan lib' avail n t).isSome := by
  obtain ⟨p, hp⟩ := Option.isSome_iff_exists.mp h
  exact plan_complete ((plan_derivable lib n avail t p hp).mono hsub)

/-- **Prefix monotonicity.** If planning succeeds with the first `k` installed
modules, it succeeds with the first `k'` for every `k' ≥ k`. The smallest
successful prefix used by `planStable` can therefore be found by binary search
with `O(log |lib|)` planner calls instead of `|lib| + 1`. -/
theorem plan_prefix_mono {lib : List (Contract Ty)} {avail : List Ty} {n : Nat} {t : Ty}
    {k k' : Nat} (hk : k ≤ k') (h : (plan (lib.take k) avail n t).isSome) :
    (plan (lib.take k') avail n t).isSome := by
  refine plan_mono (fun c hc => ?_) h
  have : lib.take k = (lib.take k').take k := by
    rw [List.take_take, Nat.min_eq_left hk]
  rw [this] at hc
  exact List.mem_of_mem_take hc

end Monotonicity

section Index

theorem firstSome_filter {α β : Type} (p : α → Prop) [DecidablePred p] (g : α → Option β) :
    ∀ l : List α,
      firstSome (fun a => if p a then g a else none) l =
        firstSome g (l.filter fun a => decide (p a))
  | [] => rfl
  | a :: as => by
    by_cases ha : p a
    · cases hg : g a <;> simp [firstSome, ha, hg, firstSome_filter p g as]
    · simp [firstSome, ha, firstSome_filter p g as]

/-- Planning that looks up producers of a type in an index instead of
scanning the library. -/
def planIdx (lib : List (Contract Ty)) (idx : Ty → List (Contract Ty)) :
    List Ty → Nat → Ty → Option (Plan Ty)
  | _, 0, _ => none
  | avail, n + 1, t =>
    if t ∈ avail then some (.given t)
    else
      (firstSome (fun c => (traverse (planIdx lib idx avail n) c.inputs).map (.apply c))
        (idx t)).orElse fun _ =>
      match elem? t with
      | none => none
      | some e => firstSome (fun a =>
          match planIdx lib idx [a] n e, planIdx lib idx avail n (seq a) with
          | some body, some src => some (.map a body src)
          | _, _ => none) (elemCandidates lib avail)

/-- **Indexed planning is exact.** If `idx t` lists the producers of `t` in
installation order, indexed planning computes the same plan as `plan`; its
contract scan per step costs `|idx t|` instead of `|lib|`. -/
theorem planIdx_eq {lib : List (Contract Ty)} {idx : Ty → List (Contract Ty)}
    (hidx : ∀ t, idx t = lib.filter fun c => decide (c.output = t)) :
    ∀ n avail t, planIdx lib idx avail n t = plan lib avail n t
  | 0, _, _ => by simp [planIdx, plan]
  | n + 1, avail, t => by
    have ih := planIdx_eq hidx n
    have ih' : planIdx lib idx avail n = plan lib avail n := funext (ih avail)
    simp only [planIdx, plan, hidx, ih, ih']
    rw [firstSome_filter (fun c : Contract Ty => c.output = t)]
    rfl

end Index

/-- **Prefix results survive installation.** Installing contracts appends to
the library, and planning with a prefix that existed before sees exactly the
same contracts, so results cached for it stay valid. -/
theorem plan_prefix_append (lib more : List (Contract Ty)) {k : Nat} (hk : k ≤ lib.length)
    (avail : List Ty) (n : Nat) (t : Ty) :
    plan ((lib ++ more).take k) avail n t = plan (lib.take k) avail n t := by
  rw [List.take_append_of_le_length hk]

end NCA
