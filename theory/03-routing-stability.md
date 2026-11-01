# 3. Routing stability

The add-and-freeze protocol requires that installing a module does not
change how already solved tasks are solved.

**Theorem 3.1 (instability).** The plain planner is not stable.
With `need1 : [x] → g`, `from2 : [y] → g`, input `y`, the planner routes `g`
through `from2`; installing `make1 : [y] → x` makes the higher-priority
`need1` applicable and the route changes, although the old route remains valid.

**Generation-layered planning** `planStable`: plan with the first `k`
installed contracts, for the smallest `k = 0, 1, …, |lib|` that succeeds.

**Theorem 3.2.** Layered planning is
sound and complete in the same sense as `plan`.

**Theorem 3.3 (stability).** If `planStable lib avail n t`
succeeds, then `planStable (lib ++ extra) avail n t = planStable lib avail n t`
for every `extra`.

Cost: at most `|lib| + 1` planner runs per goal; results can be cached per
installation generation.

[Theory index](../THEORY.md)
