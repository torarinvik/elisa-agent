# 76. Putting out or thinking on

A learner that acts in time has two things to settle at each step: what to do, and whether to do
it now. Chapter 16 treats an answer withheld where a reading is unsure. This chapter treats the
second question as a weighing of two risks, states what the plain rule earns at one step and
over a trial, what misread risks cost, why a learner under the rule cannot rest in doing
nothing, and what it costs to ask several readings in turn, and what an asking of the kernel is worth. It
gives hypotheses, chances and risks no meaning.

## 76.1 Model

At a step there are **hypotheses**, each something that could be done now, and for each a
**chance** that doing it now is right. The **best** hypothesis is one of the largest chance. The
**risk of putting out now** is the chance that the best hypothesis, taken now, is wrong; where
nothing else reads it, it is one less the best chance. The **risk of going on** is the chance
that the trial ends badly if nothing is put out at this step. The **rule** takes the best
hypothesis where its chance reaches a threshold `τ_p` and the risk of going on is at least a
threshold `τ_r` times the risk of putting out now, and otherwise goes on.

The architecture diagram also prints a selectable upper bound on the quotient of waiting risk
and acting risk. For positive acting risk this alternative takes the best hypothesis when its
chance reaches `τ_p` and waiting risk is at most `τ_r` times acting risk. The runtime treats the
quotient as infinite when acting risk is zero. The propositions below concern the lower bound.

**Proposition 76.1 (the rule takes the smaller risk).** With `τ_p = 0` and `τ_r = 1` the rule
risks the smaller of the two risks, and putting out with any chance at the step risks at least
that.

One number says where the risk lies: the share of the two risks that is in putting out now,
nought where all the risk is in going on and one where all of it is in putting out. The rule
puts out exactly where that share is at most `1 / (1 + τ_r)`, a half for `τ_r = 1`. The share
decides; it is not what is learned, since nothing that happens has it as its chance, while each
risk is the chance of something that does.

## 76.2 Risks that are misread, and other thresholds

**Proposition 76.2 (what misreading costs).** If each risk is read within `e` of what it is,
the rule applied to the readings risks at most `2e` more than the smaller risk. With the risks
exact and a threshold `τ_r ≤ 1`, it risks at most the smaller risk and `(1 − τ_r)` times the
risk of putting out now.

So the rule is as good as its two readings are near, and no better. A threshold on the chance
adds nothing where the risks are exact; it is a guard for where they are not. A learner whose
two risks are each read from few lessons loses by the rule what it would not lose by a reading
it holds more surely, which is measured.

## 76.3 A trial of several steps

A trial is a run of steps. Putting out at a step ends the trial, paid with a chance of that
step; where nothing is ever put out the trial ends unpaid. A **way of putting out** gives each
step a chance of putting out there. What it is paid is the read of 75.1 with the steps, soonest
first, as its items: the chance of putting out as the chance of a match and the chance of the
step as the value. The chance that the trial ends paid if nothing is put out at a step is what
the way of putting out is paid over the steps after it, and one less it is the risk of going on.

**Proposition 76.3 (the best of the steps left).** No way of putting out is paid more often
than the largest chance of a step. Putting out at each step whose chance is at least the largest
chance of a later step, and going on otherwise, is paid that often.

## 76.4 Why it does not rest in doing nothing

**Proposition 76.4 (never putting out is unpaid; putting out more pays).** A way of putting out
that never puts out is paid nought. Raising the chance of putting out at a step whose chance is
at least what going on from it is paid does not lower what the way is paid, whatever is done at
the steps before.

Under a way that goes on everywhere, going on is paid nought at every step, so the rule puts
out at every step whose chance is above nought. A learner that reads the risk of going on from
how its own trials ended therefore leaves doing nothing as soon as it has seen such trials end
unpaid. A share given to doing nothing among the hypotheses holds no such correction: it is
only what the others leave, and it can pass the largest of them while they together hold more.

