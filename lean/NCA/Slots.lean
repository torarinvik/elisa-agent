import NCA.Cost

/-!
# Higher-order experts

A contract may declare *slots*: sub-goals `[a₁, …, aₖ] ⇒ b` the expert has
the kernel fill with plans, and then calls as functions. The kernel plans
each slot like any goal, with the slot's inputs as the only available values,
so experts still never see one another. `map` becomes one higher-order
expert among others: a contract family with slot `[a] ⇒ e`, input `seq a`
and output `seq e` (`embed_wellTyped`, `embed_cost`).

An expert declares how often it may call its slots on one invocation
(`ν c`). A plan's cost counts each slot filling that many times. Cost stays
compositional and monotone in the cost of every filling and argument
(`HPlan.cost_mono`), the property that makes the cheapest plan of a goal be
built from the cheapest plans of its sub-goals, and it is polynomial with
degree the slot nesting depth (`HPlan.cost_le_pow`).
-/

namespace NCA

/-- A contract with slots: sub-goals from given input types to an output
type, which the kernel fills with plans. -/
structure HContract (Ty : Type) where
  id : Nat
  slots : List (List Ty × Ty)
  inputs : List Ty
  output : Ty

/-- A plan whose experts may have slots: `apply c fs ps` fills `c`'s slots
with the plans `fs` and its inputs with the plans `ps`. -/
inductive HPlan (Ty : Type) where
  | given : Ty → HPlan Ty
  | apply : HContract Ty → List (HPlan Ty) → List (HPlan Ty) → HPlan Ty

variable {Ty : Type}

mutual
/-- `HTyped lib avail p t`: `p` uses only experts satisfying `lib` and inputs
in `avail`, fills every slot with a plan from exactly the slot's inputs, and
produces `t`. The library is a predicate so that it can contain families
such as `map` at every pair of types. -/
inductive HTyped (lib : HContract Ty → Prop) : List Ty → HPlan Ty → Ty → Prop
  | given {avail : List Ty} {t : Ty} : t ∈ avail → HTyped lib avail (.given t) t
  | apply {avail : List Ty} {c : HContract Ty} {fs ps : List (HPlan Ty)} :
      lib c → HTypedSlots lib fs c.slots → HTypedArgs lib avail ps c.inputs →
      HTyped lib avail (.apply c fs ps) c.output

/-- Each slot filled by a plan from the slot's inputs to its output. -/
inductive HTypedSlots (lib : HContract Ty → Prop) :
    List (HPlan Ty) → List (List Ty × Ty) → Prop
  | nil : HTypedSlots lib [] []
  | cons {f : HPlan Ty} {fs : List (HPlan Ty)} {s : List Ty × Ty} {ss : List (List Ty × Ty)} :
      HTyped lib s.1 f s.2 → HTypedSlots lib fs ss → HTypedSlots lib (f :: fs) (s :: ss)

/-- Pointwise `HTyped` for argument lists. -/
inductive HTypedArgs (lib : HContract Ty → Prop) :
    List Ty → List (HPlan Ty) → List Ty → Prop
  | nil {avail : List Ty} : HTypedArgs lib avail [] []
  | cons {avail : List Ty} {p : HPlan Ty} {ps : List (HPlan Ty)} {t : Ty} {ts : List Ty} :
      HTyped lib avail p t → HTypedArgs lib avail ps ts →
      HTypedArgs lib avail (p :: ps) (t :: ts)
end

mutual
/-- Installing experts never invalidates a plan. -/
theorem HTyped.mono {lib lib' : HContract Ty → Prop} (hsub : ∀ c, lib c → lib' c) :
    {avail : List Ty} → {p : HPlan Ty} → {t : Ty} → HTyped lib avail p t → HTyped lib' avail p t
  | _, _, _, .given h => .given h
  | _, _, _, .apply hc hs ha =>
    .apply (hsub _ hc) (HTypedSlots.mono hsub hs) (HTypedArgs.mono hsub ha)

