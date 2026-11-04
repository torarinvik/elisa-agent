import NCA.Reliability.SampledGate

/-! Finite exact-size batching of a fixed certification outcome stream (§20.21).
Sampler freshness and correspondence to actual observations are hypotheses,
not established by this deterministic model. -/
namespace NCA

/-- Batch admission and labels drawn, including the unscored rejected suffix. -/
def batchedTest : List (List Bool) → Bool × ℕ
  | [] => (true, 0)
  | batch :: rest =>
    if batch.all id then ((batchedTest rest).1, batch.length + (batchedTest rest).2)
    else (false, batch.length)

theorem batchedTest_admits (batches : List (List Bool)) :
    (batchedTest batches).1 = batches.flatten.all id := by
  induction batches with
  | nil => rfl
  | cons batch rest ih =>
    simp only [batchedTest, List.flatten_cons, List.all_append]
    split <;> simp_all

theorem batchedTest_reads (batches : List (List Bool)) :
    (batchedTest batches).2 ≤ batches.flatten.length ∧
      ((batchedTest batches).1 = true → (batchedTest batches).2 = batches.flatten.length) := by
  induction batches with
  | nil => simp [batchedTest]
  | cons batch rest ih =>
    simp only [batchedTest, List.flatten_cons, List.length_append]
    split
    · exact ⟨by omega, fun h => by rw [ih.2 h]⟩
    · simp

theorem earlyTest_append (left right : List Bool) :
    earlyTest (left ++ right) =
      if left.all id then ((earlyTest right).1, left.length + (earlyTest right).2)
      else earlyTest left := by
  induction left with
  | nil => simp
  | cons bit rest ih =>
    cases bit
    · simp [earlyTest]
    · by_cases h : rest.all id = true
      · simp [earlyTest, ih, h, Nat.add_assoc, Nat.add_comm, Nat.add_left_comm]
      · simp [earlyTest, ih, h]

/-- A cap bounds drawn-but-unscored labels even when every batch shape differs.
The strict inequality is the natural-number form of excess ≤ cap - 1. -/
theorem batchedTest_excess (batches : List (List Bool)) (cap : ℕ) (positive : 0 < cap)
    (bounded : ∀ batch ∈ batches, batch.length ≤ cap) :
    (batchedTest batches).2 < (earlyTest batches.flatten).2 + cap := by
  induction batches with
  | nil => simpa [batchedTest, earlyTest] using positive
  | cons batch rest ih =>
    have hb := bounded batch (by simp)
    have hr := ih (fun b h => bounded b (by simp [h]))
    simp only [batchedTest, List.flatten_cons, earlyTest_append]
    split
    · omega
    · have hp : 0 < (earlyTest batch).2 := by
        cases batch with
        | nil => simp_all
        | cons bit tail => cases bit <;> simp [earlyTest]
      omega

end NCA