## 76.5 Concepts asked in turn

A **concept** is whatever gives, at a cost, an opinion of the step: chances for hypotheses, and
where it reads them the two risks. Concepts are asked in an order, and after each the rule is
applied to what has been said; the first time it takes a hypothesis no later concept is asked.

**Proposition 76.5 (asking in turn costs no more).** Where each concept is asked only if no
earlier one settled the step, the cost of thinking is the sum of each concept's cost times the
chance that it is reached, which is at most the cost of asking all.

So concepts are ordered cheaper first, and a dear one is paid for only at the steps the cheap
ones leave open. What is given up is what the later concepts would have said where an earlier
one was sure and wrong; that is the risk of putting out now, and is bounded by 76.2 as far as
that risk is read truly.

## 76.6 The scratchpad, and asking the kernel

What a concept works out at a step it may leave as a **note**, under a name, for the concepts
after it and for later steps. A note given a life of `l` steps and written at step `i` is read
at step `n` exactly when `i ≤ n < i + l`, as an entry of a channel of capacity `l` is (64.1); a
note with no life stays until it is written again or dropped. A note written again takes the
place of the one before, so what is worked out once at a step is read by every later concept at
no further cost, and a thought may be refined within a step.

A hypothesis may be an **asking of the kernel** (§20): produce a value of a type from these
inputs. Taken, it is not put out: the kernel serves it within the step, the answer is noted
under the type asked for, and the concepts are asked again from the first. At most `r` askings
are served at a step, so with `n` concepts thinking at a step asks a concept at most
`(r + 1) n` times. What the kernel guarantees of a request it guarantees of an asking: the route
is well typed, and a refusal for lack of budget is no value and never a wrong one.

## 76.7 What is assumed and what is left open

Assumed. That putting out ends the trial; where an output is passed over, putting out and going
on are paid alike there and the rule's tie puts out. That a trial in which nothing is put out
ends unpaid. That the chances and risks are what they are said to be: a learner has them only
as readings taught on its own trials, gathered under a way of putting out that was itself
changing, and how near they come is measured. That a concept's opinion does not turn on which
later concepts will be asked.

Left open. Thresholds that follow what was paid, and what they should follow. A risk of going
on that counts what thinking itself costs in time. A concept that knows no later one could
change the step, and how it may know. Steps paid in amounts and not by a chance.

## 76.8 A chance of its own for each hypothesis

The rule of 76.1 asks of a hypothesis only the chance that taking it now is right. Let the
chances instead be shares of one whole: amounts a_i > 0, the share of i being a_i over their
sum S, with going on counted among the hypotheses. A lesson is given only on the hypothesis that
was taken. Lower one amount by d, 0 < d < S, and leave the others: every other share goes from
a_j / S to a_j / (S - d), which is larger, and all of them by the one factor S / (S - d). So
what a hypothesis loses by a lesson is given to the others as they stand, to one that was never
judged as much as to one that was. Where going on is seldom or never judged, its share is then
made by what the ports were paid and says nothing of what going on is worth; where every port
taken has been unpaid, it holds nearly the whole, the rule puts nothing out, and no further
lesson comes.

Hence each hypothesis is given a chance of its own, taught on that hypothesis alone, and going
on is not a hypothesis among them: its worth is the risk of going on, read and taught apart
(76.1, 76.3). Chances of their own need not sum to one, and 76.1 to 76.5 ask nowhere that they
do.

## 76.9 What the risk of going on is taught by

By 76.3 going on at a step is worth the best chance of the steps left. A learner has those
chances only as readings. Let each trial give two readings x and y of later steps. Over any
trials the sum of the larger of the two is at least the larger of the two sums,

    max(Σ x, Σ y) ≤ Σ max(x, y),

