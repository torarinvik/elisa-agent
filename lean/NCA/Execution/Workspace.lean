import Mathlib.Data.List.Basic
import Mathlib.Logic.Function.Basic

/-! Fresh workspace identifiers and reversal of an appended suffix (§42.5).
Values denote opaque admitted message objects; no payload equality is needed.
Container fidelity, object immutability and serialized calls remain assumptions. -/
namespace NCA

variable {K V : Type*} [DecidableEq K]

def workspaceWrite (index : K → Option V) (key : K) (value : V) : K → Option V :=
  Function.update index key (some value)

def workspaceErase (index : K → Option V) (key : K) : K → Option V :=
  Function.update index key none

theorem workspace_undo_fresh (index : K → Option V) (key : K) (value : V)
    (fresh : index key = none) :
    workspaceErase (workspaceWrite index key value) key = index := by
  funext query
  by_cases same : query = key
  · subst query
    simp [workspaceErase, workspaceWrite, fresh]
  · simp [workspaceErase, workspaceWrite, Function.update, same]

theorem workspace_write_preserves (index : K → Option V) (key query : K)
    (value old : V) (fresh : index key = none) (present : index query = some old) :
    workspaceWrite index key value query = some old := by
  have distinct : query ≠ key := by
    intro same
    subst query
    rw [fresh] at present
    cases present
  simp [workspaceWrite, Function.update, distinct, present]

def workspaceFresh (index : K → Option V) : List (K × V) → Prop
  | [] => True
  | (key, value) :: rest => index key = none ∧
      workspaceFresh (workspaceWrite index key value) rest

def workspaceExtend (index : K → Option V) : List (K × V) → K → Option V
  | [] => index
  | (key, value) :: rest => workspaceExtend (workspaceWrite index key value) rest

/-- Reverse suffix erasure, matching reverse-order rollback of fresh posts. -/
def workspaceUndo (index : K → Option V) : List (K × V) → K → Option V
  | [] => index
  | (key, _) :: rest => workspaceErase (workspaceUndo index rest) key

theorem workspace_suffix_restores (index : K → Option V) (suffix : List (K × V))
    (fresh : workspaceFresh index suffix) :
    workspaceUndo (workspaceExtend index suffix) suffix = index := by
  induction suffix generalizing index with
  | nil => rfl
  | cons entry rest ih =>
    rcases entry with ⟨key, value⟩
    rcases fresh with ⟨first, tail⟩
    simp only [workspaceExtend, workspaceUndo]
    rw [ih (workspaceWrite index key value) tail]
    exact workspace_undo_fresh index key value first

theorem workspace_extension_retains (index : K → Option V) (suffix : List (K × V))
    (fresh : workspaceFresh index suffix) (query : K) (old : V)
    (present : index query = some old) :
    workspaceExtend index suffix query = some old := by
  induction suffix generalizing index with
  | nil => exact present
  | cons entry rest ih =>
    rcases entry with ⟨key, value⟩
    rcases fresh with ⟨first, tail⟩
    exact ih _ tail (workspace_write_preserves index key query value old first present)

theorem workspace_log_restores {M : Type*} (base suffix : List M) :
    (base ++ suffix).take base.length = base := by simp

end NCA
