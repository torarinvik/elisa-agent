# 6. Algorithms of the handwritten-arithmetic pipeline

**Symbol fusion.** With operator
distribution `q` over `{+, −, ×, none}` and digit distribution `p`:
`P(op) = q_op`, `P(d) = q_none · p_d`. The result is a probability
distribution over the 13 symbols whenever `p` and `q` are.

**MAP parsing.** The grammar `digit (op digit)*` fixes the
class of each position. Under independent per-position distributions the
probability of a token string factorizes, so the most probable well-formed
expression is the per-position argmax restricted to the position's class.
Even-length sequences have no parse.

**Evaluation** (`Evaluator`). `×` binds tighter than `+` and `−`; terms are
accumulated left to right.

**Comparison chains.** `a₀ r₁ a₁ … rₖ aₖ` is true iff
every adjacent relation `aᵢ₋₁ rᵢ aᵢ` holds.

[Theory index](../THEORY.md)
