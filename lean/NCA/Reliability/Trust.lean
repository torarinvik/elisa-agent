/-!
# Isolation of untrusted evidence

Decisions under a trust read the attestations it accepts. Extending the
evidence by attestations it does not accept leaves the accepted list, and
so every decision computed from it, unchanged (`decision_isolated`).
-/

namespace NCA

theorem filter_append_unaccepted {α : Type} (accepts : α → Bool) (l extra : List α)
    (h : ∀ a ∈ extra, accepts a = false) : (l ++ extra).filter accepts = l.filter accepts := by
  have hextra : extra.filter accepts = [] :=
    List.filter_eq_nil_iff.mpr fun a ha => by simp [h a ha]
  rw [List.filter_append, hextra, List.append_nil]

/-- **Isolation.** A decision computed from the accepted attestations is
unchanged by attestations the trust does not accept. -/
theorem decision_isolated {α β : Type} (accepts : α → Bool) (decide : List α → β)
    (l extra : List α) (h : ∀ a ∈ extra, accepts a = false) :
    decide ((l ++ extra).filter accepts) = decide (l.filter accepts) := by
  rw [filter_append_unaccepted accepts l extra h]

end NCA
