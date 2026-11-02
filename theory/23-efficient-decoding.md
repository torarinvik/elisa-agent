# 23. Efficient decoding

## 23.1 Decoding is paid once per climb

§21.4 prices one decoding at about `2.25 m²` multiply-adds, about 1% of a
top-rung pass over all words. But refinement climbs one word per step and
must recompute the bound after each climb. At depth 8 a full decoding
(744k operations) costs about seven top-rung word readings (103k FLOPs
each). Over the hundreds of climbs a depth-8 formula takes, exact decoding
from scratch at every step would cost more than the reading it serves. This
section makes each step's decoding cost small without giving up a valid
bound. Two facts suffice: almost all posterior weight lies near the reading
(**banding**), and a climb changes one word (**splitting**).

## 23.2 The tail outside a band

Fix a reference sequence `r`, for instance each word's most probable arity.
Word `k` has weights `qₖ` (its calibrated arity probabilities, summing to at
most 1) and off-reference mass `ρₖ = Σ_{a ≠ rₖ} qₖ(a)`; let `S = Σₖ ρₖ`.

| Theorem | Statement |
|---|---|
| 23.1 | the total weight of the sequences differing from `r` in at least `j` positions, parseable or not, is at most `e_j(ρ)`, the elementary symmetric polynomial |
| 23.2 | `j! · e_j(ρ) ≤ S^j` for nonnegative `ρ` (a Maclaurin-type inequality) |
| 23.3 | the accepted sequences among them weigh at most the same tail |

So the weight outside `j − 1` changes is at most `U_j = S^j / j!`. For
`j = 2` this is `e₂` of §19.4. Here it is a statement about the decoding
model's weights, so it needs no premise beyond (P).
If a row has total mass above one, let `cₖ = max(1, Σₐ qₖ(a))` and
`C = Πₖ cₖ`. Dividing each row by `cₖ` produces subprobability rows; their
off-reference masses sum to at most `S`. Every complete sequence weight is
divided by the same `C`, so the original tail is bounded by
`C · S^j / j!`. This covers the small row-mass excess accepted by the
implementation's numerical tolerance. The Lean proof establishes that these
row factors normalize arbitrary nonnegative weights and that the resulting
bound uses the original off-reference mass. These bounds
are exact-real statements; their floating-point evaluation is not an
outward-rounded enclosure.
For `m` positions, the tail is exactly zero when `j > m`: two length-`m`
sequences cannot differ at more than `m` positions. The search therefore
need not continue past `m + 1`, even if the polynomial bound remains large.
The polynomial bounds satisfy `U_{j+1}/U_j = S/(j+1)` for `S > 0`.
They therefore increase and then decrease. Since `C ≥ 1` and the search
threshold is below one, if `U₁` exceeds the threshold, every qualifying
index lies on the decreasing side and qualifying indices form a suffix.
The native search uses this property to locate the first qualifying index
with logarithmically many bound evaluations. Lean proves this suffix property
for the exact-real polynomial, along with the search step's bounds and interval
shrinkage, the adjacent-bound stopping condition, and the 63-step bound for a
signed 64-bit interval. Floating-point comparisons
can still round; these lemmas are not a proof of the compiled search loop.

Numerically, off-reference mass is summed directly in log space, rather than
subtracting the reference mass from a rounded row total. The tail comparison
also stays in log space, retaining finite mass below the probability range.
This avoids that cancellation and underflow; it is not an outward-rounding
guarantee for the entire risk calculation.
The off-reference masses and log row factors can each be summed by blocks:
their sums over a concatenation are the sums of the block sums. After one row
changes, recomputing its block and combining all block summaries takes
`O(B·|A| + m/B)` work for block size `B` and alphabet size `|A|`, instead of
rescanning `m·|A|` weights. Each row total is the sum of its reference and
off-reference masses, allowing the latter to be reused. The native block
summary computes off-reference mass relative to its largest log weight,
using compensated summation of the other relative weights. Entries with zero
weight contribute nothing; if no off-reference weight is positive, that row's
off-reference mass is zero. Regrouping
floating-point additions can change rounding and does not provide
outward-rounded bounds.
The native cursor reuses its initial block summaries for later row updates;
standalone band selection uses the same grouping so both start from the same
floating-point summary.
When a banded risk rounds to zero, a full format pass separately sums the
selected sequence and every other accepted sequence. Normalizing the two
parts recovers small model risks that disappear when subtracting nearly
equal log normalizers. This fallback computes exact model risk, subject to
floating-point rounding, and may require more work than the banded pass.

