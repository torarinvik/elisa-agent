import Mathlib.Logic.Equiv.List
import NCA.Types.Unification

/-!
# Completeness of pattern search

A *skeleton* fixes which contract or available type sits at each node of a
plan, and the element type of each `map`, but not the types the contracts
are applied at. Renaming the variables of the contract at each node apart,
by the node's path, turns the question "which instances make this skeleton
produce an instance of the pattern `P`?" into one finite list of equations,
`Skel.eqs`: at every node, the node's output equals the pattern its parent
asks for (THEORY §2.2).

* Every solution types the skeleton (`Skel.sound`).
* Every ground plan producing an instance of `P` is the skeleton of a
  solution, through its own instantiation of every node (`Skel.complete`).
* The most general solution types the skeleton most generally: every typed
  instantiation is a substitution instance of it (`Skel.most_general`).
* Solving the equations block by block, applying each block's most general
  unifier to the rest, reaches a most general unifier of the whole whenever
  the whole has a solution (`SeqMGU.isMGU`, `SeqMGU.exists`). Pattern search
  solves them node by node in this way.

Together: for every ground plan producing an instance of `P`, pattern search
over that plan's skeleton finds a most general typing, and the plan is an
instance of it.
-/

namespace NCA

open Term SeqTypes

/-- Variable `n` of the contract at the node with path `π`, renamed apart.
Renamed variables are odd, which leaves the even ones for the goal. -/
def renVar (π : List Nat) (n : Nat) : Nat := 2 * Encodable.encode (π, n) + 1

/-- Generated variables cannot equal an external, even-numbered variable. -/
theorem renVar_ne_external (π : List Nat) (n external : Nat) :
    renVar π n ≠ 2 * external := by
  unfold renVar
  omega

/-- The node path and original variable uniquely determine the generated identity. -/
theorem renVar_injective {π σ : List Nat} {n m : Nat} (h : renVar π n = renVar σ m) :
    π = σ ∧ n = m := by
  have encoded : Encodable.encode (π, n) = Encodable.encode (σ, m) := by
    unfold renVar at h
    omega
  have pair := Encodable.encode_injective encoded
  exact ⟨congrArg Prod.fst pair, congrArg Prod.snd pair⟩

/-- The renaming of the contract at path `π`. -/
def ren (π : List Nat) (n : Nat) : Term := .var (renVar π n)

/-- A plan without the types its contracts are applied at. -/
inductive Skel where
  | given : Term → Skel
  | apply : Contract Term → List Skel → Skel
  | map : Term → Skel → Skel → Skel

mutual
/-- The plan of a skeleton, the contract at path `π` instantiated by `σ`
after renaming. The children of the node at `π` are at `π ++ [i]`. -/
def Skel.plan (σ : Nat → Term) : List Nat → Skel → Plan Term
  | _, .given t => .given t
  | π, .apply d ss => .apply (Contract.subst σ (Contract.subst (ren π) d)) (Skel.planList σ π 0 ss)
  | π, .map a b s => .map a (Skel.plan σ (π ++ [0]) b) (Skel.plan σ (π ++ [1]) s)

def Skel.planList (σ : Nat → Term) : List Nat → Nat → List Skel → List (Plan Term)
  | _, _, [] => []
  | π, i, s :: ss => Skel.plan σ (π ++ [i]) s :: Skel.planList σ π (i + 1) ss
end

/-- An equation without solutions, for a node given the wrong number of children. -/
def unsolvable : Term × Term := (.app "nil" [], .app "cons" [])

mutual
/-- The equations under which the skeleton at path `π` produces an instance
of `Q`. A `map` node at `π` asks its body for the pattern `ren π 0`. -/
def Skel.eqs : List Nat → Skel → Term → Equations
  | _, .given t, Q => [(Q, t)]
  | π, .apply d ss, Q =>
    (Q, Term.subst (ren π) d.output) :: Skel.eqsList π 0 ss (d.inputs.map (Term.subst (ren π)))
  | π, .map a b s, Q =>
    (Q, seq (ren π 0)) :: (Skel.eqs (π ++ [1]) s (seq a) ++ Skel.eqs (π ++ [0]) b (ren π 0))

