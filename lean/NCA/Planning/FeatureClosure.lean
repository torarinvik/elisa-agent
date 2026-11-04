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

/-- Finite rules preserve ordered antecedent lists, including repeated types. -/
def featureTreeClosure {α : Type*} [DecidableEq α] (seeds : Finset α)
    (rules : Finset (List α × α)) : ℕ → Finset α
  | 0 => seeds
  | n + 1 => seeds ∪ ((rules.filter fun r =>
      ∀ a ∈ r.1, a ∈ featureTreeClosure seeds rules n).image Prod.snd)

def featureTreeReach {α : Type*} [DecidableEq α] (seeds : Finset α)
    (rules : Finset (List α × α)) : ℕ → α → Prop
  | 0, x => x ∈ seeds
  | n + 1, x => x ∈ seeds ∨ ∃ r ∈ rules, r.2 = x ∧
      ∀ a ∈ r.1, featureTreeReach seeds rules n a

/-- All antecedents must be reachable, rather than merely one input edge. -/
theorem featureTreeClosure_iff {α : Type*} [DecidableEq α] (seeds : Finset α)
    (rules : Finset (List α × α)) (n : ℕ) (x : α) :
    x ∈ featureTreeClosure seeds rules n ↔ featureTreeReach seeds rules n x := by
  induction n generalizing x with
  | zero => rfl
  | succ n ih =>
    simp only [featureTreeClosure, featureTreeReach, Finset.mem_union,
      Finset.mem_image, Finset.mem_filter]
    constructor
    · rintro (hs | ⟨r, ⟨hr, children⟩, hx⟩)
      · exact Or.inl hs
      · exact Or.inr ⟨r, hr, hx, fun a ha => (ih a).mp (children a ha)⟩
    · rintro (hs | ⟨r, hr, hx, children⟩)
      · exact Or.inl hs
      · exact Or.inr ⟨r, ⟨hr, fun a ha => (ih a).mpr (children a ha)⟩, hx⟩

/-- Retention preserves every argument position, including heterogeneous types.
This is conditional on faithful functions, not a proof of executable codecs. -/
theorem featureApplication_reloaded_eq {X Z : Type*} {n : ℕ} {Y : Fin n → Type*}
    (branches restored : (i : Fin n) → X → Y i)
    (head restoredHead : ((i : Fin n) → Y i) → Z)
    (hb : ∀ i x, restored i x = branches i x)
    (hh : ∀ values, restoredHead values = head values) :
    (fun x => restoredHead (fun i => restored i x)) =
      (fun x => head (fun i => branches i x)) := by
  funext x
  have args : (fun i => restored i x) = (fun i => branches i x) := funext (fun i => hb i x)
  rw [args, hh]

end NCA