**From changes to states** (Theorem 23.4). Arities are at most 2, so
two sequences differing in `d` positions have sums at most `2d` apart. The
same holds for every prefix. Hence the counter of `await` (one plus the
prefix sum of `a − 1`) of a sequence within `j − 1` changes of `r` stays
within `2(j − 1)` of `r`'s counter at every position. A dynamic program
restricted to the **band** of counter values `|n − n_r(k)| ≤ 2(j − 1)`
therefore sees every such sequence. The band has `W = 4(j − 1) + 1` states
per position, against up to `min(k + 1, m − k)` live states unbanded.

More generally, if all nonnegative arities in the alphabet are at most `A`,
the same argument gives a half-width of `A(j − 1)`. This permits other finite
arity alphabets without assuming that two is a system-wide limit. The bound
is based on the configured alphabet, not on a fixed set of task experts.

## 23.3 A certified banded risk

The banded passes compute:

- `Z_band`: the total weight of accepted sequences inside the band. It is at
  least the weight of accepted sequences within `j − 1` changes.
- `â`: the most probable accepted sequence inside the band, with weight `x`.

Every accepted path starts at counter 1 and ends at counter 0. If either
endpoint lies outside its band row, the band contains no accepted path and
the pass can return without evaluating intermediate weights.

Every other accepted sequence lies outside `j − 1` changes, so the true
normalizer satisfies `Z ≤ Z_band + U_j`.

**Theorem 23.5.** If `x ≥ 0`, `Z > 0` and
`Z ≤ Z_band + U`, then `1 − x / Z ≤ 1 − x / (Z_band + U)`.

The controller answers with `â` and charges `R_band = 1 − x / (Z_band + U_j)`.
That is an upper bound on `â`'s exact posterior risk, so every guarantee of
§21 holds unchanged. The cost is at most the slack `U_j`, at most
`U_j / Z_band` in relative terms.

**Exactness certificate.** Each sequence outside the band weighs at most
`U_j`. So if `x ≥ U_j`, the banded `â` is a most probable parseable sequence
overall, the same answer exact decoding gives.

**Relative slack.** The charged risk exceeds the exact one by at most a
fraction of the band's own weight.

**Theorem 23.6.** If `x ≤ Z`, `0 < Z` and `Z_band ≤ Z ≤ Z_band + U`, then `(1 − x / (Z_band + U)) − (1 − x / Z) ≤ U / (Z_band + U)`.

*Proof.* The difference is `x (Z_band + U − Z) / (Z (Z_band + U))`. The
numerator's second factor is at most `U`, and `x / Z ≤ 1`.

These two risk bounds apply to any accepted sequence of weight `x`, not just
the maximizing sequence or one inside the band: acceptance gives `0 ≤ x ≤ Z`.
Only the exactness certificate requires the selected sequence to maximize the
banded weight. When the answer is already selected, normalizer certification
can stop at the relative-tail condition without establishing or tracing a
maximum. This distinction permits one distribution to select an answer
and another to bound that same answer’s posterior risk.

The slack is pointwise at fixed readings and a fixed selected sequence.
An adaptive controller may choose different refinements after its charges
change, so the theorem does not bound the difference between final risks of
two separately stopped runs. Nor does it correct a mismatch between the
decoding model and the data distribution (§24): that requires appropriate
model assumptions or a separate deployment audit (§17).

So a slack target must be relative: `U_j ≤ η · Z_band` gives a charged risk
within `η` of the exact risk. An absolute target `U_j ≤ η` is not enough, since
`Z`, the weight of all parseable sequences, can be far below 1 when many
readings do not parse.

**Choosing `j`.** `Z_band` is known only after the banded passes, so `j` is
found by widening. Start from the least `j` with `S^j / j! ≤ η` (the band is
then at least as wide as needed when `Z = 1`), run the passes, and increase
`j` while `U_j > η · Z_band`. This terminates whenever `Z > 0`: widening never
lowers `Z_band`, and once `2(j − 1) > m` the band covers every live state (the reference
counter at position `k` lies in `[1 − k, 1 + k]`, live states in `[0, m − k]`).
Then no sequence lies outside it, the tail term can be taken as 0, and the
banded result is exact. Each widening costs one more banded pass.
For a general alphabet, check coverage against every row's actual reference
counter and the live range `0 .. m − k`; the binary-specific width test does
not apply when the reference contains larger arities. Since the reference is
fixed during cursor updates, the smallest half-width covering all rows is
`maxₖ max(n_r(k), m − k − n_r(k))` and can be computed once.
The starting `j` for `η = 10⁻⁴`:

