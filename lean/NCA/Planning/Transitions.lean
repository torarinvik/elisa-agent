import Mathlib.Data.List.Basic
import Mathlib.Data.Finset.Card

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

noncomputable def supportedGoals {S A : Type} (model : S → A → Option S)
    (goals : Finset (S × S)) : Finset (S × S) := by
  classical
  exact goals.filter (fun task => ∃ actions, modelRollout model task.1 actions = some task.2)

/-- Preserving supported edges cannot reduce the number of supplied goals with
some supported finite route. This is independent of which routes are selected. -/
theorem refinement_preserves_goal_coverage {S A : Type} [DecidableEq S]
    (old refined : S → A → Option S) (goals : Finset (S × S))
    (preserves : ∀ s a t, old s a = some t → refined s a = some t) :
    (supportedGoals old goals).card ≤ (supportedGoals refined goals).card := by
  classical
  apply Finset.card_le_card
  intro task member
  simp only [supportedGoals] at member ⊢
  simp only [Finset.mem_filter] at member ⊢
  obtain ⟨goalMember, actions, route⟩ := member
  exact ⟨goalMember, actions, refinement_preserves_rollout old refined preserves actions _ _ route⟩

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

/-- A deterministic adaptive interaction, including the successor observed at each step. -/
def adaptiveTrace {S A : Type} (step : S → A → S)
    (choose : List (S × A × S) → S → A) :
    Nat → S → List (S × A × S) → List (S × A × S)
  | 0, _, _ => []
  | n + 1, state, history =>
    let action := choose history state
    let next := step state action
    let observation := (state, action, next)
    observation :: adaptiveTrace step choose n next (history ++ [observation])

/-- Even an adaptive deterministic policy cannot distinguish worlds that agree on
every state-action pair it actually visits in the first world. -/
theorem adaptive_trace_indistinguishable {S A : Type} (first second : S → A → S)
    (choose : List (S × A × S) → S → A) :
    ∀ n state history,
      (∀ edge ∈ adaptiveTrace first choose n state history,
        first edge.1 edge.2.1 = second edge.1 edge.2.1) →
      adaptiveTrace first choose n state history = adaptiveTrace second choose n state history := by
  intro n
  induction n with
  | zero => intro state history agree; rfl
  | succ n ih =>
    intro state history agree
    let action := choose history state
    have head : first state action = second state action := by
      apply agree (state, action, first state action)
      simp [adaptiveTrace, action]
    have tail : ∀ edge ∈ adaptiveTrace first choose n (first state action)
        (history ++ [(state, action, first state action)]),
        first edge.1 edge.2.1 = second edge.1 edge.2.1 := by
      intro edge member
      apply agree edge
      simp [adaptiveTrace, action, member]
    simp only [adaptiveTrace]
    change (state, action, first state action) :: _ = (state, action, second state action) :: _
    rw [← head]
    congr 1
    exact ih _ _ tail

/-- An unvisited transition can be changed without changing the entire adaptive trace. -/
theorem unvisited_transition_alternative {S A : Type} [DecidableEq S] [DecidableEq A]
    (first : S → A → S) (choose : List (S × A × S) → S → A)
    (n : Nat) (initial : S) (history : List (S × A × S))
    (target : S) (action : A) (other : S)
    (different : other ≠ first target action)
    (unvisited : ∀ edge ∈ adaptiveTrace first choose n initial history,
      edge.1 ≠ target ∨ edge.2.1 ≠ action) :
    ∃ second : S → A → S,
      adaptiveTrace first choose n initial history = adaptiveTrace second choose n initial history ∧
      second target action ≠ first target action := by
  let second : S → A → S := fun state move =>
    if state = target ∧ move = action then other else first state move
  refine ⟨second, ?_, ?_⟩
  · apply adaptive_trace_indistinguishable
    intro edge member
    have missing : ¬ (edge.1 = target ∧ edge.2.1 = action) := by
      rcases unvisited edge member with hs | ha
      · exact fun h => hs h.1
      · exact fun h => ha h.2
    simp [second, missing]
  · simpa [second] using different

/-- A truthful observation at a disagreement strictly shrinks a finite version
space while retaining the true hypothesis. -/
theorem disagreement_refinement_progress {H Y : Type} [DecidableEq H] [DecidableEq Y]
    (versions : Finset H) (predict : H → Y) (truth : H) (member : truth ∈ versions)
    (disagreement : ∃ left ∈ versions, ∃ right ∈ versions, predict left ≠ predict right) :
    truth ∈ versions.filter (fun h => predict h = predict truth) ∧
    (versions.filter (fun h => predict h = predict truth)).card < versions.card := by
  classical
  refine ⟨by simp [member], ?_⟩
  obtain ⟨left, hleft, right, hright, different⟩ := disagreement
  have excluded : ∃ h ∈ versions, predict h ≠ predict truth := by
    by_cases h : predict left = predict truth
    · exact ⟨right, hright, fun same => different (h.trans same.symm)⟩
    · exact ⟨left, hleft, h⟩
  obtain ⟨h, hmem, hnot⟩ := excluded
  apply Finset.card_lt_card
  apply Finset.ssubset_iff_subset_ne.mpr
  refine ⟨Finset.filter_subset _ _, ?_⟩
  intro equal
  have : h ∈ versions.filter (fun candidate => predict candidate = predict truth) := by
    rw [equal]
    exact hmem
  exact hnot (Finset.mem_filter.mp this).2

/-- No finite action sequence leaves an absorbing environment state. -/
theorem absorbing_rollout {S A : Type} (step : S → A → S) (state : S)
    (absorbing : ∀ action, step state action = state) (actions : List A) :
    actualRollout step state actions = state := by
  induction actions with
  | nil => rfl
  | cons action rest ih => simpa [actualRollout, absorbing action] using ih

#print axioms projection_model_identified
#print axioms adaptive_trace_indistinguishable
#print axioms unvisited_transition_alternative
#print axioms disagreement_refinement_progress
#print axioms refinement_preserves_rollout
#print axioms refinement_preserves_goal_coverage
#print axioms absorbing_rollout
#print axioms version_rollout_sound
#print axioms supported_rollout

end NCA
