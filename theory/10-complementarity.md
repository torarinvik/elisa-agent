# 10. Complementarity

The mixed task `a op b rel c` requires arithmetic and comparison together.
Systems are compared by the composition gain
`G = Q(A⊕B) − max(Q(A), Q(B), Q(A+B), Q(baselines))` on held-out inputs, where
`A⊕B` adds integration modules to the installed capabilities and the
baselines are the majority class and a monolithic model trained on the task.

**Product-of-experts fusion.** With operator distribution
`q`, relation distribution `r` (each including a "none of mine" outcome) and
digit distribution `p`: `P(op) ∝ q_op r_none`, `P(rel) ∝ r_rel q_none`,
`P(d) ∝ q_none r_none p_d`. This treats the two recognizers as independent
evidence; unlike the two-recognizer fuser it is an assumption, not an
identity.

**Constrained MAP parsing.** Grammar
`digit ((op | rel) digit)*` with at least one relation. Under independent
per-position distributions the unconstrained MAP takes each position's best
symbol of its class. If it contains no relation, the constrained MAP differs
from it in exactly one odd position, switched to its best relation; choosing
the position maximizing `P(rel) / P(op)` minimizes the loss in probability,
so the result is the exact constrained MAP.

**Same goal type, different task.** Comparison and mixed both produce
`bool.v1` from the same image type, so after installing the integration
modules stable routing keeps the comparison route for `bool.v1` (it was
installed first). The integration route subsumes it: comparison chains are
relational expressions without operators. It is adopted through the upgrade
rule of §8, on a validation suite drawn from both boolean tasks. This shows
a limit of the type system: the task a goal stands for is not determined by
its type alone, and choosing between routes for one type is an empirical
decision.

[Theory index](../THEORY.md)
