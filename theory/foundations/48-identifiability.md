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

## 48.3 Bounded proposals from paired shapes

Suppose a training representation contains two input shapes, one obtained by
inserting a contiguous block into the other, together with their complete
output templates. First rename the shorter template's position references into
the longer input's coordinate system. A common prefix and suffix of the two
templates delimit a finite replacement that exactly reconstructs the longer
template on that training pair. Express position references in the replacement
relative to the insertion site, and associate the replacement with the block
and its immediate input context. Multiple independent shape pairs can support
the same proposal; support is a selection criterion, not an error bound.
The current implementation screens against the selected representative template
for each training shape, not against every original example separately.

For a new shape, a bounded proposer can try every supported single-block
reduction to a known shape and every matching replacement. It may return a
candidate only when the completed derivations it considered agree, and must
refuse when search was truncated or matching derivations disagree. That policy
is sound for the declared candidate set only under the completeness and
realizability assumptions of §48.1. A shared but wrong inductive bias can make
all proposals agree incorrectly, so the unchanged fresh whole-expert gate is
still required. Prefix/suffix matching, coordinate renaming, support and search
budgets are implementation choices, not discovered semantic laws; there is no
claim that this grammar can represent arbitrary transformations.

## 48.4 What agreement did and did not establish

In one previously inspected development split, the paired-shape proposer
converted 38 refusals into correct answers and one into a wrong answer, without
changing previous predictions. The wrong answer is a direct counterexample to
treating agreement among the retained rewrites as proof of the true output.
The theorem in §48.1 is conditional on the true procedure being among the
admissible candidates; support thresholds and screening on chosen training
templates cannot establish that condition. Whole-expert certification and
independent evaluation remain necessary.

## 48.5 Backing off input context

An insertion's immediate input neighbors define a narrow evidence group. A
broader group can ignore either or both neighbors, while retaining the inserted
block. Every narrow-group example also belongs to each corresponding broader
group, but support for a rule and absence of observed contradiction in that
group do not imply that it is true outside the examples. Contradiction screening
must be repeated on the broader group; merely copying a narrowly screened rule
to a broader context loses that property.

A selective fallback can first examine the original narrow group, preserving
its answer or refusal whenever it produced at least one derivation. Only if it
produced none does the learner examine all applicable broader groups together,
returning a result if their completed derivations agree and refusing otherwise.
This preserves earlier answered cases by construction, provided the underlying
template model and exact-context rules are unchanged. It does not preserve
earlier refusals, identify the true rule, or certify the wider hypothesis
family; the impossibility theorem in §48.1 still applies. Limits on input
length, rule counts and candidate execution remain caller responsibilities.

## 48.6 Observed tradeoff of broader context

On the inspected development split, separately screened broader contexts
produced eight additional correct answers and three additional wrong answers;
previous answers did not change. This demonstrates both the opportunity from
sharing evidence across contexts and the limit of finite screening: an
uncontradicted, unanimous candidate can still be wrong outside its supporting
examples. The result does not identify the true transformation family or
establish performance on an independent split.

## 48.7 Comparing learned proposals on new partitions

For two frozen proposals evaluated on the same cases, count a paired win when
the new proposal is correct and the old one is not, and a loss in the reverse
case. Their difference is exactly the change in the number of correct answers;
ties include cases where both are wrong or both refuse. Report wrong answers
and refusals separately, because an accuracy gain can coexist with additional
wrong answers. The paired sign statistic under independent, exchangeable
discordant cases has the binomial null described in §30; overlapping hash
partitions of a previously inspected dataset are not independent fresh samples
and do not by themselves justify a population significance claim.

Distinct public partition seeds can nevertheless test whether a development
improvement depends on a particular train/validation partition. Both versions
must be fit on the same training part and evaluated on the same unseen input
sentences, with the seed and source versions fixed in advance. Data used to
develop the mechanism remain development data even if a new partition is
chosen. Neither partition comparison replaces a fresh whole-expert gate or a
test on an untouched external distribution.

## 48.8 Precision of newly answered cases

In two further public-data partitions, exact-context composition corrected 57
and 44 cases while producing one and five new wrong answers. Broader-context
fallback corrected eight and seven additional cases, but also produced five and
seven additional wrong answers. The latter equality in one partition shows why
a gain in total correct answers alone is not an adequate measure of a proposal's
precision. In a whole-task gate both refusal and a wrong answer are failures;
outside that gate their practical consequences may differ.

These partitions share examples with each other and with earlier development,
so neither the observed differences nor a sign statistic establish independent
generalization. The observed backoff tradeoff motivates examining candidate
evidence and precision before any claim that wider context is an improvement
in reliability. The proof in §48.1 continues to require the true procedure to
be included in the compared family.

## 48.9 Screening against alternative observed templates

The current rewrite screen sees only the most frequent output template for
each input shape. If a shape has other observed templates, a rule may pass that
screen while contradicting another observed template. One conservative proposal
is to test every retained broad-context rule against every combination of
observed shorter- and longer-shape templates for each applicable shape pair.
An application is rejected if any result conflicts with the longer template;
the narrow-context path can remain unchanged. This is a finite contradiction
screen, not a statistical certificate or a proof of truth on unseen inputs.

The Cartesian check can reject a correct context-dependent rule: independently
observed templates need not be a compatible pair. It is therefore expected to
trade some coverage for precision. Removing candidates can also turn an
ambiguous proposal into a unanimous one, so outputs previously refused may
become wrong; it is not enough to assume that a smaller candidate set is safer.
The rule's training observations and pairing assumptions must be reported, and
whole-expert admission remains a fresh, independent step.

[Theory index](../../THEORY.md)
