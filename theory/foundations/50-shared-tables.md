# 50. Shared behaviour tables

Chapter 49 shares enumeration between goals with one contract. This chapter treats what the resulting table offers:
fewer evaluations per hypothesis, far fewer labels, and failure detected from labels alone.

## 50.1 Table

Fix a contract, a library and a pool of `P` inputs. Enumeration produces a table of `M` behaviour classes, each a
vector of outputs on the pool. The table depends on no goal's labels. A goal is its vector of true outputs on the
pool, which is known only where labelled.

## 50.2 Evaluating on fewer inputs

If each of `C` candidates costs one unit and one per input, enumeration costs `C * (1 + P)`, which grows linearly with the pool.
Examples used in search therefore cost compute as well as labels. Pruning on few inputs merges more classes and can drop
a class that a later input would separate, so a smaller pool changes which routes are reached, and can raise or lower `C`.

**Theorem 50.1 (staged evaluation).** If all `C` candidates run on `a` inputs and only `S ≤ C` survivors on `e` more,
`C * (1 + a) + S * e ≤ C * (1 + a + e)`.

Survivors of a goal's first inputs are few, so staging approaches the cost of the small pool.

## 50.3 Labels from a decision tree

Choosing inputs that split the table lets a goal identify its class adaptively. The tree is built once per contract from
outputs alone and needs no labels.

**Theorem 50.2 (identification lower bound).** If each of `d` questions has at most `b` answers and answers separate `M`
classes, then `M ≤ b ^ d`.

So at least `log_b M` labels are required, and a table with many distinct outputs per input can need very few. Choosing
each question to reduce the largest remaining group is the classical greedy tree, within a factor about `ln M` of the
best (Dasgupta, 2004, under its assumptions). Search labels therefore grow with the logarithm of `M` and not with a fixed sample.

## 50.4 Failure seen from labels

**Theorem 50.3 (failure certificate).** If a goal's label on some input differs from every remaining class's output there, no
remaining class fits the goal.

The goal is then outside the table at this cap, and this holds with no further compute on it. This is the failure predictor of
49.5 at zero compute and no false abandonment within the table. It says nothing about routes beyond the cap, and pruning on
pool inputs preserves it only relative to those inputs. A goal can also match a wrong class, so identification proposes
a candidate that must still pass fresh cases (20.22, 49.6).

## 50.5 False matches

Theorem 49.9 bounds expected false matches at `M * q ^ s` for `s` matched inputs. Tree labels are chosen to separate classes,
so they are not independent draws and that bound does not apply to them; a match from a tree has only excluded the table's other
classes, and is no evidence on goals outside the table. Identification is therefore weak evidence, and the gate carries the guarantee.

## 50.6 Consequences to test

1. Work per candidate scales with `1 + P`.
2. Most tabled goals are identified in about `log_b M` labels, and most failing goals are rejected as quickly.
3. Tree-identified candidates that are wrong are rejected at the gate at the cost of few labels.
4. Goals that only guided search solves remain outside the table and need a guided strategy or a larger table.

## 50.7 What identification leaves

When search labels and work are small, the fresh gate dominates labels. A gate needs its cases because its confidence is not tied to how
a candidate was chosen, so it does not fall with the table's cost. A candidate identified from a table is one of `M` fixed in advance of the goal's
labels, which is a smaller selection than an adaptive search over many goals. Whether that can lower gate cases soundly is open. A wrong candidate
fails early, so most gate labels go to candidates that pass.

## 50.8 The zero-error gate cannot go much lower

For a candidate with error just above `ε`, a test admitting on zero errors in `m` independent cases admits with probability about
`(1 - ε) ^ m`. So a test at level `α` requires `m ≥ log (1 / α) / -log (1 - ε)`. At `ε = 0.05` and `α = 0.001` this is 135 cases.

**Theorem 50.4 (exact count).** If `log (1 / α) ≤ -log (1 - ε) * m` and `ε < ℓ ≤ 1`, then `(1 - ℓ) ^ m ≤ α`.

**Theorem 50.5 (known decisions).** `N` decisions at shares `δ / N` spend exactly `δ`.

An open-ended sequence of requests must reserve budget, so its first decision receives at most part of `δ`. An instance that decides a known number
need not. Beyond this floor, fewer labels require a different claim: a larger `ε`, a larger `α`, or a statement about a population
of candidates, such as the expected share of false admissions, which depends on how wrong candidates' errors are distributed. Near-tolerance
candidates are the ones such a statement must weigh, because they alone survive long tests.

