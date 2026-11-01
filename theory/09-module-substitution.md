# 9. Module substitution

Plans refer to modules only through contracts, so replacing a module by one
with an identical contract leaves every
plan's shape and type unchanged; `infer` confirms the substituted route still
type-checks. Behavior is what changes.

Let `disagree i` be the event that invocation `i` of the substitute gives a
different decision than the original's, with in-situ probability at most `dᵢ`,
and suppose the answer can change only if some such invocation disagrees.

**Theorem 9.1.** `P(answer changes) ≤ Σᵢ dᵢ`.

**Theorem 9.2.** If original-correct and unchanged imply
substitute-correct, then `P(correct) ≤ P(correct′) + P(answer changes)`.

**Theorem 9.3.** Hence
`P(correct′) ≥ P(correct) − Σᵢ dᵢ`.

The bound is only as tight as the choice of events. Every invocation of the
substitute is a valid event set, but the arithmetic parser reads digit
distributions only at even positions and only through their argmax, so the
answer changes only if an even-position invocation's argmax disagrees.
Restricting `disagree` to those invocations keeps the hypothesis true and
removes the substitute's (irrelevant) disagreements on operator glyphs.
Choosing the smallest event set that still covers every way the output can
change is how a composition's structure tightens its guarantees.

[Theory index](../THEORY.md)
