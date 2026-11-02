import NCA.Planning.Pruning
import NCA.Execution.Slots
import NCA.Types.Unification

/-!
# Closure through eliminators

A polymorphic contract whose output is a bare variable `v`, such as an
eliminator, has an instance for every type, so counting all its instances as
reachable would make the forward closure total. Only the instances whose
inputs are derivable matter, and what they output is constrained: `v` is an
input, or occurs in an input pattern, or is the output of a slot filled from
the slot's inputs. `ECl` is the forward closure with one rule for each case
(THEORY §12, Theorem 12.19).

Plans are `HPlan`s over instances of installed slot contracts and the `map`
family, which models the planner's built-in `map`. Every derivable
non-sequence type is in the closure (`HTyped.eclosure`), so the closure is a
sound oracle for skipping eliminator candidates. A slot whose inputs are
already in the closure adds nothing to it (`ECl.trans`), and the source
oracle of Theorem 12.17 carries over with the sequence types of this closure
as seeds (`HTyped.seq_source`, Theorem 12.20).
-/

namespace NCA

open SeqTypes

/-- A slot contract with its types substituted. -/
def HContract.subst (σ : Nat → Term) (c : HContract Term) : HContract Term :=
  { id := c.id, slots := c.slots.map fun s => (s.1.map (Term.subst σ), Term.subst σ s.2),
    inputs := c.inputs.map (Term.subst σ), output := Term.subst σ c.output }

/-- The contracts a plan may apply: instances of installed contracts, and the
`map` family at every pair of types. -/
def Usable (lib : List (HContract Term)) (mapId : Nat) (c : HContract Term) : Prop :=
  (∃ d ∈ lib, ∃ σ : Nat → Term, c = d.subst σ) ∨ ∃ a e, c = mapContract mapId a e

/-- Variable `v` occurs in an input pattern rooted at a constructor other than
`seq`, so matching the inputs against the closure binds it. -/
def HContract.Binds (d : HContract Term) (v : Nat) : Prop :=
  ∃ f ts, Term.app f ts ∈ d.inputs ∧ elem? (Term.app f ts) = none ∧ Term.Occurs v (.app f ts)

/-- The closure from the types satisfying `A`. Sequence types count as always
reachable, so an instance is enabled once its non-sequence inputs are in the
closure. An enabled instance of a contract whose output is a constructor
application contributes its output (`fire`). For a contract whose output is a
bare variable `v` not among its inputs: if `v` is bound by an input pattern,
the instance contributes `σ v` (`bound`); otherwise, if `v` is the output of
a slot, everything in the closure of that slot's inputs (`slot`); otherwise,
everything (`free`). When `v` is an input, the output is an enabled input,
already in the closure, and there is no rule. -/
inductive ECl (lib : List (HContract Term)) : (Term → Prop) → Term → Prop
  | seed {A : Term → Prop} {t : Term} : A t → ECl lib A t
  | fire {A : Term → Prop} {d : HContract Term} {σ : Nat → Term} {f : String} {ts : List Term} :
      d ∈ lib → d.output = .app f ts →
      (∀ i ∈ d.inputs, (elem? (Term.subst σ i)).isSome = false → ECl lib A (Term.subst σ i)) →
      ECl lib A (Term.subst σ d.output)
  | bound {A : Term → Prop} {d : HContract Term} {σ : Nat → Term} {v : Nat} :
      d ∈ lib → d.output = .var v → Term.var v ∉ d.inputs → d.Binds v →
      (∀ i ∈ d.inputs, (elem? (Term.subst σ i)).isSome = false → ECl lib A (Term.subst σ i)) →
      ECl lib A (σ v)
  | slot {A : Term → Prop} {d : HContract Term} {σ : Nat → Term} {v : Nat} {ins : List Term}
      {t : Term} :
      d ∈ lib → d.output = .var v → Term.var v ∉ d.inputs → ¬ d.Binds v →
      (ins, Term.var v) ∈ d.slots →
      (∀ i ∈ d.inputs, (elem? (Term.subst σ i)).isSome = false → ECl lib A (Term.subst σ i)) →
      ECl lib (· ∈ ins.map (Term.subst σ)) t → ECl lib A t
  | free {A : Term → Prop} {d : HContract Term} {σ : Nat → Term} {v : Nat} {t : Term} :
      d ∈ lib → d.output = .var v → Term.var v ∉ d.inputs → ¬ d.Binds v →
      (∀ s ∈ d.slots, s.2 ≠ Term.var v) →
      (∀ i ∈ d.inputs, (elem? (Term.subst σ i)).isSome = false → ECl lib A (Term.subst σ i)) →
      ECl lib A t

