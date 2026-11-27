# 76 (continued). Asking while unsure

The sections of chapter 76 from 76.13 on: what an asking of the kernel is worth under the rule of
[76.1](76-putting-out-or-thinking-on.md), and how a learner comes to know it from its own askings, from the
few answers of a dear source, and from whether the answers it gave were paid.

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

## 76.20 A judgement of the answer taken

In acting nobody names the right answer. What comes back is whether the answer taken was paid: a
name for that answer where it was, and where it was not, only that some other was right.

**Proposition 76.20 (what a one-sided name teaches, and what it cannot).**
(i) The rule answers from the standing alone, so by 76.17 (i) the share paid among the answers
given at a place with the best chance in a band is the share that would be paid for all
standings like them.
(ii) That share is what answering there is had: it is the last-place value of 76.13 itself, read
from pay and not from the chance stated. A record that keeps it values every asking by where its
answers were paid, so an asking whose answers flatter is found out by the same count, with no
word on which answer was right.
(iii) It cannot say which of the answers not taken was right. Two worlds alike in every standing
and in whether each answer taken is paid give the same judgements, whatever is right among the
others; so nothing learned from the judgements tells them apart, and an answer never taken
somewhere is never corrected there. Only taking it does that, which costs what a wrong answer
costs: a try of an answer is not bounded by a charge as a try of an asking is (76.14).

*Proof.* (i) is 76.17 (i) with the answer in place of the dear asking. (ii) What answering is
paid is one where right and nought where not, so its mean is the share right. (iii) The
judgements are a function of what the two worlds share. ∎

With few answers judged at a place and band the share is pulled toward the chance stated, with
the weight of a stated number of answers; the pulled value is the mean of the two in the
proportion of the answers judged to that weight, so it lies between them. Where pay comes only
when a run of answers ends, each is judged by what the run came to: that is still what
answering there is had.

## 76.21 An asking that takes time

Until here an asking cost a stated share (76.11) and the world stood still. In acting the world
moves while an asking is served, and the clock is the task's own: a chance to press passes, or a
bank of time runs dry.

**Proposition 76.21 (what waiting costs is in the record).**
(i) Let an asking be followed, with chance h, by the inquiry being over with nothing had, and
otherwise by a standing where v is had in the mean. It is worth (1 - h) v: the share of
askings after which nothing was left is a charge of exactly the form of 76.11, and it is
counted, not stated.
(ii) So with v had by answering now and v' > 0 had after the asking where the inquiry goes on,
the asking is worth more than answering exactly where h < (v' - v) / v': thought pays where
the share of what it adds exceeds the share of times it comes too late.
(iii) The record of 76.13 holds this as it stands, if an inquiry that ended during an asking is
recorded as led to a last place where nothing is had: the worth worked backwards is then
(i) at every place, and the charge differs from place to place and from task to task as the
counts do.

*Proof.* (i) h · 0 + (1 - h) v. (ii) (1 - h) v' > v iff h v' < v' - v. (iii) is 76.13 with one
more place. ∎

What is not said. That a place tells how much time is left: it tells what the host puts in it,
and a host that leaves out how long the inquiry has run gives one charge for early and late
alike. That the standing after an asking is of the same world: the answer is of the frame it was
served on, and what is counted is where the inquiry stood then, whatever moved it.

## 76.22 An inquiry with no last place

76.13 works what is had backwards from the last places, and so needs a record in which no asking
leads back to a place it came from. In acting there is none: to let a step pass is an asking,
and after it the inquiry may stand where it stood. Let h be what is had at each place and band,
a the answers' values there, and T the step of 76.13:
(T h)(p, b) = max(a(p, b), max over askings of (1 - c) Σ w(p, b → p', b') h(p', b')),
with w the recorded shares, an inquiry that ended (76.21) among them at its own last place.

**Proposition 76.22 (what is had where places recur).**
(i) T keeps the order: h ≤ h' gives T h ≤ T h'. It maps amounts between nought and one to such.
(ii) Begun at the answers' values, a ≤ T a ≤ T T a ≤ ..., bounded by one: the sequence converges,
and its limit is the least h above a with T h = h. The n-th term is what is had by a rule that
may ask at most n times, so the limit is what is had by asking any finite number of times.
(iii) Where no asking leads back, the sequence is 76.13's value after as many steps as the
longest way is long.
(iv) An asking that leads back to the same place and band every time is worth, uncharged,
exactly what is had there. Where that is the answer's value the rule's tie goes to the answer:
what shows nothing new is not asked for, with no charge set to say so (76.11 set one).

*Proof.* (i) Sums with shares that are not negative and largest-of keep the order. (ii) a ≤ T a
since T takes a largest that includes a; by (i) the sequence rises; a bounded rising sequence
converges, T is continuous, and any h ≥ a with T h = h bounds every term from above. (iii) After
n steps every place at most n askings from a last one has its value. (iv) Its worth is the sum
of one share times what is had there. ∎

What is not said. That the least solution is the only one: with an asking that leads back for
certain and costs nothing, any amount up to one solves the equations at that place, and only the
least is what some rule is paid. That the counts of a recurring place are of one kind of moment:
the place is what the host puts in it, and a host that leaves out how long the inquiry has run
has one worth for early and late.

## 76.23 The plainer of two the record cannot tell apart

The rule of 76.13 takes the larger of what the record counts. Let the options at a standing be ordered by what
they take: the answer, which takes nothing more, then each asking, the plainer before the dearer to serve. Two
options worth the same are counted apart by chance, and the larger of the two counts is a coin: a dearer asking
that shows nothing is made half the time, at no loss the record can see and at the kernel's cost.

Let a counted worth v be a mean over n recorded times of what was had where the asking led, with scatter s² among
them, so its standard error is e = s / √n; for an answer, of the n answers judged there and what they were paid.
The rule R_z walks the options in order and leaves the one it holds for a dearer only where the dearer's counted
worth is above the held one's by more than z √(e² + e'²).

