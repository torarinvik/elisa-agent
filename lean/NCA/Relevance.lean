import Mathlib.Data.Finset.Basic
import NCA.Contract

/-!
# Positional inputs and relevant slots

Plans that name available inputs by type cannot tell two inputs of the same
type apart. A positional plan names each input by its position instead
(`PPlan.given k`). Positional typing is ordinary typing with each position
read as its type (`PTyped.erase`), and every plan typed by types has a
positional version (`WellTyped.positional`), so positions change which input
is read, never which plans exist.

`PPlan.uses` collects the positions a plan reads; a `map` body reads only its
element, so a `map` reads what its source reads. A slot may require its
fillings to use given positions. An application meets a requirement exactly
when each required position is used by one of its arguments
(`uses_apply`), which is how the planner distributes requirements, and a
single input never meets a requirement of two positions (`given_not_relevant`),
which excludes projections such as returning a fold's state unchanged.
-/

namespace NCA

variable {Ty : Type} [SeqTypes Ty]
open SeqTypes

/-- A plan whose leaves are positions of available inputs. -/
inductive PPlan (Ty : Type) where
  | given : Nat → PPlan Ty
  | apply : Contract Ty → List (PPlan Ty) → PPlan Ty
  | map : Ty → PPlan Ty → PPlan Ty → PPlan Ty

mutual
/-- `PTyped lib avail p t`: as `WellTyped`, with `given k` reading the input
at position `k`. -/
inductive PTyped (lib : List (Contract Ty)) : List Ty → PPlan Ty → Ty → Prop
  | given {avail : List Ty} {k : Nat} {t : Ty} : avail[k]? = some t →
      PTyped lib avail (.given k) t
  | apply {avail : List Ty} {c : Contract Ty} {ps : List (PPlan Ty)} :
      c ∈ lib → PTypedArgs lib avail ps c.inputs → PTyped lib avail (.apply c ps) c.output
  | map {avail : List Ty} {a e : Ty} {body src : PPlan Ty} :
      PTyped lib [a] body e → PTyped lib avail src (seq a) →
      PTyped lib avail (.map a body src) (seq e)

inductive PTypedArgs (lib : List (Contract Ty)) :
    List Ty → List (PPlan Ty) → List Ty → Prop
  | nil {avail : List Ty} : PTypedArgs lib avail [] []
  | cons {avail : List Ty} {p : PPlan Ty} {ps : List (PPlan Ty)} {t : Ty} {ts : List Ty} :
      PTyped lib avail p t → PTypedArgs lib avail ps ts →
      PTypedArgs lib avail (p :: ps) (t :: ts)
end

mutual
/-- The plan with each position replaced by the type of the input there. -/
def PPlan.erase (avail : List Ty) : PPlan Ty → Option (Plan Ty)
  | .given k => avail[k]?.map .given
  | .apply c ps => (PPlan.eraseList avail ps).map (.apply c)
  | .map a body src =>
    match PPlan.erase [a] body, PPlan.erase avail src with
    | some b, some s => some (.map a b s)
    | _, _ => none

def PPlan.eraseList (avail : List Ty) : List (PPlan Ty) → Option (List (Plan Ty))
  | [] => some []
  | p :: ps =>
    match PPlan.erase avail p, PPlan.eraseList avail ps with
    | some q, some qs => some (q :: qs)
    | _, _ => none
end

mutual
/-- **Positions are types.** Erasing a positionally typed plan gives a plan
typed by types, with the same type. -/
theorem PTyped.erase {lib : List (Contract Ty)} :
    {avail : List Ty} → {p : PPlan Ty} → {t : Ty} → PTyped lib avail p t →
    ∃ q, p.erase avail = some q ∧ WellTyped lib avail q t
  | _, _, _, .given h => ⟨_, by simp [PPlan.erase, h], .given (List.mem_of_getElem? h)⟩
  | _, _, _, .apply hc hargs => by
    obtain ⟨qs, hqs, htyped⟩ := PTypedArgs.erase hargs
    exact ⟨_, by simp [PPlan.erase, hqs], .apply hc htyped⟩
  | _, _, _, .map hbody hsrc => by
    obtain ⟨b, hb, hbt⟩ := PTyped.erase hbody
    obtain ⟨s, hs, hst⟩ := PTyped.erase hsrc
    exact ⟨_, by simp [PPlan.erase, hb, hs], .map hbt hst⟩

theorem PTypedArgs.erase {lib : List (Contract Ty)} :
    {avail : List Ty} → {ps : List (PPlan Ty)} → {ts : List Ty} → PTypedArgs lib avail ps ts →
    ∃ qs, PPlan.eraseList avail ps = some qs ∧ WellTypedArgs lib avail qs ts
  | _, _, _, .nil => ⟨[], rfl, .nil⟩
  | _, _, _, .cons hp hps => by
    obtain ⟨q, hq, hqt⟩ := PTyped.erase hp
    obtain ⟨qs, hqs, hqst⟩ := PTypedArgs.erase hps
    exact ⟨_, by simp [PPlan.eraseList, hq, hqs], .cons hqt hqst⟩
end