variable {lib : List (HContract Term)}

/-- **Closed sets absorb closures.** If every seed of `A` is in the closure
of `B`, the closure of `A` is contained in it. So a slot whose inputs are all
in the closure being computed contributes nothing new. -/
theorem ECl.trans {A B : Term → Prop} (hAB : ∀ x, A x → ECl lib B x) {t : Term}
    (h : ECl lib A t) : ECl lib B t := by
  induction h with
  | seed ht => exact hAB _ ht
  | fire hd ho _ ih => exact .fire hd ho fun i hi hs => ih i hi hs hAB
  | bound hd ho hin hb _ ih => exact .bound hd ho hin hb fun i hi hs => ih i hi hs hAB
  | slot hd ho hin hb hs _ hcl ih _ =>
    exact .slot hd ho hin hb hs (fun i hi hseq => ih i hi hseq hAB) hcl
  | free hd ho hin hb hs _ ih => exact .free hd ho hin hb hs fun i hi hseq => ih i hi hseq hAB

/-- The closure grows with its seeds. -/
theorem ECl.mono {A B : Term → Prop} (hAB : ∀ x, A x → B x) {t : Term} (h : ECl lib A t) :
    ECl lib B t :=
  h.trans fun x hx => .seed (hAB x hx)

/-- Sequence seeds are never needed to enable an instance, so the closure of
`A` lies in the closure of `B` up to sequence types once every non-sequence
seed of `A` does. -/
theorem ECl.trans_nonseq {A B : Term → Prop}
    (hAB : ∀ x, A x → (elem? x).isSome = false → ECl lib B x) {t : Term} (h : ECl lib A t) :
    (elem? t).isSome ∨ ECl lib B t := by
  have enabled : ∀ {d : HContract Term} {σ : Nat → Term},
      (∀ i ∈ d.inputs, (elem? (Term.subst σ i)).isSome = false →
        (elem? (Term.subst σ i)).isSome ∨ ECl lib B (Term.subst σ i)) →
      ∀ i ∈ d.inputs, (elem? (Term.subst σ i)).isSome = false → ECl lib B (Term.subst σ i) :=
    fun ih i hi hs => (ih i hi hs).resolve_left (by simp [hs])
  induction h with
  | @seed _ t ht =>
    cases hs : (elem? t).isSome
    · exact .inr (hAB _ ht hs)
    · exact .inl rfl
  | fire hd ho _ ih => exact .inr (.fire hd ho (enabled fun i hi hs => ih i hi hs hAB))
  | bound hd ho hin hb _ ih =>
    exact .inr (.bound hd ho hin hb (enabled fun i hi hs => ih i hi hs hAB))
  | slot hd ho hin hb hs _ hcl ih _ =>
    exact .inr (.slot hd ho hin hb hs (enabled fun i hi hseq => ih i hi hseq hAB) hcl)
  | free hd ho hin hb hs _ ih =>
    exact .inr (.free hd ho hin hb hs (enabled fun i hi hseq => ih i hi hseq hAB))

theorem HContract.mem_subst_inputs {d : HContract Term} (σ : Nat → Term) {i : Term}
    (hi : i ∈ d.inputs) : Term.subst σ i ∈ (d.subst σ).inputs :=
  List.mem_map_of_mem hi

theorem HContract.mem_subst_slots {d : HContract Term} (σ : Nat → Term) {s : List Term × Term}
    (hs : s ∈ d.slots) :
    (s.1.map (Term.subst σ), Term.subst σ s.2) ∈ (d.subst σ).slots :=
  List.mem_map_of_mem (f := fun s => (s.1.map (Term.subst σ), Term.subst σ s.2)) hs

theorem elem?_seq_isSome (e : Term) : (elem? (seq e)).isSome = true := by
  simp [elem?_eq_some.mpr rfl]

/-- The case split behind every rule for a contract whose output is a bare
variable `v`: `v` is an input, is bound by an input pattern, is the output of
a slot, or none of these. -/
theorem HContract.var_cases (d : HContract Term) (v : Nat) :
    Term.var v ∈ d.inputs ∨ (Term.var v ∉ d.inputs ∧ d.Binds v) ∨
      (Term.var v ∉ d.inputs ∧ ¬ d.Binds v ∧ ∃ ins, (ins, Term.var v) ∈ d.slots) ∨
      (Term.var v ∉ d.inputs ∧ ¬ d.Binds v ∧ ∀ s ∈ d.slots, s.2 ≠ Term.var v) := by
  by_cases hin : Term.var v ∈ d.inputs
  · exact .inl hin
  by_cases hb : d.Binds v
  · exact .inr (.inl ⟨hin, hb⟩)
  by_cases hs : ∃ ins, (ins, Term.var v) ∈ d.slots
  · exact .inr (.inr (.inl ⟨hin, hb, hs⟩))
  refine .inr (.inr (.inr ⟨hin, hb, fun s hmem heq => hs ⟨s.1, ?_⟩⟩))
  rw [← heq]
  exact hmem

