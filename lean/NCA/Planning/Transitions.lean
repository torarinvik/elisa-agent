import Mathlib.Data.List.Basic

namespace NCA

def modelRollout {S A : Type} (model : S → A → Option S) : S → List A → Option S
  | state, [] => some state
  | state, action :: rest => (model state action).bind (fun next => modelRollout model next rest)

def actualRollout {S A : Type} (step : S → A → S) : S → List A → S
  | state, [] => state
  | state, action :: rest => actualRollout step (step state action) rest

/-- Supported correctness composes even for plans selected using the model. -/
theorem supported_rollout {S A : Type} (model : S → A → Option S) (step : S → A → S)
    (faithful : ∀ s a t, model s a = some t → step s a = t)
    (actions : List A) : ∀ s t, modelRollout model s actions = some t →
      actualRollout step s actions = t := by
  induction actions with
  | nil => intro s t h; simpa [modelRollout, actualRollout] using h
  | cons a rest ih =>
    intro s t h
    cases edge : model s a with
    | none => simp [modelRollout, edge] at h
    | some next =>
      have tail : modelRollout model next rest = some t := by
        simpa [modelRollout, edge] using h
      simpa [actualRollout, faithful s a next edge] using ih next t tail

#print axioms supported_rollout

end NCA
