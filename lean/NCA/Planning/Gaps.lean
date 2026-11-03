import Mathlib.Logic.Relation

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

end NCA
