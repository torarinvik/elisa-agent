import NCA.Contract

/-!
# Planner soundness and completeness

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

/-- Traversing a single input wraps its result without another search. -/
theorem traverse_singleton (f : α → Option β) (a : α) :
    traverse f [a] = (f a).map (fun b => [b]) := by
  cases h : f a <;> simp [traverse, h]

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

theorem traverse_sound [SeqTypes Ty] {lib : List (Contract Ty)} {avail : List Ty}
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

variable [DecidableEq Ty] [SeqTypes Ty]
open SeqTypes

/-- Candidate element types for `map`: elements of available sequence types
and of sequence types some installed contract produces. -/
def elemCandidates (lib : List (Contract Ty)) (avail : List Ty) : List Ty :=
  (avail ++ lib.map Contract.output).filterMap elem?

/-- Backward-chain from goal `t` to available types within `fuel` depth:
first by applying a contract producing `t`, otherwise, for a sequence goal,
by mapping an elementwise plan over a plannable source sequence. -/
def plan (lib : List (Contract Ty)) : List Ty → Nat → Ty → Option (Plan Ty)
  | _, 0, _ => none
  | avail, n + 1, t =>
    if t ∈ avail then some (.given t)
    else
      (firstSome (fun c =>
        if c.output = t then (traverse (plan lib avail n) c.inputs).map (.apply c)
        else none) lib).orElse fun _ =>
      match elem? t with
      | none => none
      | some e => firstSome (fun a =>
          match plan lib [a] n e, plan lib avail n (seq a) with
          | some body, some src => some (.map a body src)
          | _, _ => none) (elemCandidates lib avail)

/-- A depth-one application cannot solve a nonempty input list. -/
theorem zero_fuel_nonempty_inputs (lib : List (Contract Ty)) (avail : List Ty)
    (input : Ty) (rest : List Ty) :
    traverse (plan lib avail 0) (input :: rest) = none := by
  simp [traverse, plan]

/-- Neither child of a map can be planned with zero fuel. -/
theorem zero_fuel_map_children (lib : List (Contract Ty)) (avail : List Ty)
    (a e : Ty) :
    (match plan lib [a] 0 e, plan lib avail 0 (seq a) with
     | some body, some src => some (Plan.map a body src)
     | _, _ => none) = none := by
  simp [plan]

/-- **Soundness.** Any plan returned by the planner is well-typed. -/
theorem plan_sound (lib : List (Contract Ty)) :
    ∀ (n : Nat) (avail : List Ty) (t : Ty) (p : Plan Ty), plan lib avail n t = some p →
      WellTyped lib avail p t
  | 0, _, _, _, h => by simp [plan] at h
  | n + 1, avail, t, p, h => by
    unfold plan at h
    split at h
    next ht =>
      cases h
      exact .given ht
    next =>
      cases hfs : firstSome (fun c =>
          if c.output = t then (traverse (plan lib avail n) c.inputs).map (Plan.apply c)
          else none) lib with
      | some q =>
        rw [hfs] at h
        cases h
        obtain ⟨c, hc, hf⟩ := firstSome_spec hfs
        split at hf
        next heq =>
          cases hr : traverse (plan lib avail n) c.inputs with
          | none => simp [hr] at hf
          | some ps =>
            simp [hr] at hf
            subst hf heq
            exact .apply hc (traverse_sound (plan_sound lib n avail) hr)
        next => simp at hf
      | none =>
        rw [hfs] at h
        simp only [Option.orElse] at h
        cases he : elem? t with
        | none => simp [he] at h
        | some e =>
          simp only [he] at h
          obtain ⟨a, _, hf⟩ := firstSome_spec h
          cases hb : plan lib [a] n e <;> cases hs : plan lib avail n (seq a) <;>
            simp [hb, hs] at hf
          subst hf
          rw [elem?_eq_some.mp he]
          exact .map (plan_sound lib n [a] e _ hb) (plan_sound lib n avail _ _ hs)

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

variable [SeqTypes Ty]
open SeqTypes

/-- `Derivable lib avail n t`: some composition of installed contracts of
depth at most `n` produces `t` from the available inputs. -/
inductive Derivable (lib : List (Contract Ty)) : List Ty → Nat → Ty → Prop
  | given {avail : List Ty} {n : Nat} {t : Ty} :
      t ∈ avail → Derivable lib avail (n + 1) t
  | apply {avail : List Ty} {n : Nat} {c : Contract Ty} :
      c ∈ lib → (∀ i ∈ c.inputs, Derivable lib avail n i) →
      Derivable lib avail (n + 1) c.output
  | map {avail : List Ty} {n : Nat} {a e : Ty} :
      a ∈ elemCandidates lib avail → Derivable lib [a] n e →
      Derivable lib avail n (seq a) → Derivable lib avail (n + 1) (seq e)

variable [DecidableEq Ty]

/-- **Completeness.** If a composition of depth at most `n` exists, the
planner with fuel `n` finds one. -/
theorem plan_complete {lib : List (Contract Ty)} {avail : List Ty} {n : Nat} {t : Ty}
    (h : Derivable lib avail n t) : (plan lib avail n t).isSome := by
  induction h with
  | given ht => simp [plan, ht]
  | @apply avail n c hc _ ih =>
    unfold plan
    split
    · rfl
    · obtain ⟨q, hq⟩ := Option.isSome_iff_exists.mp (firstSome_isSome hc (by
        obtain ⟨ps, hps⟩ := Option.isSome_iff_exists.mp (traverse_isSome ih)
        simp [hps]) : (firstSome (fun c' =>
          if c'.output = c.output then (traverse (plan lib avail n) c'.inputs).map (Plan.apply c')
          else none) lib).isSome)
      rw [hq]; rfl
  | @map avail n a e ha _ _ ihb ihs =>
    unfold plan
    split
    · rfl
    · cases hfs : firstSome (fun c =>
          if c.output = seq e then (traverse (plan lib avail n) c.inputs).map (Plan.apply c)
          else none) lib with
      | some q => rfl
      | none =>
        simp only [Option.orElse, elem?_eq_some.mpr rfl]
        apply firstSome_isSome ha
        obtain ⟨body, hb⟩ := Option.isSome_iff_exists.mp ihb
        obtain ⟨src, hs⟩ := Option.isSome_iff_exists.mp ihs
        simp [hb, hs]

end NCA
