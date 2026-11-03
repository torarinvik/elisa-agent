import Mathlib.Logic.Relation
import Mathlib.Data.List.Basic

/-! Capability gaps (§20.9). Connectors are unary steps `E x y` between types.
Adding one connector `a → b` gives `withGap E a b`. -/
namespace NCA

open Relation

/-- The connectors `E` together with one added connector `a → b`. -/
def withGap {τ : Type*} (E : τ → τ → Prop) (a b : τ) (x y : τ) : Prop :=
  E x y ∨ (x = a ∧ y = b)

/-- Completeness of gap candidates: if adding `a → b` creates a route from `s`
to `g`, either a route already existed or `a` is reachable from `s` and `g`
from `b`. -/
theorem gap_complete {τ : Type*} {E : τ → τ → Prop} {a b s g : τ}
    (h : ReflTransGen (withGap E a b) s g) :
    ReflTransGen E s g ∨ (ReflTransGen E s a ∧ ReflTransGen E b g) := by
  induction h with
  | refl => exact Or.inl ReflTransGen.refl
  | tail _ step ih =>
    rcases step with step | ⟨rfl, rfl⟩
    · rcases ih with ih | ⟨ha, hb⟩
      · exact Or.inl (ih.tail step)
      · exact Or.inr ⟨ha, hb.tail step⟩
    · rcases ih with ih | ⟨ha, _⟩
      · exact Or.inr ⟨ih, ReflTransGen.refl⟩
      · exact Or.inr ⟨ha, ReflTransGen.refl⟩

/-- Soundness of gap candidates: when `a` is reachable from `s` and `g` from
`b`, adding `a → b` creates a route from `s` to `g`. -/
theorem gap_sound {τ : Type*} {E : τ → τ → Prop} {a b s g : τ}
    (ha : ReflTransGen E s a) (hb : ReflTransGen E b g) :
    ReflTransGen (withGap E a b) s g := by
  have lift : ∀ {x y}, ReflTransGen E x y → ReflTransGen (withGap E a b) x y := by
    intro x y h
    induction h with
    | refl => exact ReflTransGen.refl
    | tail _ e ih => exact ih.tail (Or.inl e)
  exact ((lift ha).tail (Or.inr ⟨rfl, rfl⟩)).trans (lift hb)

/-- Exactly the single-connector repairs: when no route exists, adding `a → b`
creates one iff `a` is reachable from `s` and `g` from `b`. -/
theorem gap_iff {τ : Type*} {E : τ → τ → Prop} {a b s g : τ}
    (none : ¬ ReflTransGen E s g) :
    ReflTransGen (withGap E a b) s g ↔ ReflTransGen E s a ∧ ReflTransGen E b g :=
  ⟨fun h => (gap_complete h).resolve_left none, fun ⟨ha, hb⟩ => gap_sound ha hb⟩

/-- Routes from `s` to `g` using at most `k` new connectors, each one allowed
by `N` (those an acquirer has not refused), with routes of `E` around them
(§20.9). -/
def Repair {τ : Type*} (E N : τ → τ → Prop) : ℕ → τ → τ → Prop
  | 0, s, g => ReflTransGen E s g
  | k + 1, s, g => Repair E N k s g ∨ ∃ a b, N a b ∧ ReflTransGen E s a ∧ Repair E N k b g

/-- Walks over `E` and new connectors `F`, counting the uses of `F`. -/
inductive Gapped {τ : Type*} (E F : τ → τ → Prop) (s : τ) : τ → ℕ → Prop
  | refl : Gapped E F s s 0
  | old {c d n} : Gapped E F s c n → E c d → Gapped E F s d n
  | new {c d n} : Gapped E F s c n → F c d → Gapped E F s d (n + 1)