with equality only where one reading is the larger in every trial. So where the later steps of
a trial are readings of one and the same chance, as in a world that stands still, the largest
of them overrates it, the more so the more steps are read, and a learner taught so holds going
on above its best hypothesis and waits. The reading at one named step does not: the step at
which the rule itself next put out. Where the rule put nothing out again, what going on came to
is how the trial ended, which is no reading at all.

## 76.10 A dearer concept, asked where the cheaper is unsure

Let two concepts be asked in turn, the cheaper at cost k and the dearer at cost K ≥ 0, and let
the cheaper give its best hypothesis the chance c. Two thresholds, b ≤ a, say where the cheaper
is taken at its word: at c ≥ a its best hypothesis is held to the rule of 76.1 with no more
asked, at c ≤ b the step is settled and nothing is put out, and between them the dearer concept
is asked. If that happens at a share q of the steps, a step costs k + qK, which is at most k + K
(76.5).

What the saving can lose is bounded on both sides. Where c ≥ a, no concept can give a
hypothesis a chance above one, so not asking loses at most 1 - a. Where every one of m
hypotheses has at most b, the chance that any of them is paid is at most the sum of their
chances, hence at most mb; that is all a concept that saw everything could have had there. Both
bounds take the cheaper concept's chances to be true chances given what it reads (76.2 says what
a reading that is off costs). So thresholds near one and nought lose little and save the dearer
concept wherever the cheaper is sure either way; a task in which the cheaper is sure at every
step never pays for the dearer one.

A hypothesis that is taken and judged not at once but by what it leads to is worth, by 76.3,
the best chance of the steps left; its lesson is that worth, read as 76.9 says: at the next
step at which the rule itself put out, by whichever concept was had there, or how the trial
ended where there was none.

## 76.11 A step of going on charged a share

By 76.3 and 76.9 going on at a step is taught to be worth the chance at the step where the rule
next puts out. Where going on shows nothing new, that chance is the chance of putting out now,
and the rule of 76.1 is left to a tie between two readings of one thing: which way it falls is
their noise, and a learner whose readings are honest waits about as often as not, for nothing.
Going on is not free: the world may change and time runs out. Let a step of going on be taken
to lose a share δ of what is to be had, with 0 < δ ≤ 1, so that going on for n steps to a step
worth v is worth (1 - δ)ⁿ v.

**Proposition 76.11 (a tie puts out, and the charge costs little).** Where the later step is
worth what now is worth, c > 0, going on for any n ≥ 1 steps is worth less than c, so the rule
puts out. And where the rule puts out now with chance c because (1 - δ)ⁿ v ≤ c, it gives up at
most v - c ≤ n δ v: a share δ of the later worth for each step it did not wait.

So the charge decides the ties and is paid only where waiting would have gained less than the
charge. Where waiting gains much, as before a question is asked, (1 - δ)ⁿ v stays far above the
chance of putting out now and the rule goes on as it did.

## 76.12 Going on held to what the last concept says

The chance of going on is read by the first concept, before the dearer ones are asked, and by
76.3 it is taught what the rule's next putting out was held to be worth. Read so, it is what
going on is worth over the steps that look alike to the first concept, and a dearer concept
tells those steps apart: where it gives its best hypothesis less than they are worth on the
whole, the rule of 76.1 waits. Where going on shows nothing new the dearer concept will say
at the next step what it says now, and the wait gains nothing; it is made again at every such
step until the time since the last judgement moves the reading.

Let the last concept asked give its best hypothesis the chance c, and let going on show at
every later step what is shown now. Then by 76.11 going on for n ≥ 1 steps is worth
(1 - δ)ⁿ c.

**Proposition 76.12 (held to the last word, the rule puts out and gives up nothing).** Where
going on shows what is shown now, what it is worth is at most (1 - δ) c, so holding the chance
read of going on to the smaller of itself and (1 - δ) c takes from it nothing that going on is
worth. And with it so held, for c > 0 and δ > 0, the risk of going on is above the risk of
putting out, whatever was read: the rule puts out.

