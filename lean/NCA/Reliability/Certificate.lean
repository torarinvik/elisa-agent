import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic
import Mathlib.MeasureTheory.Measure.MeasureSpace
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.GCongr

/-!
# Grouped decisions and value-dependent certificates

Static demand (`NCA.Demand`) fixes, before anything is read, which readings a
consumer's answer depends on. Some consumers depend on a reading only through
a *coarse* decision, and some depend on a reading only for some values of the
others: `false ∧ x` is `false` whatever `x` is.

1. **Grouped decisions.** A decision may choose among groups of classes (the
   group of the most probable class). Its risk `1 − p(group) / p(C)` is at most
   the risk of choosing the class itself (`grouped_risk_le`).
2. **Certificates.** A certificate assigns, to every reading of all items,
   the agreement each item must have with the truth for the answer to be
   right. The union bound then runs over what the certificate of the actual
   reading demands (`certificate_error_le`, `certificate_error_le_support`);
   static demand is the certificate that ignores the reading.
3. **Boolean formulas.** For formula trees, certificates use the value of an
   absorbing child (`false` for `and`, `true` for `or`) and skip its sibling.
   Agreement on a valid certificate's evaluated nodes fixes the value
   (`cert_sound`). With weights per node (risk of the full decision where a
   node is evaluated, of its shape decision where it is skipped), `bestCert`
   chooses the least-weight valid certificate (`bestCert_valid`, `bestCert_le`), never
   heavier than evaluating everything (`bestCert_le_full`).
4. **Shape.** Prefix notation needs no brackets: the arity sequence of a
   formula's preorder determines its shape and where each subformula ends
   (`code_prefix`), so correct arity decisions align the read and true trees
   node by node.
5. **Scaling.** On complete alternating `and`/`or` trees of depth `d`
   (`2^d` leaves), every value assignment has a valid certificate evaluating at
   most `2^⌈d/2⌉` leaves (`alternating_cert_leaves`): about `√n` of `n`.
-/

namespace NCA

open Finset

section Grouped

variable {K : Type}

/-- **Grouped risk.** If the chosen group `g` contains the most probable class
`a`, the risk of the group decision, `1 − p(g) / s` with `s` the mass of the
classes the decision ranges over, is at most the risk of the class decision
`1 − p(a) / s`. -/
theorem grouped_risk_le (p : K → ℝ) (hp : ∀ k, 0 ≤ p k) (g : Finset K) {a : K} (ha : a ∈ g)
    {s : ℝ} (hs : 0 < s) :
    1 - (∑ k ∈ g, p k) / s ≤ 1 - p a / s := by
  have hle : p a ≤ ∑ k ∈ g, p k := single_le_sum (fun k _ => hp k) ha
  have : p a / s ≤ (∑ k ∈ g, p k) / s := by gcongr
  linarith

end Grouped

section Certificates

open MeasureTheory

variable {ι α β : Type*} [Fintype ι]

/-- `cert` certifies `f`: whenever a truth `t` agrees with a reading `r` in the
way `cert r` demands of every position, `f t = f r`. The demand may depend on
the whole reading; a position demanding nothing carries the total relation. -/
def Certifies (f : (ι → α) → β) (cert : (ι → α) → ι → α → α → Prop) : Prop :=
  ∀ r t, (∀ i, cert r i (r i) (t i)) → f t = f r

