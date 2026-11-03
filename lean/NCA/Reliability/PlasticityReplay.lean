import NCA.Reliability.Plasticity
import Lean.Data.Json.Parser

/-! Executable differential boundary for the plasticity field (§43.8), over the
rationals. Each fixture gives `rate`, `lo`, `hi` and observations
`[surprise, stability]` as `"num/den"` strings for one key starting closed at 0;
the runner returns each plasticity and open flag from `smooth` and `nextOpen`. -/
open Lean NCA

private def rational (j : Json) : Except String ℚ := do
  let text ← j.getStr?
  match text.splitOn "/" with
  | [n, d] =>
    match n.toInt?, d.toNat? with
    | some a, some b => if b = 0 then throw "zero denominator" else pure ((a : ℚ) / b)
    | _, _ => throw s!"bad rational {text}"
  | _ => throw s!"bad rational {text}"

private def render (q : ℚ) : Json := toJson s!"{q.num}/{q.den}"

private def runCase (input : Json) : Except String Json := do
  let rate ← rational (← input.getObjVal? "rate")
  let lo ← rational (← input.getObjVal? "lo")
  let hi ← rational (← input.getObjVal? "hi")
  let steps ← (← input.getObjVal? "steps").getArr?
  let mut p : ℚ := 0
  let mut opened := false
  let mut rows : Array Json := #[]
  for step in steps do
    match (← step.getArr?).toList with
    | [s, w] =>
      p := smooth rate p (← rational s) (← rational w)
      opened := nextOpen lo hi opened p
      rows := rows.push (Json.arr #[render p, toJson opened])
    | _ => throw "observation must be surprise and stability"
  return .arr rows

def main : IO Unit := do
  let line ← (← IO.getStdin).getLine
  let result : Except String Json := do
    let fixtures ← (← Json.parse line).getArr?
    return .arr (← fixtures.mapM runCase)
  match result with
  | .ok output => (← IO.getStdout).putStrLn output.compress
  | .error error => throw (IO.userError error)
