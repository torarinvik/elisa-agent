import NCA.Planning.MinCost

/-!
# Cost/error Pareto planning

Each contract has a cost `κ c` and a failure rate `ε c` (in fixed units).
Both objectives are additive over invocations, with map bodies counted once
per element: a plan's error bound (the union bound of
`composition_error_le_sum`) is `p.cost ε L`, the same functional as its cost.

`planPareto` keeps, at every type, a list of options `(plan, cost, error)` from
which every dominated option has been pruned. It is sound (each option is a
well-typed plan with its reported cost and error bound) and covers the search
space: every searchable plan within the depth bound is dominated by a returned
option. Hence the cheapest returned option meeting an error target is exactly
the cheapest searchable plan meeting it.
-/

namespace NCA

variable {Ty : Type} [DecidableEq Ty] [SeqTypes Ty]
open SeqTypes

/-- A costed option: a plan, its cost, and its error bound. -/
abbrev Option3 (Ty : Type) := Plan Ty × Nat × Nat

/-- `y` is at least as good as `x` in both objectives. -/
def Dom (y x : Option3 Ty) : Prop := y.2.1 ≤ x.2.1 ∧ y.2.2 ≤ x.2.2

instance (y x : Option3 Ty) : Decidable (Dom y x) := by unfold Dom; infer_instance

omit [DecidableEq Ty] [SeqTypes Ty] in
theorem Dom.trans {x y z : Option3 Ty} (h₁ : Dom x y) (h₂ : Dom y z) : Dom x z :=
  ⟨h₁.1.trans h₂.1, h₁.2.trans h₂.2⟩

/-- Add `x` to a pruned list: drop it if dominated, else drop what it dominates. -/
def insertFront (x : Option3 Ty) (kept : List (Option3 Ty)) : List (Option3 Ty) :=
  if kept.any (fun y => decide (Dom y x)) then kept
  else x :: kept.filter (fun y => !decide (Dom x y))

/-- The options of `l` that survive pruning. -/
def front (l : List (Option3 Ty)) : List (Option3 Ty) := l.foldr insertFront []

omit [DecidableEq Ty] [SeqTypes Ty] in
theorem front_sub : ∀ {l : List (Option3 Ty)} {y : Option3 Ty}, y ∈ front l → y ∈ l
  | [], _, h => by simp [front] at h
  | x :: xs, y, h => by
    simp only [front, List.foldr_cons] at h
    change y ∈ insertFront x (front xs) at h
    unfold insertFront at h
    split at h
    · exact List.mem_cons_of_mem _ (front_sub h)
    · rcases List.mem_cons.mp h with rfl | h
      · exact List.mem_cons_self
      · exact List.mem_cons_of_mem _ (front_sub (List.mem_filter.mp h).1)

omit [DecidableEq Ty] [SeqTypes Ty] in
/-- **Pruning loses nothing.** Every option is dominated by a surviving one. -/
theorem front_cover : ∀ {l : List (Option3 Ty)} {x : Option3 Ty}, x ∈ l →
    ∃ y ∈ front l, Dom y x
  | x' :: xs, x, hx => by
    have step : ∀ z, (∃ y ∈ front xs, Dom y z) →
        ∃ y ∈ insertFront x' (front xs), Dom y z := by
      intro z ⟨y, hy, hyz⟩
      unfold insertFront
      split
      · exact ⟨y, hy, hyz⟩
      · by_cases hxy : Dom x' y
        · exact ⟨x', List.mem_cons_self, hxy.trans hyz⟩
        · exact ⟨y, List.mem_cons_of_mem _ (List.mem_filter.mpr ⟨hy, by simp [hxy]⟩), hyz⟩
    change ∃ y ∈ insertFront x' (front xs), Dom y x
    rcases List.mem_cons.mp hx with rfl | hx
    · unfold insertFront
      split
      next h =>
        obtain ⟨y, hy, hd⟩ := List.any_eq_true.mp h
        exact ⟨y, hy, of_decide_eq_true hd⟩
      next => exact ⟨x, List.mem_cons_self, le_refl _, le_refl _⟩
    · exact step x (front_cover hx)

