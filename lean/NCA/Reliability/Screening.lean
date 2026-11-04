import NCA.Reliability.Vote
import NCA.Reliability.SampledGate

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

/-- Reopening, lost attempts and bounded-cache misses may skip spending
positions. Replaying scoped refusals creates no new false-discard event:
every such event must originate in an original wrong rejection. -/
theorem durable_refusal_risk {Ω : Type*} [MeasurableSpace Ω]
    (μ : Measure Ω) {δ : ℝ} (hδ : 0 ≤ δ) (used : Finset ℕ)
    (wrong : ℕ → Set Ω) (replayed : Set Ω)
    (origin : replayed ⊆ ⋃ k ∈ used, wrong k)
    (each : ∀ k ∈ used, μ (wrong k) ≤ ENNReal.ofReal (decisionLevel δ k)) :
    μ replayed ≤ ENNReal.ofReal δ := by
  classical
  let selected : ℕ → Set Ω := fun k => if k ∈ used then wrong k else ∅
  have bounded : ∀ k ∈ used, k < used.sup id + 1 := by
    intro k hk
    exact Nat.lt_succ_of_le (le_sup (f := id) hk)
  have sub : replayed ⊆ ⋃ k ∈ range (used.sup id + 1), selected k := by
    intro ω hω
    obtain ⟨k, hk⟩ := Set.mem_iUnion.mp (origin hω)
    obtain ⟨hk, hw⟩ := Set.mem_iUnion.mp hk
    exact Set.mem_iUnion.mpr ⟨k, Set.mem_iUnion.mpr
      ⟨mem_range.mpr (bounded k hk), by simpa [selected, hk] using hw⟩⟩
  refine (measure_mono sub).trans (acquisition_sound μ hδ _ selected ?_)
  intro k _
  by_cases hk : k ∈ used
  · simpa [selected, hk] using each k hk
  · simp [selected, hk]

/-- Retaining an unmatched new case preserves the absence of any available
contradiction when it has no edge from an earlier unmatched case. -/
theorem unmatched_append {A : Type*} (edge : A → A → Prop) (pending : List A) (x : A)
    (independent : pending.Pairwise (fun a b => ¬edge a b))
    (none : ∀ a ∈ pending, ¬edge a x) :
    (pending ++ [x]).Pairwise (fun a b => ¬edge a b) := by
  apply List.pairwise_append.mpr
  refine ⟨independent, by simp, ?_⟩
  intro a ha b hb
  have same : b = x := by simpa only [List.mem_singleton] using hb
  rw [same]
  exact none a ha

/-- Consuming a matched endpoint preserves independence of those still pending. -/
theorem unmatched_remove {A : Type*} (edge : A → A → Prop) (pending : List A) (i : ℕ)
    (independent : pending.Pairwise (fun a b => ¬edge a b)) :
    (pending.eraseIdx i).Pairwise (fun a b => ¬edge a b) :=
  List.Pairwise.sublist (List.eraseIdx_sublist pending i) independent

/-- If every alternative matching edge touches a used endpoint, that matching
has at most twice as many edges. Maximal need not mean maximum. -/
theorem maximal_pairs_half {n m k : ℕ}
    (used : Fin m × Bool → Fin n) (alternative : Fin k × Bool → Fin n)
    (disjoint : Function.Injective alternative)
    (cover : ∀ j, ∃ target : Fin m × Bool, ∃ b, used target = alternative (j, b)) :
    k ≤ 2 * m := by
  classical
  let choose : Fin k → Fin m × Bool := fun j => Classical.choose (cover j)
  have witness : ∀ j, ∃ b, used (choose j) = alternative (j, b) :=
    fun j => Classical.choose_spec (cover j)
  have inject : Function.Injective choose := by
    intro a b same
    obtain ⟨ab, ha⟩ := witness a
    obtain ⟨bb, hb⟩ := witness b
    have equal : alternative (a, ab) = alternative (b, bb) := by
      rw [← ha, ← hb, same]
    exact congrArg Prod.fst (disjoint equal)
  have bound := Fintype.card_le_of_injective choose inject
  simpa [Nat.mul_comm] using bound

end NCA