def Skel.eqsList : List Nat → Nat → List Skel → List Term → Equations
  | _, _, [], [] => []
  | π, i, s :: ss, Q :: Qs => Skel.eqs (π ++ [i]) s Q ++ Skel.eqsList π (i + 1) ss Qs
  | _, _, [], _ :: _ => [unsolvable]
  | _, _, _ :: _, [] => [unsolvable]
end

mutual
/-- The contracts of the plan of a skeleton. -/
def Skel.contracts (σ : Nat → Term) : List Nat → Skel → List (Contract Term)
  | _, .given _ => []
  | π, .apply d ss =>
    Contract.subst σ (Contract.subst (ren π) d) :: Skel.contractsList σ π 0 ss
  | π, .map _ b s => Skel.contracts σ (π ++ [0]) b ++ Skel.contracts σ (π ++ [1]) s

def Skel.contractsList (σ : Nat → Term) : List Nat → Nat → List Skel → List (Contract Term)
  | _, _, [] => []
  | π, i, s :: ss => Skel.contracts σ (π ++ [i]) s ++ Skel.contractsList σ π (i + 1) ss
end

mutual
/-- A skeleton over `lib` and `avail`: available types at its leaves,
installed contracts at its nodes, and ground `map` elements. -/
def Skel.WF (lib : List (Contract Term)) : List Term → Skel → Prop
  | avail, .given t => t ∈ avail
  | avail, .apply d ss => d ∈ lib ∧ Skel.WFList lib avail ss
  | avail, .map a b s => vars a = ∅ ∧ Skel.WF lib [a] b ∧ Skel.WF lib avail s

def Skel.WFList (lib : List (Contract Term)) : List Term → List Skel → Prop
  | _, [] => True
  | avail, s :: ss => Skel.WF lib avail s ∧ Skel.WFList lib avail ss
end

/-- A type without variables. -/
def Ground (t : Term) : Prop := vars t = ∅

theorem subst_ground {t : Term} (h : Ground t) (σ : Nat → Term) : subst σ t = t := by
  have := subst_eq_of_vars (σ := σ) (τ := Term.var) (t := t) (by simp [Ground] at h; simp [h])
  rwa [subst_id] at this

theorem ground_seq {a : Term} : Ground (seq a) ↔ Ground a := by
  show vars (.app "seq" [a]) = ∅ ↔ vars a = ∅
  simp [vars, varsList]

theorem subst_ren (σ : Nat → Term) (π : List Nat) (t : Term) :
    subst σ (subst (ren π) t) = subst (fun n => σ (renVar π n)) t := by
  rw [subst_subst]
  congr 1
  funext n
  rw [ren, subst_var]

theorem unsolvable_not_unifies (σ : Nat → Term) : subst σ unsolvable.1 ≠ subst σ unsolvable.2 := by
  simp [unsolvable, subst_app]

theorem not_unifies_unsolvable {σ : Nat → Term} {E : Equations} (h : unsolvable ∈ E) :
    ¬ Unifies σ E :=
  fun hu => unsolvable_not_unifies σ (hu _ h)

section Soundness

variable {lib : List (Contract Term)} {σ : Nat → Term}

