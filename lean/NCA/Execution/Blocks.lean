import Mathlib.Order.Basic
import NCA.Execution.Memory

/-! A trunk kept as a library of blocks that are added and never changed (chapter 66). -/
namespace NCA

variable {N X F Y : Type} [DecidableEq N]

/-- What an expert reads: each named block applied to the input, if every one is present. -/
def readBlocks (library : N → Option (X → F)) : List N → X → Option (List F)
  | [], _ => some []
  | name :: rest, x =>
    match library name, readBlocks library rest x with
    | some block, some more => some (block x :: more)
    | _, _ => none

/-- An expert's output: its last part applied to what it reads. -/
def expertOutput (library : N → Option (X → F)) (reads : List N) (last : List F → Y) (x : X) :
    Option Y :=
  (readBlocks library reads x).map last

omit [DecidableEq N] in
/-- Two libraries that agree on the blocks an expert reads give it the same reading. -/
theorem readBlocks_congr (a b : N → Option (X → F)) (reads : List N) (x : X)
    (agree : ∀ name ∈ reads, a name = b name) : readBlocks a reads x = readBlocks b reads x := by
  induction reads with
  | nil => rfl
  | cons head tail ih =>
    have here := agree head (List.mem_cons_self ..)
    have there := ih (fun name member => agree name (List.mem_cons_of_mem _ member))
    simp only [readBlocks, here, there]

omit [DecidableEq N] in
/-- An expert's output is fixed by the blocks it reads, whatever else the library holds. -/
theorem expertOutput_congr (a b : N → Option (X → F)) (reads : List N) (last : List F → Y) (x : X)
    (agree : ∀ name ∈ reads, a name = b name) :
    expertOutput a reads last x = expertOutput b reads last x := by
  unfold expertOutput
  rw [readBlocks_congr a b reads x agree]

/-- Adding a block leaves every expert whose blocks are present exactly as it was, on every input. -/
theorem added_block_preserves (library : N → Option (X → F)) (name : N) (block : X → F)
    (reads : List N) (last : List F → Y) (x : X)
    (present : ∀ read ∈ reads, ∃ old, library read = some old) :
    expertOutput (memoryInsert library name block) reads last x =
      expertOutput library reads last x := by
  apply expertOutput_congr
  intro read member
  obtain ⟨old, existing⟩ := present read member
  rw [memoryInsert_preserves library name read block old existing, existing]

/-- A library after a run of additions. -/
def addBlocks (library : N → Option (X → F)) : List (N × (X → F)) → N → Option (X → F)
  | [] => library
  | (name, block) :: rest => addBlocks (memoryInsert library name block) rest

/-- However many blocks are added afterwards, an expert's output is what it was when it was made. -/
theorem added_blocks_preserve (additions : List (N × (X → F))) (library : N → Option (X → F))
    (reads : List N) (last : List F → Y) (x : X)
    (present : ∀ read ∈ reads, ∃ old, library read = some old) :
    expertOutput (addBlocks library additions) reads last x = expertOutput library reads last x := by
  induction additions generalizing library with
  | nil => rfl
  | cons first rest ih =>
    obtain ⟨name, block⟩ := first
    have still : ∀ read ∈ reads, ∃ old, memoryInsert library name block read = some old := by
      intro read member
      obtain ⟨old, existing⟩ := present read member
      exact ⟨old, memoryInsert_preserves library name read block old existing⟩
    simp only [addBlocks]
    rw [ih (memoryInsert library name block) still]
    exact added_block_preserves library name block reads last x present

/-- A library with one block taken away. -/
def removeBlock (library : N → Option (X → F)) (name : N) : N → Option (X → F) :=
  fun query => if query = name then none else library query

/-- Taking away a block an expert does not read leaves the expert exactly as it was. -/
theorem removed_unread_preserves (library : N → Option (X → F)) (name : N) (reads : List N)
    (last : List F → Y) (x : X) (unread : name ∉ reads) :
    expertOutput (removeBlock library name) reads last x = expertOutput library reads last x := by
  apply expertOutput_congr
  intro read member
  have other : read ≠ name := fun same => unread (same ▸ member)
  simp [removeBlock, other]

omit [DecidableEq N] in
/-- A reading that names a block the library lacks is no reading. -/
theorem readBlocks_missing (library : N → Option (X → F)) (name : N) (reads : List N) (x : X)
    (missing : library name = none) (member : name ∈ reads) : readBlocks library reads x = none := by
  induction reads with
  | nil => cases member
  | cons head tail ih =>
    rcases List.mem_cons.mp member with same | later
    · subst same
      simp [readBlocks, missing]
    · have rest := ih later
      cases found : library head <;> simp [readBlocks, found, rest]

/-- Taking away a block an expert reads leaves the expert without an output. -/
theorem removed_read_fails (library : N → Option (X → F)) (name : N) (reads : List N)
    (last : List F → Y) (x : X) (read : name ∈ reads) :
    expertOutput (removeBlock library name) reads last x = none := by
  unfold expertOutput
  rw [readBlocks_missing (removeBlock library name) name reads x (by simp [removeBlock]) read]
  rfl

/-- The reading of least loss among a first and those tried after it. -/
def chooseReading {C L : Type} [LinearOrder L] (loss : C → L) (own : C) (others : List C) : C :=
  others.foldl (fun best next => if loss next < loss best then next else best) own

/-- The chosen reading has no more loss than the first. -/
theorem chosen_not_worse {C L : Type} [LinearOrder L] (loss : C → L) (own : C) (others : List C) :
    loss (chooseReading loss own others) ≤ loss own := by
  induction others generalizing own with
  | nil => exact le_refl _
  | cons next rest ih =>
    simp only [chooseReading, List.foldl_cons]
    by_cases better : loss next < loss own
    · simp only [better, if_true]
      exact le_trans (ih next) (le_of_lt better)
    · simp only [better, if_false]
      exact ih own

/-- The chosen reading has no more loss than any reading tried. -/
theorem chosen_least {C L : Type} [LinearOrder L] (loss : C → L) (own : C) (others : List C)
    (tried : C) (member : tried ∈ others) : loss (chooseReading loss own others) ≤ loss tried := by
  induction others generalizing own with
  | nil => cases member
  | cons next rest ih =>
    simp only [chooseReading, List.foldl_cons]
    rcases List.mem_cons.mp member with same | later
    · subst same
      by_cases better : loss tried < loss own
      · simp only [better, if_true]
        exact chosen_not_worse loss tried rest
      · simp only [better, if_false]
        exact le_trans (chosen_not_worse loss own rest) (not_lt.mp better)
    · exact ih _ later

end NCA