| `S` | `j` | band width `W` |
|---:|---:|---:|
| 0.04 | 3 | 9 |
| 0.18 | 4 | 13 |
| 0.71 | 7 | 25 |
| 3 | 14 | 53 |

The rows span top-rung readings at depths 8, 6 and 4 (`S` scales with the
word count) and the order of magnitude of bottom-rung readings at depth 8.

## 23.4 Splitting at the climbed word

**Theorem 23.7.** The sum over all sequences splits at any
position into prefixes, each weighted by the sum over suffixes from the state
the prefix ends in. Grouping prefixes by their end state gives

> `Z = Σₙ F_k(n) · Σₐ qₖ(a) · B_{k+1}(δ(n, a))`,

with `F_k` the forward vector before word `k` and `B_{k+1}` the backward
vector after it.

**Theorem 23.8.** With nonnegative weights, the best score splits the same
way, with `max` in place of the sums:

> `x = maxₙ F^max_k(n) · maxₐ qₖ(a) · B^max_{k+1}(δ(n, a))`,

where `F^max_k(n)` is the best weight of a prefix ending in state `n` and
`B^max_{k+1}` the best score of a suffix. Nonnegativity is needed because
`c · max(u, v) = max(c u, c v)` only for `c ≥ 0`.

A climb changes only `qₖ`. With `F_k` and `B_{k+1}` current, the new `Z` and
the new maximal weight cost `O(3 · Wₖ)` operations, where `Wₖ` is the
number of states at `k`. What must be maintained are the vectors themselves:

- `F_i` depends only on words before `i`;
- `B_i` depends only on words from `i` on.

The cursor stores each row's admitted states contiguously, with a prefix sum of
row lengths giving its starting offset. State `s` in row `k` is stored at
`offset[k] + s - low[k]`. The four tables use space proportional to the sum of
the row widths, plus `O(m)` offsets; empty rows use no table cells. This is at
most `O(m W)` for largest row width `W`, including when the band is far from
zero.

During a sweep, the nonzero sum and maximum entries of a source row lie in an
enclosing interval. States outside that interval contribute neither mass nor
maximum weight, so each transition range may be intersected with it. The
interval may include unreachable holes; it is a conservative envelope, not an
assumption that reachable states are contiguous. Scoring a replacement row
and locating the traceback junction intersect the prefix envelope with the
suffix envelope translated back through the transition for each arity.

After a climb at `p`, every `F_i` with `i ≤ p` and every `B_i` with `i > p`
stays valid. The next climb at `k` needs `F_k`, which costs recomputing the
forward vectors from `p` to `k` (or the backward ones, if `k < p`). The
split point moves like a cursor, and each step costs the states it sweeps.
Refinement climbs in charge order, which is spatially unordered.

**Theorem 23.9.** Over all ordered pairs of positions among `m`,
`Σᵢ Σⱼ |i − j| = (m³ − m) / 3`.

So if consecutive climbs fall at independent uniform positions, the cursor
sweeps `(m² − 1) / (3m) < m / 3` positions per climb on average. Climbs that
cluster sweep less; the premise is an upper reference, not a guarantee.

**Charges need not be fresh.** The account's validity requires only that
the charges sum to the bound (§19.6). The bound `R_band + Σ_{k ∈ E} rₖ` is
recomputed exactly at every step. `E` comes from the certificate dynamic
program over the decoded tree, which costs `O(m)`. The bound is split in
proportion to marginals `μₖ` from the last full refresh. Stale marginals can
only change which word climbs next, never the validity of the bound. A full
refresh of the marginals costs one banded forward–backward pass and can be
amortized, for instance once every `√m` climbs.

