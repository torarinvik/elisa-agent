# 48. Identifying composition from final answers

## 48.1 The observational ambiguity barrier

Let a learner see finitely many input/output pairs, and suppose two candidate
procedures both reproduce every observed answer but differ on a new input. Any
selective learner guaranteed correct for *both* candidates must refuse there:
either output would be wrong for one candidate
(`universally_sound_refuses_ambiguity`). The candidates may be compositional
programs, output transformations or arbitrary functions. This is a worst-case
statement, not a rate or a claim that all future inputs are ambiguous.

The existing finite version space implements this principle for its declared
family: it retains consistent predictors, returns a unanimous value and
refuses on disagreement. Its guarantee assumes the true predictor is in that
family, predictions terminate with faithful equality, and observations are
correct. A family missing a plausible procedure may appear unanimous and be
wrong. Fresh statistical certification is a separate, distributional guarantee;
neither agreement nor the theorem certifies an expert.

## 48.2 Implications for composition

An unseen input shape that can be reduced to a seen shape identifies a possible
decomposition, not an output transformation. Different procedures may agree
on all training examples while attaching, ordering, or substituting output
parts differently on the new input. Learning a transformation therefore needs
an explicitly declared, testable candidate space and evidence that separates
its alternatives, or an explicit refusal when those alternatives disagree.
Any queried final answers must be counted; subexpression labels cannot be
assumed to exist merely because a decomposition is possible.

On one already-inspected public development split, 147 of 167 template
refusals have a shape reducible to a known one by deleting one contiguous span.
That is an opportunity count, not an estimate that any particular composition
algorithm can correctly answer those cases. The 168 total failures among 2,378
cases would need at least 50 net corrections to fall below 5% on that fixed
split; a fresh gate samples a different distribution of cases and has its own
confidence and selection conditions. The inspected split is development data,
not evidence of generalization to sealed data.

[Theory index](../../THEORY.md)
