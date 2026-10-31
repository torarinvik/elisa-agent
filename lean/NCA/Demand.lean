/-!
# Demand-driven evaluation

A consumer declares what it reads of each input (its *demand*); parts nobody
reads need not be computed, and requests on them need not be resolved. Each
value type carries a family of agreement relations indexed by demands:
`agree d v v'` means `v` and `v'` look the same to a reader with demand `d`.
A module is *demand-sound* for a demand map `δ` when inputs agreeing on `δ d`
give outputs agreeing on `d`. Demand-soundness composes through sequential
composition, pairing, and elementwise maps, and at the top demand (agreement is
equality) it means: replacing unread parts by anything leaves the answer
unchanged. A gate that resolves exactly the demanded requests is therefore
sound, and gated refinement is exact (`NCA.gated_error_eq_of_sound`).

*Decision demand* uses coarser agreement: two values agree when they lead to
the same decision (for a distribution, the same restricted argmax), not only
when they are equal. Coarsening what a reader distinguishes keeps a module
demand-sound (`coarsen`) and can justify smaller input demands (`shrink`).
Readings outside the decision demand cannot change the answer, so the union
bound runs over decision-demanded readings only: `composition_error_le_sum`
with its propagation hypothesis supplied by `DemandSound.exact`.
-/

namespace NCA

/-- A type with agreement relations indexed by demands. -/
structure Readable (V : Type) where
  Demand : Type
  agree : Demand → V → V → Prop

/-- `f` is demand-sound for `δ`: inputs agreeing on `δ d` yield outputs agreeing on `d`. -/
def DemandSound {V W : Type} (A : Readable V) (B : Readable W) (f : V → W)
    (δ : B.Demand → A.Demand) : Prop :=
  ∀ d v v', A.agree (δ d) v v' → B.agree d (f v) (f v')

/-- **Composition.** Demand-sound modules compose, with demands propagated backwards. -/
theorem DemandSound.comp {U V W : Type} {A : Readable U} {B : Readable V} {C : Readable W}
    {f : U → V} {g : V → W} {δf : B.Demand → A.Demand} {δg : C.Demand → B.Demand}
    (hf : DemandSound A B f δf) (hg : DemandSound B C g δg) :
    DemandSound A C (g ∘ f) (δf ∘ δg) :=
  fun d _ _ h => hg d _ _ (hf (δg d) _ _ h)

/-- Agreement on pairs: componentwise, under a pair of demands. -/
def Readable.prod {V W : Type} (A : Readable V) (B : Readable W) : Readable (V × W) where
  Demand := A.Demand × B.Demand
  agree d p q := A.agree d.1 p.1 q.1 ∧ B.agree d.2 p.2 q.2

/-- **Pairing.** Two demand-sound modules on a shared input form a demand-sound
module into the pair, if the input's agreements are closed under the demands
of both. -/
theorem DemandSound.pair {U V W : Type} {A : Readable U} {B : Readable V} {C : Readable W}
    {f : U → V} {g : U → W} {δf : B.Demand → A.Demand} {δg : C.Demand → A.Demand}
    (join : A.Demand → A.Demand → A.Demand)
    (hjoin : ∀ a b u u', A.agree (join a b) u u' → A.agree a u u' ∧ A.agree b u u')
    (hf : DemandSound A B f δf) (hg : DemandSound A C g δg) :
    DemandSound A (B.prod C) (fun u => (f u, g u)) (fun d => join (δf d.1) (δg d.2)) :=
  fun d _ _ h => ⟨hf d.1 _ _ (hjoin _ _ _ _ h).1, hg d.2 _ _ (hjoin _ _ _ _ h).2⟩

/-- Agreement on lists of equal length under a per-position demand: the demand
for position `i` may depend on `i` and the length. -/
def Readable.list {V : Type} (A : Readable V) : Readable (List V) where
  Demand := Nat → Nat → A.Demand
  agree d xs ys := xs.length = ys.length ∧
    ∀ i (hx : i < xs.length) (hy : i < ys.length), A.agree (d i xs.length) xs[i] ys[i]

/-- **Map.** An elementwise map of a demand-sound module is demand-sound for
per-position demands. -/
theorem DemandSound.map {V W : Type} {A : Readable V} {B : Readable W} {f : V → W}
    {δ : B.Demand → A.Demand} (hf : DemandSound A B f δ) :
    DemandSound A.list B.list (List.map f) (fun d i n => δ (d i n)) := by
  intro d xs ys ⟨hlen, h⟩
  refine ⟨by simp [hlen], fun i hx hy => ?_⟩
  simp only [List.length_map] at hx hy ⊢
  simp only [List.getElem_map]
  exact hf _ _ _ (h i hx hy)

/-- **Exactness.** If the top-level demand's agreement is equality, a
demand-sound composition returns the same answer for any two inputs that agree
on the demand it propagates, in particular after replacing every unread part. -/
theorem DemandSound.exact {V W : Type} {A : Readable V} {B : Readable W} {f : V → W}
    {δ : B.Demand → A.Demand} (hf : DemandSound A B f δ) {top : B.Demand}
    (htop : ∀ w w', B.agree top w w' → w = w') {v v' : V} (h : A.agree (δ top) v v') :
    f v = f v' :=
  htop _ _ (hf top v v' h)

/-- **Coarsening.** A module stays demand-sound when its reader distinguishes
less, e.g. decisions instead of values. -/
theorem DemandSound.coarsen {V W : Type} {A : Readable V} {B B' : Readable W} {f : V → W}
    {δ : B.Demand → A.Demand} (hf : DemandSound A B f δ) (e : B'.Demand → B.Demand)
    (he : ∀ d w w', B.agree (e d) w w' → B'.agree d w w') :
    DemandSound A B' f (δ ∘ e) :=
  fun d v v' h => he d _ _ (hf (e d) v v' h)

/-- **Shrinking.** A smaller input demand is sound whenever agreeing on it
implies agreeing on a sound one. -/
theorem DemandSound.shrink {V W : Type} {A : Readable V} {B : Readable W} {f : V → W}
    {δ δ' : B.Demand → A.Demand} (hf : DemandSound A B f δ)
    (h : ∀ d v v', A.agree (δ' d) v v' → A.agree (δ d) v v') : DemandSound A B f δ' :=
  fun d v v' hv => hf d v v' (h d v v' hv)

end NCA
