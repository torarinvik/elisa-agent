import Mathlib.Tactic

/-! A read by the newest match (chapter 75). Items lie newest first; each has a chance of matching and a
value. -/
namespace NCA

section Newest

/-- What the items leave: one less each chance, multiplied together. -/
def leftBy : List ℝ → ℝ
  | [] => 1
  | m :: older => (1 - m) * leftBy older

/-- The weights the items take, summed: each its chance times what the newer ones left. -/
def takenBy : List ℝ → ℝ
  | [] => 0
  | m :: older => m + (1 - m) * takenBy older

/-- The read: each item's value weighed by its chance times what the newer ones left. An item is its chance
and its value. -/
def readBy : List (ℝ × ℝ) → ℝ
  | [] => 0
  | item :: older => item.1 * item.2 + (1 - item.1) * readBy older

/-- 75.1: what is taken and what is left make one, however many items there are. -/
theorem taken_add_left (chances : List ℝ) : takenBy chances + leftBy chances = 1 := by
  induction chances with
  | nil => simp [takenBy, leftBy]
  | cons m older ih =>
    simp only [takenBy, leftBy]
    linear_combination (1 - m) * ih

/-- What is left lies between nought and one. -/
theorem left_between (chances : List ℝ) (unit : ∀ m ∈ chances, 0 ≤ m ∧ m ≤ 1) :
    0 ≤ leftBy chances ∧ leftBy chances ≤ 1 := by
  induction chances with
  | nil => simp [leftBy]
  | cons m older ih =>
    have here := unit m (List.mem_cons_self ..)
    have rest := ih (fun x hx => unit x (List.mem_cons_of_mem _ hx))
    simp only [leftBy]
    constructor
    · exact mul_nonneg (by linarith) rest.1
    · nlinarith [mul_nonneg here.1 rest.1]

/-- 75.2: an item that matches with a chance leaves no more than one less that chance, wherever it lies. -/
theorem left_le_of_match (chances : List ℝ) (unit : ∀ m ∈ chances, 0 ≤ m ∧ m ≤ 1) (m : ℝ) (among : m ∈ chances) :
    leftBy chances ≤ 1 - m := by
  induction chances with
  | nil => simp at among
  | cons first older ih =>
    have here := unit first (List.mem_cons_self ..)
    have olderUnit : ∀ x ∈ older, 0 ≤ x ∧ x ≤ 1 := fun x hx => unit x (List.mem_cons_of_mem _ hx)
    have rest := left_between older olderUnit
    simp only [leftBy]
    rcases List.mem_cons.mp among with same | within
    · subst same
      nlinarith [mul_nonneg (sub_nonneg.mpr here.2) (sub_nonneg.mpr rest.2)]
    · have := ih olderUnit within
      nlinarith [mul_nonneg here.1 rest.1]

/-- A read of values within a bound is within the bound. -/
theorem read_within (items : List (ℝ × ℝ)) (bound : ℝ) (nonneg : 0 ≤ bound)
    (unit : ∀ item ∈ items, 0 ≤ item.1 ∧ item.1 ≤ 1) (bounded : ∀ item ∈ items, |item.2| ≤ bound) :
    |readBy items| ≤ bound := by
  induction items with
  | nil => simpa [readBy] using nonneg
  | cons item older ih =>
    have here := unit item (List.mem_cons_self ..)
    have value := bounded item (List.mem_cons_self ..)
    have rest := ih (fun x hx => unit x (List.mem_cons_of_mem _ hx)) (fun x hx => bounded x (List.mem_cons_of_mem _ hx))
    simp only [readBy]
    have first : |item.1 * item.2| ≤ item.1 * bound := by
      rw [abs_mul, abs_of_nonneg here.1]
      exact mul_le_mul_of_nonneg_left value here.1
    have second : |(1 - item.1) * readBy older| ≤ (1 - item.1) * bound := by
      rw [abs_mul, abs_of_nonneg (by linarith : (0 : ℝ) ≤ 1 - item.1)]
      exact mul_le_mul_of_nonneg_left rest (by linarith)
    calc |item.1 * item.2 + (1 - item.1) * readBy older|
        ≤ |item.1 * item.2| + |(1 - item.1) * readBy older| := abs_add_le _ _
      _ ≤ item.1 * bound + (1 - item.1) * bound := add_le_add first second
      _ = bound := by ring

/-- 75.3: the read of newer items with older ones after them is the read of the newer and, times what the
newer left, the read of the older. The weight of an item does not turn on anything older than it. -/
theorem read_append (newer older : List (ℝ × ℝ)) :
    readBy (newer ++ older) = readBy newer + leftBy (newer.map Prod.fst) * readBy older := by
  induction newer with
  | nil => simp [readBy, leftBy]
  | cons item rest ih =>
    simp only [List.cons_append, readBy, List.map_cons, leftBy, ih]
    ring

