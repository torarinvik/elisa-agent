# 65. Experiments that tell rules apart

A learner may be shown a thing whose behaviour follows a hidden rule, be allowed tests that cost, and be
asked afterwards what the thing does where it was not tested. This chapter treats how few tests serve,
when the rules that could hold are known as a set.

## 65.1 Model

A **test** `x` is drawn from a set `X`, and a **rule** `h` gives each test an **outcome** `h(x)` from a
set of `b` outcomes. The learner holds a list of rules, the **rules that could hold**, and the rule
that does hold, the **true rule**, is among them. After a test `x` shows the outcome `o`, the learner
keeps the rules with `h(x) = o`: the list is **narrowed** by the test.

Where the list comes from is outside the model. It may be given, or counted from experience: the rules
met when every test could be made. A rule never met is then not in the list, and the assumption that
the true rule is among them can fail; section 65.4 says what follows.

## 65.2 Narrowing is sound

**Proposition 65.1 (the true rule is kept).** If the true rule is in the list, it is in the list
narrowed by any test.

**Proposition 65.2 (one rule left).** If the list narrowed by a test holds one rule, that rule is the
true rule.

So a learner may answer for every test it did not make as soon as one rule is left, with no chance of
error under the model, however few tests that took.

## 65.3 How few tests

A test splits the list into at most `b` parts, one for each outcome, and the learner is left with the
part of the outcome shown. Whatever the test, some part holds at least a `b`-th of the list, so in the
worst case a test leaves at least a `b`-th.

**Proposition 65.3 (tests needed).** If `r j` rules are left after `j` tests and each test can leave a
`b`-th, that is `r j ≤ b · r (j+1)`, then `r 0 ≤ b^k · r k`. To come from `n` rules to one in `k` tests
in the worst case therefore needs `n ≤ b^k`.

The bound is met by a test whose parts are equal. A learner cannot always find one, and the choice
made here is the nearest: the test whose largest part is smallest. It is the choice that minimises
what is left in the worst case after one test; it is not shown to be the best over several tests.

A consequence for a task that pays only under a budget of tests: with `n` rules and `b` outcomes no
learner can stay under `k` tests in every case when `n > b^k`, so what a budget asks for is a small
list of rules, and counting the rules that occur, instead of holding every rule that could be
written, is what makes a small budget reachable.

## 65.4 A rule that was never met

If the true rule is not in the list, the narrowed list may come to one wrong rule, or to none. The
second is seen at once, and the learner then knows the list is short. The first is not seen from the
tests made. It is seen only if answers are judged; a learner whose answers are judged can take a wrong
judgement, after narrowing to one rule, as a sign that the list is short, and spend tests to learn the
rule that held. Nothing here bounds how often that happens: it is the share of what occurs that the
count has not yet met.
