import NCA.Loading

/-!
# Reachability pruning

A producer of the goal type whose inputs cannot be derived is a dead end, yet
the planner still explores it. Pruning skips producers that a *reachability
oracle* rejects. If the oracle is sound (it accepts every derivable type),
pruning never changes the plan. Forward closure from the available types, with
sequence types treated as always reachable, is such an oracle; it can be
computed in time proportional to the contracts that consume reachable types,
so dormant modules elsewhere in the library cost nothing.
-/

namespace NCA

variable {Ty : Type} [DecidableEq Ty] [SeqTypes Ty]
open SeqTypes

/-- Planning that skips producers with an input the oracle rejects, and `map`
candidates whose body goal or source the oracle rejects. -/
def planPruned (lib : List (Contract Ty)) (reach : List Ty → Ty → Bool) :
    List Ty → Nat → Ty → Option (Plan Ty)
  | _, 0, _ => none
  | avail, n + 1, t =>
    if t ∈ avail then some (.given t)
    else
      (firstSome (fun c =>
        if c.output = t ∧ c.inputs.all (reach avail) = true then
          (traverse (planPruned lib reach avail n) c.inputs).map (.apply c)
        else none) lib).orElse fun _ =>
      match elem? t with
      | none => none
      | some e => firstSome (fun a =>
          if reach [a] e = true ∧ reach avail (seq a) = true then
            match planPruned lib reach [a] n e, planPruned lib reach avail n (seq a) with
            | some body, some src => some (.map a body src)
            | _, _ => none
          else none) (elemCandidates lib avail)

/-- A reachability oracle is sound if it accepts every derivable type. -/
def SoundOracle (lib : List (Contract Ty)) (reach : List Ty → Ty → Bool) : Prop :=
  ∀ avail n t, Derivable lib avail n t → reach avail t = true

/-- **Pruning is exact.** With a sound oracle, pruned planning computes exactly
the plan of the unpruned planner. -/
theorem planPruned_eq {lib : List (Contract Ty)} {reach : List Ty → Ty → Bool}
    (hreach : SoundOracle lib reach) :
    ∀ n avail t, planPruned lib reach avail n t = plan lib avail n t
  | 0, _, _ => by simp [planPruned, plan]
  | n + 1, avail, t => by
    have ih := planPruned_eq hreach n
    have ih' : ∀ A, planPruned lib reach A n = plan lib A n := fun A => funext (ih A)
    simp only [planPruned, plan, ih']
    congr 1
    congr 1
    · apply firstSome_congr
      intro c _
      by_cases ho : c.output = t
      · by_cases hall : c.inputs.all (reach avail) = true
        · simp [ho, hall]
        · simp only [ho, hall, if_true]
          cases hr : traverse (plan lib avail n) c.inputs with
          | none => rfl
          | some ps =>
            exfalso
            apply hall
            rw [List.all_eq_true]
            intro i hi
            exact hreach avail n i (traverse_forall
              (fun i q hq => plan_derivable lib n avail i q hq) hr i hi)
      · simp [ho]
    · funext _
      cases elem? t with
      | none => rfl
      | some e =>
        apply firstSome_congr
        intro a _
        by_cases hg : reach [a] e = true ∧ reach avail (seq a) = true
        · rw [if_pos hg]; rfl
        · rw [if_neg hg]
          cases hb : plan lib [a] n e <;> cases hs : plan lib avail n (seq a) <;> try rfl
          exact absurd ⟨hreach _ _ _ (plan_derivable lib n [a] e _ hb),
            hreach _ _ _ (plan_derivable lib n avail _ _ hs)⟩ hg

/-- Forward closure of the available types under installed contracts, with
sequence types treated as always reachable. -/
inductive Closure (lib : List (Contract Ty)) (avail : List Ty) : Ty → Prop
  | seed {t : Ty} : t ∈ avail → Closure lib avail t
  | step {c : Contract Ty} : c ∈ lib →
      (∀ i ∈ c.inputs, (elem? i).isSome = false → Closure lib avail i) →
      Closure lib avail c.output

omit [DecidableEq Ty] in
/-- **The closure oracle is sound.** Every derivable type is a sequence type
or in the forward closure. -/
theorem derivable_closure {lib : List (Contract Ty)} {avail : List Ty} {n : Nat} {t : Ty}
    (h : Derivable lib avail n t) : (elem? t).isSome ∨ Closure lib avail t := by
  induction h with
  | given ht => exact Or.inr (.seed ht)
  | apply hc _ ih =>
    refine Or.inr (.step hc fun i hi hseq => ?_)
    rcases ih i hi with h | h
    · simp [h] at hseq
    · exact h
  | map => exact Or.inl (by simp [elem?_eq_some.mpr rfl])

omit [DecidableEq Ty] in
/-- Any oracle that accepts at least the closure is sound. -/
theorem closure_oracle_sound {lib : List (Contract Ty)} {reach : List Ty → Ty → Bool}
    (h : ∀ avail t, (elem? t).isSome ∨ Closure lib avail t → reach avail t = true) :
    SoundOracle lib reach :=
  fun _ _ _ hd => h _ _ (derivable_closure hd)

end NCA
