import NCA.Execution.Loaders
import Lean.Data.Json.Parser

/-! Executable differential boundary for loader resolution (§28.9). Python
supplies registries as identifier/location string pairs and probe identifiers;
this runner answers each probe with `resolveLoader`. -/
open Lean NCA

private def runCase (input : Json) : Except String Json := do
  let pairs ← (← input.getObjVal? "registrations").getArr?
  let registry ← pairs.toList.mapM fun pair => do
    match (← pair.getArr?).toList with
    | [.str name, .str place] => pure (name, place)
    | _ => throw "registration must be an identifier and a location"
  let probes ← (← input.getObjVal? "probes").getArr?
  let answers ← probes.mapM fun probe => do
    let name ← probe.getStr?
    return match resolveLoader registry name with
      | some place => toJson place
      | none => Json.null
  return .arr answers

def main : IO Unit := do
  let line ← (← IO.getStdin).getLine
  let result : Except String Json := do
    let fixtures ← (← Json.parse line).getArr?
    return .arr (← fixtures.mapM runCase)
  match result with
  | .ok output => (← IO.getStdout).putStrLn output.compress
  | .error error => throw (IO.userError error)
