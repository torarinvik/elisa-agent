import Mathlib.Data.Fintype.Card
import Mathlib.Data.Finset.Prod
import Mathlib.MeasureTheory.Measure.MeasureSpace

/-! Hub types (§29.4). Contributor types `T i` meet through one shared type `H`:
each contributes an encoder `T i → H` and a decoder `H → T i`. Connectors are
edges `(source, target)` over `Option ι`, with `none` the hub. -/
namespace NCA

open Finset MeasureTheory

variable {ι : Type*} [DecidableEq ι]

/-- A connector from one type to another; `none` is the hub. -/
abbrev Connector (ι : Type*) := Option ι × Option ι

/-- The hub connectors of contributor types `S`: one encoder and one decoder each. -/
def hubConnectors (S : Finset ι) : Finset (Connector ι) :=
  S.image (fun i => (some i, none)) ∪ S.image (fun i => (none, some i))

theorem hubConnectors_card (S : Finset ι) : (hubConnectors S).card = 2 * S.card := by
  unfold hubConnectors
  rw [card_union_of_disjoint, card_image_of_injective, card_image_of_injective]
  · ring
  · intro a b h; simpa using h
  · intro a b h; simpa using h
  · rw [disjoint_left]
    intro c h₁ h₂
    simp only [mem_image] at h₁ h₂
    obtain ⟨_, _, rfl⟩ := h₁
    obtain ⟨_, _, h⟩ := h₂
    cases h

/-- Every ordered pair of contributor types is joined by an encoder then a decoder. -/
theorem hub_routes {S : Finset ι} {i j : ι} (hi : i ∈ S) (hj : j ∈ S) :
    (some i, none) ∈ hubConnectors S ∧ (none, some j) ∈ hubConnectors S := by
  unfold hubConnectors
  exact ⟨mem_union_left _ (mem_image_of_mem _ hi), mem_union_right _ (mem_image_of_mem _ hj)⟩

omit [DecidableEq ι] in
/-- Without a shared type, single-step translators joining every ordered pair
of distinct types number at least `n (n - 1)`. -/
theorem direct_connectors_lower (S : Finset ι) (E : Finset (ι × ι))
    (joins : ∀ i ∈ S, ∀ j ∈ S, i ≠ j → (i, j) ∈ E) :
    S.card * S.card - S.card ≤ E.card := by
  have : S.offDiag ⊆ E := by
    intro p hp
    obtain ⟨hi, hj, ne⟩ := mem_offDiag.mp hp
    exact joins _ hi _ hj ne
  calc S.card * S.card - S.card = S.offDiag.card := (offDiag_card S).symm
    _ ≤ E.card := card_le_card this

/-- Adding a contributor type adds only connectors touching it: every existing
connector, and so every existing route, remains. -/
theorem hubConnectors_mono {S S' : Finset ι} (h : S ⊆ S') :
    hubConnectors S ⊆ hubConnectors S' := by
  unfold hubConnectors
  exact union_subset_union (image_subset_image h) (image_subset_image h)

/-- A hub route fails only if its encoder or decoder does, so its risk is at
most the sum of theirs, whatever the number of contributors. -/
theorem hub_route_risk {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    (encoderFails decoderFails : Set Ω) {a b : ENNReal}
    (ha : μ encoderFails ≤ a) (hb : μ decoderFails ≤ b) :
    μ (encoderFails ∪ decoderFails) ≤ a + b :=
  (measure_union_le _ _).trans (add_le_add ha hb)

/-- Attachment (§29.5): a type learned by pairing with a partner member maps a
value wrongly into the hub only if its own fit is wrong there or the partner's
encoder is. -/
theorem attached_risk {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    (fitWrong partnerWrong : Set Ω) {a b : ENNReal}
    (ha : μ fitWrong ≤ a) (hb : μ partnerWrong ≤ b) :
    μ (fitWrong ∪ partnerWrong) ≤ a + b :=
  (measure_union_le _ _).trans (add_le_add ha hb)

/-- Along an attachment path of length `d` whose fits each err with
probability at most `ε`, the hub error is at most `d ε`. -/
theorem attachment_depth_risk {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    (fitWrong : ℕ → Set Ω) {ε : ENNReal} (each : ∀ i, μ (fitWrong i) ≤ ε) (d : ℕ) :
    μ (⋃ i ∈ range d, fitWrong i) ≤ d * ε := by
  calc μ (⋃ i ∈ range d, fitWrong i) ≤ ∑ i ∈ range d, μ (fitWrong i) :=
        measure_biUnion_finset_le _ _
    _ ≤ ∑ _i ∈ range d, ε := sum_le_sum fun i _ => each i
    _ = d * ε := by rw [sum_const, card_range, nsmul_eq_mul]

end NCA
