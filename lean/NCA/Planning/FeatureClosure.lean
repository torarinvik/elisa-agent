import Mathlib.Data.Finset.Union

/-! Bounded unary feature construction (§36.59). The relation models only
compatible transformations; real contract matching and execution are trusted. -/
namespace NCA

def featureClosure {α : Type*} [DecidableEq α] (seeds : Finset α)
    (next : α → Finset α) : ℕ → Finset α
  | 0 => seeds
  | n + 1 => seeds ∪ (featureClosure seeds next n).biUnion next

/-- Reachability by at most n compatible transformations after a seed. -/
def featureReach {α : Type*} (seeds : Set α) (edge : α → α → Prop) : ℕ → α → Prop
  | 0, x => x ∈ seeds
  | n + 1, x => x ∈ seeds ∨ ∃ y, featureReach seeds edge n y ∧ edge y x

/-- Untruncated construction is sound and complete for its bounded fragment.
This does not infer semantic equality between experts sharing an output type. -/
theorem featureClosure_iff {α : Type*} [DecidableEq α] (seeds : Finset α)
    (next : α → Finset α) (n : ℕ) (x : α) :
    x ∈ featureClosure seeds next n ↔
      featureReach (↑seeds) (fun a b => b ∈ next a) n x := by
  induction n generalizing x with
  | zero => simp [featureClosure, featureReach]
  | succ n ih => simp [featureClosure, featureReach, ih]

end NCA
