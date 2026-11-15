# 61. How many experts, and how large

Chapter 44 counts the trials of a search over a library, and chapter 45 shows that stages found in order add
where found jointly they multiply. This chapter asks what those leave open: given many tasks, which parts
should be experts of their own, how large an expert should be, and how many there should be.

## 61.1 What is counted

A **part** is something a task needs that can be told apart from the rest of what it needs. Its **length**
`l` is the base-two logarithm of how many behaviours it is one of, so a learner that is told one bit by each
example needs `l` examples for it, and a search by trial up to `2 ^ l` trials. An **expert** is one or more
parts held once in a library of `n` experts. A user names an expert by its **address**, `a = log2 n` bits
where nothing ranks the experts, and less under a prior (45.1). A task is a **route** of `k` experts.

## 61.2 What is worth sharing

A part used by `m` tasks and held apart by each costs `m * l`. Held once and named by each it costs
`l + m * a`. The saving is `(m - 1) * l - m * a`.

**Proposition 61.1 (a shared expert pays).** For `m ≥ 2` and `l > 2 * a`, `l + m * a < m * l`. With one user
nothing is saved.

So an expert must hold more than its address, more than twice it suffices from the second user on, and a
part with one user belongs to that user. Parts with the same users make one expert: named once where they
would be named apart, they cost `a` less for each user and part. Parts with different users are kept apart,
since a user of one would otherwise be handed the other (44.7 taxes it in search).

The address depends on how many experts are kept, and what is kept on the address. Dropping an expert
lowers the address and never turns another's saving negative, so dropping until none is dropped ends in a
library every expert of which pays.

## 61.3 How large

Sharing alone would gather without limit. What bounds an expert from above is finding it. Let a task hold
`c` bits in `k` experts of `l` bits each, `c ≤ l * k`, each expert found by trial from its own examples
(45.7), and the route found by trial among `n ^ k = 2 ^ (a * k)`. The trials are `k * 2 ^ l + 2 ^ (a * k)`.

**Proposition 61.2 (the larger search).** `a * c ≤ max(l, a * k) ^ 2`, with equality where `l = a * k`
and `c = l * k`.

Neither search can be brought below `2 ^ √(a c)` without raising the other above it. At the balance an
expert holds `√(a c)` bits and a route has `√(c / a)` experts: the size is the geometric mean of what the
task holds and what a name costs. Larger experts are dearer to find than their route, and smaller ones leave
the route the dearer.

Two assumptions carry this, and either can be lifted. Experts found otherwise than by trial, at a cost
`f(l)` below `2 ^ l`, balance where `f(l) = n ^ k`, which is at a larger `l`: the cheaper an expert is to
learn, the larger it should be. And a route found under a prior or by types costs less than `n ^ k`, which
moves the balance to smaller experts. Without examples of its own a stage is not found alone (45.7), and
the route's experts multiply.

## 61.4 How many

**Proposition 61.3 (routes tell tasks apart).** Tasks with different routes of `k` experts among `n` number
at most `n ^ k`.

So `t` tasks need `a * k ≥ log2 t`, and a task whose experts are all held is learned from the `a * k` bits
of its route, not from the `c` bits it holds. With `n` fixed that is the gain of a library, and it grows with
the tasks: over `t` tasks the cost is `n * l + t * a * k` against `t * c` apart.

The number of experts is then not chosen but read off the tasks: one for each set of users that two or more
parts of sufficient length share (61.2), divided where 61.3 finds one too large to find, and each task
keeping what it alone uses.

In Lean 61.1 is `NCA.shared_expert_pays` with `NCA.expert_used_once_saves_nothing`, 61.2
`NCA.larger_search_bounded_below` with `NCA.balanced_search_attains`, and 61.3
`NCA.tasks_told_apart_by_routes`.
