import Mathlib.Data.Finset.Card
import NCA.Terms

/-!
# Most general unifiers

Pattern search (§2.2) unifies a goal with contract outputs. Its completeness
rests on unifiers being most general: every other unifier factors through
them. `mgu_exists` proves that a finite list of equations with a unifier has
a most general one, by the steps of the unification algorithm: drop `x = x`,
decompose equal roots, reject different roots (`Term.subst_app_ne`) and
occurring variables (`occurs_ne`), and eliminate a variable otherwise.
-/

namespace NCA

namespace Term

mutual
/-- The variables of a term. -/
def vars : Term → Finset Nat
  | .var n => {n}
  | .app _ ts => varsList ts

def varsList : List Term → Finset Nat
  | [] => ∅
  | t :: ts => vars t ∪ varsList ts
end

mutual
/-- The number of variable and constructor occurrences in a term. -/
def size : Term → Nat
  | .var _ => 1
  | .app _ ts => 1 + sizeList ts

def sizeList : List Term → Nat
  | [] => 0
  | t :: ts => size t + sizeList ts
end

theorem mem_varsList {x : Nat} : ∀ {ts : List Term}, x ∈ varsList ts ↔ ∃ t ∈ ts, x ∈ vars t
  | [] => by simp [varsList]
  | t :: ts => by simp [varsList, mem_varsList]

theorem size_le_sizeList {t : Term} : ∀ {ts : List Term}, t ∈ ts → size t ≤ sizeList ts
  | [], h => by simp at h
  | u :: ts, h => by
    rcases List.mem_cons.mp h with rfl | h
    · simp [sizeList]
    · have := size_le_sizeList h
      simp only [sizeList]
      omega

theorem subst_var (σ : Nat → Term) (n : Nat) : subst σ (.var n) = σ n := by
  rw [subst]

theorem mem_vars_subst {σ : Nat → Term} {x : Nat} :
    (t : Term) → x ∈ vars (subst σ t) ↔ ∃ y ∈ vars t, x ∈ vars (σ y)
  | .var n => by simp [subst_var, vars]
  | .app f ts => by
    rw [subst_app, vars, vars]
    simp only [mem_varsList]
    constructor
    · rintro ⟨u, hu, hx⟩
      obtain ⟨t, ht, rfl⟩ := List.mem_map.mp hu
      obtain ⟨y, hy, hxy⟩ := (mem_vars_subst t).mp hx
      exact ⟨y, ⟨t, ht, hy⟩, hxy⟩
    · rintro ⟨y, ⟨t, ht, hy⟩, hxy⟩
      exact ⟨subst σ t, List.mem_map_of_mem ht, (mem_vars_subst t).mpr ⟨y, hy, hxy⟩⟩

/-- Substitutions agreeing on a term's variables agree on it. -/
theorem subst_eq_of_vars {σ τ : Nat → Term} :
    (t : Term) → (∀ y ∈ vars t, σ y = τ y) → subst σ t = subst τ t
  | .var n, h => by simpa [subst_var, vars] using h
  | .app f ts, h => by
    rw [subst_app, subst_app]
    congr 1
    exact List.map_congr_left fun t ht =>
      subst_eq_of_vars t fun y hy => h y (by rw [vars, mem_varsList]; exact ⟨t, ht, hy⟩)

theorem subst_id : (t : Term) → subst Term.var t = t
  | .var n => by rw [subst_var]
  | .app f ts => by
    rw [subst_app]
    congr 1
    conv => rhs; rw [← List.map_id ts]
    exact List.map_congr_left fun t _ => subst_id t

/-- A variable's instance is no larger than the instance of a term it occurs
in, and strictly smaller when the term is a constructor application. -/
theorem size_subst_le {σ : Nat → Term} {x : Nat} :
    (t : Term) → x ∈ vars t → size (σ x) ≤ size (subst σ t)
  | .var n, h => by
    simp [vars] at h
    subst h
    rw [subst_var]
  | .app f ts, h => by
    rw [vars, mem_varsList] at h
    obtain ⟨t, ht, hx⟩ := h
    rw [subst_app, size]
    have h1 := size_subst_le (σ := σ) t hx
    have h2 := size_le_sizeList (List.mem_map_of_mem (f := subst σ) ht)
    omega

theorem size_subst_lt {σ : Nat → Term} {x : Nat} {f : String} {ts : List Term}
    (h : x ∈ vars (.app f ts)) : size (σ x) < size (subst σ (.app f ts)) := by
  rw [vars, mem_varsList] at h
  obtain ⟨t, ht, hx⟩ := h
  rw [subst_app, size]
  have h1 := size_subst_le (σ := σ) t hx
  have h2 := size_le_sizeList (List.mem_map_of_mem (f := subst σ) ht)
  omega