**Proposition 76.23 (told apart).**
(i) Where a dearer option is worth what the held one is, R_z takes it with chance at most 1 / (1 + z²) whatever
the scatter's shape (Cantelli), and about Φ(-z) where the counts are many: for z = 2, one time in five at most
and about one in forty-four.
(ii) Where the dearer is worth more by d, holding to the plainer loses d a time and no more; and R_z holds to it
with chance at most 1 / (1 + (d / √(e² + e'²) - z)²) once that difference is positive, which goes to nought as
the counts grow.
(iii) The counts of an option R_z does not take grow only by tries. With each asking tried until its count at
a standing is the square root of the visits there, the tries are a share 1 / √N of N visits, which goes to
nought, and the count grows without bound: by (ii) a dearer asking that is worth more is found, and by (i) one
that is not is made about Φ(-z) of the time and in its tries.

*Proof.* (i) The difference of the two counts has mean nought and standard error √(e² + e'²); Cantelli's
inequality bounds the chance of a mean-nought amount exceeding z of its standard errors by 1 / (1 + z²). (ii) The
difference has mean d; it falls under z standard errors only by lying d / √(e² + e'²) - z of them under its mean;
Cantelli again. (iii) k tries among N visits with k² ≤ N are a share at most 1 / k. ∎

What is not said. That z is given by anything: two is the line this work draws everywhere and is chosen. That
the square root is the best pace of tries: any pace that grows without bound and slower than the visits serves
(iii). That the standard error is right: what is had where an asking led is itself counted, and its own error is
left out, so a deep record is told apart sooner than it should be. That what is had upstream follows R_z: the
sweep of 76.22 takes the larger everywhere, so the worth of an asking counts on dearer askings further on that
R_z may decline.

## 76.24 Trying by turns

76.23 (iii) left the pace of tries open and took the square root of the visits. The pace is what a dearer asking
that is worth more costs before it is found, and the square root is a slow one.

Let an asking be worth d more than the plainer option at a standing, d of either sign, and let what an inquiry
comes to scatter with variance at most s² under either. Counted m times and n times, their difference has
standard error s √(1/m + 1/n), and R_z of 76.23 tells them apart once d is z of those. Write k = (z s / d)².

**Proposition 76.24 (the pace of telling apart).**
(i) Tried on to the square root of N visits the asking has √N counts against N, the squared standard error is
over s² / √N, and it is told apart only after N ≥ k² visits.
(ii) Tried by turns, one inquiry in two, each has m counts after 2 m visits and they are told apart once m ≥ 2 k:
after 4 k visits, fewer than k² wherever k is over four.
(iii) Let the turns end where the asking is told apart, or where its gain is told to be under a smallest gain
looked for, δ: the gain counted and z standard errors together under δ. An asking worth no more than the plainer
(d ≤ 0) is so left, with chance at least 1 - 1 / (1 + z²) at each reading, once two times z standard errors are
within δ, that is once m ≥ 8 z² s² / δ². The makings spent on it are bounded, where tries at the square root
have no end.

*Proof.* (i) 1/m + 1/n > 1/m = 1/√N, so z² s² / √N < d² is needed, which is √N > k. (ii) With m = n the squared
standard error is 2 s² / m, and z² · 2 s² / m ≤ d² is m ≥ 2 k; and 4 k ≤ k² for k ≥ 4. (iii) By Cantelli, as in
76.23, the gain counted is at most z standard errors over d ≤ 0 with that chance; then the gain and z standard
errors together are at most 2 z standard errors, within δ; and 2 z s √(2 / m) ≤ δ is m ≥ 8 z² s² / δ². ∎

For a gain of a tenth with s = 0.45 and z = 2, k is 81: some 320 visits by turns against 6,500 at the square
root.

Two things a trial by turns needs, which are not in the proposition.
The turns are of whole inquiries. If an inquiry that took the plainer option at a standing stands there again a
step later and then takes the asking, both arms have made it, and what is counted is the gain of making it now
over a step on. An inquiry whose turn is the plainer option's makes no asking that is on trial, and only such
inquiries are counted as plain.
A count read at every making is not a count read once. A line of z standard errors that a count read once
crosses by chance about Φ(-z) of the time is crossed at some reading far more often, and with certainty if the
readings never end (the law of the iterated logarithm); over readings from 10 to 600 counts the chance is about
a sixth for z = 2 and one in forty for z = 3. A trial whose "gains" is acted on needs the stiffer line, or
readings at few set counts.

What is not said. That a half is the best share of turns, or that the arms need equal counts. That three is
the right stiffer line: a line that rises with the count so as to hold at every reading at once is known and
is not used. That the gain stays what it was while it is counted: where the readers are still being taught, the
early counts are of another learner, and nothing here forgets them. That δ is given by anything.

## 76.25 Sorting the steps of a place by a reading

A place holds every standing a host files under it, and 76.23 and 76.24 learn one number there: the mean of
what an asking gains over the plainer option. Let the standings of a place be of kinds i, with shares w_i and
gains d_i, and write D = Σ w_i d_i.

**Proposition 76.25 (sorted apart).**
(i) Counted as one place the asking is taken at every kind or at none, and what is had over the plainer option
is max(D, 0) at the most. Counted apart it is Σ w_i max(d_i, 0), which is no less, and more wherever the gains
differ in sign: for two kinds in equal shares gaining a and -a, the one place has nothing of the a / 2 there is.
(ii) Let each standing be put in a class by any reading of it made before what the inquiry comes to is known,
and let each class be a place with its own count. Then 76.23 and 76.24 hold in every class whatever the
reading is worth, what is had is Σ_c v_c max(D_c, 0) for classes of shares v_c and mean gains D_c, and that is
no less than max(D, 0). A reading that tells the kinds apart has all of (i); one that tells nothing has what
the one place had.
(iii) A class of share v has that share of the makings: telling its gain apart takes 1 / v times the visits
the whole place would need for the same gain.

*Proof.* (i) and (ii): max(·, 0) is convex, so the larger of a mean and nought is at most the mean of the
larger of each and nought; D is the mean of the d_i and of the D_c alike. A class fixed before the outcome is
a place like any other, and the counts in it are of its own standings. (iii) is counting. ∎

Three things a reading taught on the askings themselves needs, which are not in the proposition.
A class is read alone, on its own counts, and they are few at first: a class left on two makings must be open
to being found wrong. The tries of 76.23 (iii) for what the count does not take are what does that, and a
trial by turns (76.24) does not replace them.
What follows the plainer option can be read only from where it was taken. Once an asking is taken at every
standing of a class, standings of a new kind that fall in that class meet the asking alone, and a reading of
its gain there has one of its two sides from elsewhere. The plainer option's tries (76.23 iii) must go on in
what is new: counted by the stretch of one world in hand, not by all the place has ever seen.
The trial that teaches the reading must not be ended by the count the reading is to replace. Before the
reading has lessons the standings are still one place; if that place is found to gain under the smallest gain
looked for and left, no more makings come and the reading is never taught. Until it is, the one place may be
found to gain but is not left.

What is not said. That the reading sorts well, or how many classes there should be: three, cut at the smallest
gain looked for either side of nought, is chosen. That a standing put in the wrong class is found: it is
counted with its class. That what an asking costs in time is seen: the gains are of what inquiries come to,
and an asking that changes nothing there but takes a step is worth nought here, not less.

In Lean, 76.13 is `NCA.taking_the_larger_is_best`,
`NCA.dearer_worth_no_more`, `NCA.mean_had_no_more`, `NCA.dearer_has_no_more` and
`NCA.dearer_puts_out`; 76.14 is `NCA.try_costs_charge` and `NCA.tries_cost_at_most`; 76.15 is
`NCA.more_askings_have_no_less` and `NCA.one_dearer_has_no_more`, with `NCA.dearer_puts_out` read
against any rival, an answer or another asking; 76.16 is `NCA.right_chance_does_not_drift`,
`NCA.too_sure_falls` and `NCA.too_modest_rises` (that the power reading is concave above a half
for t above one is used and not proved there); 76.17 is `NCA.asked_from_the_standing_names_fairly`,
`NCA.counted_where_asked_is_a_half` and `NCA.named_change_is_the_gap` (that the fitted weights solve
the score equations is the calculus of the likelihood and is not proved there); 76.18 is
`NCA.price_takes_its_share` and `NCA.kept_by_a_price_is_best_within`; 76.19 is
`NCA.right_promise_does_not_drift` and `NCA.best_of_counts_flatters`; 76.20 is
`NCA.pulled_share_lies_between`, with `NCA.asked_from_the_standing_names_fairly` read for the
answer taken; 76.21 is `NCA.ended_share_is_a_charge` and `NCA.thought_pays_where_gain_exceeds_hazard`;
76.22 is `NCA.asking_once_more_has_no_less` and `NCA.back_to_where_it_stood_ties`;
76.23 is `NCA.holding_to_the_plainer_loses_the_gap` and `NCA.tries_to_the_root_are_a_falling_share` (Cantelli's
inequality is used and not proved there);
76.24 is `NCA.told_apart_by_turns`, `NCA.turns_need_fewer_than_the_root` and
`NCA.left_once_the_error_is_small` (the chance of crossing a line read many times is quoted and not proved);
76.25 is `NCA.sorted_apart_has_no_less`, for two kinds.
