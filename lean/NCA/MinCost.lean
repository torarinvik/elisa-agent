import NCA.Cost
import NCA.Loading

/-!
# Minimum-cost planning

`planMin` returns, for each goal, a plan of least cost among all plans the
planner can express within its depth bound: a Bellman-style recursion that
keeps the cheapest candidate at every type. It is sound (well-typed, with the
reported cost) and optimal against every *searchable* plan of smaller depth,
where searchable plans are those whose map elements are candidate element
types, the space the planner enumerates.
-/

namespace NCA

variable {Ty : Type} [DecidableEq Ty] [SeqTypes Ty]
open SeqTypes

mutual
/-- Depth of a plan (a `given` has depth 0). -/
def Plan.depth : Plan Ty → Nat
  | .given _ => 0
  | .apply _ ps => Plan.depthArgs ps + 1
  | .map _ body src => max body.depth src.depth + 1

/-- Largest depth in a list of plans. -/
def Plan.depthArgs : List (Plan Ty) → Nat
  | [] => 0
  | p :: ps => max p.depth (Plan.depthArgs ps)
end

mutual
/-- Well-typed plans whose map elements are candidate element types. -/
inductive Searchable (lib : List (Contract Ty)) : List Ty → Plan Ty → Ty → Prop
  | given {avail : List Ty} {t : Ty} : t ∈ avail → Searchable lib avail (.given t) t
  | apply {avail : List Ty} {c : Contract Ty} {ps : List (Plan Ty)} :
      c ∈ lib → SearchableArgs lib avail ps c.inputs →
      Searchable lib avail (.apply c ps) c.output
  | map {avail : List Ty} {a e : Ty} {body src : Plan Ty} :
      a ∈ elemCandidates lib avail → Searchable lib [a] body e →
      Searchable lib avail src (seq a) → Searchable lib avail (.map a body src) (seq e)

/-- Pointwise `Searchable` for argument lists. -/
inductive SearchableArgs (lib : List (Contract Ty)) :
    List Ty → List (Plan Ty) → List Ty → Prop
  | nil {avail : List Ty} : SearchableArgs lib avail [] []
  | cons {avail : List Ty} {p : Plan Ty} {ps : List (Plan Ty)} {t : Ty} {ts : List Ty} :
      Searchable lib avail p t → SearchableArgs lib avail ps ts →
      SearchableArgs lib avail (p :: ps) (t :: ts)
end

/-- The cheapest entry of a list of costed plans (the first among ties). -/
def best : List (Plan Ty × Nat) → Option (Plan Ty × Nat)
  | [] => none
  | x :: xs =>
    match best xs with
    | none => some x
    | some y => if x.2 ≤ y.2 then some x else some y

omit [DecidableEq Ty] [SeqTypes Ty] in
theorem best_mem : ∀ {l : List (Plan Ty × Nat)} {y : Plan Ty × Nat},
    best l = some y → y ∈ l
  | [], _, h => by simp [best] at h
  | x :: xs, y, h => by
    unfold best at h
    cases hb : best xs with
    | none => simp [hb] at h; simp [h]
    | some z =>
      simp only [hb] at h
      split at h
      · cases h; simp
      · cases h; exact List.mem_cons_of_mem _ (best_mem hb)

omit [DecidableEq Ty] [SeqTypes Ty] in
theorem best_le : ∀ {l : List (Plan Ty × Nat)} {x : Plan Ty × Nat},
    x ∈ l → ∃ y, best l = some y ∧ y.2 ≤ x.2
  | x' :: xs, x, hx => by
    unfold best
    rcases List.mem_cons.mp hx with rfl | hx
    · cases hb : best xs with
      | none => exact ⟨x, rfl, le_refl _⟩
      | some z =>
        by_cases hle : x.2 ≤ z.2
        · exact ⟨x, by simp [hle], le_refl _⟩
        · exact ⟨z, by simp [hle], by omega⟩
    · obtain ⟨z, hz, hzx⟩ := best_le hx
      rw [hz]
      by_cases hle : x'.2 ≤ z.2
      · exact ⟨x', by simp [hle], by omega⟩
      · exact ⟨z, by simp [hle], hzx⟩