/-- All ways of choosing one entry of `f t` for each `t` in a list. -/
def combos {X : Type} (f : Ty → List X) : List Ty → List (List X)
  | [] => [[]]
  | t :: ts => (f t).flatMap fun x => (combos f ts).map (x :: ·)

/-- Pareto options for `t` within depth `fuel`. -/
def planPareto (lib : List (Contract Ty)) (κ ε : Contract Ty → Nat) (L : Nat) :
    List Ty → Nat → Ty → List (Option3 Ty)
  | _, 0, _ => []
  | avail, n + 1, t =>
    if t ∈ avail then [(.given t, 0, 0)]
    else
      front (lib.flatMap (fun c =>
          if c.output = t then
            (combos (planPareto lib κ ε L avail n) c.inputs).map fun os =>
              (.apply c (os.map Prod.fst), κ c + (os.map (·.2.1)).sum,
                ε c + (os.map (·.2.2)).sum)
          else []) ++
        match elem? t with
        | none => []
        | some e => (elemCandidates lib avail).flatMap fun a =>
            (planPareto lib κ ε L [a] n e).flatMap fun b =>
              (planPareto lib κ ε L avail n (seq a)).map fun s =>
                (.map a b.1 s.1, L * b.2.1 + s.2.1, L * b.2.2 + s.2.2))

omit [DecidableEq Ty] [SeqTypes Ty] in
theorem costArgs_map (κ : Contract Ty → Nat) (L : Nat) (g : Option3 Ty → Nat) :
    ∀ (os : List (Option3 Ty)), (∀ x ∈ os, x.1.cost κ L = g x) →
      Plan.costArgs κ L (os.map Prod.fst) = (os.map g).sum
  | [], _ => by simp [Plan.costArgs]
  | x :: xs, h => by
    simp only [List.map_cons, Plan.costArgs, List.sum_cons]
    rw [h x List.mem_cons_self, costArgs_map κ L g xs fun y hy => h y (List.mem_cons_of_mem _ hy)]

/-- An option is a well-typed plan for `t` with its reported cost and error. -/
def Valid (lib : List (Contract Ty)) (κ ε : Contract Ty → Nat) (L : Nat) (avail : List Ty)
    (t : Ty) (o : Option3 Ty) : Prop :=
  WellTyped lib avail o.1 t ∧ o.1.cost κ L = o.2.1 ∧ o.1.cost ε L = o.2.2

omit [DecidableEq Ty] in
theorem combos_valid {lib : List (Contract Ty)} {κ ε : Contract Ty → Nat} {L : Nat}
    {avail : List Ty} {f : Ty → List (Option3 Ty)}
    (hf : ∀ i o, o ∈ f i → Valid lib κ ε L avail i o) :
    ∀ {ts : List Ty} {os : List (Option3 Ty)}, os ∈ combos f ts →
      WellTypedArgs lib avail (os.map Prod.fst) ts ∧ ∀ x ∈ os,
        x.1.cost κ L = x.2.1 ∧ x.1.cost ε L = x.2.2
  | [], os, h => by simp [combos] at h; subst h; exact ⟨.nil, by simp⟩
  | t :: ts, os, h => by
    simp only [combos, List.mem_flatMap, List.mem_map] at h
    obtain ⟨x, hx, rest, hrest, rfl⟩ := h
    obtain ⟨hw, hc⟩ := combos_valid hf hrest
    refine ⟨.cons (hf t x hx).1 hw, ?_⟩
    intro y hy
    rcases List.mem_cons.mp hy with rfl | hy
    · exact (hf t y hx).2
    · exact hc y hy

