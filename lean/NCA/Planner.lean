import NCA.Contract

/-!
# Planner soundness

Reference model of `nca.planner.plan`: depth-bounded backward chaining that
tries contracts in installation order. Every plan it returns is well-typed.
-/

namespace NCA

variable {α β Ty : Type}

/-- Apply `f` to every element; fail if any application fails. -/
def traverse (f : α → Option β) : List α → Option (List β)
  | [] => some []
  | a :: as =>
    match f a, traverse f as with
    | some b, some bs => some (b :: bs)
    | _, _ => none

/-- The first successful application of `f`, in list order. -/
def firstSome (f : α → Option β) : List α → Option β
  | [] => none
  | a :: as =>
    match f a with
    | some b => some b
    | none => firstSome f as

theorem firstSome_spec {f : α → Option β} {b : β} :
    ∀ {l : List α}, firstSome f l = some b → ∃ a ∈ l, f a = some b
  | [], h => by simp [firstSome] at h
  | a :: as, h => by
    cases hf : f a with
    | some b' =>
      simp [firstSome, hf] at h
      exact ⟨a, List.mem_cons_self .., h ▸ hf⟩
    | none =>
      simp [firstSome, hf] at h
      obtain ⟨a', ha', hfa'⟩ := firstSome_spec h
      exact ⟨a', List.mem_cons_of_mem _ ha', hfa'⟩

theorem traverse_sound {lib : List (Contract Ty)} {avail : List Ty}
    {f : Ty → Option (Plan Ty)} (hf : ∀ t p, f t = some p → WellTyped lib avail p t) :
    ∀ {ts : List Ty} {ps : List (Plan Ty)}, traverse f ts = some ps →
      WellTypedArgs lib avail ps ts
  | [], ps, h => by
    simp [traverse] at h
    subst h
    exact .nil
  | t :: ts, ps, h => by
    cases hp : f t <;> cases hr : traverse f ts <;> simp [traverse, hp, hr] at h
    subst h
    exact .cons (hf _ _ hp) (traverse_sound hf hr)

variable [DecidableEq Ty]

/-- Backward-chain from goal `t` to available types within `fuel` depth. -/
def plan (lib : List (Contract Ty)) (avail : List Ty) : Nat → Ty → Option (Plan Ty)
  | 0, _ => none
  | n + 1, t =>
    if t ∈ avail then some (.given t)
    else
      firstSome (fun c =>
        if c.output = t then (traverse (plan lib avail n) c.inputs).map (.apply c)
        else none) lib

/-- **Soundness.** Any plan returned by the planner is well-typed. -/
theorem plan_sound (lib : List (Contract Ty)) (avail : List Ty) :
    ∀ (n : Nat) (t : Ty) (p : Plan Ty), plan lib avail n t = some p →
      WellTyped lib avail p t
  | 0, _, _, h => by simp [plan] at h
  | n + 1, t, p, h => by
    unfold plan at h
    split at h
    next ht =>
      cases h
      exact .given ht
    next =>
      obtain ⟨c, hc, hf⟩ := firstSome_spec h
      split at hf
      next heq =>
        cases hr : traverse (plan lib avail n) c.inputs with
        | none => simp [hr] at hf
        | some ps =>
          simp [hr] at hf
          subst hf heq
          exact .apply hc (traverse_sound (plan_sound lib avail n) hr)
      next => simp at hf

end NCA

namespace NCA
variable {α β Ty : Type}

theorem traverse_isSome {f : α → Option β} :
    ∀ {l : List α}, (∀ a ∈ l, (f a).isSome) → (traverse f l).isSome
  | [], _ => rfl
  | a :: as, h => by
    obtain ⟨b, hb⟩ := Option.isSome_iff_exists.mp (h a List.mem_cons_self)
    obtain ⟨bs, hbs⟩ := Option.isSome_iff_exists.mp
      (traverse_isSome fun x hx => h x (List.mem_cons_of_mem _ hx))
    simp [traverse, hb, hbs]

theorem firstSome_isSome {f : α → Option β} :
    ∀ {l : List α} {a : α}, a ∈ l → (f a).isSome → (firstSome f l).isSome
  | x :: xs, a, hmem, ha => by
    cases hx : f x with
    | some b => simp [firstSome, hx]
    | none =>
      simp only [firstSome, hx]
      rcases List.mem_cons.mp hmem with rfl | hmem
      · simp [hx] at ha
      · exact firstSome_isSome hmem ha

/-- `Derivable lib avail n t`: some composition of installed contracts of
depth at most `n` produces `t` from the available inputs. -/
inductive Derivable (lib : List (Contract Ty)) (avail : List Ty) : Nat → Ty → Prop
  | given {n : Nat} {t : Ty} : t ∈ avail → Derivable lib avail (n + 1) t
  | apply {n : Nat} {c : Contract Ty} :
      c ∈ lib → (∀ i ∈ c.inputs, Derivable lib avail n i) →
      Derivable lib avail (n + 1) c.output

variable [DecidableEq Ty]

/-- **Completeness.** If a composition of depth at most `n` exists, the
planner with fuel `n` finds one. -/
theorem plan_complete {lib : List (Contract Ty)} {avail : List Ty} {n : Nat} {t : Ty}
    (h : Derivable lib avail n t) : (plan lib avail n t).isSome := by
  induction h with
  | given ht => simp [plan, ht]
  | @apply n c hc _ ih =>
    unfold plan
    split
    · rfl
    · apply firstSome_isSome hc
      obtain ⟨ps, hps⟩ := Option.isSome_iff_exists.mp (traverse_isSome ih)
      simp [hps]

end NCA