mutual
/-- **Solutions type the skeleton.** -/
theorem Skel.sound {L : List (Contract Term)} :
    {avail : List Term} → {π : List Nat} → (s : Skel) → {Q : Term} →
    (∀ t ∈ avail, Ground t) → Skel.WF lib avail s → Unifies σ (s.eqs π Q) →
    (∀ c ∈ s.contracts σ π, c ∈ L) → WellTyped L avail (s.plan σ π) (subst σ Q)
  | _, _, .given t, Q, hav, hwf, hu, _ => by
    have h := hu (Q, t) (by simp [Skel.eqs])
    simp only at h
    rw [h, subst_ground (hav t hwf), Skel.plan]
    exact .given hwf
  | _, π, .apply d ss, Q, hav, hwf, hu, hsub => by
    simp only [Skel.eqs] at hu
    rw [unifies_cons] at hu
    simp only [Skel.contracts] at hsub
    rw [hu.1, Skel.plan]
    exact .apply (hsub _ (List.mem_cons_self ..))
      (Skel.soundList ss hav hwf.2 hu.2 fun c hc => hsub c (List.mem_cons_of_mem _ hc))
  | _, π, .map a b s, Q, hav, hwf, hu, hsub => by
    simp only [Skel.eqs] at hu
    rw [unifies_cons, unifies_append] at hu
    simp only [Skel.contracts, List.mem_append] at hsub
    obtain ⟨ha, hb, hs⟩ := hwf
    have hsrc := Skel.sound s hav hs hu.2.1 fun c hc => hsub c (.inr hc)
    have hbody := Skel.sound b (fun t ht => by rw [List.mem_singleton.mp ht]; exact ha) hb
      hu.2.2 fun c hc => hsub c (.inl hc)
    rw [Term.subst_seq, subst_ground ha] at hsrc
    rw [hu.1, Term.subst_seq, Skel.plan]
    exact .map hbody hsrc

theorem Skel.soundList {L : List (Contract Term)} :
    {avail : List Term} → {π : List Nat} → {i : Nat} → (ss : List Skel) → {Qs : List Term} →
    (∀ t ∈ avail, Ground t) → Skel.WFList lib avail ss → Unifies σ (Skel.eqsList π i ss Qs) →
    (∀ c ∈ Skel.contractsList σ π i ss, c ∈ L) →
    WellTypedArgs L avail (Skel.planList σ π i ss) (Qs.map (subst σ))
  | _, _, _, [], [], _, _, _, _ => by simp [Skel.planList]; exact .nil
  | _, _, _, [], _ :: _, _, _, hu, _ =>
    absurd hu (not_unifies_unsolvable (by simp [Skel.eqsList]))
  | _, _, _, _ :: _, [], _, _, hu, _ =>
    absurd hu (not_unifies_unsolvable (by simp [Skel.eqsList]))
  | _, π, i, s :: ss, Q :: Qs, hav, hwf, hu, hsub => by
    simp only [Skel.eqsList] at hu
    rw [unifies_append] at hu
    simp only [Skel.contractsList, List.mem_append] at hsub
    rw [Skel.planList, List.map_cons]
    exact .cons (Skel.sound s hav hwf.1 hu.1 fun c hc => hsub c (.inl hc))
      (Skel.soundList ss hav hwf.2 hu.2 fun c hc => hsub c (.inr hc))
end

mutual
/-- The contracts of a skeleton's plan are instances of installed contracts. -/
theorem Skel.contracts_instances :
    {avail : List Term} → {π : List Nat} → (s : Skel) → Skel.WF lib avail s →
    ∀ c ∈ s.contracts σ π, InstanceOf lib c
  | _, _, .given _, _ => by simp [Skel.contracts]
  | _, π, .apply d ss, hwf => by
    intro c hc
    simp only [Skel.contracts, List.mem_cons] at hc
    rcases hc with rfl | hc
    · exact ⟨d, hwf.1, _, Contract.subst_subst σ (ren π) d⟩
    · exact Skel.contractsList_instances ss hwf.2 c hc
  | _, _, .map _ b s, hwf => by
    intro c hc
    simp only [Skel.contracts, List.mem_append] at hc
    rcases hc with hc | hc
    · exact Skel.contracts_instances b hwf.2.1 c hc
    · exact Skel.contracts_instances s hwf.2.2 c hc

theorem Skel.contractsList_instances :
    {avail : List Term} → {π : List Nat} → {i : Nat} → (ss : List Skel) →
    Skel.WFList lib avail ss → ∀ c ∈ Skel.contractsList σ π i ss, InstanceOf lib c
  | _, _, _, [], _ => by simp [Skel.contractsList]
  | _, _, _, s :: ss, hwf => by
    intro c hc
    simp only [Skel.contractsList, List.mem_append] at hc
    rcases hc with hc | hc
    · exact Skel.contracts_instances s hwf.1 c hc
    · exact Skel.contractsList_instances ss hwf.2 c hc
end

end Soundness

section Generality

variable {lib : List (Contract Term)}

