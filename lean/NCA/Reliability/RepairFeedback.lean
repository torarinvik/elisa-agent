import Mathlib.Data.Finset.Card

/-! Counterexample-guided progress (§31.10). Monotonic repair is a hypothesis
about the supplied learner, not a guarantee of the feedback transport. -/
namespace NCA

/-- A supplied feature key selects an observed end-to-end correction. -/
def keyCorrection {X Y K : Type*} [DecidableEq K] (base : X → Y) (key : X → K)
    (point : X) (label : Y) (x : X) : Y :=
  if key x = key point then label else base x

theorem keyCorrection_outside {X Y K : Type*} [DecidableEq K]
    (base : X → Y) (key : X → K) (point x : X) (label : Y)
    (outside : key x ≠ key point) : keyCorrection base key point label x = base x := by
  simp [keyCorrection, outside]

/-- A constant correction preserves protected observed successes when every
such success in its key fiber has the correction's target. -/
theorem keyCorrection_protected {X Y K : Type*} [DecidableEq K]
    (base truth : X → Y) (key : X → K) (point : X) (label : Y) (controls : Set X)
    (compatible : ∀ x ∈ controls, base x = truth x → key x = key point → label = truth x) :
    ∀ x ∈ controls, base x = truth x → keyCorrection base key point label x = truth x := by
  intro x hx good
  by_cases same : key x = key point
  · simpa [keyCorrection, same] using compatible x hx good same
  · simpa [keyCorrection, same] using good

/-- Injectivity is unnecessary when the truth is constant on the corrected
fiber. Learning that condition from finite data still requires validation. -/
theorem fiber_correction_errors {X Y K : Type*} [DecidableEq K]
    (base truth : X → Y) (key : X → K) (point x : X)
    (consistent : ∀ y, key y = key point → truth y = truth point)
    (wrong : keyCorrection base key point (truth point) x ≠ truth x) :
    base x ≠ truth x ∧ key x ≠ key point := by
  by_cases same : key x = key point
  · have equal := consistent x same
    simp [keyCorrection, same, equal] at wrong
  · exact ⟨by simpa [keyCorrection, same] using wrong, same⟩

/-- With a complete injective key and a truthful observed target, no new
error is introduced, and the observed point cannot remain an error. -/
theorem endpoint_correction_errors {X Y K : Type*} [DecidableEq K]
    (base truth : X → Y) (key : X → K) (complete : Function.Injective key)
    (point x : X) (wrong : keyCorrection base key point (truth point) x ≠ truth x) :
    base x ≠ truth x ∧ x ≠ point := by
  by_cases same : key x = key point
  · have equal := complete same
    subst x
    simp [keyCorrection] at wrong
  · refine ⟨by simpa [keyCorrection, same] using wrong, ?_⟩
    intro equal
    exact same (congrArg key equal)

theorem feedback_repair_progress {α : Type*} [DecidableEq α]
    (errors repaired : Finset α) (case : α) (failed : case ∈ errors)
    (monotone : repaired ⊆ errors.erase case) : repaired.card < errors.card :=
  (Finset.card_le_card monotone).trans_lt (Finset.card_erase_lt_of_mem failed)

theorem feedback_chain_bound {α : Type*} [DecidableEq α]
    (errors : ℕ → Finset α) (witness : ℕ → α) (n : ℕ)
    (steps : ∀ i < n, witness i ∈ errors i ∧ errors (i + 1) ⊆ (errors i).erase (witness i)) :
    (errors n).card + n ≤ (errors 0).card := by
  induction n with
  | zero => simp
  | succ n ih =>
    have previous := ih (fun i hi => steps i (by omega))
    have step := steps n (by omega)
    have smaller := feedback_repair_progress (errors n) (errors (n + 1)) (witness n)
      step.1 step.2
    omega

/-- Retaining already charged observations adds no new label identifiers, and
fresh later tests remain disjoint even when retained data train the candidate.
Identifiers denote draws, not potentially repeated payload values. -/
theorem retained_feedback_account {α : Type*} [DecidableEq α]
    (drawn retained future : Finset α) (kept : retained ⊆ drawn)
    (fresh : Disjoint drawn future) :
    (drawn ∪ retained).card = drawn.card ∧ Disjoint retained future := by
  exact ⟨by rw [Finset.union_eq_left.mpr kept], fresh.mono_left kept⟩

end NCA