What this presumes is that going on shows the same again. It is false where the world moves
of itself, and there a concept asked last and held to in this way puts out where waiting was
right; whether a world stands still is not read here but taken, and where it is taken wrongly
the cost is that of 76.11 with the later worth in place of c.

## 76.13 What an asking is worth

By 76.6 a hypothesis may be an asking of the kernel, and by 76.8 it needs a chance of its own.
Nothing so far says what that chance is. Let a **place** be what has been asked so far in a
trial. An asking leads from a place to a later one and no run of askings leads back, so every
run of askings ends. At a place the answers have chances, the best of them c. An asking is right
where what is put out after it is right (76.9), and it is not free: let it be charged the share
δ of 76.11, 0 ≤ δ ≤ 1, the cost of an asking as a share of what a right answer is worth. Let
H(p, c) be **what is had** at place p with best chance c. Where nothing may be asked,
H(p, c) = c. Elsewhere the asking a, which leads to the place p_a, is worth

    w_a(p, c) = (1 - δ) E[H(p_a, c′) | p, c, a],        H(p, c) = max(c, max_a w_a(p, c)),

the mean being over what the best chance c′ is found to be once the asking is answered. Give
each answer its chance and each open asking the chance w_a. The rule of 76.1 with no risk read
then takes the hypothesis of greatest chance, an answer where they tie: it answers where
c ≥ max_a w_a and otherwise makes the asking worth most.

**Proposition 76.13 (taking the larger is best, and a dearer asking asks less).**
(i) Whatever chance of answering a way of deciding gives a place, what it has there is at most
max(c, max_a w_a). So no way of answering and asking has more than H, askings charged, and the
rule has H.
(ii) Let δ ≤ δ′. At every place and chance an asking is worth no more under δ′ than under δ,
and no more is had. So wherever the rule answers under δ it answers under δ′.
(iii) Where the rule answers with chance c in place of an asking that leads to worth v, it
gives up at most v - c ≤ δ v.

*Proof.* (i) For 0 ≤ q ≤ 1, q c + (1 - q) g ≤ max(c, g), at each place from the last places
backwards. (ii) At a last place the same is had under both charges. If no more is had under δ′
at every later place, the mean over them is no more, the weights being non-negative, and
(1 - δ′) times the less is at most (1 - δ) times the more; the larger of c and it is then no
more either. An answer under δ has c ≥ max_a w_a, which is at least the same under δ′.
(iii) is 76.11 with one step. ∎

The mean is not known. It is **read from recorded askings**: the chances are divided into
bands, and a record counts, for a place, a band of c and an asking, how often it led to which
later place and which band of c′. The mean is taken over the counts with a band's chance at its
middle. An asking never recorded at a place with c in a band has no worth there and is not made,
which is not the same as being worth nothing.

What this presumes. That the chances are calibrated, H being made of them. That the trials
recorded are like the trials met: a record of every asking at every place, from trials in which
all was asked, says what each is worth everywhere; a record of what one rule asked says it only
where that rule went. That what follows an asking turns on the place and the band of c and on
nothing else the concept could have read. And that a band is narrow: taking a band's chance at
its middle moves what is had by at most half a band's width at every place, since a mean of
values each off by at most that much, charged, is off by no more.

## 76.14 A record of one's own askings

The record of 76.13 may be given: made from trials in which everything was asked. A learner
has no such trials. It has the askings its own rule made, and with an empty record the rule of
76.13 makes none: an asking with no worth is not made, so nothing is recorded and the record
stays empty. As in 76.4, a rule that does only what it knows to be worth doing cannot learn
what anything else is worth.

Let an asking recorded fewer than m times at a place with c in a band be **tried**: made
whatever the answers' chances. Presume, as 76.13 does, that the chances are calibrated, and
that after an asking an answer may still be given. Each answer's chance after the asking is
then in the mean its chance before, and the best of them after is in the mean at least the
best before (the mean of the largest is at least the largest of the means, 76.9). Call the
best chance before c and the mean of the best after c′ ≥ c.