mutual
theorem Skel.plan_subst (σ θ : Nat → Term) :
    {avail : List Term} → {π : List Nat} → (s : Skel) → (∀ t ∈ avail, Ground t) →
    Skel.WF lib avail s →
    Plan.subst σ (s.plan θ π) = s.plan (fun x => subst σ (θ x)) π
  | _, _, .given t, hav, hwf => by
    rw [Skel.plan, Plan.subst, subst_ground (hav t hwf), Skel.plan]
  | _, π, .apply d ss, hav, hwf => by
    rw [Skel.plan, Plan.subst_apply, Skel.plan, Contract.subst_subst,
      Skel.planList_subst σ θ ss hav hwf.2]
  | _, π, .map a b s, hav, hwf => by
    rw [Skel.plan, Plan.subst, subst_ground hwf.1,
      Skel.plan_subst σ θ b (fun t ht => by rw [List.mem_singleton.mp ht]; exact hwf.1) hwf.2.1,
      Skel.plan_subst σ θ s hav hwf.2.2, Skel.plan]

theorem Skel.planList_subst (σ θ : Nat → Term) :
    {avail : List Term} → {π : List Nat} → {i : Nat} → (ss : List Skel) →
    (∀ t ∈ avail, Ground t) → Skel.WFList lib avail ss →
    (Skel.planList θ π i ss).map (Plan.subst σ) = Skel.planList (fun x => subst σ (θ x)) π i ss
  | _, _, _, [], _, _ => by simp [Skel.planList]
  | _, _, _, s :: ss, hav, hwf => by
    rw [Skel.planList, List.map_cons, Skel.plan_subst σ θ s hav hwf.1,
      Skel.planList_subst σ θ ss hav hwf.2, Skel.planList]
end

/-- **Most general typing.** If a skeleton's equations have a solution,
their most general unifier types it, over instances of installed contracts,
and every solution's plan is a substitution instance of that plan. -/
theorem Skel.most_general {avail : List Term} {π : List Nat} {s : Skel} {Q : Term}
    (hav : ∀ t ∈ avail, Ground t) (hwf : s.WF lib avail) (hu : ∃ τ, Unifies τ (s.eqs π Q)) :
    ∃ θ, IsMGU θ (s.eqs π Q) ∧ (∀ c ∈ s.contracts θ π, InstanceOf lib c) ∧
      WellTyped (s.contracts θ π) avail (s.plan θ π) (subst θ Q) ∧
      ∀ σ, Unifies σ (s.eqs π Q) →
        s.plan σ π = Plan.subst σ (s.plan θ π) ∧ subst σ Q = subst σ (subst θ Q) := by
  obtain ⟨θ, hθ⟩ := mgu_exists _ hu
  refine ⟨θ, hθ, s.contracts_instances hwf, s.sound hav hwf hθ.1 fun _ h => h, fun σ hσ => ?_⟩
  have hfac : (fun x => subst σ (θ x)) = σ := funext fun x => (hθ.2 σ hσ x).symm
  refine ⟨?_, (subst_absorb (hθ.2 σ hσ) Q).symm⟩
  rw [s.plan_subst σ θ hav hwf, hfac]

end Generality

section Completeness

variable {lib : List (Contract Term)}

/-- A contract without variables. -/
def Contract.Ground (c : Contract Term) : Prop := (∀ t ∈ c.inputs, NCA.Ground t) ∧ NCA.Ground c.output

mutual
/-- Over ground contracts and ground available types, every type a plan
produces is ground. -/
theorem WellTyped.ground {L : List (Contract Term)} (hL : ∀ c ∈ L, c.Ground) :
    {avail : List Term} → {p : Plan Term} → {t : Term} → (∀ a ∈ avail, Ground a) →
    WellTyped L avail p t → Ground t
  | _, _, _, hav, .given h => hav _ h
  | _, _, _, _, .apply hc _ => (hL _ hc).2
  | _, _, _, hav, .map hbody hsrc => by
    have ha := ground_seq.mp (WellTyped.ground hL hav hsrc)
    exact ground_seq.mpr (WellTyped.ground hL (fun x hx => by
      rw [List.mem_singleton.mp hx]; exact ha) hbody)
