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
type that the goal does not determine.

[Theory index](../THEORY.md)