variable {mapId : Nat}

mutual
/-- **Theorem 12.19.** Every non-sequence type derivable from `avail`, by
plans over instances of installed contracts, slots and `map`, is in the
closure through eliminators. -/
theorem HTyped.eclosure :
    {avail : List Term} → {p : HPlan Term} → {t : Term} →
    HTyped (Usable lib mapId) avail p t → (elem? t).isSome = false →
    ECl lib (· ∈ avail) t
  | _, _, _, .given ht, _ => .seed ht
  | _, _, _, .apply (c := c) hc hs ha, hseq => by
    have hargs := HTypedArgs.eclosure ha
    have hslots := HTypedSlots.eclosure hs
    rcases hc with ⟨d, hd, σ, rfl⟩ | ⟨a, e, rfl⟩
    · have enabled : ∀ i ∈ d.inputs, (elem? (Term.subst σ i)).isSome = false →
          ECl lib (· ∈ _) (Term.subst σ i) :=
        fun i hi => hargs _ (HContract.mem_subst_inputs σ hi)
      show ECl lib _ (Term.subst σ d.output)
      match ho : d.output with
      | .app f ts => rw [← ho]; exact .fire hd ho enabled
      | .var v =>
        rw [Term.subst_var]
        have hout : (d.subst σ).output = σ v := by
          show Term.subst σ d.output = σ v
          rw [ho, Term.subst_var]
        rw [hout] at hseq
        rcases d.var_cases v with hin | ⟨hin, hb⟩ | ⟨hin, hb, ins, hmem⟩ | ⟨hin, hb, hnone⟩
        · have := hargs _ (HContract.mem_subst_inputs σ hin) (by rwa [Term.subst_var])
          rwa [Term.subst_var] at this
        · exact .bound hd ho hin hb enabled
        · have := hslots _ (HContract.mem_subst_slots σ hmem) (by rwa [Term.subst_var])
          rw [Term.subst_var] at this
          exact .slot hd ho hin hb hmem enabled this
        · exact .free hd ho hin hb hnone enabled
    · exact absurd (elem?_seq_isSome e) (by simpa [mapContract] using hseq)

theorem HTypedArgs.eclosure :
    {avail : List Term} → {ps : List (HPlan Term)} → {ts : List Term} →
    HTypedArgs (Usable lib mapId) avail ps ts →
    ∀ t ∈ ts, (elem? t).isSome = false → ECl lib (· ∈ avail) t
  | _, _, _, .nil => fun _ h => absurd h List.not_mem_nil
  | _, _, _, .cons hp hps => fun t ht hseq => by
    rcases List.mem_cons.mp ht with rfl | ht
    · exact HTyped.eclosure hp hseq
    · exact HTypedArgs.eclosure hps t ht hseq

theorem HTypedSlots.eclosure :
    {fs : List (HPlan Term)} → {ss : List (List Term × Term)} →
    HTypedSlots (Usable lib mapId) fs ss →
    ∀ s ∈ ss, (elem? s.2).isSome = false → ECl lib (· ∈ s.1) s.2
  | _, _, .nil => fun _ h => absurd h List.not_mem_nil
  | _, _, .cons hf hfs => fun s hs hseq => by
    rcases List.mem_cons.mp hs with rfl | hs
    · exact HTyped.eclosure hf hseq
    · exact HTypedSlots.eclosure hfs s hs hseq
end

/-- Elements of the sequence types in the closure of `A`. -/
def SeqSeeds (lib : List (HContract Term)) (A : Term → Prop) (a : Term) : Prop :=
  ECl lib A (seq a)

/-- Sequence types in the closure of a slot's inputs reach the closure of
`A` through the `slot` rule. -/
theorem seqSeeds_slot {A : Term → Prop} {d : HContract Term} {σ : Nat → Term} {v : Nat}
    {ins : List Term} (hd : d ∈ lib) (ho : d.output = .var v) (hin : Term.var v ∉ d.inputs)
    (hb : ¬ d.Binds v) (hmem : (ins, Term.var v) ∈ d.slots)
    (enabled : ∀ i ∈ d.inputs, (elem? (Term.subst σ i)).isSome = false →
      ECl lib A (Term.subst σ i)) {e : Term}
    (h : ECl lib (SeqSeeds lib (· ∈ ins.map (Term.subst σ))) e) :
    ECl lib (SeqSeeds lib A) e :=
  h.mono fun _ ha => .slot hd ho hin hb hmem enabled ha

