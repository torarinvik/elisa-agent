# 34. Compiled routes

## 34.1 Columnar evaluation

The runtime evaluates a route one input and one invocation at a time,
recording every value. A *compiled* route evaluates it for a batch of
inputs at once, column by column: each node of the route is evaluated for
all rows of the batch together, and a map's body is evaluated once for the
elements of every row's sequence, concatenated. An expert may offer a
*batch* form, a function from columns of argument values to the column of
its outputs; it is *batch-sound* if that column equals the expert applied
to each row.

Demand is kept: a row whose demand on an argument is empty does not
evaluate that argument and passes the unread value instead, exactly as the
runtime does (§14).

**Theorem 34.1 (compilation is invisible).** For a route of functional,
batch-sound experts without slots or requests, the compiled route returns,
for every row of a batch, the answer the runtime returns for that row
alone.

*Proof.* By induction on the route. A given input is read per row; an
application evaluates, per row, the arguments the row demands, and the
batch form returns each row's application by batch-soundness; a map's
body, evaluated on the concatenation of the rows' elements, returns the
concatenation of its per-row results (Theorem 34.2), which regrouping by
the rows' lengths splits back. ∎

**Theorem 34.2 (batching across rows).** Mapping a function over the
concatenation of sequences equals concatenating its maps over each.

## 34.2 What compilation does not do

A compiled route spends no budget, keeps no workspace and resolves no
requests: experts that need the kernel (slots, requests, continuations)
are not compiled, and an expert that returns a request at run time stops
the compiled call. Such routes run on the runtime, which remains the
reference semantics; compilation is an optimization for the routes, and
the parts of routes, that are plain functions of their inputs.

## 34.3 Ledgers and caches on compiled routes

A compiled route can keep one ledger per row (§33.2) and read a result
cache (§28.4). Alongside each row's demand it propagates the row's
decision demand, exactly as the runtime does, and charges each row's
relevant invocations to that row's ledger; an expert that accounts inside
runs with the row's ledger current. A cache lookup is made per row; the
misses of one batch that share a key are evaluated once.

**Theorem 34.3 (compiled ledgers).** Under the premises of Theorem 34.1,
the compiled route charges each row's ledger the same reports, and leaves
it uncertified by the same experts, as the runtime executing that row
alone; with a sound cache it returns the same answers.

*Proof.* By the induction of Theorem 34.1, every row's invocations, their
inputs and their read and decision demands are the runtime's, and the
charge of an invocation depends only on these and its output. A cache hit
returns the output of an earlier invocation with the same expert and
inputs, which for a pure expert is its output now (Theorem 28.4);
evaluating once for rows that share a key is the same argument within a
batch. ∎

So Theorems 33.1–33.4 hold for answers produced by a compiled route, and
selective answering or refinement may use it in place of the runtime.
