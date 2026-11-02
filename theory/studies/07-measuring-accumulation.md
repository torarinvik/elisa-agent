# 7. Measuring accumulation

For deterministic modules, an unchanged route implies identical answers, so
Theorem 3.3 predicts **zero changed answers** on every previously
covered task. The changed-answer count is the stricter regression metric:
equal accuracy can hide offsetting changes; zero changed answers cannot.

Stability is a guarantee about *unrequested* change. It also means a newly
installed module never improves an already covered task on its own: adopting
a better route must be an explicit, evaluated decision (for example,
reordering or replacing modules after comparing both routes on the suite),
not a side effect of installation.

[Theory index](../THEORY.md)