**Proposition 76.14 (a try costs at most the charge, and one's own askings say what all
askings would).**
(i) A try followed by answering has in the mean (1 - δ) c′, so it gives up at most
c - (1 - δ) c′ ≤ δ c′ ≤ δ against answering at once, and nothing where asking was the better.
A record with K cells of place, band and asking is then tried at most m K times over any
number of trials, at a cost of at most m K δ in all.
(ii) Let what follows an asking turn on the place and the band of c alone, as 76.13 presumes.
A rule that reads only place and band in deciding to ask makes, at each cell it visits, askings
drawn from the same law as all askings there. So the record of its own askings has the means
of the full record at those cells, and a cell it never visits is never asked from.

*Proof.* (i) c ≤ c′ gives c - (1 - δ) c′ ≤ δ c′, and c′ ≤ 1. Each cell is tried while it holds
fewer than m records and every try adds one. (ii) Whether the asking is made is settled by
place and band, and given those what follows does not turn on anything else, so the asking's
outcome is independent of its having been made. ∎

What is not said. How large m must be: a cell's mean worth read from m records is off by about
σ/√m, a misread worth costs at most twice what it is off (76.2), and narrower bands give more
cells, so K m grows as the bands narrow and the record is best begun coarse. A cell whose m
records read an asking as worth less than answering is not asked from again, so that reading
is never mended; by 76.2 it costs at most twice what it is off. And (ii) fails
where the presumption does: a rule that reads more than place and band, or chances that are
not calibrated, make the record of one's own askings a record of the askings one chose.

## 76.15 Askings at different charges, served by whoever serves them

Nothing in 76.13 needs the askings open at a place to be of one kind or of one cost. One may
be a further look by the expert that gave the first, another a second opinion from a dearer
expert, a third a question put to a person. Let each asking a have its own charge δ_a, the
share of what a right answer is worth that making it costs. Then, as in 76.13,

    w_a(p, c) = (1 - δ_a) E[H(p_a, c′) | p, c, a],    H(p, c) = max(c, max_a w_a(p, c)).

Who serves an asking is no part of this: the record holds for a place, a band and an asking
where it led, and the charge is a number the host states. So the inquiry is held by whoever
holds the answers, outside every expert, and the kernel serves each asking by whichever
installed expert gives the type asked for.

**Proposition 76.15 (one rule over all askings).**
(i) Taking the hypothesis of greatest chance, among the answers and every open asking with its
worth as its chance, has at every place the most that any way of answering and asking has.
(ii) With more askings open, no less is had at any place: the rule over all askings is paid at
least as the rule over any part of them, each at its own charge.
(iii) One asking made dearer, the others as they were, leaves no more to be had at any place,
and is taken nowhere it was not taken before; where it was taken, another asking or the answer
is taken as soon as that is worth more.
(iv) A try of an asking (76.14) gives up at most that asking's own charge.

*Proof.* (i) is 76.13 (ii) read with max_a over askings of unlike charges; its proof used no
equality of charges. (ii) The largest over more worths is at least the largest over fewer, at
the last places and so, by induction backwards, at every place. (iii) By induction backwards
as in 76.13 (iii): the dearer asking is worth no more by `dearer_worth_no_more`, the others'
worths rest on later places where no more is had, and a largest of terms none of which grew
did not grow; an asking worth no more than before against rivals is taken no more. (iv) is
76.14 (i) with δ_a for δ. ∎

What is not said: that a dear asking is worth its tries. Trying an asking m times in each of
its cells costs up to m K δ_a, which for a question to a person is the dearest learning there
is; a host that knows what a dear asking gives can hand the record those askings instead of
having them tried.

## 76.16 What one's own askings say of one's chances

76.13 to 76.15 presume calibrated chances, and a chance calibrated where names were to be had
need not hold where the system is used. Names are not needed to see that it does not. Let p
be the true chance of the answer held and p′ its true chance once an asking has been
answered; whatever the asking, p is the mean of p′ over what it may give.

