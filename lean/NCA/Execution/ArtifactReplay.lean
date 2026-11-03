import NCA.Execution.Artifacts
import Lean.Data.Json.Parser

/-! Executable differential boundary for canonical UTF-8 artifact fixtures.
Python supplies the digest table and already validated canonical object texts.
The proved model quantifies over arbitrary digests/codecs; this runner instantiates
its serialization boundary with UTF-8. Schema-invalid inputs have separate Python
regressions. No filesystem or interpreter-isolation claim follows from this test. -/
open Lean NCA.Artifacts

private def textCodec : Codec String :=
  ⟨String.toUTF8, String.fromUTF8?⟩

private def admissionName : Admission → String
  | .invalid => "invalid"
  | .duplicate => "duplicate"
  | .collision => "collision"
  | .rejected => "rejected"
  | .inserted => "inserted"

private def optionalText : Option String → Json
  | none => .null
  | some value => toJson value

private def runCase (input : Json) : Except String Json := do
  let hashes ← (← input.getObjVal? "hashes").getArr?
  let mut digestTable : Std.HashMap String String := ∅
  for pair in hashes do
    match (← pair.getArr?).toList with
    | [.str text, .str key] => digestTable := digestTable.insert text key
    | _ => throw "digest entry must contain canonical text and reference"
  let digest := fun bytes => digestTable.getD (String.fromUTF8! bytes) "missing-digest"
  let probes ← (← input.getObjVal? "probes").getArr?
  let keys ← probes.mapM Json.getStr?
  let events ← (← input.getObjVal? "events").getArr?
  let mut store : Store := ∅
  let mut rows : Array Json := #[]
  for event in events do
    let mut status := "outside"
    let mut value : Option String := none
    match (← event.getArr?).toList with
    | [.str "put", .str text, .bool allowed] =>
      let result := put textCodec digest (fun _ _ => allowed) store text
      store := result.1
      status := admissionName result.2
    | [.str "get", .str key] =>
      value := get textCodec digest store key
      status := if value.isSome then "found" else "missing"
    | [.str "outside"] => pure ()
    | _ => throw "unknown artifact event"
    let state := keys.map fun key =>
      optionalText ((store[key]?).map String.fromUTF8!)
    rows := rows.push (Json.mkObj [
      ("status", toJson status), ("value", optionalText value), ("state", .arr state)])
  return .arr rows

def main : IO Unit := do
  let line ← (← IO.getStdin).getLine
  let result : Except String Json := do
    let fixtures ← (← Json.parse line).getArr?
    return .arr (← fixtures.mapM runCase)
  match result with
  | .ok output => (← IO.getStdout).putStrLn output.compress
  | .error error => throw (IO.userError error)