**Theorem 23.11 (stale priority allocation).** Let nonnegative priorities
`hₖ` have positive sum `H`, and let the current sequence risk be `R ≥ 0`.
The charges `cₖ = R hₖ / H` are nonnegative and sum exactly to `R`,
regardless of when the priorities were computed. Thus stale priorities may
allocate the current risk without changing its total. This does not permit
caching the risk itself: `R` and the within-certificate risk must still be
current. If every priority is zero, a nonempty set of `m` items can instead
receive uniform charges `R / m`.

**Theorem 23.12 (revision cache invariant).** Suppose a cached quantity
is a deterministic function `f(v)` of an item's revision `v`. Reusing a
cached value `f(v₀)` is exact whenever `v = v₀`. The revision must identify
both the observation and its calibration; equality of raw observations
alone is insufficient. Revisions are scoped to one refinement run, whose
experts and calibration parameters remain fixed.

**Theorem 23.13 (one-sided numerical allowance).** Let `q(x)` be the
true error probability, `b(x)` a valid real-valued bound, and `b̂(x)` its
numerical evaluation. Suppose `q(x) ≤ b(x) ≤ b̂(x) + ε(x)`. Answering only
where `b̂(x) + ε(x) ≤ δ` bounds the weighted error among answered inputs
by `δ` times their total weight, for any nonnegative input weights.
This follows by applying selective risk to the upper envelope `b̂ + ε`.
The allowance must be justified for the actual calculation; a maximum
observed on finitely many examples does not establish the premise.

**Threshold stability.** If two evaluations differ by at most `ε`, their
answer/refuse decisions agree whenever the reference evaluation is either
at most `δ − ε` or strictly greater than `δ + ε`. Between these margins,
arbitrarily small numerical changes can change a threshold decision.
This concerns numerical evaluation of a valid bound, separately from
whether its statistical modeling assumptions hold.

Without a certified pointwise numerical allowance, the distribution-level
audit of §17 can instead certify the entire answering policy. Candidate
policies must be fixed independently of the checking sample and must use
the same numerical decision rule during checking and deployment. A change
to that rule produces a new policy; observed agreement on a finite sample
does not itself transfer the earlier policy's guarantee.

The decoded sequence must still be recovered after each step, to evaluate
the formula and find `E`. It too is read from the split, without a sweep.

**Theorem 23.10.** Let a prefix `u` of the first `k` words end in state `n`,
let `v` be a suffix of the remaining words from state `δ(n, a)`, and let
`u a v` be accepted. Its weight is

> `w(u) · qₖ(a) · w(v)`.

If `w(u) = F^max_k(n)`, `w(v) = B^max_{k+1}(δ(n, a))`, and `(n, a)` attains
the maximum of Theorem 23.8, then `u a v` is a best sequence.

The best prefix ending in `n` is traced backwards through the forward max
vectors: at each position, a predecessor state and arity whose product
attains the vector entry. The best suffix is traced forwards through the
backward max vectors in the same way. With the vectors current on either
side of the climbed word, as they are after Theorem 23.8 scores it, the
decoded sequence costs `O(3 m)` comparisons and no recomputed vectors.
This construction requires a positive-weight accepted path. When none
exists, the maximum log weight is `−∞` and there is no sequence to trace;
subsequent row updates can restore one.

**Banding with a moving cursor.** Theorems 23.1–23.6 hold for *any*
reference sequence `r`, not only the per-word argmax. So the reference, and
with it the band's centre at every position, is fixed when the band is
built and kept through later climbs, even where a climb changes a word's
most probable arity. Only `S = Σₖ ρₖ`, with `ρₖ` the climbed word's mass off
`rₖ`, changes, and it is updated in `O(1)` per climb. A climb that moves a
word's mass away from its reference raises `S`, and with it `U_j`; the band is
rebuilt wider (§23.3) only when `U_j > η · Z_band`.

With the centre fixed, the band is a position-dependent restriction of the
counter automaton: pair each state with its position and send states outside
the band to the dead state. That is again a deterministic automaton, so the
splits of Theorems 23.7 and 23.8 apply to the banded programs unchanged, and
the cursor sweeps `W` states per position instead of up to `min(k + 1, m − k)`.

**Theorem 23.14 (row normalization preserves ordering).** Multiplying all
weights in position `k` by a positive constant changes every complete
sequence's log score by the same sum of row log constants. Subtracting a
common constant preserves score ordering. Therefore normalizing each
positive-mass row leaves the set of maximizing sequences unchanged.
Zero-mass rows admit no positive-weight complete sequence and must be
handled separately.

