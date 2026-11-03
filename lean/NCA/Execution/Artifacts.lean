import Std.Data.HashMap.Lemmas
import Mathlib.Data.List.Basic

/-! Canonical artifact snapshots. The map contains bytes, never decoded caller
objects. Codec and admission policies are arbitrary; successful decoding is
checked by re-encoding. Hash collisions are refused, not assumed impossible.
The transition model covers serialized in-memory calls, not filesystem writes. -/
namespace NCA.Artifacts

abbrev Store := Std.HashMap String ByteArray

structure Codec (V : Type) where
  encode : V → ByteArray
  decode : ByteArray → Option V

def checked (codec : Codec V) (bytes : ByteArray) : Option V := do
  let value ← codec.decode bytes
  if codec.encode value = bytes then some value else none

inductive Admission where
  | invalid | duplicate | collision | rejected | inserted
  deriving DecidableEq, Repr

def put (codec : Codec V) (digest : ByteArray → String)
    (allow : Store → V → Bool) (store : Store) (value : V) : Store × Admission :=
  let bytes := codec.encode value
  let key := digest bytes
  match checked codec bytes with
  | none => (store, .invalid)
  | some snapshot =>
    match store[key]? with
    | some old => if old = bytes then (store, .duplicate) else (store, .collision)
    | none => if allow store snapshot then (store.insert key bytes, .inserted)
              else (store, .rejected)

def get (codec : Codec V) (digest : ByteArray → String)
    (store : Store) (key : String) : Option V := do
  let bytes ← store[key]?
  if digest bytes = key then checked codec bytes else none

inductive Event (V : Type) where
  | admit (value : V) (allow : Store → V → Bool)
  | read (key : String)
  | outside

def step (codec : Codec V) (digest : ByteArray → String)
    (store : Store) : Event V → Store
  | .admit value allow => (put codec digest allow store value).1
  | .read _ => store
  | .outside => store

def run (codec : Codec V) (digest : ByteArray → String)
    (store : Store) (events : List (Event V)) : Store :=
  events.foldl (step codec digest) store

theorem put_retains (codec : Codec V) (digest : ByteArray → String)
    (allow : Store → V → Bool) (store : Store) (value : V)
    (key : String) (bytes : ByteArray) (present : store[key]? = some bytes) :
    (put codec digest allow store value).1[key]? = some bytes := by
  cases decoded : checked codec (codec.encode value) with
  | none => simp [put, decoded, present]
  | some snapshot =>
    cases previous : store[digest (codec.encode value)]? with
    | some old =>
      by_cases same : old = codec.encode value <;> simp [put, decoded, previous, same, present]
    | none =>
      have distinct : digest (codec.encode value) ≠ key := by
        intro equal
        rw [equal, present] at previous
        cases previous
      cases admitted : allow store snapshot <;>
        simp [put, decoded, previous, admitted, Std.HashMap.getElem?_insert, distinct, present]

/-- Any serialized interleaving of admissions, reads and caller-side operations
retains every previously admitted byte sequence, even for colliding digests and
policies that depend on the whole preceding store. -/
theorem run_retains (codec : Codec V) (digest : ByteArray → String)
    (events : List (Event V)) (store : Store) (key : String) (bytes : ByteArray)
    (present : store[key]? = some bytes) :
    (run codec digest store events)[key]? = some bytes := by
  induction events generalizing store with
  | nil => exact present
  | cons event rest ih =>
    apply ih
    cases event with
    | admit value allow => exact put_retains codec digest allow store value key bytes present
    | read _ => exact present
    | outside => exact present

theorem checked_encodes (codec : Codec V) (bytes : ByteArray) (value : V)
    (success : checked codec bytes = some value) : codec.encode value = bytes := by
  cases decoded : codec.decode bytes with
  | none => simp [checked, decoded] at success
  | some result =>
    by_cases roundtrip : codec.encode result = bytes
    · simp [checked, decoded, roundtrip] at success
      subst result
      exact roundtrip
    · simp [checked, decoded, roundtrip] at success

theorem put_inserted (codec : Codec V) (digest : ByteArray → String)
    (allow : Store → V → Bool) (store : Store) (value : V)
    (inserted : (put codec digest allow store value).2 = .inserted) :
    (put codec digest allow store value).1[digest (codec.encode value)]? =
      some (codec.encode value) ∧
      ∃ snapshot, checked codec (codec.encode value) = some snapshot := by
  cases decoded : checked codec (codec.encode value) with
  | none => simp [put, decoded] at inserted
  | some snapshot =>
    cases previous : store[digest (codec.encode value)]? with
    | some old =>
      by_cases same : old = codec.encode value <;>
        simp [put, decoded, previous, same] at inserted
    | none =>
      cases admitted : allow store snapshot with
      | false => simp [put, decoded, previous, admitted] at inserted
      | true =>
        constructor
        · simp [put, decoded, previous, admitted]
        · exact ⟨snapshot, rfl⟩

/-- Successful admission guarantees an available, unchanged serialized read
after every later interleaving, with no assumption on subsequent policies or
digest collisions. The checked decoder, not a round-trip axiom, supplies the
returned view. -/
theorem admitted_read_stable (codec : Codec V) (digest : ByteArray → String)
    (allow : Store → V → Bool) (store : Store) (value : V)
    (inserted : (put codec digest allow store value).2 = .inserted)
    (events : List (Event V)) :
    ∃ snapshot, get codec digest (run codec digest (put codec digest allow store value).1 events)
      (digest (codec.encode value)) = some snapshot ∧ codec.encode snapshot = codec.encode value := by
  obtain ⟨present, snapshot, decoded⟩ := put_inserted codec digest allow store value inserted
  have retained := run_retains codec digest events (put codec digest allow store value).1
    (digest (codec.encode value)) (codec.encode value) present
  refine ⟨snapshot, ?_, checked_encodes codec (codec.encode value) snapshot decoded⟩
  simp [get, retained, decoded]

/-- A successful read after any interleaving at an existing key returns precisely
its original serialized contents. No codec round-trip or collision-freedom
hypothesis is needed: validation and non-overwriting admission enforce the claim. -/
theorem run_read_identity (codec : Codec V) (digest : ByteArray → String)
    (events : List (Event V)) (store : Store) (key : String) (bytes : ByteArray)
    (present : store[key]? = some bytes) (value : V)
    (success : get codec digest (run codec digest store events) key = some value) :
    codec.encode value = bytes ∧ digest bytes = key := by
  have retained := run_retains codec digest events store key bytes present
  by_cases aligned : digest bytes = key
  · have validated : checked codec bytes = some value := by
      simpa [get, retained, aligned] using success
    exact ⟨checked_encodes codec bytes value validated, aligned⟩
  · simp [get, retained, aligned] at success

end NCA.Artifacts
