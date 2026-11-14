import Mathlib.Data.Fintype.Basic
import Mathlib.Data.Fintype.Card
import Mathlib.Data.Multiset.Basic
import Mathlib.Data.Finset.Image
import Mathlib.Logic.Equiv.Defs
import Mathlib.Tactic.FinCases

/-! Structures that are the same under a renaming of their parts: what counting the joins of each part tells and
does not, and descriptions of parts by their neighbours' descriptions, which a renaming keeps. -/

namespace NCA

/-- What a description of a part is after each round: at first its mark, then its description so far with the
descriptions so far of the parts it is joined to, as many times as they occur. -/
def Described (M : Type) : ℕ → Type
  | 0 => M
  | n + 1 => Described M n × Multiset (Described M n)

/-- The description of a part after `n` rounds. -/
def described {α M : Type} [Fintype α] (mark : α → M) (joined : α → α → Prop) [DecidableRel joined] :
    (n : ℕ) → α → Described M n
  | 0, a => mark a
  | n + 1, a => (described mark joined n a, (Finset.univ.filter (joined a)).val.map (described mark joined n))

/-- **Theorem 58.2 (a renaming keeps every description).** If a one-to-one map of the parts of one structure
onto those of another keeps marks and joins, each part has, after every round, the description of the part it is
sent to. -/
theorem renaming_keeps_descriptions {α β M : Type} [Fintype α] [Fintype β] (mark : α → M) (mark' : β → M)
    (joined : α → α → Prop) (joined' : β → β → Prop) [DecidableRel joined] [DecidableRel joined'] (φ : α ≃ β)
    (marks : ∀ a, mark' (φ a) = mark a) (joins : ∀ a b, joined' (φ a) (φ b) ↔ joined a b) :
    ∀ n a, described mark' joined' n (φ a) = described mark joined n a := by
  intro n
  induction n with
  | zero => exact marks
  | succ n ih =>
    intro a
    have near : Finset.univ.filter (joined' (φ a)) = (Finset.univ.filter (joined a)).map φ.toEmbedding := by
      ext b
      simp only [Finset.mem_filter, Finset.mem_univ, true_and, Finset.mem_map, Equiv.coe_toEmbedding]
      constructor
      · intro held
        exact ⟨φ.symm b, by simpa using (joins a (φ.symm b)).mp (by simpa using held), by simp⟩
      · rintro ⟨c, held, rfl⟩
        exact (joins a c).mpr held
    show (described mark' joined' n (φ a), _) = (described mark joined n a, _)
    rw [ih a, near, Finset.map_val, Multiset.map_map]
    congr 1
    exact Multiset.map_congr rfl fun c _ => ih c

/-- **Corollary 58.2 (the descriptions of the two structures are the same, as many times each).** -/
theorem renamed_structures_described_alike {α β M : Type} [Fintype α] [Fintype β] (mark : α → M) (mark' : β → M)
    (joined : α → α → Prop) (joined' : β → β → Prop) [DecidableRel joined] [DecidableRel joined'] (φ : α ≃ β)
    (marks : ∀ a, mark' (φ a) = mark a) (joins : ∀ a b, joined' (φ a) (φ b) ↔ joined a b) (n : ℕ) :
    (Finset.univ : Finset β).val.map (described mark' joined' n) =
      (Finset.univ : Finset α).val.map (described mark joined n) := by
  have all : (Finset.univ : Finset β) = (Finset.univ : Finset α).map φ.toEmbedding := by
    ext b
    simp only [Finset.mem_univ, Finset.mem_map, Equiv.coe_toEmbedding, true_and, true_iff]
    exact ⟨φ.symm b, by simp⟩
  rw [all, Finset.map_val, Multiset.map_map]
  exact Multiset.map_congr rfl fun a _ => renaming_keeps_descriptions mark mark' joined joined' φ marks joins n a

/-- Six parts joined in a ring. -/
def ringOfSix (a b : Fin 6) : Prop := a.val + 1 = b.val ∨ b.val + 1 = a.val ∨ (a.val = 0 ∧ b.val = 5) ∨ (a.val = 5 ∧ b.val = 0)

/-- Six parts joined in two rings of three. -/
def twoRingsOfThree (a b : Fin 6) : Prop := a ≠ b ∧ a.val / 3 = b.val / 3

instance : DecidableRel ringOfSix := fun a b => by unfold ringOfSix; infer_instance
instance : DecidableRel twoRingsOfThree := fun a b => by unfold twoRingsOfThree; infer_instance

/-- **Proposition 58.1 (as many parts, as many joins at every part, and not the same).** A ring of six parts and two
rings of three have six parts each, every part joined to two, and no renaming takes one to the other. -/
theorem counting_joins_does_not_tell :
    (∀ a : Fin 6, (Finset.univ.filter (ringOfSix a)).card = 2) ∧
      (∀ a : Fin 6, (Finset.univ.filter (twoRingsOfThree a)).card = 2) ∧
      ¬∃ φ : Fin 6 ≃ Fin 6, ∀ a b, ringOfSix (φ a) (φ b) ↔ twoRingsOfThree a b := by
  refine ⟨by decide, by decide, ?_⟩
  rintro ⟨φ, keeps⟩
  have none : ∀ x y z : Fin 6, ¬(ringOfSix x y ∧ ringOfSix y z ∧ ringOfSix x z) := by decide
  exact none (φ 0) (φ 1) (φ 2) ⟨(keeps 0 1).mpr (by decide), (keeps 1 2).mpr (by decide), (keeps 0 2).mpr (by decide)⟩

end NCA
