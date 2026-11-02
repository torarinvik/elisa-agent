# 36. Acquiring experts

## 36.1 Where to acquire

Audits (§35) and ledgers (§33) say where a route falls short. Summed over
a batch, a ledger's entries give each expert's share of the charged risk;
an expert with a large share, or one an audit refuted and recalibration
left uninformative, is where a better expert lowers the route's risk
most, by Theorem 31.3. *Acquisition* builds a challenger for that
expert's contract and lets the evidence decide between them.

## 36.2 Honest promotion of a trained challenger

The labeled invocations an audit collects are split, before any training,
into a training part `T` and an evaluation part `E`. A trainer, supplied
by the domain and arbitrary otherwise, maps `T` to a challenger with the
incumbent's contract. Both experts are then evaluated on `E`, and the
challenger is promoted by the paired sign test of §30.

**Theorem 36.1 (split promotion).** If `T` and `E` are independent, and
the test rejects with probability at most `α` for every fixed challenger
no better than the incumbent, then the probability of promoting a trained
challenger no better than the incumbent is at most `α`.

*Proof.* The challenger is a function of `T` alone. Conditionally on
`T`, it is fixed and `E` keeps its distribution, so a false promotion has
conditional probability at most `α`; averaging over `T` keeps the bound. ∎

The theorem fails if the trainer sees `E`, for instance by selecting
among training runs by their score on it, which is the overfitting the
split exists to prevent.

A promoted challenger reports risk only once it is calibrated; it is
calibrated and audited on `E` as in §35.2, which the sign test, not
depending on reports, leaves valid. Its calibration and promotion hold on
the distribution the audit sampled, so acquisition answers a shift
exactly as far as the audit's inputs represent it.

## 36.3 Proposing decompositions and interfaces

A proposer uses only `T` to return a finite family of experts with the
incumbent's external contract. Each expert may introduce new intermediate
constructor objects and an arbitrary internal composition. These declarations
are hypotheses about useful representations, not proofs of their meaning.
Freeze the whole family before evaluating any proposal on `E`.

**Theorem 36.2 (finite proposal selection).** Conditional on `T`, suppose
there are `k > 0` proposals and every no-better proposal's paired test has
false acceptance probability at most `α/k`. Then the probability of selecting
any no-better proposal is at most `α`. Independence between proposals is
unnecessary: selection implies that at least one proposal passed, so the union
bound applies. Averaging over independent `T` gives the unconditional bound
as in Theorem 36.1. With no proposals, nothing is selected.

The proposer must not select, retrain, or add proposals after seeing `E`.
Repeated adaptive searches need their own budget accounting. Shallow sequence
snapshots do not isolate mutable sample objects. This mechanism evaluates
proposed interfaces; it does not itself invent representations or prove transfer.

A proposed decomposition may be a stored package rather than a live expert.
Its candidate family consists of all installed exports with the incumbent's
external contract, identified by source object reference and export identity.
The budget counts these exports, not packages: a package can contribute several
competing experts. Package references are frozen using `T` alone before any
export is evaluated on `E`. Unselected objects can remain in a candidate store
without being added to the active expert library.

**Proposition 36.3 (reloaded outcomes).** If reloading a selected export preserves
its function on every input, then its scored outcomes on a fixed labeled sample
are unchanged. This follows pointwise by substitution. Content references alone
do not establish the premise: entry points, external weights, runtime state and
scoring behavior must also be preserved. Selection evidence is neither a
calibration certificate nor a proof of representation semantics.

## 36.4 Learning decoders for candidate representations

Given training pairs `(x, y)` and a fixed feature expert `f`, let `n(z, y)`
count training pairs with `f(x) = z` and target `y`. Construct a decoder `d`
by choosing a label of maximal count at each observed key `z`. Break ties
by first occurrence; at unseen keys use the global training mode. This defines
a proposed decomposition `x → f(x) → d(f(x))`, with the decoder contract
derived from the feature's output and the required target type. Keys and labels
must have stable hash/equality semantics, and the feature must not change.

**Theorem 36.4 (empirical decoder optimality).** For any decoder `g` on the
same representation, the modal decoder has at least as many correct training
predictions: `Σ_z n(z, g(z)) ≤ Σ_z n(z, d(z))`. Each summand is bounded by its
chosen maximum; sum over the finitely many observed keys. This asserts nothing
about unseen keys or held-out accuracy. Freezing several such decompositions
on `T` and selecting on independent `E` uses Theorem 36.2.

This learns the decoder and its interface contract without hand-writing one
for each representation. The feature family and its type meanings are still
supplied; this construction does not invent a feature space or new type meaning.
An inadequate feature irreversibly loses information, while an overly specific
one can memorize training pairs and generalize poorly.

## 36.5 Searching joint representations

For feature experts `f : X → A` and `g : X → B`, their joint representation is
`h(x) = (f(x), g(x)) : A × B`. Its interface is a structural product of the
existing feature types, not a claim of semantic equivalence or a new primitive
meaning. Repeated pairing represents any finite nonempty subset of features.
Enumerate subsets in increasing size, freeze them using training data alone,
fit the decoders of §36.4, then select using §36.3. The subset size and total
candidate count are explicit search resource bounds; enumeration can be
exponential in the number of available features.

**Proposition 36.5 (joint representation can simulate a component).** For
any decoder `d : A → Y`, the decoder `d'(a,b) = d(a)` satisfies
`d'(h(x)) = d(f(x))` for every `x`. Thus the optimal empirical decoder for a
joint representation cannot have fewer training successes than a decoder
using its first component, by Theorem 36.4. This does not imply better
held-out performance: a joint table can have many more unseen keys.

Joint feature execution calls both components on the same inputs and slot
fillings, in order. Declared costs and known slot-call counts add; effects
are their union when both are declared, otherwise unknown. Stateful features
need extra care: this construction does not make calls commute or preserve
a feature's behavior across separate training and evaluation invocations.