/-- 75.3: more items held, however many, move the read by no more than what the newer ones left times the
bound of a value. -/
theorem more_held_moves_little (newer older : List (ℝ × ℝ)) (bound : ℝ) (nonneg : 0 ≤ bound)
    (unitNewer : ∀ item ∈ newer, 0 ≤ item.1 ∧ item.1 ≤ 1)
    (unitOlder : ∀ item ∈ older, 0 ≤ item.1 ∧ item.1 ≤ 1) (bounded : ∀ item ∈ older, |item.2| ≤ bound) :
    |readBy (newer ++ older) - readBy newer| ≤ leftBy (newer.map Prod.fst) * bound := by
  have left := left_between (newer.map Prod.fst) (by
    intro m hm
    obtain ⟨item, within, rfl⟩ := List.mem_map.mp hm
    exact unitNewer item within)
  rw [read_append, add_sub_cancel_left, abs_mul, abs_of_nonneg left.1]
  exact mul_le_mul_of_nonneg_left (read_within older bound nonneg unitOlder bounded) left.1

/-- 75.3: where one of the newer items matches with chance at least one less `miss`, any number of older
items moves the read by no more than `miss` times the bound of a value. -/
theorem sure_match_fixes_read (newer older : List (ℝ × ℝ)) (bound miss : ℝ) (nonneg : 0 ≤ bound) (item : ℝ × ℝ)
    (among : item ∈ newer) (sure : 1 - miss ≤ item.1) (unitNewer : ∀ item ∈ newer, 0 ≤ item.1 ∧ item.1 ≤ 1)
    (unitOlder : ∀ item ∈ older, 0 ≤ item.1 ∧ item.1 ≤ 1) (bounded : ∀ item ∈ older, |item.2| ≤ bound) :
    |readBy (newer ++ older) - readBy newer| ≤ miss * bound := by
  have unit : ∀ m ∈ newer.map Prod.fst, 0 ≤ m ∧ m ≤ 1 := by
    intro m hm
    obtain ⟨other, within, rfl⟩ := List.mem_map.mp hm
    exact unitNewer other within
  have left := left_le_of_match (newer.map Prod.fst) unit item.1 (List.mem_map_of_mem among)
  calc |readBy (newer ++ older) - readBy newer|
      ≤ leftBy (newer.map Prod.fst) * bound := more_held_moves_little newer older bound nonneg unitNewer unitOlder bounded
    _ ≤ miss * bound := mul_le_mul_of_nonneg_right (by linarith) nonneg

/-- 75.4: items that each match with chance at most `false` leave at least one less `false` for each of
them. -/
theorem newer_leave_most (chances : List ℝ) (falsely : ℝ) (small : falsely ≤ 1)
    (each : ∀ m ∈ chances, 0 ≤ m ∧ m ≤ falsely) : 1 - falsely * chances.length ≤ leftBy chances := by
  induction chances with
  | nil => simp [leftBy]
  | cons m older ih =>
    have here := each m (List.mem_cons_self ..)
    have olderEach : ∀ x ∈ older, 0 ≤ x ∧ x ≤ falsely := fun x hx => each x (List.mem_cons_of_mem _ hx)
    have rest := ih olderEach
    have between := left_between older (fun x hx => ⟨(olderEach x hx).1, le_trans (olderEach x hx).2 small⟩)
    have count : (0 : ℝ) ≤ older.length := Nat.cast_nonneg _
    simp only [leftBy, List.length_cons, Nat.cast_add, Nat.cast_one]
    have some : 0 ≤ falsely := le_trans here.1 here.2
    nlinarith [mul_nonneg (sub_nonneg.mpr here.2) between.1, mul_nonneg (sub_nonneg.mpr small) (sub_nonneg.mpr rest),
      mul_nonneg (mul_nonneg some some) count]

/-- 75.5: under a weighted mean, an item among `others` items that each weigh at least `near` times what it
does is given no more than one in one and `others` times `near`: its share falls as more are held. -/
theorem mean_wears (own rest near : ℝ) (others : ℕ) (pos : 0 < own) (close : 0 ≤ near)
    (heavy : others * near * own ≤ rest) : own / (own + rest) ≤ 1 / (1 + others * near) := by
  have count : (0 : ℝ) ≤ others := Nat.cast_nonneg _
  have below : 0 < 1 + (others : ℝ) * near := by positivity
  have whole : 0 < own + rest := by nlinarith [mul_nonneg (mul_nonneg count close) pos.le]
  rw [div_le_div_iff₀ whole below]
  nlinarith [heavy]

end Newest

end NCA
