import Mathlib.Data.Finset.Card

/-! Counterexample-guided progress (§31.10). Monotonic repair is a hypothesis
about the supplied learner, not a guarantee of the feedback transport. -/
namespace NCA

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

end NCA
