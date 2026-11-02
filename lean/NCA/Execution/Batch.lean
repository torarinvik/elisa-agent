/-!
# Batching across rows

A compiled route evaluates a map's body once on the concatenation of every
row's elements. Mapping over a concatenation equals concatenating the maps
(`batch_flatten`), so regrouping by the rows' lengths recovers each row's
result.
-/

namespace NCA

/-- **Batching across rows.** -/
theorem batch_flatten {α β : Type} (f : α → β) (rows : List (List α)) :
    rows.flatten.map f = (rows.map (List.map f)).flatten := by
  simp [List.map_flatten]

/-- A batch-sound expert's batch form can stand for elementwise application. -/
theorem batch_sound_flatten {α β : Type} (f : α → β) (batch : List α → List β)
    (sound : ∀ xs, batch xs = xs.map f) (rows : List (List α)) :
    batch rows.flatten = (rows.map (List.map f)).flatten := by
  rw [sound, batch_flatten]

end NCA
