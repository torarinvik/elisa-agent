import Mathlib.Data.List.Dedup
import Mathlib.Data.List.Perm.Basic

/-! Loader registries (§28.9). A registry is the finite list of (identifier,
location) registrations contributed by installed distributions, in any order.
Resolution succeeds only when every registration of an identifier agrees. -/
namespace NCA

variable {N L : Type} [DecidableEq N] [DecidableEq L]

/-- The locations registered for identifier `n`, with repetition. -/
def loaderLocations (registry : List (N × L)) (n : N) : List L :=
  (registry.filter (fun r => r.1 = n)).map Prod.snd

/-- The unique location registered for `n`, if every registration agrees. -/
def resolveLoader (registry : List (N × L)) (n : N) : Option L :=
  match (loaderLocations registry n).dedup with
  | [l] => some l
  | _ => none

theorem resolveLoader_eq_some {registry : List (N × L)} {n : N} {l : L} :
    resolveLoader registry n = some l ↔ (loaderLocations registry n).dedup = [l] := by
  unfold resolveLoader
  constructor
  · intro h
    split at h
    · next l' heq => cases h; exact heq
    · cases h
  · intro h; rw [h]

/-- Resolution does not depend on the order distributions are installed. -/
theorem resolveLoader_perm {registry registry' : List (N × L)}
    (p : registry.Perm registry') (n : N) :
    resolveLoader registry n = resolveLoader registry' n := by
  have hp : ((loaderLocations registry n).dedup).Perm (loaderLocations registry' n).dedup :=
    ((p.filter _).map _).dedup
  cases h : resolveLoader registry' n with
  | some l =>
    rw [resolveLoader_eq_some] at h ⊢
    rw [h] at hp
    exact List.perm_singleton.mp hp
  | none =>
    cases h' : resolveLoader registry n with
    | none => rfl
    | some l =>
      rw [resolveLoader_eq_some] at h'
      rw [h'] at hp
      have := List.singleton_perm.mp hp
      have hs : resolveLoader registry' n = some l := resolveLoader_eq_some.mpr this.symm
      rw [hs] at h
      cases h

/-- Registrations of other identifiers never change how `n` resolves. -/
theorem resolveLoader_unrelated (registry extra : List (N × L)) (n : N)
    (other : ∀ r ∈ extra, r.1 ≠ n) :
    resolveLoader (registry ++ extra) n = resolveLoader registry n := by
  have : extra.filter (fun r => r.1 = n) = [] :=
    List.filter_eq_nil_iff.mpr (fun r hr => by simpa using other r hr)
  simp [resolveLoader, loaderLocations, List.filter_append, this]

/-- Two registrations of `n` with different locations are refused. -/
theorem resolveLoader_conflict {registry : List (N × L)} {n : N} {a b : L}
    (ha : (n, a) ∈ registry) (hb : (n, b) ∈ registry) (ne : a ≠ b) :
    resolveLoader registry n = none := by
  cases h : resolveLoader registry n with
  | none => rfl
  | some l =>
    rw [resolveLoader_eq_some] at h
    have mem : ∀ x, (n, x) ∈ registry → x = l := by
      intro x hx
      have : x ∈ loaderLocations registry n :=
        List.mem_map.mpr ⟨(n, x), List.mem_filter.mpr ⟨hx, by simp⟩, rfl⟩
      rw [← List.mem_dedup, h] at this
      simpa using this
    exact absurd ((mem a ha).trans (mem b hb).symm) ne

/-- Moving code relabels every location by an injective `move`; stored
identifiers are untouched and resolve to the moved factories. -/
theorem resolveLoader_relocate (registry : List (N × L)) (move : L → L)
    (inj : Function.Injective move) (n : N) :
    resolveLoader (registry.map (fun r => (r.1, move r.2))) n =
      (resolveLoader registry n).map move := by
  have hloc : loaderLocations (registry.map (fun r => (r.1, move r.2))) n =
      (loaderLocations registry n).map move := by
    simp [loaderLocations, List.filter_map, Function.comp_def, List.map_map]
  have hdedup : ((loaderLocations registry n).map move).dedup =
      ((loaderLocations registry n).dedup).map move :=
    List.dedup_map_of_injective inj _
  unfold resolveLoader
  rw [hloc, hdedup]
  generalize (loaderLocations registry n).dedup = xs
  match xs with
  | [] => rfl
  | [_] => rfl
  | _ :: _ :: _ => rfl

end NCA