end

theorem take_path (π r : List Nat) (j : Nat) : (π ++ j :: r).take (π.length + 1) = π ++ [j] := by
  simp [List.take_append]

theorem path_ne (π r : List Nat) (j : Nat) : π ++ j :: r ≠ π := by
  intro h
  have := congrArg List.length h
  simp at this

theorem path_inj {π : List Nat} {i j : Nat} (h : π ++ [j] = π ++ [i]) : j = i := by
  simpa using h

/-- The statement proved for each plan by `Skel.complete_at`: a skeleton
and an instantiation `ρ` of its nodes, by path, such that every substitution
agreeing with `ρ` on the nodes below `π` reproduces the plan and solves its
equations for every pattern it instantiates to the plan's type. -/
def Fits (lib : List (Contract Term)) (avail : List Term) (π : List Nat) (p : Plan Term)
    (T : Term) : Prop :=
  ∃ s : Skel, ∃ ρ : List Nat → Nat → Term, s.WF lib avail ∧
    ∀ σ : Nat → Term, (∀ r n, σ (renVar (π ++ r) n) = ρ (π ++ r) n) →
      s.plan σ π = p ∧ ∀ Q, subst σ Q = T → Unifies σ (s.eqs π Q)

/-- `Fits` for the arguments of a node at `π`, from child index `i` on. -/
def FitsList (lib : List (Contract Term)) (avail : List Term) (π : List Nat) (i : Nat)
    (ps : List (Plan Term)) (Ts : List Term) : Prop :=
  ∃ ss : List Skel, ∃ ρ : List Nat → Nat → Term, Skel.WFList lib avail ss ∧
    ∀ σ : Nat → Term, (∀ j r n, i ≤ j → σ (renVar (π ++ j :: r) n) = ρ (π ++ j :: r) n) →
      Skel.planList σ π i ss = ps ∧
        ∀ Qs, Qs.map (subst σ) = Ts → Unifies σ (Skel.eqsList π i ss Qs)