## 50.9 Tables without queries

Inputs need no labels, so a table can be built on an unlabelled pool even when a goal cannot answer chosen inputs. A goal then has only its own
labelled cases, on inputs outside the pool, so each remaining class's hypothesis must be run on them. Read cases in turn, keep the classes that agree, and stop when at most one
remains.

**Theorem 50.6 (narrowing cost).** If at most `r` classes remain after each case and the first case tests all `M`, narrowing over `s + 1` cases costs at most
`M + s * r` evaluations, for one goal, and it needs at most `s + 1` labels.

With `C` candidates, `N` goals and pool `P`, the total is about `C * (1 + P) + N * M`, in place of `N * C * (1 + s)`. It saves whenever `M` is far below `C`.
The table's classes are distinct only on the pool, so a hypothesis merged there may be the one a goal's inputs needed. This loss falls as
the pool grows and needs the pool to resemble the goals' inputs. A single goal shares with nothing, so this does not help a task such as a lone
translation problem, where `N = 1`; sharing there would need many subgoals of one contract.

Measured, narrowing lost nothing to chosen inputs on these families (see the diary), so chosen inputs are not needed for sharing where goals share a contract. Sections 50.3 and 50.4 remain the theory of what chosen inputs would add.

## 50.10 Setting the table from no labels

**Work.** Enumeration can stop anywhere and keep what it found, so only a total budget is needed, and that is a declared resource and not a tuned value. By 45.2 and 45.3,
with `n c` goals of contract `c`, shares proportional to `√(n c)` minimize `∑ n c / share c`, the expected cost when a goal's solution is equally likely at any depth of its contract's share.

**Pool.** A small pool merges classes a goal may need to separate, and a large one costs more per candidate. Whether inputs still separate classes can be read from the table alone, without labels. Let `D p` be the number of distinct prefixes of length `p` among a table's vectors. `D` is monotone, so choose the smallest `p` with `D p = D (2 * p)`, where doubling the pool separates nothing further among those classes.

**Theorem 50.7 (prefixes refine).** If `p ≤ q`, equal prefixes of length `q` have equal prefixes of length `p`, so `D p ≤ D q`.

This compares only classes found so far. Early tables are small, so few inputs separate them, and the rule then picks too small a pool for later classes: distinctness among found classes says nothing about classes a small pool never retained. Label-free stopping of this form is therefore unreliable.

**Pool from fit.** Without that signal, a goal's own cases can judge a pool. Enumerate at each candidate size on an equal part of the budget, count the goals for which a hypothesis agrees with all their training cases, and continue at the size that fits the most, the smaller on a tie. The count is a selection score from training labels, not evidence of correctness.

## 50.11 Composing answers from tables

A label may determine labels for parts of a goal. If an output constructor is injective, as a pair is, each case gives each part a case of its own, so each part is its own goal with its own table.

**Theorem 50.8 (a product is its parts).** For `f x = (g x, h x)`, a pair of functions agrees with `f` on a case exactly when each agrees with its part.

Narrowing parts separately tests about `M₁ + M₂` hypotheses, where the whole needs `M₁ * M₂`, so a table of depth `n` reaches pairs of depth `n` at nearly no added work. The checks on parts bind jointly, and agreement on training cases is only a proposal: a composed route still passes the gate as one candidate. A failure of either part means no composition exists in these tables.

## 50.12 Tables for slots

A higher-order route `h(x, b)` has a body `b` that runs in its own scope. Enumerating such routes whole multiplies body choices by every argument choice and pays for all bodies at every enclosing size. A body has its own contract, so it can have its own behaviour table on inputs from its scope. With `B` body classes and `A` argument choices, the enclosing table needs at most `A * B` routes. Bodies that agree on the body pool collapse into one.

**Theorem 50.9 (behaviourally equal bodies fold equally).** If two steps agree on every state and item a fold visits, the folds agree.

The condition is on states the fold reaches, which a pool only samples, so a merged pair can differ on a goal. Candidates still pass the gate. Measured on simple accumulations, whole enumeration costs 76,596 to reach sum on two inputs, and 3,000,000 does not reach counting above a threshold.

Slot tables reach single-operation bodies cheaply but not the bodies these goals need. A count needs a guarded step, `if p (a) then s + 1 else s`, whose body is itself large when enumerated whole, so an eightfold budget adds nothing.