theorem HTypedSlots.mono {lib lib' : HContract Ty → Prop} (hsub : ∀ c, lib c → lib' c) :
    {fs : List (HPlan Ty)} → {ss : List (List Ty × Ty)} →
    HTypedSlots lib fs ss → HTypedSlots lib' fs ss
  | _, _, .nil => .nil
  | _, _, .cons h hs => .cons (HTyped.mono hsub h) (HTypedSlots.mono hsub hs)

theorem HTypedArgs.mono {lib lib' : HContract Ty → Prop} (hsub : ∀ c, lib c → lib' c) :
    {avail : List Ty} → {ps : List (HPlan Ty)} → {ts : List Ty} →
    HTypedArgs lib avail ps ts → HTypedArgs lib' avail ps ts
  | _, _, _, .nil => .nil
  | _, _, _, .cons h hs => .cons (HTyped.mono hsub h) (HTypedArgs.mono hsub hs)
end

section Cost

variable (κ ν : HContract Ty → Nat)

mutual
/-- Cost of a plan when expert `c` costs `κ c` per invocation and calls each
of its slots at most `ν c` times per invocation. -/
def HPlan.cost : HPlan Ty → Nat
  | .given _ => 0
  | .apply c fs ps => κ c + ν c * HPlan.costList fs + HPlan.costList ps

/-- Total cost of a list of plans. -/
def HPlan.costList : List (HPlan Ty) → Nat
  | [] => 0
  | p :: ps => p.cost + HPlan.costList ps
end

mutual
/-- Slot nesting depth: the largest number of slot fillings enclosing an expert. -/
def HPlan.nest : HPlan Ty → Nat
  | .given _ => 0
  | .apply _ fs ps => max (HPlan.nestSlots fs) (HPlan.nestList ps)

/-- Each slot filling adds one level. -/
def HPlan.nestSlots : List (HPlan Ty) → Nat
  | [] => 0
  | f :: fs => max (f.nest + 1) (HPlan.nestSlots fs)

/-- Largest nesting depth in a list of plans. -/
def HPlan.nestList : List (HPlan Ty) → Nat
  | [] => 0
  | p :: ps => max p.nest (HPlan.nestList ps)
end

