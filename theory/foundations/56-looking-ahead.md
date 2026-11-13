# 56. Looking ahead

A learner of 53 or 54 judges an action in the situation before it. What the action leads to is not in that
situation. This chapter carries a choice forward through what follows an action, and states what that does and
does not rule out.

## 56.1 Model

Let `follow : S → A → S` give the situation after an action and let `R ⊆ S × A` be the pairs **ruled out**. An
action is open at `s` when `(s, a) ∉ R`. A situation **lasts** `0` steps always, and lasts `d + 1` steps when some
action open at it leads to a situation that lasts `d` steps. An action lasts `d + 1` steps at `s` when it is open
there and what follows it lasts `d` steps. The choice is made among the actions that last longest, up to a depth
`D`; among those the learner chooses as before.

What follows an action is the contributor's: an exact rule, or a learned one that declines where it has no support
(46.2). Where it declines, the action is taken to last the whole depth, so nothing unknown is held against it.

## 56.2 What is ruled out

**Proposition 56.1 (lasting longer is lasting shorter).** A situation that lasts `d + 1` steps lasts `d` steps.

By induction on `d`: the action that witnesses `d + 1` leads to a situation lasting `d`, hence `d − 1`.

**Proposition 56.2 (ruling out less rules out no path).** If `R ⊆ R'`, a situation that lasts `d` steps under `R'`
lasts `d` steps under `R`.

The same actions witness it. So let `R*` be the pairs that truly fail. If everything ruled out truly fails,
`R ⊆ R*`, then every action from which `d` steps without failure exist lasts `d` steps: looking ahead never sets
aside an action that could have been carried through. It sets aside an action only when every way on from it meets
a pair ruled out within the depth.

## 56.3 Which pairs to rule out

The proposition needs `R ⊆ R*`. A takeover does not supply that. A teacher takes over when they prefer another
action, so an action judged bad has not thereby failed, and where every open action is judged bad nothing lasts and
looking ahead decides nothing. An end that the situation itself shows, as an episode that stops, is a failure
whoever judges it. Ruling out those pairs alone satisfies the proposition, and what it then avoids is ends, not
objections.

## 56.4 Cost and what is not covered

With at most `b` actions open the search reads at most `b^D` situations for each action. An end further off than
`D` is not seen. Chance in what follows is not treated: `follow` gives one situation. Nothing here learns `follow`,
or learns which pairs fail short of an end; a learner that predicted the teacher's own objection a step ahead would
need the second.
