import Mathlib.Data.Fintype.BigOperators
import Mathlib.Algebra.Order.BigOperators.GroupWithZero.Finset

/-! Exact outcome-partition cardinality for independent field choices. -/

open scoped BigOperators

namespace NCA

/-- Filtering complete independent rules by observations factorizes by output field. -/
theorem training_version_eq {I J F V : Type} [Fintype I] [Fintype J] [DecidableEq J]
    [DecidableEq F] [DecidableEq V] (allowed : J → Finset F)
    (value : I → F → V) (target : I → J → V) :
    (Fintype.piFinset allowed).filter (fun rule => ∀ i j, value i (rule j) = target i j) =
      Fintype.piFinset (fun j => (allowed j).filter (fun field => ∀ i, value i field = target i j)) := by
  classical
  ext rule
  simp only [Finset.mem_filter, Fintype.mem_piFinset]
  constructor
  · intro h j
    exact ⟨h.1 j, fun i => h.2 i j⟩
  · intro h
    exact ⟨fun j => (h j).1, fun i j => (h j).2 i⟩

theorem training_version_count {I J F V : Type} [Fintype I] [Fintype J] [DecidableEq J]
    [DecidableEq F] [DecidableEq V] (allowed : J → Finset F)
    (value : I → F → V) (target : I → J → V) :
    ((Fintype.piFinset allowed).filter (fun rule => ∀ i j, value i (rule j) = target i j)).card =
      ∏ j, ((allowed j).filter (fun field => ∀ i, value i field = target i j)).card := by
  rw [training_version_eq allowed value target, Fintype.card_piFinset]

/-- The number of independent field-copy rules predicting an output tuple
is the product of the matching field counts at each output position. -/
theorem output_partition_count {J F V : Type} [Fintype J] [DecidableEq J]
    [DecidableEq F] [DecidableEq V] (allowed : J → Finset F) (value : F → V) (target : J → V) :
    ((Fintype.piFinset allowed).filter (fun rule => ∀ j, value (rule j) = target j)).card =
      ∏ j, ((allowed j).filter (fun field => value field = target j)).card := by
  classical
  have same : (Fintype.piFinset allowed).filter (fun rule => ∀ j, value (rule j) = target j) =
      Fintype.piFinset (fun j => (allowed j).filter (fun field => value field = target j)) := by
    ext rule
    simp only [Finset.mem_filter, Fintype.mem_piFinset]
    constructor
    · intro h j
      exact ⟨h.1 j, h.2 j⟩
    · intro h
      exact ⟨fun j => (h j).1, fun j => (h j).2⟩
  rw [same, Fintype.card_piFinset]

/-- Per-position maxima multiply to the attained largest joint outcome partition. -/
theorem largest_output_partition {J F V : Type} [Fintype J] [DecidableEq J]
    [DecidableEq F] [DecidableEq V] (allowed : J → Finset F) (value : F → V) (maximum : J → Nat)
    (upper : ∀ j v, ((allowed j).filter (fun field => value field = v)).card ≤ maximum j)
    (attained : ∀ j, ∃ v, ((allowed j).filter (fun field => value field = v)).card = maximum j) :
    (∀ target : J → V,
      ((Fintype.piFinset allowed).filter (fun rule => ∀ j, value (rule j) = target j)).card ≤
        ∏ j, maximum j) ∧
    (∃ target : J → V,
      ((Fintype.piFinset allowed).filter (fun rule => ∀ j, value (rule j) = target j)).card =
        ∏ j, maximum j) := by
  classical
  constructor
  · intro target
    rw [output_partition_count]
    apply Finset.prod_le_prod
    · intro i hi
      exact Nat.zero_le _
    · intro i hi
      exact upper i (target i)
  · choose target htarget using attained
    refine ⟨target, ?_⟩
    rw [output_partition_count]
    apply Finset.prod_congr rfl
    intro j hj
    exact htarget j

/-- Injective assembly preserves the product outcome partition counts. -/
theorem assembled_partition_count {J F V Y : Type} [Fintype J] [DecidableEq J]
    [DecidableEq F] [DecidableEq V] [DecidableEq Y]
    (allowed : J → Finset F) (value : F → V) (encode : (J → V) → Y)
    (injective : Function.Injective encode) (target : J → V) :
    ((Fintype.piFinset allowed).filter
      (fun rule => encode (fun j => value (rule j)) = encode target)).card =
        ∏ j, ((allowed j).filter (fun field => value field = target j)).card := by
  classical
  have same : (Fintype.piFinset allowed).filter
      (fun rule => encode (fun j => value (rule j)) = encode target) =
      (Fintype.piFinset allowed).filter (fun rule => ∀ j, value (rule j) = target j) := by
    ext rule
    simp only [Finset.mem_filter]
    constructor
    · intro h
      exact ⟨h.1, fun j => congrFun (injective h.2) j⟩
    · intro h
      refine ⟨h.1, ?_⟩
      congr 1
      funext j
      exact h.2 j
  rw [same, output_partition_count]

#print axioms training_version_eq
#print axioms training_version_count
#print axioms output_partition_count
#print axioms largest_output_partition
#print axioms assembled_partition_count

end NCA