mutual
/-- **Theorem 12.20.** If `seq e` is derivable from `avail`, then `e` is a
sequence type or in the closure of the elements of the sequence types in the
closure of `avail`: the source oracle of Theorem 12.17 holds through
eliminators. -/
theorem HTyped.seq_source :
    {avail : List Term} → {p : HPlan Term} → {t : Term} →
    HTyped (Usable lib mapId) avail p t →
    ∀ e, t = seq e → (elem? e).isSome = false → ECl lib (SeqSeeds lib (· ∈ avail)) e
  | _, _, _, .given ht, e, he, _ => .seed (.seed (he ▸ ht))
  | _, _, _, .apply (c := c) hc hs ha, e, he, hseq => by
    have hsrc := HTypedArgs.seq_source ha
    have hfill := HTypedSlots.seq_source hs
    have hargs := HTypedArgs.eclosure ha
    have hslots := HTypedSlots.eclosure hs
    rcases hc with ⟨d, hd, σ, rfl⟩ | ⟨a, e', rfl⟩
    · have enabled : ∀ i ∈ d.inputs, (elem? (Term.subst σ i)).isSome = false →
          ECl lib (· ∈ _) (Term.subst σ i) :=
        fun i hi => hargs _ (HContract.mem_subst_inputs σ hi)
      have he' : Term.subst σ d.output = seq e := he
      match ho : d.output with
      | .app f ts =>
        refine .seed ?_
        show ECl lib _ (seq e)
        rw [← he']
        exact .fire hd ho enabled
      | .var v =>
        rw [ho, Term.subst_var] at he'
        rcases d.var_cases v with hin | ⟨hin, hb⟩ | ⟨hin, hb, ins, hmem⟩ | ⟨hin, hb, hnone⟩
        · exact hsrc _ (HContract.mem_subst_inputs σ hin) e (by rw [Term.subst_var, he']) hseq
        · refine .seed ?_
          show ECl lib _ (seq e)
          rw [← he']
          exact .bound hd ho hin hb enabled
        · exact seqSeeds_slot hd ho hin hb hmem enabled
            (hfill _ (HContract.mem_subst_slots σ hmem) e (by rw [Term.subst_var, he']) hseq)
        · exact .seed (.free hd ho hin hb hnone enabled)
    · have he' : seq e' = seq e := he
      rw [seq_inj he'] at hslots
      have hbody := hslots ([a], e) (List.mem_singleton.mpr rfl) hseq
      rcases hbody.trans_nonseq (B := SeqSeeds lib (· ∈ _)) (fun x hx hxs => by
          rw [List.mem_singleton.mp hx] at hxs ⊢
          exact hsrc (seq a) (List.mem_singleton.mpr rfl) a rfl hxs) with h | h
      · simp [hseq] at h
      · exact h

theorem HTypedArgs.seq_source :
    {avail : List Term} → {ps : List (HPlan Term)} → {ts : List Term} →
    HTypedArgs (Usable lib mapId) avail ps ts →
    ∀ t ∈ ts, ∀ e, t = seq e → (elem? e).isSome = false →
      ECl lib (SeqSeeds lib (· ∈ avail)) e
  | _, _, _, .nil => fun _ h => absurd h List.not_mem_nil
  | _, _, _, .cons hp hps => fun t ht e he hseq => by
    rcases List.mem_cons.mp ht with rfl | ht
    · exact HTyped.seq_source hp e he hseq
    · exact HTypedArgs.seq_source hps t ht e he hseq

theorem HTypedSlots.seq_source :
    {fs : List (HPlan Term)} → {ss : List (List Term × Term)} →
    HTypedSlots (Usable lib mapId) fs ss →
    ∀ s ∈ ss, ∀ e, s.2 = seq e → (elem? e).isSome = false →
      ECl lib (SeqSeeds lib (· ∈ s.1)) e
  | _, _, .nil => fun _ h => absurd h List.not_mem_nil
  | _, _, .cons hf hfs => fun s hs e he hseq => by
    rcases List.mem_cons.mp hs with rfl | hs
    · exact HTyped.seq_source hf e he hseq
    · exact HTypedSlots.seq_source hfs s hs e he hseq
end

end NCA
