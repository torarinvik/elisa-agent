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

[Theory index](../THEORY.md)