**Theorem 23.15 (eviction preserves exact lookup).** Let `f : K → V` be a
deterministic computation and let a cache contain only pairs `(k, f(k))`.
A lookup that returns the cached value on a hit and computes `f(k)` on a
miss always returns `f(k)`. Removing any entries or inserting a freshly
computed pair preserves this invariant, independently of the eviction policy
or capacity. The key must include every input on which `f` depends; the result
does not justify reusing a value after an unrepresented input changes.

## 23.5 Predicted operation counts

Per refinement step, counting multiply-adds over the arity alternatives:

- **exact from scratch:** forward, backward and max passes, `2.25 m²`;
- **banded from scratch:** `9 m W`, capped by the live states;
- **incremental:** a sweep of `m / 3` positions for the sum and max forward
  vectors, `0.5 m²` exact or `2 m W` banded.

`W` is taken at the top-rung `S` for each depth, with `η = 10⁻⁴`.

| depth | words `m` | `W` | exact | banded | incremental exact | incremental banded | one top-rung word |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 35 | 9 | 2.8k | 2.8k (no gain) | 0.6k | 0.6k | 103k |
| 6 | 143 | 13 | 46k | 17k | 10k | 3.7k | 103k |
| 8 | 575 | 25 | 744k | 129k | 165k | 29k | 103k |

At depth 8, banding and splitting together cut the per-step decoding cost
from about seven word readings to about a quarter of one, a factor of 26.
At depth 4 the band already covers every live state, and only splitting
helps.

## 23.7 Exact decoding in linear space

Before banding, the exact passes can be made cheap per operation. The
log-space recursion of §21.4 pays a logarithm and an exponential for every
transition. In linear space with each forward row rescaled to total 1, a
transition is one multiply-add. If `c_k` is the total of forward row `k`
computed from the rescaled row `k − 1` (`c_0 = 1`), then `log Z = Σ_k log
c_k`. With the backward rows divided by the same totals, a marginal is
`F̂_k(n) q_k(a) B̂_{k+1}(δ(n, a)) / c_{k+1}`. The rescaling only factors
constants out of `dpSum`, so the results are exact. The most probable sequence
stays in log space, where it needs only additions.

The same rescaling can be applied to the cursor of §23.4. Store each forward row as
`F̂_k = F_k / C_k` with `log C_k`, and each backward row as `B̂_k = B_k / D_k`
with `log D_k`. A row recomputed from its neighbour costs one multiply-add per
transition, one division per state and one logarithm per row:
`log C_{k+1} = log C_k + log Σₙ F̃_{k+1}(n)`, with `F̃_{k+1}` the unnormalized row
computed from `F̂_k`. The split of Theorem 23.7 becomes

> `log Z = log C_k + log D_{k+1} + log Σₙ F̂_k(n) Σₐ qₖ(a) B̂_{k+1}(δ(n, a))`,

since both factors come out of the double sum. The band restricts which
states a row holds, not how it is scaled, so banding is unaffected. A row
whose total is 0 has no accepted continuation through it; it is stored as
zeros with `log C = −∞`, and so is every row computed from it in exact
arithmetic. In floating point, a nonzero path can still underflow within a
scaled row. The incremental cursor therefore stores its sum tables in log
space; this preserves finite log weights across that failure mode, at the
cost of more expensive transitions. Other floating-point errors remain.
If a finite log-weight addition overflows, cursor sweeps and split scoring
report an arithmetic error instead of treating the path as unreachable. A
failed row update leaves the previous row unchanged.
In the log semiring, an unreachable state or zero-weight transition has
weight `−∞` and contributes nothing to a sum or maximum. The cursor may
skip those contributions, and may insert the first finite contribution
directly, without changing the real-arithmetic recurrence.
The cursor also intersects each row's band with the format decoder's
arity-dependent prefix reachability bound from §21.4. Later row updates
cannot make a state beyond that bound reachable.
The nonincremental band pass can also use unchecked additions when each
finite input is bounded by `MAX / (4(m+1))`, where `MAX` is the largest
binary64 value. An `m`-word path then stays within `MAX/4` in magnitude;
the log of the finite number of representable input paths is negligible
relative to the remaining range. Larger inputs use checked additions.

[Theory index](../THEORY.md)