/-- Cheapest plan for `t` within depth `fuel`, with its cost, for per-invocation
costs `κ` and sequence length `L`. -/
def planMin (lib : List (Contract Ty)) (κ : Contract Ty → Nat) (L : Nat) :
    List Ty → Nat → Ty → Option (Plan Ty × Nat)
  | _, 0, _ => none
  | avail, n + 1, t =>
    if t ∈ avail then some (.given t, 0)
    else
      best (lib.filterMap (fun c =>
          if c.output = t then
            (traverse (planMin lib κ L avail n) c.inputs).map fun pcs =>
              (.apply c (pcs.map Prod.fst), κ c + (pcs.map Prod.snd).sum)
          else none) ++
        match elem? t with
        | none => []
        | some e => (elemCandidates lib avail).filterMap fun a =>
            match planMin lib κ L [a] n e, planMin lib κ L avail n (seq a) with
            | some (b, cb), some (s, cs) => some (.map a b s, L * cb + cs)
            | _, _ => none)

omit [DecidableEq Ty] [SeqTypes Ty] in
theorem costArgs_map_fst (κ : Contract Ty → Nat) (L : Nat) :
    ∀ (pcs : List (Plan Ty × Nat)), (∀ x ∈ pcs, x.1.cost κ L = x.2) →
      Plan.costArgs κ L (pcs.map Prod.fst) = (pcs.map Prod.snd).sum
  | [], _ => by simp [Plan.costArgs]
  | x :: xs, h => by
    simp only [List.map_cons, Plan.costArgs, List.sum_cons]
    rw [h x List.mem_cons_self, costArgs_map_fst κ L xs fun y hy => h y (List.mem_cons_of_mem _ hy)]

omit [DecidableEq Ty] in
theorem traverse_costed {lib : List (Contract Ty)} {avail : List Ty} {κ : Contract Ty → Nat}
    {L : Nat} {f : Ty → Option (Plan Ty × Nat)}
    (hsound : ∀ i x, f i = some x → WellTyped lib avail x.1 i ∧ x.1.cost κ L = x.2) :
    ∀ {ts : List Ty} {pcs : List (Plan Ty × Nat)}, traverse f ts = some pcs →
      WellTypedArgs lib avail (pcs.map Prod.fst) ts ∧ ∀ x ∈ pcs, x.1.cost κ L = x.2
  | [], pcs, h => by simp [traverse] at h; subst h; exact ⟨.nil, by simp⟩
  | t :: ts, pcs, h => by
    cases hp : f t <;> cases hr : traverse f ts <;> simp [traverse, hp, hr] at h
    subst h
    obtain ⟨hw, hc⟩ := traverse_costed hsound hr
    refine ⟨.cons (hsound _ _ hp).1 hw, ?_⟩
    intro x hx
    rcases List.mem_cons.mp hx with rfl | hx
    · exact (hsound _ _ hp).2
    · exact hc x hx

/-- **Soundness.** `planMin` returns a well-typed plan together with its cost. -/
theorem planMin_sound (lib : List (Contract Ty)) (κ : Contract Ty → Nat) (L : Nat) :
    ∀ (n : Nat) (avail : List Ty) (t : Ty) (q : Plan Ty) (c : Nat),
      planMin lib κ L avail n t = some (q, c) → WellTyped lib avail q t ∧ q.cost κ L = c
  | 0, _, _, _, _, h => by simp [planMin] at h
  | n + 1, avail, t, q, cost, h => by
    unfold planMin at h
    split at h
    next ht =>
      cases h
      exact ⟨.given ht, rfl⟩
    next =>
      have hmem := best_mem h
      rcases List.mem_append.mp hmem with hmem | hmem
      · obtain ⟨c, hc, hf⟩ := List.mem_filterMap.mp hmem
        split at hf
        next heq =>
          cases hr : traverse (planMin lib κ L avail n) c.inputs with
          | none => simp [hr] at hf
          | some pcs =>
            simp only [hr, Option.map_some, Option.some.injEq, Prod.mk.injEq] at hf
            obtain ⟨rfl, rfl⟩ := hf
            subst heq
            have hsound : ∀ i x, planMin lib κ L avail n i = some x →
                WellTyped lib avail x.1 i ∧ x.1.cost κ L = x.2 :=
              fun i x hx => planMin_sound lib κ L n avail i x.1 x.2 hx
            obtain ⟨hw, hcost⟩ := traverse_costed hsound hr
            refine ⟨.apply hc hw, ?_⟩
            simp only [Plan.cost]
            rw [costArgs_map_fst κ L pcs hcost]
        next => simp at hf
      · cases he : elem? t with
        | none => simp [he] at hmem
        | some e =>
          simp only [he] at hmem
          obtain ⟨a, _, hf⟩ := List.mem_filterMap.mp hmem
          cases hb : planMin lib κ L [a] n e with
          | none => simp [hb] at hf
          | some bc =>
            cases hs : planMin lib κ L avail n (seq a) with
            | none => simp [hb, hs] at hf
            | some sc =>
              simp only [hb, hs, Option.some.injEq, Prod.mk.injEq] at hf
              obtain ⟨rfl, rfl⟩ := hf
              obtain ⟨hbw, hbc⟩ := planMin_sound lib κ L n [a] e bc.1 bc.2 hb
              obtain ⟨hsw, hsc⟩ := planMin_sound lib κ L n avail (seq a) sc.1 sc.2 hs
              rw [elem?_eq_some.mp he]
              exact ⟨.map hbw hsw, by simp [Plan.cost, hbc, hsc]⟩

