# 63. Places of ports and a rule read round a place

Chapter 62 composes an answer from statements. This chapter treats a situation that is a picture and a row
of ports, one press of which is judged: where each port acts, how few paid presses settle that, and what
makes a rule learned at some ports hold at ports never paid, on a picture of another size.

## 63.1 Model

A learner has **ports**, numbered, and is shown a **frame**. It presses one port and is **paid** or not.
Nothing tells it what a port does. A port **acts at a place** in the frame when what the press is paid for
lies there; the place is taken from the frame that follows a paid press, as where something came to be
that does not come to be on every trial.

Ports **run in rows like their places** when, for some width `w`, the place of port `p` is a start, plus a
step for each row `p / w`, plus a step for each column `p % w`.

## 63.2 A few paid ports place the rest

**Theorem 63.1 (three ports place the rest).** Two placings in rows that agree on three ports not in a
line agree on every port.

So the places of all the ports are fixed by three paid ones whose rows and columns are not in a line, for
a given width; the width is the one for which the paid ports fit and on whose places the marks seen lie.
More paid ports are wanted only to tell widths apart and to set aside a mark taken in the wrong place.

What this costs is governed by how often a press is paid before anything is learned. Where one press in
`n` is paid, `k` paid ports take about `k * n` presses, and nothing in the learner shortens that: it is
the price of being told nothing about the ports.

## 63.3 A rule read round a place

A **reading** of a port in a frame is what lies round its place, taken at the scale of the step between
places. A rule is **read round a place** when what is paid is a function of the reading alone.

**Theorem 63.2 (read alike, paid alike).** Under a rule read round a place, two presses with the same
reading are paid alike, in whatever frames and at whatever ports.

The reading does not name the port or the size of the picture, so what is learned at one port holds at
every port, and what is learned on one picture holds on a larger one with the same step taken as the
scale. The examples wanted are as many as tell the readings apart, however many ports there are.

**Theorem 63.3 (a rule kept port by port is open where unpaid).** Two rules kept port by port can agree
at every port that has been paid and differ at one that has not.

So a learner that keeps what is paid port by port needs every port paid, and learns nothing for a picture
with other ports; that is what the reading buys.

## 63.4 What this assumes

That one press is judged, so that a payment belongs to a port. That something comes to be where a paid
port acts. That ports run in rows like their places. That the rule is read round a place within the
reading taken, which a rule turning on something farther off is not, and that it is the same whichever
way round the frame is turned, where readings are turned to make more of them. Where a press is seldom
paid the places are found late or not at all (63.2), and what was learned elsewhere cannot be used until
they are.

In Lean 63.1 is `NCA.three_ports_place_the_rest`, 63.2 `NCA.paid_alike_where_read_alike` and 63.3
`NCA.a_rule_by_port_is_open_where_unpaid`.
