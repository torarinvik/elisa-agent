# 2. Planning

`plan lib avail n t` searches
backward from the goal with depth bound `n`:

1. If `t ∈ avail`, return `given t`.
2. Otherwise try contracts in installation order; the first `c` with
   `c.output = t` whose inputs are all plannable at depth `n - 1` wins.
3. Otherwise, if `t = seq e`, try each candidate element type `a` (elements of
   sequence types that are available or produced by some contract, in that
   order); succeed when `e` is plannable from `[a]` and `seq a` from `avail`.

**Derivability** `Derivable lib avail n t` is the specification: a composition
of depth at most `n` exists (for `map`, with `a` a candidate element type).

**Theorem 2.1 (soundness).** `plan lib avail n t = some p` implies
`WellTyped lib avail p t`.

**Theorem 2.2 (completeness).** `Derivable lib avail n t` implies
`plan lib avail n t` succeeds.

The depth-bounded search above is used at increasing bounds from `1` to `n`.
The first success has the smallest successful depth bound, with installation
order breaking ties within that bound. This changes which valid route is
selected but preserves soundness and completeness at the maximum bound.

**Type checking.** `infer lib avail p`
computes the type a plan produces: `given t` needs `t ∈ avail`; `apply c ps`
needs `c ∈ lib` and the argument types to equal `c.inputs`; `map a body src`
needs `body` to type-check under `[a]` and `src` to produce `seq a`.

**Theorem 2.3 (decidability).** `infer lib avail p = some t ↔
WellTyped lib avail p t`. Plans not produced by the planner, such as
hand-written pipelines and proposed upgrades, are admitted by checking.

## 2.1 Polymorphic contracts

With polymorphic contracts (§1.2), a library stands for the set of all
instances of its contracts, and a plan applies instances. Typing is as in
§1 with `c ∈ lib` read as "`c` is an instance of a contract in `lib`".

That set is infinite, so planning must choose instances. A contract is
**range-restricted** when every variable of its inputs (and of its slots)
also occurs in its output.

**Theorem 2.4 (instances are determined by their output).** Let `c` be
range-restricted. If `σ(c.output) = τ(c.output)`, then `σ(c) = τ(c)`.

So for a ground goal `t`, a range-restricted contract has at most one
instance producing `t`. That instance is found by **matching** `c.output`
against `t`, which binds each variable of `c.output` to the subterm at its
position, or fails. Backward chaining needs no search over instances. At
each goal it considers, for every contract, the single matching instance or
none. Planning with range-restricted contracts is planning with the finite
library of these instances, so Theorems 2.1–2.3 apply to it unchanged.

Range restriction excludes contracts such as `seq(α) → length`, whose input
variables cannot be read off the goal. Instantiating those needs a choice of
type that the goal does not determine. §2.2 makes that choice.

## 2.2 Free variables and pattern goals

A variable of a contract's inputs that does not occur in its output is
**free**. After matching the output against the goal, the free variables
remain, and the inputs become **pattern goals**: types with variables, any
instance of which will do. The free variables are determined by the plans
found for the inputs, not by the goal.

A pattern goal `P` is solved by the same backward search, with
**unification** in place of matching. A unifier of two terms is a
substitution that makes them equal. The candidates for `P` are:

1. an available type `t` that `P` matches;
2. a contract `c`, its variables renamed apart from `P`'s, whose output
   unifies with `P`, with its inputs solved in turn as pattern goals; each
   input's solution extends the substitution before the next input is solved;
3. a `map` whose body solves the element pattern, when `P = seq(Q)`.

The search keeps every alternative open: when a later input has no solution
under the substitution an earlier one produced, it backtracks to the earlier
input's next solution. A solution is accepted only if it determines every
variable it involves, so the type it produces is ground. A candidate that
leaves a variable undetermined is **ambiguous** and is skipped: the plan
would not say which type to produce. For example, `nothing: → seq(α)` cannot
be planned on its own, but it can be planned under a consumer whose goal
fixes `α`.

**Map sources.** With polymorphic contracts, the candidate element types of
step 3 include the elements of the sequence types that instances produce, of
which there may be infinitely many. Every non-sequence element whose
sequence is derivable lies in the closure of Theorem 12.20, so the search
tries the elements of that closure after the enumerated candidates. When the
closure admits every type, it solves the pattern goal `seq(α)` instead and
tries the ground elements of its solutions.

Most contracts cannot be candidates for a given pattern goal, for two
reasons:

- **Head mismatch.** Terms with different constructors at their roots, or the
  same constructor with different arities, have no unifier: substitution
  never changes a root constructor (Theorem 2.6). A goal `C(…)` needs only the contracts
  whose output's root is `C` with the same arity, or a variable. Contracts
  can be indexed by the root of their output.
- **Underivable inputs.** A contract with a ground input outside the forward
  closure of the available types (§12) has no plan, since its inputs cannot
  all be derived. Only contracts that fire in that closure can be candidates,
  and the closure records which ones fire.

**Theorem 2.6 (head mismatch).** If `C ≠ D`, or `n ≠ k`, then
`σ(C(t₁, …, tₙ)) ≠ τ(D(u₁, …, u_k))` for all substitutions `σ` and `τ`.