/-- **Soundness.** Every option is a well-typed plan with its reported cost
and error bound. -/
theorem planPareto_sound (lib : List (Contract Ty)) (κ ε : Contract Ty → Nat) (L : Nat) :
    ∀ (n : Nat) (avail : List Ty) (t : Ty) (o : Option3 Ty),
      o ∈ planPareto lib κ ε L avail n t → Valid lib κ ε L avail t o
  | 0, _, _, _, h => by simp [planPareto] at h
  | n + 1, avail, t, o, h => by
    unfold planPareto at h
    split at h
    next ht =>
      simp only [List.mem_singleton] at h
      subst h
      exact ⟨.given ht, rfl, rfl⟩
    next =>
      have ih : ∀ A i o, o ∈ planPareto lib κ ε L A n i → Valid lib κ ε L A i o :=
        fun A i o h => planPareto_sound lib κ ε L n A i o h
      rcases List.mem_append.mp (front_sub h) with hmem | hmem
      · obtain ⟨c, hc, hf⟩ := List.mem_flatMap.mp hmem
        split at hf
        next heq =>
          obtain ⟨os, hos, rfl⟩ := List.mem_map.mp hf
          subst heq
          obtain ⟨hw, hcost⟩ := combos_valid (ih avail) hos
          refine ⟨.apply hc hw, ?_, ?_⟩
          · simp only [Plan.cost]
            rw [costArgs_map κ L (·.2.1) os fun x hx => (hcost x hx).1]
          · simp only [Plan.cost]
            rw [costArgs_map ε L (·.2.2) os fun x hx => (hcost x hx).2]
        next => simp at hf
      · cases he : elem? t with
        | none => simp [he] at hmem
        | some e =>
          simp only [he, List.mem_flatMap, List.mem_map] at hmem
          obtain ⟨a, _, b, hb, s, hs, rfl⟩ := hmem
          obtain ⟨hbw, hbc, hbe⟩ := ih [a] e b hb
          obtain ⟨hsw, hsc, hse⟩ := ih avail (seq a) s hs
          rw [elem?_eq_some.mp he]
          exact ⟨.map hbw hsw, by simp [Plan.cost, hbc, hsc], by simp [Plan.cost, hbe, hse]⟩

omit [DecidableEq Ty] in
theorem combos_cover {lib : List (Contract Ty)} {avail : List Ty} {κ ε : Contract Ty → Nat}
    {L n : Nat} {f : Ty → List (Option3 Ty)}
    (hcov : ∀ p t, Searchable lib avail p t → p.depth < n →
      ∃ o ∈ f t, o.2.1 ≤ p.cost κ L ∧ o.2.2 ≤ p.cost ε L) :
    ∀ {ps : List (Plan Ty)} {ts : List Ty}, SearchableArgs lib avail ps ts →
      Plan.depthArgs ps < n →
      ∃ os ∈ combos f ts, (os.map (·.2.1)).sum ≤ Plan.costArgs κ L ps ∧
        (os.map (·.2.2)).sum ≤ Plan.costArgs ε L ps
  | _, _, .nil, _ => ⟨[], by simp [combos], by simp [Plan.costArgs], by simp [Plan.costArgs]⟩
  | p :: ps, t :: ts, .cons h hs, hd => by
    simp only [Plan.depthArgs] at hd
    obtain ⟨o, ho, hoc, hoe⟩ := hcov p t h (by omega)
    obtain ⟨os, hos, hc, he⟩ := combos_cover hcov hs (by omega)
    refine ⟨o :: os, ?_, ?_, ?_⟩
    · simp only [combos, List.mem_flatMap, List.mem_map]
      exact ⟨o, ho, os, hos, rfl⟩
    · simp only [List.map_cons, List.sum_cons, Plan.costArgs]; omega
    · simp only [List.map_cons, List.sum_cons, Plan.costArgs]; omega