**Proposition 76.16 (a chance that is right does not drift).**
(i) A calibrated stated chance of the answer held is in the mean the same after an asking as
before.
(ii) Let the stated chance be c = f(p). Where f is concave over the chances met, c falls in
the mean over an asking, and where f is convex it rises.
(iii) Let the true chance be p = g(c) for some g. Then g of the stated chance of the answer
held does not drift, so g is to be sought among the readings under which the mean of
g(c′) - g(c) over one's own askings is nought.

*Proof.* (i) is the law of total chance: Σ_j w_j p′_j = p with weights w_j summing to one, so
Σ_j w_j (p′_j - p) = 0. (ii) is Jensen's inequality for f over the same weights. (iii) is (i)
for g(c) = p. ∎

Being too sure is a concave reading above a half. Take the stated odds to be the true odds to
a power t: c = p^t / (p^t + (1 - p)^t). For t above one this is concave on [1/2, 1] and for t
below one convex there, so by (ii) the chance of the answer held, where it stays the likelier,
falls over an asking if the system is too sure and rises if it is too modest; and by (iii) the
power t̂ under which g_t(c) = σ(logit(c) / t) stops drifting estimates t from the askings the
system makes for its own ends. Whether an asking was made may turn on the place and on c
without harm, since (i) holds given both.

How much to believe a root. Over n askings the drift under a power has a mean and a standard
error, and a root of a drift that chance alone would give is no finding: over a few hundred
askings the spread of a chance's change is larger than a drift of a few tenths of a point, and
the root follows the spread. So the power used is the one nearest one under which the mean
drift is within a stated number of its standard errors of nought. It is one while the askings
do not contradict the chances as stated, moves out only as far as they force, and comes to the
root as n grows; nothing is claimed that the askings do not carry.

What is not said. That one power serves every place: where the chances after an asking are
less off than those before it, the root lies further from one than the power that would mend
the chance before, so a host may shrink it (use t̂^λ with λ below one), and λ is then a number
to be chosen where names are to be had. That a drift of nought means a right chance: a chance
off by the same amount in a way no asking moves is not seen. And (iii) needs the inquiry to
say the chance of each of its answers, so that the one held before can be followed.

## 76.17 Whom to trust, from the few dear answers

76.13 to 76.16 take the chances as the inquiry states them, and an inquiry over several sources
has so far been told how far each is to be believed by counting on trials whose answers were
named. Let one source, the dearest, be taken at its word: what it answers is a name for what was
right, believed to a stated share. The rest can then be learned from the askings the rule
itself makes of it.

Let the inquiry say, at a standing, what each source s has said as a number o(s, k) for each
answer k, and let the chance of answer k be the pool of those words, each at a weight:
proportional to exp(Σ_s w(s) · o(s, k)). Weight nought is trusting nobody: every answer is as
likely as every other whatever was said.

**Proposition 76.17 (which names are fair, and what they fit).**
(i) The rule asks from the standing alone. So given the standing, whether the dear source is
asked is independent of which answer is right, and the share right among the standings it was
asked at is the share right among all standings like them. A try (76.14) is the same case.
(ii) Counting how often a source agreed with the dear answers is not fair to it. Two sources,
each right with chance p and independently, the dear source asked where they disagree: among
those trials each is right exactly half the time, whatever p.
(iii) A trial named by a coin tossed apart from everything is a fair draw at every standing it
passed, and by 76.14 the coin gives up at most the charge each time it falls.
(iv) Over the dear asking the chance of an answer goes to one where it was right and to nought
where it was not, so its mean change at a standing is the share right there less the chance
stated. The dear answers therefore do not move the chances in the mean exactly where the
chances are right.

