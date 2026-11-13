import Mathlib.Order.Monotone.Basic

/-! Relations between what is read: what judgements on some values leave open about sameness, and what sameness and
order are unchanged by. -/

namespace NCA

/-- **Proposition 55.1 (judgements on some values do not settle sameness on others).** Sameness, and sameness of a
value in `U`, agree wherever the first value lies in `U` and differ at any value outside it. -/
theorem sameness_open_outside_shown {V : Type*} (U : Set V) (v : V) (new : v ∉ U) :
    (∀ a b, a ∈ U → (a = b ↔ a = b ∧ a ∈ U)) ∧ ¬(v = v ↔ v = v ∧ v ∈ U) :=
  ⟨fun _ _ shown => ⟨fun same => ⟨same, shown⟩, fun both => both.1⟩, fun agree => new (agree.mp rfl).2⟩

/-- **Proposition 55.2 (renaming).** Two values are the same exactly when their images under a one-to-one map are. -/
theorem sameness_renamed {V W : Type*} (rename : V → W) (one_to_one : Function.Injective rename) (a b : V) :
    rename a = rename b ↔ a = b :=
  one_to_one.eq_iff

/-- **Proposition 55.2 (rescaling).** Two values are ordered as their images under a strictly increasing map are. -/
theorem order_rescaled {V W : Type*} [LinearOrder V] [Preorder W] (rescale : V → W) (increasing : StrictMono rescale)
    (a b : V) : rescale a < rescale b ↔ a < b :=
  increasing.lt_iff_lt

end NCA