/-- **Occurs check.** A variable occurring in a different term is never
unified with it. -/
theorem occurs_ne {σ : Nat → Term} {x : Nat} {t : Term} (hx : x ∈ vars t) (ht : t ≠ .var x) :
    σ x ≠ subst σ t := by
  intro heq
  match t, hx, ht with
  | .var n, hx, ht =>
    simp [vars] at hx
    exact ht (by rw [hx])
  | .app f ts, hx, _ =>
    have := size_subst_lt (σ := σ) hx
    rw [← heq] at this
    exact lt_irrefl _ this

end Term

open Term

/-- Equations between terms. -/
abbrev Equations := List (Term × Term)

/-- `σ` solves every equation. -/
def Unifies (σ : Nat → Term) (E : Equations) : Prop :=
  ∀ p ∈ E, subst σ p.1 = subst σ p.2

/-- `σ` is a most general unifier of `E`: it unifies `E`, and every unifier
`τ` of `E` satisfies `τ = τ ∘ σ`. -/
def IsMGU (σ : Nat → Term) (E : Equations) : Prop :=
  Unifies σ E ∧ ∀ τ, Unifies τ E → ∀ x, τ x = subst τ (σ x)

/-- The variables of a list of equations. -/
def eqVars : Equations → Finset Nat
  | [] => ∅
  | (s, t) :: E => vars s ∪ vars t ∪ eqVars E

/-- The total size of a list of equations. -/
def eqSize : Equations → Nat
  | [] => 0
  | (s, t) :: E => size s + size t + eqSize E

theorem isMGU_congr {σ : Nat → Term} {E F : Equations} (h : ∀ τ, Unifies τ E ↔ Unifies τ F)
    (hm : IsMGU σ E) : IsMGU σ F :=
  ⟨(h σ).mp hm.1, fun τ hτ => hm.2 τ ((h τ).mpr hτ)⟩

theorem unifies_cons {σ : Nat → Term} {s t : Term} {E : Equations} :
    Unifies σ ((s, t) :: E) ↔ subst σ s = subst σ t ∧ Unifies σ E := by
  simp [Unifies]

theorem unifies_append {σ : Nat → Term} {E F : Equations} :
    Unifies σ (E ++ F) ↔ Unifies σ E ∧ Unifies σ F := by
  simp only [Unifies, List.mem_append, or_imp, forall_and]

theorem map_eq_iff_zip (f : Term → Term) : ∀ {ss ts : List Term}, ss.length = ts.length →
    (ss.map f = ts.map f ↔ ∀ p ∈ ss.zip ts, f p.1 = f p.2)
  | [], [], _ => by simp
  | s :: ss, t :: ts, h => by
    simp [map_eq_iff_zip f (ss := ss) (ts := ts) (by simpa using h)]
  | [], _ :: _, h => by simp at h
  | _ :: _, [], h => by simp at h

theorem unifies_decompose {σ : Nat → Term} {f : String} {ss ts : List Term} {E : Equations}
    (h : ss.length = ts.length) :
    Unifies σ ((.app f ss, .app f ts) :: E) ↔ Unifies σ (ss.zip ts ++ E) := by
  rw [unifies_cons, unifies_append, subst_app, subst_app]
  simp only [Term.app.injEq, true_and]
  rw [map_eq_iff_zip _ h]
  rfl

theorem eqVars_append : ∀ (E F : Equations), eqVars (E ++ F) = eqVars E ∪ eqVars F
  | [], _ => by simp [eqVars]
  | (s, t) :: E, F => by
    simp only [List.cons_append, eqVars, eqVars_append E F, Finset.union_assoc]

theorem eqSize_append : ∀ (E F : Equations), eqSize (E ++ F) = eqSize E + eqSize F
  | [], _ => by simp [eqSize]
  | (s, t) :: E, F => by
    simp only [List.cons_append, eqSize, eqSize_append E F]
    omega

theorem eqVars_zip : ∀ {ss ts : List Term}, ss.length = ts.length →
    eqVars (ss.zip ts) = varsList ss ∪ varsList ts
  | [], [], _ => by simp [eqVars, varsList]
  | s :: ss, t :: ts, h => by
    rw [List.zip_cons_cons, eqVars, eqVars_zip (by simpa using h), varsList, varsList]
    ext y
    simp only [Finset.mem_union]
    tauto
  | [], _ :: _, h => by simp at h
  | _ :: _, [], h => by simp at h

