import Mathlib.Data.Fintype.Card
import Mathlib.Data.Multiset.Sort
import Mathlib.Order.Interval.Finset.Nat
import Mathlib.Tactic

/-! Looking where the picture is unusual (chapter 69). -/
namespace NCA

section Usual

variable {T P V : Type} [Fintype T] [DecidableEq V]

/-- In how many of the pictures looked back over a point held a value. -/
def timesHeld (past : T → P → V) (p : P) (v : V) : Nat :=
  (Finset.univ.filter fun t => past t p = v).card

/-- A value is usual at a point when no value was held there in more of the pictures looked back over. -/
def Usual (past : T → P → V) (p : P) (u : V) : Prop :=
  ∀ v, timesHeld past p v ≤ timesHeld past p u

/-- Two values share the pictures looked back over between them. -/
theorem timesHeld_two_le (past : T → P → V) (p : P) (u v : V) (ne : u ≠ v) :
    timesHeld past p u + timesHeld past p v ≤ Fintype.card T := by
  classical
  unfold timesHeld
  rw [← Finset.card_union_of_disjoint
    (Finset.disjoint_filter.2 fun t _ isU isV => ne (isU.symm.trans isV))]
  exact Finset.card_le_univ _

/-- Where there are values at all, every point has a usual one. -/
theorem usual_exists [Nonempty V] (past : T → P → V) (p : P) : ∃ u, Usual past p u := by
  rcases isEmpty_or_nonempty T with empty | nonempty
  · exact ⟨Classical.arbitrary V, fun v => by simp [timesHeld]⟩
  · obtain ⟨t, -, most⟩ := Finset.exists_max_image Finset.univ
      (fun t => timesHeld past p (past t p)) Finset.univ_nonempty
    refine ⟨past t p, fun v => ?_⟩
    by_cases seen : ∃ s, past s p = v
    · obtain ⟨s, rfl⟩ := seen
      exact most s (Finset.mem_univ s)
    · have never : timesHeld past p v = 0 :=
        Finset.card_eq_zero.2 (Finset.filter_eq_empty_iff.2 fun s _ is => seen ⟨s, is⟩)
      omega

/-- 69.1: a value held in more than half of the pictures looked back over is usual. -/
theorem most_is_usual (past : T → P → V) (p : P) (v : V)
    (most : Fintype.card T < 2 * timesHeld past p v) : Usual past p v := by
  intro w
  by_cases same : w = v
  · rw [same]
  · have shared := timesHeld_two_le past p w v same
    omega

/-- 69.1: and it is the only usual value, whatever the other pictures held. -/
theorem usual_is_most (past : T → P → V) (p : P) (v u : V)
    (most : Fintype.card T < 2 * timesHeld past p v) (usual : Usual past p u) : u = v := by
  by_contra ne
  have shared := timesHeld_two_le past p u v ne
  have least := usual v
  omega

/-- 69.1: where the pictures looked back over never differed, what they held is the usual value. -/
theorem same_is_usual [Nonempty T] (past : T → P → V) (p : P) (c u : V)
    (same : ∀ t, past t p = c) (usual : Usual past p u) : u = c := by
  refine usual_is_most past p c u ?_ usual
  have all : timesHeld past p c = Fintype.card T := by
    unfold timesHeld
    rw [Finset.filter_true_of_mem fun t _ => same t, Finset.card_univ]
  have some : 0 < Fintype.card T := Fintype.card_pos
  omega

/-- 69.1: so a picture that agrees with them at the point is not unusual there. -/
theorem agreeing_not_unusual [Nonempty T] (past : T → P → V) (p : P) (u : V)
    (usual : Usual past p u) (pic : P → V) (same : ∀ t, past t p = pic p) : pic p = u :=
  (same_is_usual past p (pic p) u same usual).symm

/-- 69.1: a point that held its ground in more than half of the pictures looked back over is unusual in
exactly the pictures where it does not hold its ground. -/
theorem unusual_iff_off_ground (past : T → P → V) (p : P) (ground u : V)
    (most : Fintype.card T < 2 * timesHeld past p ground) (usual : Usual past p u) (pic : P → V) :
    pic p ≠ u ↔ pic p ≠ ground := by
  rw [usual_is_most past p ground u most usual]

/-- 69.2: if outside a set of points every picture looked back over holds what the present one holds,
every unusual point lies in the set. -/
theorem unusual_within [Nonempty T] (past : T → P → V) (usual : P → V)
    (is : ∀ p, Usual past p (usual p)) (pic : P → V) (R : Set P)
    (still : ∀ p, p ∉ R → ∀ t, past t p = pic p) (p : P) (odd : pic p ≠ usual p) : p ∈ R := by
  by_contra out
  exact odd (agreeing_not_unusual past p (usual p) (is p) pic (still p out))

end Usual

/-- A coordinate lies in the window of a half-width about a middle. -/
def Near (h m x : Nat) : Prop := m ≤ x + h ∧ x ≤ m + h

/-- 69.3: a middle chosen between two unusual coordinates lies in every stretch that holds them all. -/
theorem middle_between (U : Finset Nat) (a b : Nat) (inside : ∀ x ∈ U, a ≤ x ∧ x ≤ b)
    (m x y : Nat) (xU : x ∈ U) (yU : y ∈ U) (low : x ≤ m) (high : m ≤ y) : a ≤ m ∧ m ≤ b :=
  ⟨(inside x xU).1.trans low, high.trans (inside y yU).2⟩