/-- **Coverage.** Every searchable plan of depth below `n` is dominated, in
both cost and error bound, by an option `planPareto` returns with fuel `n`. -/
theorem planPareto_cover (lib : List (Contract Ty)) (κ ε : Contract Ty → Nat) (L : Nat) :
    ∀ (n : Nat) (avail : List Ty) (t : Ty) (p : Plan Ty), Searchable lib avail p t →
      p.depth < n → ∃ o ∈ planPareto lib κ ε L avail n t,
        o.2.1 ≤ p.cost κ L ∧ o.2.2 ≤ p.cost ε L
  | 0, _, _, _, _, hd => absurd hd (Nat.not_lt_zero _)
  | n + 1, avail, t, p, h, hd => by
    by_cases ht : t ∈ avail
    · exact ⟨(.given t, 0, 0), by simp [planPareto, ht], Nat.zero_le _, Nat.zero_le _⟩
    · have ih : ∀ A p t, Searchable lib A p t → p.depth < n →
          ∃ o ∈ planPareto lib κ ε L A n t, o.2.1 ≤ p.cost κ L ∧ o.2.2 ≤ p.cost ε L :=
        fun A p t h hd => planPareto_cover lib κ ε L n A t p h hd
      have pick : ∀ {l : List (Option3 Ty)} {x : Option3 Ty}, x ∈ l →
          x.2.1 ≤ p.cost κ L → x.2.2 ≤ p.cost ε L →
          ∃ o ∈ front l, o.2.1 ≤ p.cost κ L ∧ o.2.2 ≤ p.cost ε L := by
        intro l x hx hc he
        obtain ⟨y, hy, hyc, hye⟩ := front_cover hx
        exact ⟨y, hy, hyc.trans hc, hye.trans he⟩
      unfold planPareto
      rw [if_neg ht]
      cases h with
      | given hm => exact absurd hm ht
      | @apply _ c ps hc hargs =>
        simp only [Plan.depth] at hd
        obtain ⟨os, hos, hsc, hse⟩ := combos_cover (ih avail) hargs (by omega)
        refine pick (x := (.apply c (os.map Prod.fst), κ c + (os.map (·.2.1)).sum,
          ε c + (os.map (·.2.2)).sum)) ?_ ?_ ?_
        · apply List.mem_append_left
          exact List.mem_flatMap.mpr ⟨c, hc, by rw [if_pos rfl]; exact List.mem_map_of_mem hos⟩
        · simp only [Plan.cost]; omega
        · simp only [Plan.cost]; omega
      | @map _ a e body src ha hb hs =>
        simp only [Plan.depth] at hd
        obtain ⟨ob, hob, hbc, hbe⟩ := ih [a] body e hb (by omega)
        obtain ⟨os, hos, hsc, hse⟩ := ih avail src (seq a) hs (by omega)
        have he : elem? (seq e) = some e := elem?_eq_some.mpr rfl
        refine pick (x := (.map a ob.1 os.1, L * ob.2.1 + os.2.1, L * ob.2.2 + os.2.2)) ?_ ?_ ?_
        · apply List.mem_append_right
          rw [he]
          simp only [List.mem_flatMap, List.mem_map]
          exact ⟨a, ha, ob, hob, os, hos, rfl⟩
        · simp only [Plan.cost]
          exact add_le_add (Nat.mul_le_mul_left _ hbc) hsc
        · simp only [Plan.cost]
          exact add_le_add (Nat.mul_le_mul_left _ hbe) hse

/-- **Exact constrained selection.** If some searchable plan meets error
target `τ`, a returned option meets it at no greater cost. -/
theorem planPareto_within (lib : List (Contract Ty)) (κ ε : Contract Ty → Nat) (L : Nat)
    {n : Nat} {avail : List Ty} {t : Ty} {p : Plan Ty} {τ : Nat}
    (h : Searchable lib avail p t) (hd : p.depth < n) (hτ : p.cost ε L ≤ τ) :
    ∃ o ∈ planPareto lib κ ε L avail n t, o.2.2 ≤ τ ∧ o.2.1 ≤ p.cost κ L := by
  obtain ⟨o, ho, hc, he⟩ := planPareto_cover lib κ ε L n avail t p h hd
  exact ⟨o, ho, he.trans hτ, hc⟩

end NCA
