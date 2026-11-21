# 74. Lessons from what follows a judged press

A learner taught by payment alone is told, at a judged press, only whether the port it pressed
was the one paid. Chapter 67 draws more from an unpaid trial by counting sub-goals. This chapter
treats a second source: what is shown after the press. Where that shows which port was paid, a
reader of it can name the port after an unpaid press, and the name can be taught. The chapter
states what a press tells with and without the name, how many of the lessons so taken are false,
what can be measured of that and what has to be assumed.

## 74.1 Model

There are finitely many ports, `k` of them, at least two. A **judged press** is a situation, the
port pressed in it and whether the press was paid. In every such situation one port is the **paid
port**; the press is paid when the port pressed is that one, and unpaid otherwise. After a judged
press something is shown. A **teller** names a port after a press, or names none. It **errs** at a
press where it names a port other than the paid port. A **lesson** is a situation with a port
taken to be its paid port; it is **false** where that port is another. The frame gives ports,
situations and what is shown no meaning, and nothing says how a teller comes by its names.

## 74.2 What a press tells

**Proposition 74.1 (what a press leaves open).** After a paid press one port may be the paid
port. After an unpaid press `k − 1` may.

So a paid press is a lesson and an unpaid press strikes one port out. Where the ports are
pressed evenly and each is as likely as another to be the paid port, a press is paid one time in
`k`, and a judged press tells `(1/k) log₂ k + (1 − 1/k) log₂ (k/(k − 1))` bits of the `log₂ k`
that naming the port tells: 0.81 of 2 for four ports, and all of it for two, where an unpaid
press leaves one port open and a name adds nothing. Of `n` judged presses `n/k` are lessons;
where a teller names the port after a share `c` of the unpaid ones, the lessons are
`n (1/k + c (1 − 1/k))`, which for four ports and `c` of 0.85 is three and a half times as many.
Kakade, Shalev-Shwartz and Tewari (2008) bound what being told only right or wrong costs a
learner of linear rules against being told the port.

## 74.3 How many lessons are false

Take a lesson from an unpaid press wherever the teller names a port other than the one pressed,
that port being the lesson's. Where it names the port pressed nothing is taken: that port was
not paid, so there the teller is **seen to err**.

**Proposition 74.2 (the false lessons are the errors not seen).** Over any unpaid presses, the
teller is seen to err no more often than it errs, and the false lessons number its errors less
the errors seen.

So the lessons are false exactly where the teller errs without naming the port pressed, and a
teller that errs at a share `e` of the unpaid presses gives false lessons at no more than that
share of them. The errors seen are counted from the presses themselves and need no assumption;
they bound the errors from below and say nothing of the rest.

**Proposition 74.3 (the port named most).** Where, among the lessons of one situation, the paid
port is named in more than any other port is, the port named in most of them is the paid port.

So false lessons at a situation do no harm to a reader that follows the port named most there,
as long as no wrong port is named as often as the paid one; they need not be fewer than half. A
reader taught to fit the lessons it is given is taken, not proved, to follow the port named most.

## 74.4 What is assumed and what is measured

What 74.2 needs, the share of unpaid presses at which the teller errs, payment never shows. It
is taken from paid presses, where the paid port is known:

1. **One paid port.** In a situation where several ports would be paid, a lesson naming any of
   them is as good, and 74.1 overstates what an unpaid press leaves open.
2. **The teller errs after unpaid presses no more often than after paid ones.** This is not
   proved and can fail: once a learner chooses its own presses, the unpaid ones are those where
   it chose wrongly, and a teller that reads what the learner reads may err at the same
   situations. Such errors that name the port pressed are seen (74.2) and counted; a teller that
   is seen to err more often than it is allowed to err at all is not gone by.
3. **The share measured is the share.** A teller is gone by when it named the paid port at so
   many of the newest paid presses it had not been taught on. Taking those presses as
   independent, a teller that is right at 0.7 of presses names the paid port at 18 or more of 20
   with chance 0.036, and one that is right at half of them with chance 0.0002. The presses of a
   play are not independent, and the measure is taken again and again, so the chance of going by
   a poor teller at some time in a play is higher than at one time.
4. **The teller is taught by payment alone**, as any reader is, on what followed each judged
   press; it is given no port but the one pressed and whether that was paid.

Where what follows a press does not show the paid port, no teller is right on new paid presses,
none is gone by, and the learner is the learner without lessons. The lessons are taught and are
not stored among the learner's steps, which stay a record of what was pressed and paid; nothing
proved of stored steps turns on them.
