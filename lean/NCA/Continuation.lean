import Mathlib.Order.Basic

/-!
# Continuation requests

An expert that needs a sub-result mid-computation is a *program*: it either
returns, or asks the kernel a question and continues with the answer. Answers
come from the kernel's handler, which may fail (no route). Programs compose
by `bind`, so an expert can ask several questions in sequence.

The specification of each question is a relation `R q a` ("`a` is a correct
answer to `q`"). A program is `Safe` for a postcondition when it meets it
whatever correct answers it receives; with a handler that only returns correct
answers, every result of a safe program meets the postcondition. A program
with question depth at most `n` makes at most `n` requests on any run.
-/

namespace NCA

/-- A program asking questions `q : Q` with answers in `A q`. -/
inductive Prog (Q : Type) (A : Q → Type) (α : Type) where
  | pure : α → Prog Q A α
  | ask (q : Q) : (A q → Prog Q A α) → Prog Q A α

namespace Prog

variable {Q : Type} {A : Q → Type} {α β : Type}

/-- Continue with `f` after `p` returns. -/
def bind : Prog Q A α → (α → Prog Q A β) → Prog Q A β
  | pure a, f => f a
  | ask q k, f => ask q fun a => (k a).bind f

/-- Run against a handler; also returns the number of requests made. -/
def run (h : (q : Q) → Option (A q)) : Prog Q A α → Option (α × Nat)
  | pure a => some (a, 0)
  | ask q k => (h q).bind fun a => (run h (k a)).map fun r => (r.1, r.2 + 1)

/-- `p` meets `post` for every answer correct by `R`. -/
inductive Safe (R : (q : Q) → A q → Prop) (post : α → Prop) : Prog Q A α → Prop
  | pure {a : α} : post a → Safe R post (pure a)
  | ask {q : Q} {k : A q → Prog Q A α} : (∀ a, R q a → Safe R post (k a)) → Safe R post (ask q k)

/-- Question depth at most `n`. -/
inductive Depth : Nat → Prog Q A α → Prop
  | pure {n : Nat} {a : α} : Depth n (pure a)
  | ask {n : Nat} {q : Q} {k : A q → Prog Q A α} : (∀ a, Depth n (k a)) → Depth (n + 1) (ask q k)

/-- **Soundness.** A handler returning only correct answers makes every result
of a safe program meet its postcondition. -/
theorem Safe.run {R : (q : Q) → A q → Prop} {post : α → Prop} {h : (q : Q) → Option (A q)}
    (hh : ∀ q a, h q = some a → R q a) {p : Prog Q A α} (hp : Safe R post p)
    {x : α} {m : Nat} (hx : p.run h = some (x, m)) : post x := by
  induction hp generalizing m with
  | pure ha => simp [Prog.run] at hx; exact hx.1 ▸ ha
  | @ask q k _ ih =>
    simp only [Prog.run, Option.bind_eq_some_iff, Option.map_eq_some_iff] at hx
    obtain ⟨a, ha, r, hr, hrx⟩ := hx
    have : r = (x, m - 1) := by cases r; simp at hrx; obtain ⟨rfl, rfl⟩ := hrx; simp
    exact ih a (hh q a ha) (hr.trans (congrArg some this))

/-- **Composition.** `bind` is safe when the first program establishes what
the continuation needs. -/
theorem Safe.bind {R : (q : Q) → A q → Prop} {mid : α → Prop} {post : β → Prop}
    {p : Prog Q A α} {f : α → Prog Q A β} (hp : Safe R mid p) (hf : ∀ a, mid a → Safe R post (f a)) :
    Safe R post (p.bind f) := by
  induction hp with
  | pure ha => exact hf _ ha
  | ask _ ih => exact Safe.ask fun a ha => ih a ha

/-- **Request bound.** A program of depth `n` makes at most `n` requests. -/
theorem Depth.run_le {h : (q : Q) → Option (A q)} {n : Nat} {p : Prog Q A α} (hp : Depth n p)
    {x : α} {m : Nat} (hx : p.run h = some (x, m)) : m ≤ n := by
  induction hp generalizing m with
  | pure => simp [Prog.run] at hx; omega
  | @ask n q k _ ih =>
    simp only [Prog.run, Option.bind_eq_some_iff, Option.map_eq_some_iff] at hx
    obtain ⟨a, _, r, hr, hrx⟩ := hx
    cases r; simp at hrx; obtain ⟨rfl, rfl⟩ := hrx
    have := ih a hr; omega

theorem Depth.mono {n m : Nat} {p : Prog Q A α} (hp : Depth n p) (hnm : n ≤ m) : Depth m p := by
  induction hp generalizing m with
  | pure => exact Depth.pure
  | @ask n q k _ ih =>
    obtain ⟨m, rfl⟩ : ∃ m', m = m' + 1 := ⟨m - 1, by omega⟩
    exact Depth.ask fun a => ih a (by omega)

/-- **Depth of a sequence.** Depths add under `bind`. -/
theorem Depth.bind {n m : Nat} {p : Prog Q A α} {f : α → Prog Q A β} (hp : Depth n p)
    (hf : ∀ a, Depth m (f a)) : Depth (n + m) (p.bind f) := by
  induction hp with
  | pure => exact (hf _).mono (Nat.le_add_left m _)
  | @ask n q k _ ih => rw [Nat.add_right_comm]; exact Depth.ask ih

end Prog
end NCA