omit [DecidableEq Ty] in
theorem traverse_optimal {lib : List (Contract Ty)} {avail : List Ty} {κ : Contract Ty → Nat}
    {L n : Nat} {f : Ty → Option (Plan Ty × Nat)}
    (hopt : ∀ p t, Searchable lib avail p t → p.depth < n →
      ∃ x, f t = some x ∧ x.2 ≤ p.cost κ L) :
    ∀ {ps : List (Plan Ty)} {ts : List Ty}, SearchableArgs lib avail ps ts →
      Plan.depthArgs ps < n →
      ∃ pcs, traverse f ts = some pcs ∧ (pcs.map Prod.snd).sum ≤ Plan.costArgs κ L ps
  | _, _, .nil, _ => ⟨[], rfl, by simp [Plan.costArgs]⟩
  | p :: ps, t :: ts, .cons h hs, hd => by
    simp only [Plan.depthArgs] at hd
    obtain ⟨x, hx, hxle⟩ := hopt p t h (by omega)
    obtain ⟨pcs, hr, hle⟩ := traverse_optimal hopt hs (by omega)
    refine ⟨x :: pcs, by simp [traverse, hx, hr], ?_⟩
    simp only [List.map_cons, List.sum_cons, Plan.costArgs]
    omega

omit [DecidableEq Ty] [SeqTypes Ty] in
theorem best_le_of_mem {l : List (Plan Ty × Nat)} {x : Plan Ty × Nat} {bound : Nat}
    (hx : x ∈ l) (hb : x.2 ≤ bound) : ∃ y, best l = some y ∧ y.2 ≤ bound :=
  (best_le hx).imp fun _ h => ⟨h.1, h.2.trans hb⟩

/-- **Optimality.** For every searchable plan `p` of depth below `n`, `planMin`
with fuel `n` returns a plan costing at most `p`. -/
theorem planMin_optimal (lib : List (Contract Ty)) (κ : Contract Ty → Nat) (L : Nat) :
    ∀ (n : Nat) (avail : List Ty) (t : Ty) (p : Plan Ty), Searchable lib avail p t →
      p.depth < n → ∃ x, planMin lib κ L avail n t = some x ∧ x.2 ≤ p.cost κ L
  | 0, _, _, _, _, hd => absurd hd (Nat.not_lt_zero _)
  | n + 1, avail, t, p, h, hd => by
    by_cases ht : t ∈ avail
    · exact ⟨(.given t, 0), by simp [planMin, ht], Nat.zero_le _⟩
    · have ih : ∀ A p t, Searchable lib A p t → p.depth < n →
          ∃ x, planMin lib κ L A n t = some x ∧ x.2 ≤ p.cost κ L :=
        fun A p t h hd => planMin_optimal lib κ L n A t p h hd
      cases h with
      | given hm => exact absurd hm ht
      | @apply _ c ps hc hargs =>
        simp only [Plan.depth] at hd
        obtain ⟨pcs, hr, hsum⟩ := traverse_optimal (ih avail) hargs (by omega)
        unfold planMin
        rw [if_neg ht]
        apply best_le_of_mem (x := (Plan.apply c (pcs.map Prod.fst),
          κ c + (pcs.map Prod.snd).sum))
        · apply List.mem_append_left
          rw [List.mem_filterMap]
          exact ⟨c, hc, by simp [hr]⟩
        · simp only [Plan.cost]
          omega
      | @map _ a e body src ha hb hs =>
        simp only [Plan.depth] at hd
        obtain ⟨⟨qb, cb⟩, hbq, hble⟩ := ih [a] body e hb (by omega)
        obtain ⟨⟨qs, cs⟩, hsq, hsle⟩ := ih avail src (seq a) hs (by omega)
        have he : elem? (seq e) = some e := elem?_eq_some.mpr rfl
        unfold planMin
        rw [if_neg ht]
        apply best_le_of_mem (x := (Plan.map a qb qs, L * cb + cs))
        · apply List.mem_append_right
          rw [he, List.mem_filterMap]
          exact ⟨a, ha, by simp [hbq, hsq]⟩
        · simp only [Plan.cost] at hble hsle ⊢
          exact add_le_add (Nat.mul_le_mul_left _ hble) hsle

end NCA