*Proof.* (i) With a the event that the dear source is asked and r that an answer is right,
P(r and a) = P(r) P(a) given the standing, so P(r | a) = P(r). (ii) They disagree where exactly
one is right, with chance 2 p (1 - p), and the first is the right one in p (1 - p) of it.
(iii) The coin is independent of the trial, so the trials it names are drawn as all trials are;
the cost is `NCA.try_costs_charge`. (iv) p (1 - c) + (1 - p) (0 - c) = p - c. ∎

So the weights are fitted by likelihood to the names: on the standing asked at for every dear
answer the rule or a try brought, by (i), and on every standing passed for a trial the coin
named, by (iii); never on the earlier standings of a trial the rule later chose to name, which
are selected on what followed, and never by counting, by (ii). At the fitted weights the names
less the chances, weighed by each source's words, sum to nought: that is (iv) asked source by
source, and it is 76.16's condition put to the one asking after which nothing drifts. A pull
toward the starting weights, of the strength of a stated number of names, keeps a few names
from carrying far. The dear source is asked while that is worth more than answering, as any
asking is (76.15), so its use falls away by itself as the cheaper sources come to be believed.

What is not said. That the pool is the true chance: it is where the sources' words are
independent given the answer, and where a trial is hard for all of them at once the weights
fitted at the unsure standings, which are the hard trials, are too low for the easy ones; a
coin's names widen the fit to every standing, and a source's weight may be kept apart for
places the inquiry tells apart. That the dear source is right: its share is stated, and a name
wrong more often than stated teaches wrongly to that extent. That a record of askings kept
while the weights were still moving is the record of the chances now stated: it is not, until
the weights have settled.

## 76.18 An asking that may be made only so often

A host may say that an asking is to be made in no more than a stated share of inquiries, whatever
it is charged: the dear source of 76.17 has only so many answers to give. The rule of 76.13 has
one way of asking less, a dearer charge. So the asking is given a price λ ≥ 0, added to its
charge where the rule weighs it and nowhere else.

For a way of asking, let P be what it is paid at the charges, and R what passes through the
limited asking: the mean, over inquiries, of what is had after it wherever it is made. Take the
asking as made at most once in an inquiry.

**Proposition 76.18 (a price keeps a limit, and is not paid).**
(i) Weighed at the charge c and the price λ, the asking is worth (1 - c - λ) h where h is had
after it, which is what it is paid, (1 - c) h, less λ h. So the rule of 76.13 run at the charge
c + λ is the way that is best for P - λ R.
(ii) Let a way be best for P - λ R and put R through the asking, and let b be a limit with
λ (b - R) = 0: the price is nought, or the limit is met. Then no way that puts at most b through
the asking is paid more.
(iii) What that way is paid is P, not P - λ R. What is had at a place, reckoned at the charges
alone along the askings the priced rule takes, is its promise; reckoned with the price it
promises λ R too little.

*Proof.* (i) is arithmetic. (ii) For a way paid P' that puts R' ≤ b through,
P' ≤ P - λ R + λ R' ≤ P - λ R + λ b = P + λ (b - R) = P. (iii) By (i), summed along the way. ∎

So the price is moved after each inquiry by a step times the askings made in it less the limit,
and never below nought: it rests only where the limit is met, or at nought where the asking is
made less often than the limit, which are the two cases of (ii). By 76.13 a dearer charge asks
no more, so the movement is toward the limit from either side.

What is not said. That the price comes to rest: that is the convergence of a small step along a
scattered slope, and is not proved here. That the count is what (ii) bounds: the limit is put on
how often the asking is made, and R is what is had after it there, at most that count, so (ii)
holds among ways that put no more through the asking, which is a little less than among ways
that make it no more often. That a price kept still keeps the limit: it does so only for the
inquiries it settled on, and a record or a trust that goes on changing moves how often the
asking is worth making.

## 76.19 A promise that is right does not drift

What is had at an inquiry's first place (76.13) is a promise: what following the rule from there
is paid. A record counted from few askings, or in another setting than the one at hand, promises
wrongly, and 76.16's argument, put to the promise in place of the chance, says by how much
without a word on what was right.