Restricting candidates by both conditions never discards a solution. With
both, a pattern goal visits only contracts that can still contribute to it.

The answer is the plan built over types with variables, with the final
substitution applied. Write `c ≼ lib` when `c = τ(d)` for a contract `d` in
`lib` and some substitution `τ`.

**Theorem 2.5 (answers are instances).** Instances of instances are
instances: `σ(τ(d)) = (σ ∘ τ)(d)`. Hence if a plan is well-typed over
contracts `c ≼ lib` producing `t`, then with an answer substitution `σ`
applied, it is well-typed over contracts `σ(c) ≼ lib` producing `σ(t)`.

The first part is proved by induction on terms; the second combines it with
Theorem 1.2. So pattern search is sound however its unifiers are computed.
Its completeness, that a pattern goal with an instance plannable within
depth `n` is solved within depth `n`, rests on unification returning *most
general* unifiers, through which every other solution factors.

A substitution `σ` is a **most general unifier** of a finite list of
equations `E` if it unifies every equation, and every unifier `τ` of `E`
satisfies `τ = τ ∘ σ`: applying `σ` first loses nothing that `τ` needs.

**Theorem 2.7 (most general unifiers).** If a finite list of equations has a
unifier, it has a most general one.

The proof follows the unification algorithm, by induction on the number of
distinct variables in `E` and then on the total size of its terms:

- `x = x` is dropped, which reduces the size.
- `C(s₁, …, sₙ) = C(t₁, …, tₙ)` is replaced by the equations `sᵢ = tᵢ`, which
  reduces the size and keeps the variables. Different roots have no unifier
  (Theorem 2.6).
- `x = t` with `x` occurring in `t ≠ x` has no unifier: any instance of `t`
  is strictly larger than the same instance of `x`. This is the occurs check.
- Otherwise `x = t`, or `t = x`, eliminates `x`: substitute `ρ = [x ↦ t]` into
  the other equations. Their unifiers are exactly the unifiers of the original
  list, restricted through `ρ`, and `x` no longer occurs, so the number of
  variables drops. If `σ'` is most general for the rest, `σ' ∘ ρ` is most
  general for the whole.

The unification procedure follows these steps one by one, so it returns a
most general unifier whenever any unifier exists.

**Completeness of pattern search.** Fix the *skeleton* of a plan: which
contract or available type sits at each node, without the types. Rename the
variables of the contract at each node apart, by tagging them with the node.
The skeleton then produces an instance of the goal `P` exactly when one
finite list of equations has a solution: at every node, the node's output
equals the pattern its parent asks for. A `map` node asks its body for a
fresh variable and its source for the sequence of its element. A ground plan
whose skeleton is this one gives such a solution, namely its own
instantiation of every node. Variables are renamed apart by the node's path
in the skeleton, into a set disjoint from the goal's.

**Theorem 2.9 (skeleton equations).** Let `s` be a skeleton over installed
contracts and ground available types.

1. Every solution `σ` of the equations of `s` for `P` types `s`: with each
   node's contract instantiated by `σ`, `s` is a plan over instances of
   installed contracts producing `σ(P)`.
2. If a ground plan over ground instances of installed contracts produces an
   instance `θ₀(P)`, then it is the plan of its own skeleton at a solution of
   that skeleton's equations for `P`, one agreeing with `θ₀` on `P`.
3. If the equations of `s` for `P` have a solution, their most general
   unifier `θ` types `s`, and the plan of every solution `σ` is `σ` applied
   to the plan at `θ`.

Part 2 builds the solution node by node: each node's own instantiation is
placed on its renamed variables, which no other node uses. Part 3 combines
part 1 with Theorem 2.7 and the defining property `σ = σ ∘ θ`.

Pattern search does not solve that list at once. It solves the equations
node by node, in search order, applying each node's most general unifier to
the equations that follow.

**Theorem 2.8 (sequential unification).** Let `θ₁` be a most general unifier
of `E₁`.

1. If `E₁ ++ E₂` has a unifier `τ`, then `τ` unifies `θ₁(E₂)`.
2. If `θ₂` is a most general unifier of `θ₁(E₂)`, then `θ₂ ∘ θ₁` is a most
   general unifier of `E₁ ++ E₂`.

**Theorem 2.10 (solving block by block).** Split a list of equations into
blocks, and solve them in order, each with the substitution found so far
applied, most generally, composing the results. If the whole list has a
solution, this never fails, and it ends with a most general unifier of the
whole list.

This is Theorem 2.8 by induction over the blocks, with Theorem 2.7 for each
block. With one block per node, the sequential solution never fails while
the equations still have a solution. When it finishes, it is a most general
unifier of the whole list, which exists by Theorem 2.7. So for every skeleton
of depth at most `n`, pattern search finds the most general typing of that
skeleton, and every ground instance of the skeleton's result factors through
it. Pattern search backtracks over every skeleton within the depth bound, so
it solves every pattern goal that has a plannable instance. The answer it
returns is most general for the skeleton it settles on, though not
necessarily over all skeletons. If that typing leaves a variable
undetermined, the skeleton is ambiguous and the search goes on to the next.

[Theory index](../THEORY.md)
