import NCA.Planning.Pruning

/-!
# Depth pruning

Reachability pruning (`planPruned_eq`) skips producers whose inputs cannot
be derived at all, but a search with fuel `n` still explores producers whose
inputs can only be derived deeper than `n`. A *depth oracle* also receives
the fuel. If it accepts every type derivable within that fuel, pruning by it
never changes the plan (`planDepth_eq`). The depth-bounded closure, which
treats sequence types as derivable at every positive depth, is such an
oracle (`derivable_within`).
-/

namespace NCA

variable {Ty : Type} [DecidableEq Ty] [SeqTypes Ty]
open SeqTypes

/-- Planning that skips producers with an input the depth oracle rejects at
the remaining fuel, and `map` candidates it rejects likewise. -/
def planDepth (lib : List (Contract Ty)) (reach : List Ty → Nat → Ty → Bool) :
    List Ty → Nat → Ty → Option (Plan Ty)
  | _, 0, _ => none
  | avail, n + 1, t =>
    if t ∈ avail then some (.given t)
    else
      (firstSome (fun c =>
        if c.output = t ∧ c.inputs.all (reach avail n) = true then
          (traverse (planDepth lib reach avail n) c.inputs).map (.apply c)
        else none) lib).orElse fun _ =>
      match elem? t with
      | none => none
      | some e => firstSome (fun a =>
          if reach [a] n e = true ∧ reach avail n (seq a) = true then
            match planDepth lib reach [a] n e, planDepth lib reach avail n (seq a) with
            | some body, some src => some (.map a body src)
            | _, _ => none
          else none) (elemCandidates lib avail)

/-- A depth oracle is sound if it accepts every type derivable within the fuel. -/
def SoundDepthOracle (lib : List (Contract Ty)) (reach : List Ty → Nat → Ty → Bool) : Prop :=
  ∀ avail n t, Derivable lib avail n t → reach avail n t = true

/-- **Depth pruning is exact.** With a sound depth oracle, pruned planning
computes exactly the plan of the unpruned planner. -/
theorem planDepth_eq {lib : List (Contract Ty)} {reach : List Ty → Nat → Ty → Bool}
    (hreach : SoundDepthOracle lib reach) :
    ∀ n avail t, planDepth lib reach avail n t = plan lib avail n t
  | 0, _, _ => by simp [planDepth, plan]
  | n + 1, avail, t => by
    have ih := planDepth_eq hreach n
    have ih' : ∀ A, planDepth lib reach A n = plan lib A n := fun A => funext (ih A)
    simp only [planDepth, plan, ih']
    congr 1
    congr 1
    · apply firstSome_congr
      intro c _
      by_cases ho : c.output = t
      · by_cases hall : c.inputs.all (reach avail n) = true
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
        by_cases hg : reach [a] n e = true ∧ reach avail n (seq a) = true
        · rw [if_pos hg]; rfl
        · rw [if_neg hg]
          cases hb : plan lib [a] n e <;> cases hs : plan lib avail n (seq a) <;> try rfl
          exact absurd ⟨hreach _ _ _ (plan_derivable lib n [a] e _ hb),
            hreach _ _ _ (plan_derivable lib n avail _ _ hs)⟩ hg

/-- The types derivable within depth `n` by forward closure, with sequence
types counted as derivable at every positive depth. -/
inductive Within (lib : List (Contract Ty)) (avail : List Ty) : Nat → Ty → Prop
  | seed {n : Nat} {t : Ty} : t ∈ avail → Within lib avail (n + 1) t
  | seq {n : Nat} {t : Ty} : (elem? t).isSome → Within lib avail (n + 1) t
  | step {n : Nat} {c : Contract Ty} : c ∈ lib →
      (∀ i ∈ c.inputs, (elem? i).isSome = false → Within lib avail n i) →
      Within lib avail (n + 1) c.output

omit [DecidableEq Ty] in
/-- **The depth-bounded closure is sound.** Every type derivable within
depth `n` is in it. -/
theorem derivable_within {lib : List (Contract Ty)} {avail : List Ty} {n : Nat} {t : Ty}
    (h : Derivable lib avail n t) : Within lib avail n t := by
  induction h with
  | given ht => exact .seed ht
  | apply hc _ ih => exact .step hc fun i hi _ => ih i hi
  | map => exact .seq (by simp [elem?_eq_some.mpr rfl])

end NCA
