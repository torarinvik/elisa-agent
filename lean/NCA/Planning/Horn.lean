import Mathlib.Data.Set.Insert

/-! Gaps for experts with several inputs (§20.9). An expert is a rule
`(inputs, output)`; a type is derivable from the given types `S` when it is
given or the output of a rule whose inputs are all derivable. -/
namespace NCA

/-- Types derivable from `S` under rules `R`. -/
inductive HornDerivable {τ : Type*} (R : Set (Set τ × τ)) (S : Set τ) : τ → Prop
  | given {x} : x ∈ S → HornDerivable R S x
  | rule {A b} : (A, b) ∈ R → (∀ a ∈ A, HornDerivable R S a) → HornDerivable R S b

theorem HornDerivable.mono {τ : Type*} {R R' : Set (Set τ × τ)} {S S' : Set τ}
    (hR : R ⊆ R') (hS : S ⊆ S') {x : τ} (h : HornDerivable R S x) : HornDerivable R' S' x := by
  induction h with
  | given hx => exact .given (hS hx)
  | rule hr _ ih => exact .rule (hR hr) ih

/-- Cut: a type derivable once `b` is given is derivable when `b` is derivable. -/
theorem HornDerivable.cut {τ : Type*} {R : Set (Set τ × τ)} {S : Set τ} {b x : τ}
    (hb : HornDerivable R S b) (h : HornDerivable R (insert b S) x) : HornDerivable R S x := by
  induction h with
  | given hx =>
    rcases Set.mem_insert_iff.mp hx with rfl | hx
    · exact hb
    · exact .given hx
  | rule hr _ ih => exact .rule hr ih

/-- Completeness: whatever adding the rule `A → b` derives was derivable
already, or needs only `A` to be derivable and `b` to be given. -/
theorem horn_gap_complete {τ : Type*} {R : Set (Set τ × τ)} {S A : Set τ} {b g : τ}
    (h : HornDerivable (insert (A, b) R) S g) :
    HornDerivable R S g ∨ ((∀ a ∈ A, HornDerivable R S a) ∧ HornDerivable R (insert b S) g) := by
  induction h with
  | given hx => exact .inl (.given hx)
  | @rule I c hr _ ih =>
    by_cases all : ∀ i ∈ I, HornDerivable R S i
    · rcases Set.mem_insert_iff.mp hr with hr | hr
      · cases hr
        exact .inr ⟨all, .given (Set.mem_insert _ _)⟩
      · exact .inl (.rule hr all)
    · push Not at all
      obtain ⟨i, hi, hn⟩ := all
      obtain ⟨hA, -⟩ := (ih i hi).resolve_left hn
      have lifted : ∀ j ∈ I, HornDerivable R (insert b S) j := fun j hj =>
        (ih j hj).elim (fun d => d.mono le_rfl (Set.subset_insert _ _)) And.right
      rcases Set.mem_insert_iff.mp hr with hr | hr
      · cases hr
        exact .inr ⟨hA, .given (Set.mem_insert _ _)⟩
      · exact .inr ⟨hA, .rule hr lifted⟩

/-- Soundness: if `A` is derivable and `g` is derivable once `b` is given,
adding `A → b` derives `g`. -/
theorem horn_gap_sound {τ : Type*} {R : Set (Set τ × τ)} {S A : Set τ} {b g : τ}
    (hA : ∀ a ∈ A, HornDerivable R S a) (hg : HornDerivable R (insert b S) g) :
    HornDerivable (insert (A, b) R) S g := by
  have sub : R ⊆ insert (A, b) R := Set.subset_insert _ _
  exact HornDerivable.cut (.rule (Set.mem_insert _ _) fun a ha => (hA a ha).mono sub le_rfl)
    (hg.mono sub le_rfl)

/-- Exactly the one-rule repairs, for experts with any number of inputs. -/
theorem horn_gap_iff {τ : Type*} {R : Set (Set τ × τ)} {S A : Set τ} {b g : τ}
    (none : ¬ HornDerivable R S g) :
    HornDerivable (insert (A, b) R) S g ↔
      (∀ a ∈ A, HornDerivable R S a) ∧ HornDerivable R (insert b S) g :=
  ⟨fun h => (horn_gap_complete h).resolve_left none, fun ⟨hA, hg⟩ => horn_gap_sound hA hg⟩

/-- Repeated input types have the same type-level reachability as their set.
Distinct argument positions remain a separate obligation. -/
theorem horn_gap_list_iff {τ : Type*} {R : Set (Set τ × τ)} {S : Set τ}
    {inputs : List τ} {b g : τ} (none : ¬ HornDerivable R S g) :
    HornDerivable (insert ({a | a ∈ inputs}, b) R) S g ↔
      (∀ a ∈ inputs, HornDerivable R S a) ∧ HornDerivable R (insert b S) g := by
  simpa using (horn_gap_iff (A := {a | a ∈ inputs}) (b := b) none)

end NCA
