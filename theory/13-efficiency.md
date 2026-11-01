# 13. Efficiency

**Goal.** Cost proportional to a task's dependency structure, not to the size
of the library or to all pairs of inputs. For local, compositional tasks that
means linear in input length and constant in library size; quadratic cost
should appear only in modules whose contracts require all-pairs interaction,
and only there.

**Cost model.** Each contract costs `κ(c)` per
invocation . On
sequences of length `L`:
`cost(given t) = 0`, `cost(apply c ps) = κ(c) + Σ cost(pᵢ)`,
`cost(map a body src) = L · cost(body) + cost(src)`.
Cost is additive by definition: a composition has no interaction term between
its modules.

| Theorem | Statement |
|---|---|
| 13.1 | `cost_L(p) ≤ (L + 1)^nest(p) · cost_1(p)`: polynomial degree is the map nesting depth |
| 13.2 | plans without nested maps cost at most `(L + 1) · cost_1(p)`: linear in length |
| 13.3 | installing modules never changes the cost of an existing route |

Together with Theorem 12.2 (§12), a task's cost and memory are
independent of library size.

**Minimum-cost planning**.
`planMin` keeps, at every type and depth, the cheapest candidate: a Bellman
recursion over the AND/OR structure of plans (a type needs *one* producer; a
producer needs *all* its inputs). *Searchable* plans are the well-typed plans
whose map elements are candidate element types, the space the planner
enumerates.

| Theorem | Statement |
|---|---|
| 13.4 | the returned plan is well-typed and its cost is the reported cost |
| 13.5 | it costs at most any searchable plan of smaller depth |

With memoization the recursion visits each `(available, type, depth)` once.
Minimizing total compute is polynomial; minimizing the number of *distinct*
experts (memory) is a set-cover problem and is handled as a constraint, not an
objective.

**Cost under an error target.** By the union bound
(§4) a route's error is at most the sum of its invocations' failure rates, so
error composes exactly like cost, with map bodies counted `L` times. The
planner keeps the Pareto frontier of non-dominated (cost, error) pairs at each
type; combining sub-goal frontiers and discarding dominated results yields the
exact frontier for two additive objectives, from which the cheapest route
within an error target is read off. Since error composes like cost, a plan's
error bound is `p.cost ε L` for per-invocation failure rates `ε`, and the
recursion is `planMin` with `best` replaced by dominance pruning
:

| Theorem | Statement |
|---|---|
| 13.6 | pruning dominated options loses nothing: every option is dominated by a survivor |
| 13.7 | every option is a well-typed plan with its reported cost and error bound |
| 13.8 | every searchable plan within the depth bound is dominated by a returned option |
| 13.9 | if a searchable plan meets error target `τ`, a returned option meets it at no greater cost |

**Length–accuracy coupling.** Every route's cost and error bound grow linearly
in `L`, so the cheapest expert meeting a fixed target changes with length, and
beyond some length no route meets it. The planner reports infeasibility
rather than silently degrading. Keeping error constant as inputs grow
requires per-glyph failure rates falling as `1/L`, or redundancy and
refinement (sub-goal requests) spent where uncertainty is high.

**Comparison with attention.** A transformer over `T` tokens of width `d` with
`ℓ` layers costs about `ℓ(24Td² + 4T²d)` floating-point operations; the
quadratic term dominates once `T > 6d`. At glyph granularity and moderate
lengths the linear term dominates and costs are comparable; at
image-patch granularity the quadratic term dominates and cost grows
superlinearly. The modular pipeline's cost is proved linear at every length.

[Theory index](../THEORY.md)