/-- **Certificate union bound.** For any distribution `μ` of the truth given
the reading `r`, the answer `f r` is wrong with probability at most the sum,
over positions, of the probability that the truth violates what the
certificate of `r` demands there. -/
theorem certificate_error_le {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    {f : (ι → α) → β} {cert : (ι → α) → ι → α → α → Prop} (hc : Certifies f cert)
    (r : ι → α) (truth : Ω → ι → α) :
    μ {ω | f (truth ω) ≠ f r} ≤ ∑ i, μ {ω | ¬ cert r i (r i) (truth ω i)} := by
  calc μ {ω | f (truth ω) ≠ f r} ≤ μ (⋃ i, {ω | ¬ cert r i (r i) (truth ω i)}) := by
        apply measure_mono
        intro ω hω
        simp only [Set.mem_ofPred_eq, Set.mem_iUnion] at hω ⊢
        by_contra h
        push Not at h
        exact hω (hc r _ h)
    _ ≤ _ := measure_iUnion_fintype_le μ _

/-- **Only demanded positions count.** If the certificate of `r` demands
nothing outside `S`, the sum runs over `S`. -/
theorem certificate_error_le_support {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω)
    {f : (ι → α) → β} {cert : (ι → α) → ι → α → α → Prop} (hc : Certifies f cert)
    (r : ι → α) (truth : Ω → ι → α) (S : Finset ι) (hS : ∀ i ∉ S, ∀ a b, cert r i a b) :
    μ {ω | f (truth ω) ≠ f r} ≤ ∑ i ∈ S, μ {ω | ¬ cert r i (r i) (truth ω i)} := by
  refine (certificate_error_le μ hc r truth).trans_eq ?_
  refine (sum_subset (subset_univ S) fun i _ hi => ?_).symm
  simp [hS i hi]

end Certificates

section Formulas

/-- Binary connectives. -/
inductive Op
  | and
  | or
  | xor
  deriving DecidableEq

def Op.apply : Op → Bool → Bool → Bool
  | .and, a, b => a && b
  | .or, a, b => a || b
  | .xor, a, b => Bool.xor a b

/-- The value that determines the connective's result by itself, if any. -/
def Op.absorbing : Op → Option Bool
  | .and => some false
  | .or => some true
  | .xor => none

theorem Op.apply_absorbing_left {o : Op} {v : Bool} (h : o.absorbing = some v) (x : Bool) :
    o.apply v x = v := by
  cases o <;> simp_all [absorbing, apply]

theorem Op.apply_absorbing_right {o : Op} {v : Bool} (h : o.absorbing = some v) (x : Bool) :
    o.apply x v = v := by
  cases o <;> cases x <;> simp_all [absorbing, apply]

/-- Formula trees whose nodes carry annotations of type `ω` (for a reading:
each node's risks). -/
inductive Formula (ω : Type)
  | const (w : ω) (b : Bool)
  | not (w : ω) (f : Formula ω)
  | bin (w : ω) (o : Op) (f g : Formula ω)

namespace Formula

variable {ω ω' : Type}

def eval : Formula ω → Bool
  | const _ b => b
  | not _ f => !f.eval
  | bin _ o f g => o.apply f.eval g.eval

end Formula

open Formula

/-- Certificates: which subformulas are evaluated. `left c` evaluates only the
left child (by `c`) and skips the right one; `right c` the reverse. -/
inductive Cert
  | leaf
  | not (c : Cert)
  | both (c d : Cert)
  | left (c : Cert)
  | right (c : Cert)

variable {ω ω' : Type}

/-- `c` is a valid certificate for the reading `r`: a child is skipped only
when its sibling's read value is absorbing. -/
def ValidCert : Formula ω → Cert → Prop
  | .const _ _, .leaf => True
  | .not _ f, .not c => ValidCert f c
  | .bin _ _ f g, .both c d => ValidCert f c ∧ ValidCert g d
  | .bin _ o f _, .left c => o.absorbing = some f.eval ∧ ValidCert f c
  | .bin _ o _ g, .right c => o.absorbing = some g.eval ∧ ValidCert g c
  | _, _ => False

/-- The truth `t` agrees with the reading `r` on the nodes `c` evaluates: same
constructor, connective and constant there. Skipped subtrees are unconstrained. -/
def Agree : Cert → Formula ω → Formula ω' → Prop
  | .leaf, .const _ a, .const _ b => a = b
  | .not c, .not _ f, .not _ g => Agree c f g
  | .both c d, .bin _ o f g, .bin _ o' f' g' => o = o' ∧ Agree c f f' ∧ Agree d g g'
  | .left c, .bin _ o f _, .bin _ o' f' _ => o = o' ∧ Agree c f f'
  | .right c, .bin _ o _ g, .bin _ o' _ g' => o = o' ∧ Agree c g g'
  | _, _, _ => False

/-- **Certificate soundness.** A truth agreeing with the reading on the nodes
a valid certificate evaluates has the reading's value. -/
theorem cert_sound : ∀ (r : Formula ω) (c : Cert) (t : Formula ω'),
    ValidCert r c → Agree c r t → t.eval = r.eval
  | .const _ _, .leaf, .const _ _, _, h => by simp_all [Agree, eval]
  | .not _ f, .not c, .not _ g, hv, h => by
      simp only [eval]
      rw [cert_sound f c g hv h]
  | .bin _ o f g, .both c d, .bin _ o' f' g', hv, h => by
      obtain ⟨rfl, hf, hg⟩ := h
      simp only [eval]
      rw [cert_sound f c f' hv.1 hf, cert_sound g d g' hv.2 hg]
  | .bin _ o f g, .left c, .bin _ o' f' g', hv, h => by
      obtain ⟨rfl, hf⟩ := h
      simp only [eval]
      rw [cert_sound f c f' hv.2 hf, Op.apply_absorbing_left hv.1, Op.apply_absorbing_left hv.1]
  | .bin _ o f g, .right c, .bin _ o' f' g', hv, h => by
      obtain ⟨rfl, hg⟩ := h
      simp only [eval]
      rw [cert_sound g c g' hv.2 hg, Op.apply_absorbing_right hv.1,
        Op.apply_absorbing_right hv.1]
  | .const _ _, .not _, _, hv, _ | .const _ _, .both _ _, _, hv, _
  | .const _ _, .left _, _, hv, _ | .const _ _, .right _, _, hv, _
  | .not _ _, .leaf, _, hv, _ | .not _ _, .both _ _, _, hv, _
  | .not _ _, .left _, _, hv, _ | .not _ _, .right _, _, hv, _
  | .bin _ _ _ _, .leaf, _, hv, _ | .bin _ _ _ _, .not _, _, hv, _ => by simp [ValidCert] at hv
  | .const _ _, .leaf, .not _ _, _, h | .const _ _, .leaf, .bin _ _ _ _, _, h
  | .not _ _, .not _, .const _ _, _, h | .not _ _, .not _, .bin _ _ _ _, _, h
  | .bin _ _ _ _, .both _ _, .const _ _, _, h | .bin _ _ _ _, .both _ _, .not _ _, _, h
  | .bin _ _ _ _, .left _, .const _ _, _, h | .bin _ _ _ _, .left _, .not _ _, _, h
  | .bin _ _ _ _, .right _, .const _ _, _, h | .bin _ _ _ _, .right _, .not _ _, _, h => by
      simp [Agree] at h

section Weights

variable (wf ws : ω → ℝ)

/-- Weight of deciding only the shape of every node of a skipped subtree. -/
def shapeWeight : Formula ω → ℝ
  | .const w _ => ws w
  | .not w f => ws w + shapeWeight f
  | .bin w _ f g => ws w + shapeWeight f + shapeWeight g

/-- Weight of a certificate: full-decision weight `wf` at evaluated nodes,
shape weight `ws` throughout skipped subtrees. -/
def weight : Cert → Formula ω → ℝ
  | .leaf, .const w _ => wf w
  | .not c, .not w f => wf w + weight c f
  | .both c d, .bin w _ f g => wf w + weight c f + weight d g
  | .left c, .bin w _ f g => wf w + weight c f + shapeWeight ws g
  | .right c, .bin w _ f g => wf w + shapeWeight ws f + weight c g
  | _, _ => 0

/-- The certificate evaluating every node. -/
def fullCert : Formula ω → Cert
  | .const _ _ => .leaf
  | .not _ f => .not (fullCert f)
  | .bin _ _ f g => .both (fullCert f) (fullCert g)

theorem fullCert_valid : ∀ f : Formula ω, ValidCert f (fullCert f)
  | .const _ _ => trivial
  | .not _ f => fullCert_valid f
  | .bin _ _ f g => ⟨fullCert_valid f, fullCert_valid g⟩

/-- The least-weight valid certificate, chosen node by node. -/
noncomputable def bestCert : Formula ω → Cert
  | .const _ _ => .leaf
  | .not _ f => .not (bestCert f)
  | .bin w o f g =>
      let b := Cert.both (bestCert f) (bestCert g)
      let l := if o.absorbing = some f.eval ∧
          weight wf ws (.left (bestCert f)) (.bin w o f g) ≤ weight wf ws b (.bin w o f g)
        then Cert.left (bestCert f) else b
      if o.absorbing = some g.eval ∧
          weight wf ws (.right (bestCert g)) (.bin w o f g) ≤ weight wf ws l (.bin w o f g)
        then Cert.right (bestCert g) else l

/-- Choosing `a` over `b` when allowed and no heavier weighs at most `b`, and
at most `a` when allowed. -/
theorem choose_le {P : Prop} {_ : Decidable P} (F : Cert → ℝ) (a b : Cert) :
    F (if P ∧ F a ≤ F b then a else b) ≤ F b ∧
      (P → F (if P ∧ F a ≤ F b then a else b) ≤ F a) := by
  split_ifs with h
  · exact ⟨h.2, fun _ => le_rfl⟩
  · refine ⟨le_rfl, fun hp => ?_⟩
    push Not at h
    exact (h hp).le

theorem bestCert_valid : ∀ f : Formula ω, ValidCert f (bestCert wf ws f)
  | .const _ _ => trivial
  | .not _ f => bestCert_valid f
  | .bin w o f g => by
      have hf := bestCert_valid f
      have hg := bestCert_valid g
      simp only [bestCert]
      split_ifs with h₁ h₂ h₂ <;> simp_all [ValidCert]

/-- **Optimality.** `bestCert` weighs no more than any valid certificate. -/
theorem bestCert_le : ∀ (f : Formula ω) (c : Cert), ValidCert f c →
    weight wf ws (bestCert wf ws f) f ≤ weight wf ws c f
  | .const _ _, .leaf, _ => le_rfl
  | .not _ f, .not c, hv => by
      simp only [bestCert, weight]
      linarith [bestCert_le f c hv]
  | .bin w o f g, c, hv => by
      let F := fun c => weight wf ws c (.bin w o f g)
      have hb : weight wf ws (bestCert wf ws (.bin w o f g)) (.bin w o f g) ≤
          weight wf ws (.both (bestCert wf ws f) (bestCert wf ws g)) (.bin w o f g) := by
        simp only [bestCert]
        exact (choose_le F _ _).1.trans (choose_le F _ _).1
      have hl : o.absorbing = some f.eval →
          weight wf ws (bestCert wf ws (.bin w o f g)) (.bin w o f g) ≤
            weight wf ws (.left (bestCert wf ws f)) (.bin w o f g) := fun ha => by
        simp only [bestCert]
        exact (choose_le F _ _).1.trans ((choose_le F _ _).2 ha)
      have hr : o.absorbing = some g.eval →
          weight wf ws (bestCert wf ws (.bin w o f g)) (.bin w o f g) ≤
            weight wf ws (.right (bestCert wf ws g)) (.bin w o f g) := fun ha => by
        simp only [bestCert]
        exact (choose_le F _ _).2 ha
      have key : ∀ {x y z : ℝ}, x ≤ y → y ≤ z → x ≤ z := fun hx hy => hx.trans hy
      match c, hv with
      | .both c d, hv =>
          refine key hb ?_
          simp only [weight]
          linarith [bestCert_le f c hv.1, bestCert_le g d hv.2]
      | .left c, hv =>
          refine key (hl hv.1) ?_
          simp only [weight]
          linarith [bestCert_le f c hv.2]
      | .right c, hv =>
          refine key (hr hv.1) ?_
          simp only [weight]
          linarith [bestCert_le g c hv.2]

/-- **Never above reading everything.** -/
theorem bestCert_le_full (f : Formula ω) :
    weight wf ws (bestCert wf ws f) f ≤ weight wf ws (fullCert f) f :=
  bestCert_le wf ws f (fullCert f) (fullCert_valid f)

end Weights

/-- Arity sequence of the preorder (prefix) word sequence. -/
def code : Formula ω → List ℕ
  | .const _ _ => [0]
  | .not _ f => 1 :: code f
  | .bin _ _ f g => 2 :: (code f ++ code g)

/-- **Prefix code.** If one formula's arity sequence followed by `a` equals
another's followed by `b`, the two arity sequences, and the rests, are equal.
So arities alone determine where every subformula of a prefix word sequence
ends, and two formulas with the same arity sequence have the same shape. -/
theorem code_prefix : ∀ (f : Formula ω) (g : Formula ω') (a b : List ℕ),
    code f ++ a = code g ++ b → code f = code g ∧ a = b
  | .const _ _, .const _ _, a, b, h => by simpa [code] using h
  | .not _ f, .not _ g, a, b, h => by
      simp only [code, List.cons_append, List.cons.injEq, true_and] at h ⊢
      exact code_prefix f g a b h
  | .bin _ _ f₁ f₂, .bin _ _ g₁ g₂, a, b, h => by
      simp only [code, List.cons_append, List.append_assoc, List.cons.injEq, true_and] at h ⊢
      obtain ⟨h₁, h₂⟩ := code_prefix f₁ g₁ _ _ h
      obtain ⟨h₃, rfl⟩ := code_prefix f₂ g₂ a b h₂
      exact ⟨by rw [h₁, h₃], rfl⟩
  | .const _ _, .not _ _, _, _, h | .const _ _, .bin _ _ _ _, _, _, h
  | .not _ _, .const _ _, _, _, h | .not _ _, .bin _ _ _ _, _, _, h
  | .bin _ _ _ _, .const _ _, _, _, h | .bin _ _ _ _, .not _ _, _, _, h => by
      simp [code] at h

/-- The number of leaves a certificate evaluates. -/
def Cert.leaves : Cert → ℕ
  | .leaf => 1
  | .not c => c.leaves
  | .both c d => c.leaves + d.leaves
  | .left c => c.leaves
  | .right c => c.leaves

/-- The connective of level `isAnd` of an alternating tree. -/
def alt (isAnd : Bool) : Op := if isAnd then .and else .or

theorem alt_absorbing (isAnd : Bool) : (alt isAnd).absorbing = some (!isAnd) := by
  cases isAnd <;> rfl

/-- A connective's value is its absorbing value exactly when one argument is. -/
theorem Op.apply_eq_absorbing {o : Op} {v : Bool} (h : o.absorbing = some v) (x y : Bool) :
    o.apply x y = v ↔ x = v ∨ y = v := by
  cases o <;> cases v <;> cases x <;> cases y <;> simp_all [absorbing, apply]

/-- Complete alternating trees of depth `d`: `and` at levels with `isAnd`,
`or` at the others, constants at depth 0. -/
inductive Alt : Bool → ℕ → Formula ω → Prop
  | leaf (isAnd : Bool) (w : ω) (b : Bool) : Alt isAnd 0 (.const w b)
  | node (isAnd : Bool) (d : ℕ) (w : ω) (f g : Formula ω) :
      Alt (!isAnd) d f → Alt (!isAnd) d g → Alt isAnd (d + 1) (.bin w (alt isAnd) f g)

/-- A node of an alternating tree whose children have certificates of at most
`L` leaves has one of at most `2 L` leaves, and of at most `L` leaves when its
value is absorbing for its connective. -/
theorem node_cert {w : ω} {o : Op} {v : Bool} (ho : o.absorbing = some v) {f g : Formula ω}
    {L : ℕ} (hf : ∃ c, ValidCert f c ∧ c.leaves ≤ L) (hg : ∃ c, ValidCert g c ∧ c.leaves ≤ L) :
    (∃ c, ValidCert (.bin w o f g) c ∧ c.leaves ≤ 2 * L) ∧
      ((Formula.bin w o f g).eval = v → ∃ c, ValidCert (.bin w o f g) c ∧ c.leaves ≤ L) := by
  obtain ⟨cf, hcf, hlf⟩ := hf
  obtain ⟨cg, hcg, hlg⟩ := hg
  refine ⟨⟨.both cf cg, ⟨hcf, hcg⟩, by simp only [Cert.leaves]; omega⟩, fun hv => ?_⟩
  simp only [eval] at hv
  rcases (Op.apply_eq_absorbing ho _ _).mp hv with h | h
  · exact ⟨.left cf, ⟨by rw [ho, h], hcf⟩, hlf⟩
  · exact ⟨.right cg, ⟨by rw [ho, h], hcg⟩, hlg⟩

/-- **Certificates of alternating trees.** Every complete alternating
`and`/`or` tree of depth `d`, whatever its leaf values, has a valid
certificate evaluating at most `2 ^ ⌈d / 2⌉` of its `2 ^ d` leaves. -/
theorem alternating_cert_leaves : ∀ (d : ℕ) (isAnd : Bool) (f : Formula ω),
    Alt isAnd d f → ∃ c, ValidCert f c ∧ c.leaves ≤ 2 ^ ((d + 1) / 2)
  | 0, _, _, .leaf _ _ _ => ⟨.leaf, trivial, by simp [Cert.leaves]⟩
  | 1, _, _, .node _ 0 _ _ _ (.leaf _ _ _) (.leaf _ _ _) =>
      ⟨.both .leaf .leaf, ⟨trivial, trivial⟩, by simp [Cert.leaves]⟩
  | d + 2, isAnd, _, .node _ _ w f g hf hg => by
      have hpow : 2 ^ ((d + 2 + 1) / 2) = 2 * 2 ^ ((d + 1) / 2) := by
        rw [show (d + 2 + 1) / 2 = (d + 1) / 2 + 1 by omega, pow_succ]
        ring
      rw [hpow]
      -- each child is a node of the other connective over depth-`d` trees
      have child : ∀ {h : Formula ω}, Alt (!isAnd) (d + 1) h →
          (∃ c, ValidCert h c ∧ c.leaves ≤ 2 * 2 ^ ((d + 1) / 2)) ∧
            (h.eval = isAnd → ∃ c, ValidCert h c ∧ c.leaves ≤ 2 ^ ((d + 1) / 2)) := by
        intro h hh
        cases hh with
        | node _ _ w' h₁ h₂ hh₁ hh₂ =>
            have ho : (alt (!isAnd)).absorbing = some isAnd := by
              rw [alt_absorbing, Bool.not_not]
            exact node_cert ho (alternating_cert_leaves d _ h₁ hh₁)
              (alternating_cert_leaves d _ h₂ hh₂)
      have ho := alt_absorbing isAnd
      by_cases hv : (Formula.bin w (alt isAnd) f g).eval = !isAnd
      · -- absorbing root value: one child has it, and that child needs both of its children
        simp only [eval] at hv
        rcases (Op.apply_eq_absorbing ho _ _).mp hv with h | h
        · obtain ⟨c, hc, hl⟩ := (child hf).1
          exact ⟨.left c, ⟨by rw [ho, h], hc⟩, hl⟩
        · obtain ⟨c, hc, hl⟩ := (child hg).1
          exact ⟨.right c, ⟨by rw [ho, h], hc⟩, hl⟩
      · -- otherwise both children have the value absorbing for their own connective
        simp only [eval] at hv
        have hne : ¬ ((alt isAnd).apply f.eval g.eval = !isAnd) := hv
        rw [Op.apply_eq_absorbing ho] at hne
        push Not at hne
        have hfv : f.eval = isAnd := by
          cases h : f.eval <;> cases isAnd <;> simp_all
        have hgv : g.eval = isAnd := by
          cases h : g.eval <;> cases isAnd <;> simp_all
        obtain ⟨cf, hcf, hlf⟩ := (child hf).2 hfv
        obtain ⟨cg, hcg, hlg⟩ := (child hg).2 hgv
        exact ⟨.both cf cg, ⟨hcf, hcg⟩, by simp only [Cert.leaves]; omega⟩

end Formulas

end NCA
