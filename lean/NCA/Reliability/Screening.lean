import NCA.Reliability.Vote

/-! Contradictory pairs as witnesses of unavoidable empirical error (§20.16).
Pairs may be chosen after observing the cases: disjointness, rather than
independence of the selected pairs, is what the deterministic step needs. -/
namespace NCA

open Finset MeasureTheory Classical

/-- Equal input keys force equal predictions. Separation must exclude joint
agreement for every possible output, including approximate agreement rules. -/
theorem separated_pair_conflicts {K Y Z : Type*} (predict : K → Z)
    (agree : Z → Y → Prop) {a b : K} {y z : Y} (same : a = b)
    (separated : ∀ output, ¬(agree output y ∧ agree output z)) :
    ¬(agree (predict a) y ∧ agree (predict b) z) := by
  simpa [same] using separated (predict b)

/-- Every disjoint pair that a predictor cannot satisfy forces a distinct
error. The endpoint injection is the certificate's disjointness condition. -/
theorem contradictory_pairs_errors {n m : ℕ} (correct : Fin n → Prop)
    (endpoint : Fin m × Bool → Fin n) (disjoint : Function.Injective endpoint)
    (conflict : ∀ j, ¬(correct (endpoint (j, false)) ∧ correct (endpoint (j, true)))) :
    m ≤ (univ.filter (fun i => ¬correct i)).card := by
  classical
  let choose : Fin m → Fin n := fun j =>
    if correct (endpoint (j, false)) then endpoint (j, true) else endpoint (j, false)
  have wrong : ∀ j, ¬correct (choose j) := by
    intro j
    dsimp [choose]
    split_ifs with h
    · exact fun ht => conflict j ⟨h, ht⟩
    · exact h
  have inject : Function.Injective choose := by
    intro a b h
    dsimp [choose] at h
    split_ifs at h <;> exact congrArg Prod.fst (disjoint h)
  have sub : univ.image choose ⊆ univ.filter (fun i => ¬correct i) := by
    intro i hi
    obtain ⟨j, _, rfl⟩ := mem_image.mp hi
    exact mem_filter.mpr ⟨mem_univ _, wrong j⟩
  have card := card_le_card sub
  simpa [card_image_of_injective _ inject] using card

/-- A rejection certificate forcing at least `r` errors has probability no
larger than the union over all `r`-subsets of case errors. The joint-error
sampling hypothesis follows from fresh independent cases with error ≤ `ε`;
it is about the original cases, never the adaptively selected pairs. -/
theorem contradiction_screen_risk {Ω : Type*} [MeasurableSpace Ω]
    (μ : Measure Ω) (fails : ℕ → Set Ω) (reject : Set Ω) (n r : ℕ) (ε : ENNReal)
    (forced : ∀ ω ∈ reject, r ≤ ((range n).filter (fun i => ω ∈ fails i)).card)
    (joint : ∀ S ∈ (range n).powersetCard r,
      μ (⋂ i ∈ S, fails i) ≤ ε ^ r) :
    μ reject ≤ n.choose r * ε ^ r := by
  calc
    μ reject ≤ μ {ω | r ≤ ((range n).filter (fun i => ω ∈ fails i)).card} :=
      measure_mono forced
    _ ≤ ∑ S ∈ (range n).powersetCard r, ∏ _i ∈ S, ε := by
      apply vote_risk
      intro S hS
      simpa [(mem_powersetCard.mp hS).2] using joint S hS
    _ = n.choose r * ε ^ r := by
      have : ∀ S ∈ (range n).powersetCard r, (∏ _i ∈ S, ε) = ε ^ r := by
        intro S hS
        simp [(mem_powersetCard.mp hS).2]
      rw [sum_congr rfl this]
      simp [sum_const, nsmul_eq_mul]

end NCA
