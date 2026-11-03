import Mathlib.Data.List.Basic

/-! Conditional invariant preservation for ordinary routes threaded through state.
This models successful finite prefixes, not mutable payloads or external effects. -/
namespace NCA

variable {S E : Type}

def stateRun (step : S → E → S) : S → List E → S
  | state, [] => state
  | state, event :: rest => stateRun step (step state event) rest

theorem stateRun_invariant (step : S → E → S) (P : S → Prop)
    (preserves : ∀ state event, P state → P (step state event))
    (events : List E) (state : S) (initial : P state) :
    P (stateRun step state events) := by
  induction events generalizing state with
  | nil => exact initial
  | cons event rest ih => exact ih (step state event) (preserves state event initial)

/-- Failed transitions leave the cursor unchanged; this assumes immutable state. -/
def stateCommit (state : S) (result : Option S) : S := result.getD state

theorem stateCommit_failure (state : S) : stateCommit state none = state := rfl

theorem stateCommit_invariant (P : S → Prop) (state : S) (result : Option S)
    (initial : P state) (accepted : ∀ next, result = some next → P next) :
    P (stateCommit state result) := by
  cases result with
  | none => exact initial
  | some next => exact accepted next rfl

end NCA