mutual
/-- **Every plan has a positional version**, reading each input at a
position where it is available. -/
theorem WellTyped.positional {lib : List (Contract Ty)} :
    {avail : List Ty} → {q : Plan Ty} → {t : Ty} → WellTyped lib avail q t →
    ∃ p, PTyped lib avail p t ∧ p.erase avail = some q
  | _, _, _, .given h => by
    obtain ⟨k, hk, hkt⟩ := List.getElem_of_mem h
    have h' : _ = some _ := List.getElem?_eq_getElem hk
    rw [hkt] at h'
    exact ⟨.given k, .given h', by simp [PPlan.erase, h']⟩
  | _, _, _, .apply hc hargs => by
    obtain ⟨ps, hps, hpe⟩ := WellTypedArgs.positional hargs
    exact ⟨_, .apply hc hps, by simp [PPlan.erase, hpe]⟩
  | _, _, _, .map hbody hsrc => by
    obtain ⟨b, hb, hbe⟩ := WellTyped.positional hbody
    obtain ⟨s, hs, hse⟩ := WellTyped.positional hsrc
    exact ⟨_, .map hb hs, by simp [PPlan.erase, hbe, hse]⟩

theorem WellTypedArgs.positional {lib : List (Contract Ty)} :
    {avail : List Ty} → {qs : List (Plan Ty)} → {ts : List Ty} →
    WellTypedArgs lib avail qs ts →
    ∃ ps, PTypedArgs lib avail ps ts ∧ PPlan.eraseList avail ps = some qs
  | _, _, _, .nil => ⟨[], .nil, rfl⟩
  | _, _, _, .cons hq hqs => by
    obtain ⟨p, hp, hpe⟩ := WellTyped.positional hq
    obtain ⟨ps, hps, hpse⟩ := WellTypedArgs.positional hqs
    exact ⟨_, .cons hp hps, by simp [PPlan.eraseList, hpe, hpse]⟩
end

mutual
/-- The positions of the available inputs a plan reads. -/
def PPlan.uses : PPlan Ty → Finset Nat
  | .given k => {k}
  | .apply _ ps => PPlan.usesList ps
  | .map _ _ src => PPlan.uses src

def PPlan.usesList : List (PPlan Ty) → Finset Nat
  | [] => ∅
  | p :: ps => PPlan.uses p ∪ PPlan.usesList ps
end

omit [SeqTypes Ty] in
theorem PPlan.mem_usesList {r : Nat} : ∀ {ps : List (PPlan Ty)},
    r ∈ PPlan.usesList ps ↔ ∃ p ∈ ps, r ∈ p.uses
  | [] => by simp [PPlan.usesList]
  | p :: ps => by simp [PPlan.usesList, PPlan.mem_usesList]

omit [SeqTypes Ty] in
/-- **Requirements distribute over arguments.** An application uses every
required position exactly when each is used by one of its arguments. -/
theorem PPlan.uses_apply (c : Contract Ty) (ps : List (PPlan Ty)) (R : Finset Nat) :
    R ⊆ (PPlan.apply c ps).uses ↔ ∀ r ∈ R, ∃ p ∈ ps, r ∈ p.uses := by
  simp only [PPlan.uses]
  exact ⟨fun h r hr => PPlan.mem_usesList.mp (h hr),
    fun h r hr => PPlan.mem_usesList.mpr (h r hr)⟩

omit [SeqTypes Ty] in
/-- A `map` uses what its source uses. -/
theorem PPlan.uses_map (a : Ty) (body src : PPlan Ty) :
    (PPlan.map a body src).uses = src.uses := rfl

omit [SeqTypes Ty] in
/-- **Projections are not relevant.** A single input never meets a
requirement of two distinct positions. -/
theorem PPlan.given_not_relevant {i j k : Nat} (hij : i ≠ j) :
    ¬ ({i, j} : Finset Nat) ⊆ (PPlan.given k : PPlan Ty).uses := by
  intro h
  have hi := h (Finset.mem_insert_self i {j})
  have hj := h (Finset.mem_insert_of_mem (Finset.mem_singleton_self j))
  simp only [PPlan.uses, Finset.mem_singleton] at hi hj
  exact hij (hi.trans hj.symm)

mutual
/-- A typed plan reads only positions that exist. -/
theorem PTyped.uses_lt {lib : List (Contract Ty)} :
    {avail : List Ty} → {p : PPlan Ty} → {t : Ty} → PTyped lib avail p t →
    ∀ k ∈ p.uses, k < avail.length
  | _, _, _, .given h => fun k hk => by
    simp only [PPlan.uses, Finset.mem_singleton] at hk
    subst hk
    exact (List.getElem?_eq_some_iff.mp h).1
  | _, _, _, .apply _ hargs => PTypedArgs.uses_lt hargs
  | _, _, _, .map _ hsrc => fun k hk => PTyped.uses_lt hsrc k hk

theorem PTypedArgs.uses_lt {lib : List (Contract Ty)} :
    {avail : List Ty} → {ps : List (PPlan Ty)} → {ts : List Ty} → PTypedArgs lib avail ps ts →
    ∀ k ∈ PPlan.usesList ps, k < avail.length
  | _, _, _, .nil => fun _ hk => by simp [PPlan.usesList] at hk
  | _, _, _, .cons hp hps => fun k hk => by
    simp only [PPlan.usesList, Finset.mem_union] at hk
    rcases hk with hk | hk
    · exact PTyped.uses_lt hp k hk
    · exact PTypedArgs.uses_lt hps k hk
end

end NCA