/-- 69.3: the window about a middle within a stretch no longer than the half-width holds the stretch. -/
theorem window_holds (h a b m : Nat) (short : b ≤ a + h) (above : a ≤ m) (below : m ≤ b)
    (z : Nat) (az : a ≤ z) (zb : z ≤ b) : Near h m z := by
  unfold Near
  omega

/-- 69.3: so does a window that would reach past an edge of the picture and is moved whole to lie
inside it. -/
theorem moved_window_holds (n h a b m : Nat) (fits : 2 * h + 1 ≤ n) (short : b ≤ a + h)
    (edge : b < n) (above : a ≤ m) (below : m ≤ b) (z : Nat) (az : a ≤ z) (zb : z ≤ b) :
    Near h (max h (min m (n - 1 - h))) z := by
  unfold Near
  omega

/-- The middle of some coordinates: the one at the middle place when they stand in order. -/
def middle (s : Multiset Nat) (some : 0 < Multiset.card s) : Nat :=
  s.sort[Multiset.card s / 2]'(by rw [Multiset.length_sort]; omega)

/-- The middle of some coordinates is one of them. -/
theorem middle_mem (s : Multiset Nat) (some : 0 < Multiset.card s) : middle s some ∈ s :=
  (Multiset.mem_sort ..).1 (List.getElem_mem _)

/-- The rows of some points, one for each point. -/
def rows (U : Finset (Nat × Nat)) : Multiset Nat := U.val.map Prod.fst

/-- The columns of some points, one for each point. -/
def cols (U : Finset (Nat × Nat)) : Multiset Nat := U.val.map Prod.snd

theorem rows_pos (U : Finset (Nat × Nat)) (some : U.Nonempty) : 0 < Multiset.card (rows U) := by
  simpa [rows] using some.card_pos

theorem cols_pos (U : Finset (Nat × Nat)) (some : U.Nonempty) : 0 < Multiset.card (cols U) := by
  simpa [cols] using some.card_pos

/-- 69.4: if the unusual points lie in a box no taller and no wider than the half-width, the window about
their middle row and middle column holds the whole box. -/
theorem window_holds_box (U : Finset (Nat × Nat)) (some : U.Nonempty) (h a b c d : Nat)
    (tall : b ≤ a + h) (wide : d ≤ c + h)
    (inside : ∀ p ∈ U, (a ≤ p.1 ∧ p.1 ≤ b) ∧ (c ≤ p.2 ∧ p.2 ≤ d))
    (z : Nat × Nat) (zr : a ≤ z.1 ∧ z.1 ≤ b) (zc : c ≤ z.2 ∧ z.2 ≤ d) :
    Near h (middle (rows U) (rows_pos U some)) z.1
      ∧ Near h (middle (cols U) (cols_pos U some)) z.2 := by
  obtain ⟨p, pU, pr⟩ := Multiset.mem_map.1 (middle_mem (rows U) (rows_pos U some))
  obtain ⟨q, qU, qc⟩ := Multiset.mem_map.1 (middle_mem (cols U) (cols_pos U some))
  have atP := inside p (Finset.mem_def.2 pU)
  have atQ := inside q (Finset.mem_def.2 qU)
  rw [← pr, ← qc]
  unfold Near
  omega

/-- 69.5: a window has at most the square of its side in points, whatever the picture. -/
theorem window_points_le (W : Finset (Nat × Nat)) (h r c : Nat)
    (within : ∀ p ∈ W, Near h r p.1 ∧ Near h c p.2) : W.card ≤ (2 * h + 1) * (2 * h + 1) := by
  have sub : W ⊆ Finset.Icc (r - h) (r + h) ×ˢ Finset.Icc (c - h) (c + h) := by
    intro p pW
    obtain ⟨⟨r1, r2⟩, c1, c2⟩ := within p pW
    simp only [Finset.mem_product, Finset.mem_Icc]
    omega
  refine (Finset.card_le_card sub).trans ?_
  rw [Finset.card_product, Nat.card_Icc, Nat.card_Icc]
  exact Nat.mul_le_mul (by omega) (by omega)

/-- 69.5: a window no wider than the picture has no more points than the picture. -/
theorem cut_saves (w n : Nat) (le : w ≤ n) : w * w ≤ n * n :=
  Nat.mul_le_mul le le

/-- 69.5: and has as many only when it is the whole picture. -/
theorem cut_saves_unless_whole (w n : Nat) : w * w = n * n ↔ w = n :=
  Nat.mul_self_inj

/-- 69.6: a point further than the half-width below every unusual coordinate, or above every one, is in
no window about a middle chosen among them. -/
theorem still_point_missed (h a b m q : Nat) (above : a ≤ m) (below : m ≤ b)
    (far : q + h < a ∨ b + h < q) : ¬ Near h m q := by
  unfold Near
  omega

/-- 69.7: two coordinates further apart than the window is wide are in no one window. -/
theorem far_apart_not_both (h m x y : Nat) (far : x + 2 * h < y) :
    ¬ (Near h m x ∧ Near h m y) := by
  unfold Near
  omega

/-- 69.7: a middle at one end of a stretch longer than the half-width leaves the other end out. -/
theorem long_stretch_cut (h a b : Nat) (long : a + h < b) : ¬ Near h a b := by
  unfold Near
  omega

end NCA