theorem eqSize_zip : ∀ {ss ts : List Term}, ss.length = ts.length →
    eqSize (ss.zip ts) = sizeList ss + sizeList ts
  | [], [], _ => by simp [eqSize, sizeList]
  | s :: ss, t :: ts, h => by
    rw [List.zip_cons_cons, eqSize, eqSize_zip (by simpa using h), sizeList, sizeList]
    omega
  | [], _ :: _, h => by simp at h
  | _ :: _, [], h => by simp at h

/-- The substitution eliminating `x` in favour of `t`. -/
def elim (x : Nat) (t : Term) (y : Nat) : Term := if y = x then t else .var y

theorem subst_elim_of_not_mem {x : Nat} {t : Term} (hx : x ∉ vars t) :
    subst (elim x t) t = t := by
  calc subst (elim x t) t = subst Term.var t :=
        subst_eq_of_vars t fun y hy => by
          have : y ≠ x := fun h => hx (h ▸ hy)
          simp [elim, this]
    _ = t := subst_id t

/-- A unifier of `x = t` absorbs the elimination of `x`. -/
theorem subst_elim_absorb {τ : Nat → Term} {x : Nat} {t : Term} (h : τ x = subst τ t)
    (s : Term) : subst τ (subst (elim x t) s) = subst τ s := by
  rw [subst_subst]
  congr 1
  funext y
  by_cases hy : y = x
  · simp [elim, hy, h]
  · simp [elim, hy, subst_var]

theorem mem_vars_elim {x y : Nat} {t s : Term} (hx : x ∉ vars t)
    (h : y ∈ vars (subst (elim x t) s)) : y ≠ x ∧ (y ∈ vars s ∨ y ∈ vars t) := by
  obtain ⟨z, hz, hy⟩ := (mem_vars_subst s).mp h
  by_cases hzx : z = x
  · simp only [elim, hzx, if_true] at hy
    exact ⟨fun h => hx (h ▸ hy), Or.inr hy⟩
  · simp only [elim, hzx, if_false, vars, Finset.mem_singleton] at hy
    subst hy
    exact ⟨hzx, Or.inl hz⟩

/-- The other equations with `x` eliminated. -/
def elimEqs (x : Nat) (t : Term) (E : Equations) : Equations :=
  E.map fun p => (subst (elim x t) p.1, subst (elim x t) p.2)

theorem eqVars_elimEqs {x : Nat} {t : Term} (hx : x ∉ vars t) :
    ∀ (E : Equations), eqVars (elimEqs x t E) ⊆ (eqVars E ∪ vars t).erase x
  | [] => by simp [elimEqs, eqVars]
  | (a, b) :: E => by
    intro y hy
    simp only [elimEqs, List.map_cons, eqVars, Finset.mem_union] at hy
    rw [Finset.mem_erase]
    rcases hy with (hy | hy) | hy
    · obtain ⟨hne, h⟩ := mem_vars_elim hx hy
      refine ⟨hne, ?_⟩
      simp only [eqVars, Finset.mem_union]
      tauto
    · obtain ⟨hne, h⟩ := mem_vars_elim hx hy
      refine ⟨hne, ?_⟩
      simp only [eqVars, Finset.mem_union]
      tauto
    · have := Finset.mem_erase.mp (eqVars_elimEqs hx E hy)
      refine ⟨this.1, ?_⟩
      simp only [eqVars, Finset.mem_union] at this ⊢
      tauto

theorem unifies_elimEqs {τ : Nat → Term} {x : Nat} {t : Term} {E : Equations}
    (h : Unifies τ ((.var x, t) :: E)) : Unifies τ (elimEqs x t E) := by
  rw [unifies_cons, subst_var] at h
  intro p hp
  obtain ⟨q, hq, rfl⟩ := List.mem_map.mp hp
  rw [subst_elim_absorb h.1, subst_elim_absorb h.1]
  exact h.2 q hq