mutual
theorem Skel.complete_at {L : List (Contract Term)} (hinst : ∀ c ∈ L, InstanceOf lib c)
    (hL : ∀ c ∈ L, c.Ground) :
    {avail : List Term} → {p : Plan Term} → {T : Term} → (∀ a ∈ avail, Ground a) →
    WellTyped L avail p T → ∀ π, Fits lib avail π p T
  | _, _, _, hav, .given (t := t) ht, π => by
    refine ⟨.given t, fun _ _ => .var 0, ht, fun σ _ => ⟨rfl, fun Q hQ => ?_⟩⟩
    intro e he
    simp only [Skel.eqs, List.mem_singleton] at he
    subst he
    rw [hQ, subst_ground (hav t ht)]
  | _, _, _, hav, .apply (c := c) hc hargs, π => by
    obtain ⟨d, hd, τ, rfl⟩ := hinst c hc
    obtain ⟨ss, ρ, hwf, hfit⟩ := Skel.completeList_at hinst hL hav hargs π 0
    refine ⟨.apply d ss, fun q n => if q = π then τ n else ρ q n, ⟨hd, hwf⟩, fun σ hσ => ?_⟩
    have hnode : (fun n => σ (renVar π n)) = τ := funext fun n => by
      simpa using hσ [] n
    have hd' : Contract.subst σ (Contract.subst (ren π) d) = Contract.subst τ d := by
      rw [Contract.subst_subst, ← hnode]
      congr 1
      funext n
      rw [ren, subst_var]
    have hch : ∀ j r n, 0 ≤ j → σ (renVar (π ++ j :: r) n) = ρ (π ++ j :: r) n := by
      intro j r n _
      have := hσ (j :: r) n
      simp only [if_neg (path_ne π r j)] at this
      exact this
    obtain ⟨hplan, heqs⟩ := hfit σ hch
    refine ⟨by rw [Skel.plan, hd', hplan], fun Q hQ => ?_⟩
    simp only [Skel.eqs]
    refine unifies_cons.mpr ⟨?_, heqs _ ?_⟩
    · rw [hQ, subst_ren, hnode]
      rfl
    · rw [List.map_map]
      show d.inputs.map (fun t => subst σ (subst (ren π) t)) = d.inputs.map (Term.subst τ)
      exact List.map_congr_left fun t _ => by rw [subst_ren, hnode]
  | _, _, _, hav, .map (a := a) (e := e) hbody hsrc, π => by
    have ha : Ground a := ground_seq.mp (WellTyped.ground hL hav hsrc)
    have hav' : ∀ x ∈ [a], Ground x := fun x hx => by rw [List.mem_singleton.mp hx]; exact ha
    obtain ⟨sb, ρb, hwfb, hfb⟩ := Skel.complete_at hinst hL hav' hbody (π ++ [0])
    obtain ⟨sr, ρr, hwfr, hfr⟩ := Skel.complete_at hinst hL hav hsrc (π ++ [1])
    refine ⟨.map a sb sr,
      fun q n => if q = π then e else if q.take (π.length + 1) = π ++ [0] then ρb q n
        else ρr q n,
      ⟨ha, hwfb, hwfr⟩, fun σ hσ => ?_⟩
    have hv : σ (renVar π 0) = e := by simpa using hσ [] 0
    have hb := hfb σ fun r n => by
      have := hσ (0 :: r) n
      simp only [if_neg (path_ne π r 0), if_pos (take_path π r 0)] at this
      simpa using this
    have hr := hfr σ fun r n => by
      have := hσ (1 :: r) n
      simp only [if_neg (path_ne π r 1), take_path π r 1,
        if_neg (fun h => absurd (path_inj h) (by omega) : ¬ π ++ [1] = π ++ [0])] at this
      simpa using this
    refine ⟨by rw [Skel.plan, hb.1, hr.1], fun Q hQ => ?_⟩
    simp only [Skel.eqs]
    refine unifies_cons.mpr ⟨?_, unifies_append.mpr ⟨hr.2 _ ?_, hb.2 _ ?_⟩⟩
    · rw [hQ, Term.subst_seq, ren, subst_var, hv]
    · rw [Term.subst_seq, subst_ground ha]
    · rw [ren, subst_var, hv]

theorem Skel.completeList_at {L : List (Contract Term)} (hinst : ∀ c ∈ L, InstanceOf lib c)
    (hL : ∀ c ∈ L, c.Ground) :
    {avail : List Term} → {ps : List (Plan Term)} → {Ts : List Term} →
    (∀ a ∈ avail, Ground a) → WellTypedArgs L avail ps Ts →
    ∀ π i, FitsList lib avail π i ps Ts
  | _, _, _, _, .nil, π, i => by
    refine ⟨[], fun _ _ => .var 0, trivial, fun σ _ => ⟨rfl, fun Qs hQs => ?_⟩⟩
    rw [List.map_eq_nil_iff.mp hQs]
    simp [Skel.eqsList, Unifies]
  | _, _, _, hav, .cons hp hps, π, i => by
    obtain ⟨s, ρ₁, hwf₁, hf₁⟩ := Skel.complete_at hinst hL hav hp (π ++ [i])
    obtain ⟨ss, ρ₂, hwf₂, hf₂⟩ := Skel.completeList_at hinst hL hav hps π (i + 1)
    refine ⟨s :: ss, fun q n => if q.take (π.length + 1) = π ++ [i] then ρ₁ q n else ρ₂ q n,
      ⟨hwf₁, hwf₂⟩, fun σ hσ => ?_⟩
    have h₁ := hf₁ σ fun r n => by
      have := hσ i r n le_rfl
      simp only [if_pos (take_path π r i)] at this
      simpa using this
    have h₂ := hf₂ σ fun j r n hj => by
      have := hσ j r n (by omega)
      simp only [take_path π r j,
        if_neg (fun h => absurd (path_inj h) (by omega) : ¬ π ++ [j] = π ++ [i])] at this
      exact this
    refine ⟨by rw [Skel.planList, h₁.1, h₂.1], fun Qs hQs => ?_⟩
    match Qs, hQs with
    | Q :: Qs, hQs =>
      simp only [List.map_cons, List.cons.injEq] at hQs
      simp only [Skel.eqsList]
      exact unifies_append.mpr ⟨h₁.2 Q hQs.1, h₂.2 Qs hQs.2⟩
end

/-- **Every plan is found through its skeleton.** A ground plan producing an
instance `θ₀(P)` of a pattern whose variables are even, over ground instances
of installed contracts and ground available types, is the plan of its
skeleton at a solution of the skeleton's equations that agrees with `θ₀` on
the pattern. -/
theorem Skel.complete {L : List (Contract Term)} {avail : List Term} {p : Plan Term}
    {P : Term} {θ₀ : Nat → Term} (hinst : ∀ c ∈ L, InstanceOf lib c) (hL : ∀ c ∈ L, c.Ground)
    (hav : ∀ a ∈ avail, Ground a) (hP : ∀ x ∈ vars P, x % 2 = 0)
    (h : WellTyped L avail p (subst θ₀ P)) :
    ∃ s : Skel, ∃ σ : Nat → Term, s.WF lib avail ∧ s.plan σ [] = p ∧ Unifies σ (s.eqs [] P) ∧
      ∀ x ∈ vars P, σ x = θ₀ x := by
  obtain ⟨s, ρ, hwf, hfit⟩ := Skel.complete_at hinst hL hav h []
  let σ : Nat → Term := fun m =>
    if m % 2 = 1 then
      match Encodable.decode (α := List Nat × Nat) (m / 2) with
      | some (q, n) => ρ q n
      | none => .var m
    else θ₀ m
  have hσ : ∀ r n, σ (renVar ([] ++ r) n) = ρ ([] ++ r) n := by
    intro r n
    have h1 : (2 * Encodable.encode (r, n) + 1) % 2 = 1 := by omega
    have h2 : (2 * Encodable.encode (r, n) + 1) / 2 = Encodable.encode (r, n) := by omega
    simp only [List.nil_append, renVar, σ, if_pos h1, h2, Encodable.encodek]
  have hagree : ∀ x ∈ vars P, σ x = θ₀ x := fun x hx => by
    simp only [σ, if_neg (by have := hP x hx; omega : ¬ x % 2 = 1)]
  obtain ⟨hplan, heqs⟩ := hfit σ hσ
  refine ⟨s, σ, hwf, hplan, heqs P ?_, hagree⟩
  exact subst_eq_of_vars P fun x hx => hagree x hx

end Completeness

/-- Solving a list of equation blocks one after another: each block with the
substitution found so far applied, solved most generally, and composed. -/
inductive SeqMGU : List Equations → (Nat → Term) → Prop
  | nil : SeqMGU [] Term.var
  | snoc {Es : List Equations} {E : Equations} {Θ θ : Nat → Term} :
      SeqMGU Es Θ → IsMGU θ (eqSubst Θ E) → SeqMGU (Es ++ [E]) (fun x => subst θ (Θ x))

/-- **Sequential solving is most general.** -/
theorem SeqMGU.isMGU {Es : List Equations} {Θ : Nat → Term} (h : SeqMGU Es Θ) :
    IsMGU Θ Es.flatten := by
  induction h with
  | nil => exact ⟨fun _ hp => by simp at hp, fun τ _ x => by rw [subst_var]⟩
  | snoc _ hθ ih =>
    rw [List.flatten_append, List.flatten_singleton]
    exact isMGU_append ih hθ

/-- **Sequential solving never fails while a solution exists.** -/
theorem SeqMGU.exists {Es : List Equations} (h : ∃ τ, Unifies τ Es.flatten) :
    ∃ Θ, SeqMGU Es Θ := by
  induction Es using List.reverseRecOn with
  | nil => exact ⟨_, .nil⟩
  | append_singleton Es E ih =>
    obtain ⟨τ, hτ⟩ := h
    rw [List.flatten_append, List.flatten_singleton] at hτ
    obtain ⟨Θ, hΘ⟩ := ih ⟨τ, (unifies_append.mp hτ).1⟩
    obtain ⟨θ, hθ⟩ := mgu_exists _ ⟨τ, unifies_eqSubst hΘ.isMGU hτ⟩
    exact ⟨_, .snoc hΘ hθ⟩

end NCA