**Proposition 76.19 (the promise against what the last place holds).**
(i) Let the record's shares be those with which each asking does lead on. Then what is had does
not drift over an asking the rule takes: the mean of what is had after it, less the charge, less
what was had before, is nought. Along the rule's way, what is promised at the first place is in
the mean what the last place holds, the chance of the answer given there, times what the
charges paid on the way have left.
(ii) A record that takes at each place the best of several counted worths is too hopeful: the
best of the sums is at most the sum of the bests, so the mean of the largest counted worth is at
least the largest of their means.
(iii) Both ends of (i) are the asker's own figures. The mean, over the inquiries the rule has
made, of the promise less what the last place held with the charges off is how far the record
promises too much; a promise given less that mean agrees in the mean with the asker's own last
places.

*Proof.* (i) With shares w summing to one, had before h = (1 - c) Σ w_i h_i, so
Σ w_i ((1 - c) h_i - h) = 0; over several askings the differences add, each weighted by what the
earlier charges left. (ii) max(a + b, c + d) ≤ max(a, c) + max(b, d), and so for any number of
counts and askings. (iii) is (i) read as a measurement. ∎

What is not said. That the promise then is what is paid: it is what the last places hold, and
what separates that from pay is how far the chances stated there are from the share right, which
is 76.16's and 76.17's matter and needs askings or names, not this. That one number serves every
first place: it is the mean over those met. That every inquiry counts: one in which an asking
was tried (76.14) or named by a coin (76.17) did not follow the rule the promise is of, and is
left out. That the mean keeps up with a record still growing: a thin record's hope shrinks as it
is counted, and a mean over all inquiries so far lags behind it.

In Lean, 76.1 is `NCA.rule_risks_least`, `NCA.least_risk_le` and `NCA.share_le_iff`; 76.2 is
`NCA.read_risks_cost_little` and `NCA.threshold_costs_little`; 76.3 is `NCA.paid_le_best` and
`NCA.out_where_best_paid`, over `NCA.bestBy`, `NCA.outWhereBest` and the `NCA.readBy` of chapter
75; 76.4 is `NCA.never_out_unpaid` and `NCA.out_more_pays`; 76.5 is `NCA.cost_le_all`, over
`NCA.costBy`; 76.8 is `NCA.share_rises` and `NCA.shares_rise_alike`; 76.9 is
`NCA.largest_overrates`; 76.10 is `NCA.unsure_costs_less`, `NCA.sure_costs_little` and
`NCA.settled_costs_little`; 76.11 is `NCA.charged_tie_puts_out` and `NCA.charge_costs_little`; 76.12 is
`NCA.still_worth_within` and `NCA.held_to_last_puts_out`; 76.13 is `NCA.taking_the_larger_is_best`,
`NCA.dearer_worth_no_more`, `NCA.mean_had_no_more`, `NCA.dearer_has_no_more` and
`NCA.dearer_puts_out`; 76.14 is `NCA.try_costs_charge` and `NCA.tries_cost_at_most`; 76.15 is
`NCA.more_askings_have_no_less` and `NCA.one_dearer_has_no_more`, with `NCA.dearer_puts_out` read
against any rival, an answer or another asking; 76.16 is `NCA.right_chance_does_not_drift`,
`NCA.too_sure_falls` and `NCA.too_modest_rises` (that the power reading is concave above a half
for t above one is used and not proved there); 76.17 is `NCA.asked_from_the_standing_names_fairly`,
`NCA.counted_where_asked_is_a_half` and `NCA.named_change_is_the_gap` (that the fitted weights solve
the score equations is the calculus of the likelihood and is not proved there); 76.18 is
`NCA.price_takes_its_share` and `NCA.kept_by_a_price_is_best_within`; 76.19 is
`NCA.right_promise_does_not_drift` and `NCA.best_of_counts_flatters`.
