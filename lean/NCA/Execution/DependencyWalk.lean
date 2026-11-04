import Mathlib.Data.List.Basic
import Mathlib.Data.Finset.Basic
import Lean.Elab.Tactic.Omega

/-! Explicit visit/emit tasks for dependency-first DAG traversal (§28.10).
A finite admitted DAG supplies a weight larger than one plus its children's
weights. The executable walker uses a stack, not these analytical weights. -/
namespace NCA

variable {A : Type*}

def dependencyWork (weight : A → ℕ) (tasks : List (A × Bool)) : ℕ :=
  (tasks.map fun task => if task.2 then 1 else weight task.1).sum

/-- Expand a first visit into ordered child visits followed by its emission.
The stack's work decreases regardless of the continuation's depth. -/
theorem dependency_expand_decreases (weight : A → ℕ) (node : A)
    (children : List A) (rest : List (A × Bool))
    (acyclic : 1 + (children.map weight).sum < weight node) :
    dependencyWork weight
      (children.map (fun child => (child, false)) ++ (node, true) :: rest) <
      dependencyWork weight ((node, false) :: rest) := by
  simp only [dependencyWork, List.map_append, List.map_map, List.map_cons,
    List.sum_append, List.sum_cons, Function.comp_def, Bool.false_eq_true, ↓reduceIte]
  change (children.map (fun child => weight child)).sum +
    (1 + dependencyWork weight rest) < weight node + dependencyWork weight rest
  have same : children.map (fun child => weight child) = children.map weight := rfl
  rw [same]
  omega

/-- Popping a duplicate visit or an emission consumes positive work. -/
theorem dependency_pop_decreases (weight : A → ℕ) (node : A) (emit : Bool)
    (rest : List (A × Bool)) (positive : 0 < weight node) :
    dependencyWork weight rest < dependencyWork weight ((node, emit) :: rest) := by
  cases emit <;> simp [dependencyWork]
  omega

def dependencyStep [DecidableEq A] (children : A → List A)
    (state : Finset A × List (A × Bool)) : Option (Finset A × List (A × Bool)) :=
  match state.2 with
  | [] => none
  | (node, emit) :: rest =>
    if emit then some (state.1, rest)
    else if node ∈ state.1 then some (state.1, rest)
    else some (insert node state.1,
      (children node).map (fun child => (child, false)) ++ (node, true) :: rest)

/-- Every actual machine step decreases the analytical pending work. -/
theorem dependency_step_decreases [DecidableEq A] (children : A → List A)
    (weight : A → ℕ)
    (acyclic : ∀ node, 1 + ((children node).map weight).sum < weight node)
    (before after : Finset A × List (A × Bool))
    (step : dependencyStep children before = some after) :
    dependencyWork weight after.2 < dependencyWork weight before.2 := by
  rcases before with ⟨seen, tasks⟩
  cases tasks with
  | nil => simp [dependencyStep] at step
  | cons task rest =>
    rcases task with ⟨node, emit⟩
    have positive : 0 < weight node := by have := acyclic node; omega
    cases emit with
    | true =>
      simp only [dependencyStep, ↓reduceIte, Option.some.injEq] at step
      subst after
      exact dependency_pop_decreases weight node true rest positive
    | false =>
      by_cases present : node ∈ seen
      · simp only [dependencyStep, Bool.false_eq_true, ↓reduceIte, present,
          Option.some.injEq] at step
        subst after
        exact dependency_pop_decreases weight node false rest positive
      · simp only [dependencyStep, Bool.false_eq_true, ↓reduceIte, present,
          Option.some.injEq] at step
        subst after
        exact dependency_expand_decreases weight node (children node) rest (acyclic node)

/-- An infinite run is impossible; this concerns the explicit machine, with no
bound on host recursion depth or on the number of admitted graph vertices. -/
theorem dependency_no_infinite_run [DecidableEq A] (children : A → List A)
    (weight : A → ℕ)
    (acyclic : ∀ node, 1 + ((children node).map weight).sum < weight node)
    (states : ℕ → Finset A × List (A × Bool)) :
    ¬(∀ k, dependencyStep children (states k) = some (states (k + 1))) := by
  intro run
  have bound : ∀ k, k + dependencyWork weight (states k).2 ≤
      dependencyWork weight (states 0).2 := by
    intro k
    induction k with
    | zero => omega
    | succ k ih =>
      have smaller := dependency_step_decreases children weight acyclic _ _ (run k)
      omega
  have impossible := bound (dependencyWork weight (states 0).2 + 1)
  omega

