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

def transitionConsistent {S A : Type} [DecidableEq S]
    (observed : List (S × A × S)) (predict : S → A → S) : Bool :=
  observed.all (fun edge => decide (predict edge.1 edge.2.1 = edge.2.2))

/-- Correct observations and finite-family unanimity justify an adaptively chosen rollout. -/
theorem version_rollout_sound {S A : Type} [DecidableEq S]
    (family : List (S → A → S)) (truth : S → A → S)
    (observed : List (S × A × S)) (member : truth ∈ family)
    (correct : ∀ edge ∈ observed, truth edge.1 edge.2.1 = edge.2.2)
    (model : S → A → Option S)
    (unanimous : ∀ h ∈ family.filter (transitionConsistent observed),
      ∀ s a next, model s a = some next → h s a = next)
    (actions : List A) (state terminal : S)
    (returned : modelRollout model state actions = some terminal) :
    actualRollout truth state actions = terminal := by
  have retained : truth ∈ family.filter (transitionConsistent observed) := by
    simp only [List.mem_filter]
    refine ⟨member, ?_⟩
    unfold transitionConsistent
    apply List.all_eq_true.mpr
    intro edge hedge
    simp [correct edge hedge]
  exact supported_rollout model truth (unanimous truth retained) actions state terminal returned

/-- Preserving supported edges preserves each finite supported rollout. -/
theorem refinement_preserves_rollout {S A : Type} (old refined : S → A → Option S)
    (preserves : ∀ s a t, old s a = some t → refined s a = some t)
    (actions : List A) : ∀ s t, modelRollout old s actions = some t →
      modelRollout refined s actions = some t := by
  induction actions with
  | nil => intro s t h; simpa [modelRollout] using h
  | cons action rest ih =>
    intro s t h
    cases edge : old s action with
    | none => simp [modelRollout, edge] at h
    | some next =>
      have tail : modelRollout old next rest = some t := by
        simpa [modelRollout, edge] using h
      have newer : refined s action = some next := preserves s action next edge
      simpa [modelRollout, newer] using ih next t tail

/-- Distinct observed field signatures identify every projection, hence unseen states. -/
theorem projection_model_identified {I J F V : Type} (observed : I → F → V)
    (truth candidate : J → F)
    (separates : Function.Injective (fun field => fun sample => observed sample field))
    (consistent : ∀ sample output, observed sample (candidate output) = observed sample (truth output))
    (state : F → V) : (fun output => state (candidate output)) = (fun output => state (truth output)) := by
  funext output
  have same : candidate output = truth output := by
    apply separates
    funext sample
    exact consistent sample output
  rw [same]

/-- No finite action sequence leaves an absorbing environment state. -/
theorem absorbing_rollout {S A : Type} (step : S → A → S) (state : S)
    (absorbing : ∀ action, step state action = state) (actions : List A) :
    actualRollout step state actions = state := by
  induction actions with
  | nil => rfl
  | cons action rest ih => simpa [actualRollout, absorbing action] using ih

#print axioms projection_model_identified
#print axioms refinement_preserves_rollout
#print axioms absorbing_rollout
#print axioms version_rollout_sound
#print axioms supported_rollout

end NCA
