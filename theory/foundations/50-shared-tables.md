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