/-- Scope occurrences are not memoized: repeated exports may be fresh wrappers.
Each frame finishes only after all its ordered child requests return. -/
def scopeStep (children : A → List A) : List (A × Bool) → Option (List (A × Bool))
  | [] => none
  | (node, emit) :: rest =>
    if emit then some rest
    else some ((children node).map (fun child => (child, false)) ++ (node, true) :: rest)

theorem scope_step_decreases (children : A → List A) (weight : A → ℕ)
    (acyclic : ∀ node, 1 + ((children node).map weight).sum < weight node)
    (before after : List (A × Bool)) (step : scopeStep children before = some after) :
    dependencyWork weight after < dependencyWork weight before := by
  cases before with
  | nil => simp [scopeStep] at step
  | cons task rest =>
    rcases task with ⟨node, emit⟩
    cases emit with
    | true =>
      simp only [scopeStep, ↓reduceIte, Option.some.injEq] at step
      subst after
      have positive : 0 < weight node := by have := acyclic node; omega
      exact dependency_pop_decreases weight node true rest positive
    | false =>
      simp only [scopeStep, Bool.false_eq_true, ↓reduceIte, Option.some.injEq] at step
      subst after
      exact dependency_expand_decreases weight node (children node) rest (acyclic node)

/-- Even with fresh repeated occurrences, scope expansion terminates under
acyclic weights; the finite graph may induce exponentially many occurrences. -/
theorem scope_no_infinite_run (children : A → List A) (weight : A → ℕ)
    (acyclic : ∀ node, 1 + ((children node).map weight).sum < weight node)
    (states : ℕ → List (A × Bool)) :
    ¬(∀ k, scopeStep children (states k) = some (states (k + 1))) := by
  intro run
  have bound : ∀ k, k + dependencyWork weight (states k) ≤
      dependencyWork weight (states 0) := by
    intro k
    induction k with
    | zero => omega
    | succ k ih =>
      have smaller := scope_step_decreases children weight acyclic _ _ (run k)
      omega
  have impossible := bound (dependencyWork weight (states 0) + 1)
  omega

/-- Exact stack accounting: an expansion schedules one emission and d edges.
Other pops change only pending and consumed counts. -/
theorem dependency_expand_account (pending consumed vertices edges d : ℕ)
    (account : pending + 1 + consumed = 1 + vertices + edges) :
    (pending + d + 1) + (consumed + 1) = 1 + (vertices + 1) + (edges + d) := by
  omega

theorem dependency_pop_account (pending consumed vertices edges : ℕ)
    (account : pending + 1 + consumed = 1 + vertices + edges) :
    pending + (consumed + 1) = 1 + vertices + edges := by
  omega

/-- Appending a fresh ready vertex preserves dependency-before-parent order.
Readiness of the actual stack schedule and faithful decoding remain boundaries. -/
theorem dependency_append_order [DecidableEq A] (children : A → List A)
    (output : List A) (node : A) (fresh : node ∉ output)
    (ordered : ∀ parent ∈ output, ∀ child ∈ children parent,
      child ∈ output ∧ output.idxOf child < output.idxOf parent)
    (ready : ∀ child ∈ children node, child ∈ output) :
    ∀ parent ∈ output ++ [node], ∀ child ∈ children parent,
      child ∈ output ++ [node] ∧
        (output ++ [node]).idxOf child < (output ++ [node]).idxOf parent := by
  intro parent hp child hc
  rcases List.mem_append.mp hp with old | new
  · obtain ⟨present, before⟩ := ordered parent old child hc
    refine ⟨List.mem_append_left _ present, ?_⟩
    simpa only [List.idxOf_append_of_mem present, List.idxOf_append_of_mem old] using before
  · have same : parent = node := by simpa only [List.mem_singleton] using new
    subst parent
    have present := ready child hc
    refine ⟨List.mem_append_left _ present, ?_⟩
    rw [List.idxOf_append_of_mem present, List.idxOf_append]
    simpa [fresh] using (List.idxOf_lt_length_iff.mpr present)

end NCA