/-- **Optimal substructure.** Cost is monotone in the cost of every slot
filling and every argument: replacing them by cheaper plans of the same
types never makes a plan dearer. So the cheapest plan of a goal is built from
cheapest plans of its sub-goals, and the Bellman recursion of `planMin`
extends to slots, with each filling's cost weighted by its call bound. -/
theorem HPlan.cost_mono (c : HContract Ty) {fs fs' ps ps' : List (HPlan Ty)}
    (hf : HPlan.costList κ ν fs' ≤ HPlan.costList κ ν fs)
    (hp : HPlan.costList κ ν ps' ≤ HPlan.costList κ ν ps) :
    (HPlan.apply c fs' ps').cost κ ν ≤ (HPlan.apply c fs ps).cost κ ν := by
  simp only [HPlan.cost]
  gcongr

mutual
/-- **Polynomial degree = slot nesting.** If every expert calls its slots at
most `N ≥ 1` times, a plan costs at most `N ^ nest` times its cost with every
slot called once. -/
theorem HPlan.cost_le_pow (N : Nat) (hN : 1 ≤ N) (hν : ∀ c, ν c ≤ N) :
    (p : HPlan Ty) → p.cost κ ν ≤ N ^ p.nest * p.cost κ (fun _ => 1)
  | .given _ => by simp [HPlan.cost]
  | .apply c fs ps => by
    have hf := HPlan.costSlots_le_pow N hN hν fs
    have hp := HPlan.costList_le_pow N hN hν ps
    simp only [HPlan.cost, HPlan.nest, one_mul]
    set m := max (HPlan.nestSlots fs) (HPlan.nestList ps)
    have h1 : 1 ≤ N ^ m := Nat.one_le_pow _ _ (by omega)
    have h2 : N * HPlan.costList κ ν fs ≤ N ^ m * HPlan.costList κ (fun _ => 1) fs :=
      hf.trans (Nat.mul_le_mul_right _ (Nat.pow_le_pow_right (by omega) (le_max_left _ _)))
    have h3 : HPlan.costList κ ν ps ≤ N ^ m * HPlan.costList κ (fun _ => 1) ps :=
      hp.trans (Nat.mul_le_mul_right _ (Nat.pow_le_pow_right (by omega) (le_max_right _ _)))
    have h4 : ν c * HPlan.costList κ ν fs ≤ N * HPlan.costList κ ν fs :=
      Nat.mul_le_mul_right _ (hν c)
    nlinarith

/-- Slot fillings, each called up to `N` times. -/
theorem HPlan.costSlots_le_pow (N : Nat) (hN : 1 ≤ N) (hν : ∀ c, ν c ≤ N) :
    (fs : List (HPlan Ty)) →
      N * HPlan.costList κ ν fs ≤ N ^ HPlan.nestSlots fs * HPlan.costList κ (fun _ => 1) fs
  | [] => by simp [HPlan.costList]
  | f :: fs => by
    have hf := HPlan.cost_le_pow N hN hν f
    have hfs := HPlan.costSlots_le_pow N hN hν fs
    simp only [HPlan.costList, HPlan.nestSlots]
    set m := max (f.nest + 1) (HPlan.nestSlots fs)
    have e1 : N * N ^ f.nest ≤ N ^ m := by
      rw [← pow_succ']; exact Nat.pow_le_pow_right (by omega) (le_max_left _ _)
    have e2 : N ^ HPlan.nestSlots fs ≤ N ^ m := Nat.pow_le_pow_right (by omega) (le_max_right _ _)
    calc N * (f.cost κ ν + HPlan.costList κ ν fs)
        = N * f.cost κ ν + N * HPlan.costList κ ν fs := by ring
      _ ≤ N * (N ^ f.nest * f.cost κ (fun _ => 1)) +
          N ^ HPlan.nestSlots fs * HPlan.costList κ (fun _ => 1) fs := by gcongr
      _ = (N * N ^ f.nest) * f.cost κ (fun _ => 1) +
          N ^ HPlan.nestSlots fs * HPlan.costList κ (fun _ => 1) fs := by ring
      _ ≤ N ^ m * f.cost κ (fun _ => 1) + N ^ m * HPlan.costList κ (fun _ => 1) fs := by gcongr
      _ = _ := by ring

/-- Arguments. -/
theorem HPlan.costList_le_pow (N : Nat) (hN : 1 ≤ N) (hν : ∀ c, ν c ≤ N) :
    (ps : List (HPlan Ty)) →
      HPlan.costList κ ν ps ≤ N ^ HPlan.nestList ps * HPlan.costList κ (fun _ => 1) ps
  | [] => by simp [HPlan.costList]
  | p :: ps => by
    have hp := HPlan.cost_le_pow N hN hν p
    have hps := HPlan.costList_le_pow N hN hν ps
    simp only [HPlan.costList, HPlan.nestList]
    set m := max p.nest (HPlan.nestList ps)
    have e1 : N ^ p.nest ≤ N ^ m := Nat.pow_le_pow_right (by omega) (le_max_left _ _)
    have e2 : N ^ HPlan.nestList ps ≤ N ^ m := Nat.pow_le_pow_right (by omega) (le_max_right _ _)
    calc p.cost κ ν + HPlan.costList κ ν ps
        ≤ N ^ p.nest * p.cost κ (fun _ => 1) +
          N ^ HPlan.nestList ps * HPlan.costList κ (fun _ => 1) ps := add_le_add hp hps
      _ ≤ N ^ m * p.cost κ (fun _ => 1) + N ^ m * HPlan.costList κ (fun _ => 1) ps := by gcongr
      _ = _ := by ring
end

end Cost

section Embedding

variable [SeqTypes Ty]
open SeqTypes

/-- A slot-free expert. -/
def Contract.lift (c : Contract Ty) : HContract Ty := ⟨c.id, [], c.inputs, c.output⟩

/-- `map` at element types `a` and `e`, as a higher-order expert. Its id is
reserved: library contracts are lifted with their own ids. -/
def mapContract (mapId : Nat) (a e : Ty) : HContract Ty := ⟨mapId, [([a], e)], [seq a], seq e⟩

/-- The library with `map` as an expert: its contracts, lifted, and `map` at
every pair of types. -/
def withMap (mapId : Nat) (lib : List (Contract Ty)) (c : HContract Ty) : Prop :=
  (∃ c₀ ∈ lib, c = c₀.lift) ∨ ∃ a e, c = mapContract mapId a e

/-- Call bounds: `map` calls its slot once per element, `L` times; other
experts have no slots. -/
def mapCalls (mapId L : Nat) (c : HContract Ty) : Nat := if c.id = mapId then L else 0

mutual
/-- **`map` is a higher-order expert.** Every well-typed plan is expressed,
at the same cost, by a plan in which `map` is an expert of zero own cost that
calls its slot `L` times. -/
theorem embed_wellTyped (mapId : Nat) {lib : List (Contract Ty)} (κ : Contract Ty → Nat)
    (L : Nat) (κH : HContract Ty → Nat) (hκ : ∀ c ∈ lib, κH c.lift = κ c)
    (hκmap : ∀ a e, κH (mapContract mapId a e) = 0) :
    {avail : List Ty} → {p : Plan Ty} → {t : Ty} → WellTyped lib avail p t →
      ∃ q : HPlan Ty, HTyped (withMap mapId lib) avail q t ∧
        q.cost κH (mapCalls mapId L) = p.cost κ L
  | _, _, _, .given h => ⟨.given _, .given h, rfl⟩
  | _, _, _, @WellTyped.apply _ _ _ _ c ps hc hargs => by
    obtain ⟨qs, hqs, hcost⟩ := embed_args mapId κ L κH hκ hκmap hargs
    refine ⟨.apply c.lift [] qs, HTyped.apply (c := c.lift) (Or.inl ⟨c, hc, rfl⟩) .nil hqs, ?_⟩
    simp only [HPlan.cost, HPlan.costList, mul_zero, add_zero, Plan.cost, hκ _ hc, hcost]
  | _, _, _, @WellTyped.map _ _ _ _ a e body src hbody hsrc => by
    obtain ⟨qb, hqb, hcb⟩ := embed_wellTyped mapId κ L κH hκ hκmap hbody
    obtain ⟨qs, hqs, hcs⟩ := embed_wellTyped mapId κ L κH hκ hκmap hsrc
    refine ⟨.apply (mapContract mapId a e) [qb] [qs],
      .apply (Or.inr ⟨a, e, rfl⟩) (.cons hqb .nil) (.cons hqs .nil), ?_⟩
    have h0 := hκmap a e
    simp only [mapContract] at h0
    simp [HPlan.cost, HPlan.costList, Plan.cost, mapCalls, mapContract, h0, hcb, hcs]

theorem embed_args (mapId : Nat) {lib : List (Contract Ty)} (κ : Contract Ty → Nat)
    (L : Nat) (κH : HContract Ty → Nat) (hκ : ∀ c ∈ lib, κH c.lift = κ c)
    (hκmap : ∀ a e, κH (mapContract mapId a e) = 0) :
    {avail : List Ty} → {ps : List (Plan Ty)} → {ts : List Ty} → WellTypedArgs lib avail ps ts →
      ∃ qs : List (HPlan Ty), HTypedArgs (withMap mapId lib) avail qs ts ∧
        HPlan.costList κH (mapCalls mapId L) qs = Plan.costArgs κ L ps
  | _, _, _, .nil => ⟨[], .nil, rfl⟩
  | _, _, _, .cons h hs => by
    obtain ⟨q, hq, hc⟩ := embed_wellTyped mapId κ L κH hκ hκmap h
    obtain ⟨qs, hqs, hcs⟩ := embed_args mapId κ L κH hκ hκmap hs
    exact ⟨q :: qs, .cons hq hqs, by simp [HPlan.costList, Plan.costArgs, hc, hcs]⟩
end

end Embedding

end NCA