/-- Eliminating `x` with a most general unifier of the rest gives one of the
whole. -/
theorem isMGU_elim {σ' : Nat → Term} {x : Nat} {t : Term} {E : Equations} (hx : x ∉ vars t)
    (hm : IsMGU σ' (elimEqs x t E)) :
    IsMGU (fun y => subst σ' (elim x t y)) ((.var x, t) :: E) := by
  have hcomp : ∀ s, subst (fun y => subst σ' (elim x t y)) s = subst σ' (subst (elim x t) s) :=
    fun s => (subst_subst σ' (elim x t) s).symm
  refine ⟨?_, fun τ hτ y => ?_⟩
  · rw [unifies_cons, subst_var, hcomp, subst_elim_of_not_mem hx]
    refine ⟨by simp [elim], fun p hp => ?_⟩
    rw [hcomp, hcomp]
    exact hm.1 _ (List.mem_map_of_mem hp)
  · have hτx : τ x = subst τ t := by
      have := (unifies_cons.mp hτ).1
      rwa [subst_var] at this
    have hgen := hm.2 τ (unifies_elimEqs hτ)
    calc τ y = subst τ (elim x t y) := by
          by_cases hy : y = x
          · simp [elim, hy, hτx]
          · simp [elim, hy, subst_var]
      _ = subst (fun n => subst τ (σ' n)) (elim x t y) := by
          congr 1
          funext n
          exact hgen n
      _ = subst τ (subst σ' (elim x t y)) := (subst_subst τ σ' _).symm

theorem size_pos : (t : Term) → 0 < size t
  | .var _ => by simp [size]
  | .app _ _ => by rw [size]; omega

/-- **Most general unifiers.** A finite list of equations with a unifier has
a most general unifier. -/
theorem mgu_exists (E : Equations) (hu : ∃ τ, Unifies τ E) : ∃ σ, IsMGU σ E := by
  induction hn : (eqVars E).card using Nat.strong_induction_on generalizing E with
  | _ n ihn =>
  induction hk : eqSize E using Nat.strong_induction_on generalizing E with
  | _ k ihk =>
  have recur : ∀ F : Equations, (∃ τ, Unifies τ F) →
      (eqVars F).card < n ∨ ((eqVars F).card ≤ n ∧ eqSize F < k) → ∃ σ, IsMGU σ F := by
    intro F hF h
    rcases h with h | ⟨h1, h2⟩
    · exact ihn _ h F hF rfl
    · rcases Nat.lt_or_eq_of_le h1 with h1 | h1
      · exact ihn _ h1 F hF rfl
      · exact ihk _ (hk ▸ h2) F hF h1 rfl
  have eliminate : ∀ (x : Nat) (u : Term) (F : Equations), x ∉ vars u →
      eqVars ((.var x, u) :: F) = eqVars E → (∃ τ, Unifies τ ((.var x, u) :: F)) →
      ∃ σ, IsMGU σ ((.var x, u) :: F) := by
    intro x u F hx hvars hF
    obtain ⟨τ, hτ⟩ := hF
    have hmem : x ∈ eqVars ((.var x, u) :: F) := by simp [eqVars, vars]
    have hsub : eqVars (elimEqs x u F) ⊆ (eqVars ((.var x, u) :: F)).erase x := by
      refine (eqVars_elimEqs hx F).trans (Finset.erase_subset_erase x ?_)
      intro y hy
      simp only [eqVars, Finset.mem_union] at hy ⊢
      tauto
    have hlt : (eqVars (elimEqs x u F)).card < n := by
      rw [← hn, ← hvars]
      exact lt_of_le_of_lt (Finset.card_le_card hsub) (Finset.card_erase_lt_of_mem hmem)
    obtain ⟨σ', hσ'⟩ := recur _ ⟨τ, unifies_elimEqs hτ⟩ (Or.inl hlt)
    exact ⟨_, isMGU_elim hx hσ'⟩
  match E, hu, hn, hk, recur, eliminate with
  | [], _, _, _, _, _ =>
    exact ⟨Term.var, fun p hp => by simp at hp, fun τ _ x => by rw [subst_var]⟩
  | (s, t) :: E, hu, hn, hk, recur, eliminate =>
    obtain ⟨τ, hτ⟩ := hu
    have hsub : eqVars E ⊆ eqVars ((s, t) :: E) := by
      intro y hy
      simp only [eqVars, Finset.mem_union]
      exact Or.inr hy
    match s, t with
    | .var x, .var y =>
      by_cases hxy : x = y
      · subst hxy
        have hiff : ∀ σ, Unifies σ E ↔ Unifies σ ((.var x, .var x) :: E) := fun σ => by
          rw [unifies_cons]
          simp
        obtain ⟨σ, hσ⟩ := recur E ⟨τ, (hiff τ).mpr hτ⟩ (Or.inr ⟨hn ▸ Finset.card_le_card hsub, by
          rw [← hk, eqSize]
          have := size_pos (.var x)
          omega⟩)
        exact ⟨σ, isMGU_congr hiff hσ⟩
      · exact eliminate x (.var y) E (by simp [vars, hxy]) rfl ⟨τ, hτ⟩
    | .var x, .app f ts =>
      by_cases hx : x ∈ vars (.app f ts)
      · exact absurd (by simpa [unifies_cons, subst_var] using (unifies_cons.mp hτ).1)
          (occurs_ne (σ := τ) hx (by simp))
      · exact eliminate x (.app f ts) E hx rfl ⟨τ, hτ⟩
    | .app f ts, .var x =>
      have hswap : ∀ σ, Unifies σ ((.var x, .app f ts) :: E) ↔
          Unifies σ ((.app f ts, .var x) :: E) := fun σ => by
        simp only [unifies_cons]
        constructor <;> rintro ⟨h, h'⟩ <;> exact ⟨h.symm, h'⟩
      by_cases hx : x ∈ vars (.app f ts)
      · exact absurd ((unifies_cons.mp hτ).1.trans (subst_var τ x)).symm
          (occurs_ne (σ := τ) hx (by simp))
      · obtain ⟨σ, hσ⟩ := eliminate x (.app f ts) E hx
          (by simp only [eqVars]; ext y; simp only [Finset.mem_union]; tauto)
          ⟨τ, (hswap τ).mpr hτ⟩
        exact ⟨σ, isMGU_congr hswap hσ⟩
    | .app f ss, .app g ts =>
      by_cases hfg : f = g ∧ ss.length = ts.length
      · obtain ⟨rfl, hlen⟩ := hfg
        have hiff : ∀ σ, Unifies σ (ss.zip ts ++ E) ↔ Unifies σ ((.app f ss, .app f ts) :: E) :=
          fun σ => (unifies_decompose hlen).symm
        have hvars : eqVars (ss.zip ts ++ E) ⊆ eqVars ((.app f ss, .app f ts) :: E) := by
          rw [eqVars_append, eqVars_zip hlen]
          intro y hy
          simp only [eqVars, vars, Finset.mem_union] at hy ⊢
          tauto
        obtain ⟨σ, hσ⟩ := recur _ ⟨τ, (hiff τ).mpr hτ⟩ (Or.inr ⟨hn ▸ Finset.card_le_card hvars, by
          rw [← hk, eqSize_append, eqSize_zip hlen, eqSize, size, size]
          omega⟩)
        exact ⟨σ, isMGU_congr hiff hσ⟩
      · refine absurd (unifies_cons.mp hτ).1 (subst_app_ne τ τ ?_)
        by_cases h : f = g
        · exact Or.inr fun hl => hfg ⟨h, hl⟩
        · exact Or.inl h

/-- Equations with a substitution applied to both sides. -/
def eqSubst (θ : Nat → Term) (E : Equations) : Equations :=
  E.map fun p => (subst θ p.1, subst θ p.2)

/-- A unifier factoring through `θ` absorbs it. -/
theorem subst_absorb {τ θ : Nat → Term} (h : ∀ x, τ x = subst τ (θ x)) (s : Term) :
    subst τ (subst θ s) = subst τ s := by
  rw [subst_subst]
  congr 1
  funext x
  exact (h x).symm

/-- **Sequential unification.** Solving `E₁` most generally never loses a
solution of `E₁ ++ E₂`, and a most general solution of the rest, composed
with it, is most general for the whole. -/
theorem unifies_eqSubst {θ₁ τ : Nat → Term} {E₁ E₂ : Equations} (h₁ : IsMGU θ₁ E₁)
    (hτ : Unifies τ (E₁ ++ E₂)) : Unifies τ (eqSubst θ₁ E₂) := by
  have hgen := h₁.2 τ (unifies_append.mp hτ).1
  intro p hp
  obtain ⟨q, hq, rfl⟩ := List.mem_map.mp hp
  rw [subst_absorb hgen, subst_absorb hgen]
  exact (unifies_append.mp hτ).2 q hq

theorem isMGU_append {θ₁ θ₂ : Nat → Term} {E₁ E₂ : Equations} (h₁ : IsMGU θ₁ E₁)
    (h₂ : IsMGU θ₂ (eqSubst θ₁ E₂)) :
    IsMGU (fun x => subst θ₂ (θ₁ x)) (E₁ ++ E₂) := by
  have hcomp : ∀ s, subst (fun x => subst θ₂ (θ₁ x)) s = subst θ₂ (subst θ₁ s) :=
    fun s => (subst_subst θ₂ θ₁ s).symm
  refine ⟨unifies_append.mpr ⟨fun p hp => ?_, fun p hp => ?_⟩, fun τ hτ x => ?_⟩
  · rw [hcomp, hcomp, h₁.1 p hp]
  · rw [hcomp, hcomp]
    exact h₂.1 _ (List.mem_map_of_mem hp)
  · have g₁ := h₁.2 τ (unifies_append.mp hτ).1
    have g₂ := h₂.2 τ (unifies_eqSubst h₁ hτ)
    rw [subst_absorb g₂]
    exact g₁ x

end NCA