theorem Repair.old {τ : Type*} {E N : τ → τ → Prop} {c d : τ} (e : E c d) :
    ∀ {n : ℕ} {s : τ}, Repair E N n s c → Repair E N n s d := by
  intro n
  induction n with
  | zero => intro s h; exact ReflTransGen.tail h e
  | succ n ih =>
    intro s h
    rcases h with h | ⟨a, b, n, ha, hb⟩
    · exact Or.inl (ih h)
    · exact Or.inr ⟨a, b, n, ha, ih hb⟩

theorem Repair.new {τ : Type*} {E N : τ → τ → Prop} {c d : τ} (allowed : N c d) :
    ∀ {n : ℕ} {s : τ}, Repair E N n s c → Repair E N (n + 1) s d := by
  intro n
  induction n with
  | zero => intro s h; exact Or.inr ⟨c, d, allowed, h, ReflTransGen.refl⟩
  | succ n ih =>
    intro s h
    rcases h with h | ⟨a, b, m, ha, hb⟩
    · exact Or.inl (ih h)
    · exact Or.inr ⟨a, b, m, ha, ih hb⟩

/-- Completeness: whatever allowed connectors `F` are added, a walk using
them `n` times is a repair with `n` new connectors. -/
theorem repair_complete {τ : Type*} {E N F : τ → τ → Prop} (allowed : ∀ x y, F x y → N x y)
    {s g : τ} {n : ℕ} (h : Gapped E F s g n) : Repair E N n s g := by
  induction h with
  | refl => exact ReflTransGen.refl
  | old _ e ih => exact Repair.old e ih
  | new _ f ih => exact Repair.new (allowed _ _ f) ih

theorem Gapped.lift {τ : Type*} {E F : τ → τ → Prop} {s c d : τ} (h : ReflTransGen E c d)
    {n : ℕ} (hc : Gapped E F s c n) : Gapped E F s d n := by
  induction h with
  | refl => exact hc
  | tail _ e ih => exact ih.old e

/-- Walks compose, and a walk over fewer new connectors is one over more. -/
theorem Gapped.append {τ : Type*} {E F F' : τ → τ → Prop} {s b g : τ} {m n : ℕ}
    (first : Gapped E F s b m) (sub : ∀ x y, F' x y → F x y) (rest : Gapped E F' b g n) :
    Gapped E F s g (m + n) := by
  induction rest with
  | refl => exact first
  | old _ e ih => exact ih.old e
  | new _ f ih => exact ih.new (sub _ _ f)

/-- Soundness: a repair with `k` new connectors is realized by adding a list
of at most `k` allowed connectors, used at most `k` times. -/
theorem repair_sound {τ : Type*} {E N : τ → τ → Prop} :
    ∀ {k : ℕ} {s g : τ}, Repair E N k s g →
      ∃ L : List (τ × τ), L.length ≤ k ∧ (∀ p ∈ L, N p.1 p.2) ∧
        ∃ n ≤ k, Gapped E (fun x y => (x, y) ∈ L) s g n := by
  intro k
  induction k with
  | zero =>
    intro s g h
    exact ⟨[], Nat.le_refl _, by simp, 0, Nat.le_refl _, Gapped.lift h Gapped.refl⟩
  | succ k ih =>
    intro s g h
    rcases h with h | ⟨a, b, ab, ha, hb⟩
    · obtain ⟨L, hL, hN, n, hn, w⟩ := ih h
      exact ⟨L, by omega, hN, n, by omega, w⟩
    obtain ⟨L, hL, hN, n, hn, w⟩ := ih hb
    have first : Gapped E (fun x y => (x, y) ∈ (a, b) :: L) s b (0 + 1) :=
      (Gapped.lift ha Gapped.refl).new (by simp)
    refine ⟨(a, b) :: L, by simp; omega, ?_, 0 + 1 + n, by omega, first.append ?_ w⟩
    · intro p hp
      rcases List.mem_cons.mp hp with rfl | hp
      · exact ab
      · exact hN p hp
    intro x y h
    exact List.mem_cons_of_mem _ h

end NCA
