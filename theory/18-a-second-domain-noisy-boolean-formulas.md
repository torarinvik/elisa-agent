# 18. A second domain: noisy Boolean formulas

## 18.1 The task

Everything up to §17 was shown on handwritten arithmetic. The machinery is
meant to be generic, so the claim needs a second task that shares nothing
with the first except the kernel: different inputs, different experts, and
a different structure of what the answer depends on.

**Input.** A Boolean formula in prefix (Polish) notation, written as text
whose words have passed through a noisy channel (typing errors). The
vocabulary is `true`, `false`, `not`, `and`, `or`, `xor`. For example, the
formula `and or true false not false` might arrive as
`anf ot tru fasle nto flase`. Prefix notation needs no brackets: arities
alone determine the formula (§18.5).

**Output.** The formula's truth value.

**Channel.** Each character independently, at noise level `ν`, is replaced by
a random letter with probability `ν/2`, deleted with probability `ν/5`,
followed by an inserted random letter with probability `ν/5`, or swapped with
the next character with probability `ν/10`. A word never becomes empty (a
fully deleted word keeps one random letter). Spaces are not corrupted, so
word boundaries are known. A noise shift is a larger `ν` in use than in calibration; a structural
shift changes the formula generator as described below.

**Formulas.** Complete binary trees of depth `d` (`n = 2^d` leaves) whose
levels alternate between `and` and `or` (root chosen at random), with uniform
random leaves, each leaf negated (`not`) with probability ¼. A variant
replaces each connective by `xor` with probability `x`.

**Structural-shift variant.** At every node with positive remaining depth,
stop with probability `p ∈ [0,1]` and draw a leaf (optionally negated) instead
of a binary connective. Otherwise recurse into both children. The default
`p=0` recovers the complete family; `p=1` stops at the root. Every resulting
formula has height at most `d+1`, but its length or shape may lie outside
the complete-tree prior's support. Reader vocabulary and the typing channel
are unchanged.

Let `L_d` and `I_d` denote expected constant leaves and binary branches.
The recurrences are `L_0=1`, `I_0=0`,
`L_{d+1}=p+2(1-p)L_d` and `I_{d+1}=(1-p)(1+2I_d)`.
Induction gives `I_d=L_d−1`. With independent leaf-negation probability η,
expected word count is `(2+η)L_d−1`. These are expectations of the generator,
not posterior risk claims for a decoder.

**Symbolic reader recurrence.** For code-point strings x and y, let D(i,j)
be the optimal-string-alignment distance between their prefixes of lengths
i and j. Set D(0,j)=j and D(i,0)=i. For positive i and j, take the minimum
of D(i−1,j)+1, D(i,j−1)+1 and D(i−1,j−1)+1[xᵢ≠yⱼ]. If i,j≥2 and
xᵢ=yⱼ₋₁, xᵢ₋₁=yⱼ, also admit D(i−2,j−2)+1. Indices here start at one.
This is the existing reader's restricted alignment recurrence, not an
unrestricted edit metric permitting arbitrary overlapping transpositions.
Only the current left cell and the two preceding rows are needed, so three
cyclic rows use O(|y|) memory and O(|x|·|y|) time.
The recurrence is symmetric in the two strings, so the shorter string can
be used for the rows, reducing working memory to O(min(|x|, |y|)).
Empty-prefix distances are their lengths, identical prefixes have distance zero, and
D(i,j)≤max(i,j), since substitutions plus insertions/deletions suffice.
The reader uses p(w) proportional to exp(−D(|x|,|w|)); this symbolic score
is not itself a calibrated channel likelihood.

## 18.2 What carries over, and what must not be added

The kernel, the planner, ladders, calibration, refinement and certification
are reused unchanged. The domain contributes only experts: a tokenizer, two
word readers and a formula evaluator, each with an ordinary contract. Two
generic extensions are needed. Each is proved, and each reduces exactly to
the earlier behavior on arithmetic.

1. **Grouped decisions (§18.3).** A decision may choose a *group* of classes,
   not one class. Restriction (§16) is the special case of singleton groups.
2. **Value-dependent certificates (§18.4).** Which readings the answer
   depends on may depend on the readings themselves. Static demand (§14) is
   the special case that ignores them.

## 18.3 Grouped decisions

To parse a prefix formula, the evaluator needs every word's **arity**: 0 for
`true` and `false`, 1 for `not`, 2 for the connectives. It needs a word's
identity only where that word's value is used (§18.5). A decision of the
first kind chooses among the groups `{true, false}`, `{not}` and
`{and, or, xor}`.

**Definition.** A *grouped decision* is a partition `G` of a set `C` of a
reading's classes. Given a reading `p`, it chooses the group `g*` that
contains the most probable class of `C`. Its risk is

> `1 − p(g*) / p(C)`,

the probability, under the reading, that the true class lies in `C` but
outside the chosen group. With singleton groups this is the restricted risk
`1 − max_C p / p(C)` of §16. With `C` all classes and singleton groups, it is
the class risk `1 − max p`.

For a total group map `g : C → G`, define `q(a) = Σ_{c : g(c)=a} p(c)`.
Every class contributes to exactly one group, so `Σ_a q(a) = Σ_c p(c)`;
nonnegative class masses give nonnegative group masses. Thus grouping a
normalized class distribution produces a normalized group distribution,
including zero mass for empty groups. Raw answer decoding and calibrated
risk estimation can use this same grouping operation on their respective
readings without identifying those readings with each other.

**Theorem 18.1.** If the chosen
group contains the most probable class `a`, then `p(a) ≤ p(g*)`, so the group
risk is at most the class risk `1 − p(a) / p(C)`. Coarser decisions never
carry more risk than finer ones under the same reading.

The group is chosen by the most probable *class*, not the heaviest group,
because that is the decision the consumer actually makes: it reads the word
as its most probable class and takes the arity from there. Choosing the
heaviest group could pair a word's identity with a different word's arity.

**Calibration.** As in §16, each decision gets its own temperature. It is
fitted by negative log-likelihood of the *group* labels on held-out inputs
whose label lies in `C`, the group probability being the sum of the
temperature-scaled class probabilities in the group. The inequality above
holds under one temperature. With separately fitted temperatures it may
fail numerically, so the controller never assumes it: it computes every
risk it uses.

## 18.4 Value-dependent certificates

In arithmetic every demanded reading matters whatever the other readings
say. Here that is false: `and false x` is `false` whatever `x` is, so once
`false` is read with confidence, the identity of every word inside `x` is
irrelevant, and only its arity (needed to find where `x` ends) is not.

**Definition.** Let `r` be the readings of all items and `t` the truth. A
*certificate* assigns, to each reading `r`, an agreement relation
`∼_{cert(r), i}` for each item `i`: equality of class, equality of group, or
the total relation ("nothing demanded"). It *certifies* `f` when

> `∀ r t, (∀ i, t_i ∼_{cert(r), i} r_i) ⇒ f(t) = f(r)`.

The certificate is computed from the reading. It never needs the truth,
which is unknown. Note the asymmetry: `cert(t)` may differ from `cert(r)`,
and only `cert(r)` matters.

**Theorem 18.2.** For any
distribution of the truth given the reading `r`,

> `P(f(t) ≠ f(r) | r) ≤ Σ_i P(t_i ≁_{cert(r), i} r_i | r)`,

and items demanding nothing contribute nothing. The proof: if every
demanded agreement holds, the answer is right, so a wrong answer violates
some demanded agreement, and the union bound applies.

With per-decision risks calibrated given the reading, the bound is
`Σ_{i ∈ cert(r)} risk_i(decision_i)`. This is the same premise as in §16: each
item's error probability, given the readings, is its calibrated risk. Static
demand is the certificate that ignores `r`. `DemandSound` (§14) is the
special case where all readings agreeing on a fixed demand give the same
answer.

**Choice of certificate.** One reading can have several valid certificates
(`and false false` can use either child). The controller may choose the one
with least risk. The choice depends on `r` only, so validity is unaffected.

## 18.5 Certificates for prefix formulas

**Trees.** Formula trees carry an annotation at each node
(for a reading: the node's risks), evaluated in the usual way. A certificate
is a tree of choices:

- `leaf` at constants;
- `not c` at negations;
- `both c d` at a connective, evaluating both children;
- `left c` (or `right c`) at a connective, evaluating one child and skipping
  the other.

A certificate is *valid* for a reading when it skips a child only if the
other child's read value is *absorbing* for the connective: `false` for
`and`, `true` for `or`, never for `xor`. A truth `t` *agrees* with the reading
`r` on a certificate when it has the same constructor, connective and
constant at every evaluated node. Skipped subtrees are unconstrained.

| Theorem | Statement |
|---|---|
| 18.3 | if `c` is valid for `r` and `t` agrees with `r` on `c`, then `t` and `r` have the same value |
| 18.4 | with a weight per node (`w_full` where evaluated, `w_shape` throughout skipped subtrees), the node-by-node choice `bestCert` is valid and weighs no more than any valid certificate |
| 18.5 | `bestCert` weighs no more than evaluating every node |
| 18.6 | if one formula's arity sequence followed by `a` equals another's followed by `b`, the arity sequences are equal and `a = b` |

**Words.** The words of a formula are its preorder. By Theorem 18.6, the
arity sequence of a word sequence determines the tree's shape and where each
subformula ends. If every word's arity decision is right, the read tree and
the true tree have the same shape, and the node at preorder position `k` is
word `k` in both. The word-level certificate is therefore:

- the **arity decision** at every word;
- the **full decision** at every word that is a node `bestCert` evaluates.

Agreement on these gives agreement on the tree certificate, and Theorem 18.3
gives the right answer, so this certifies the evaluator in the sense of
§18.4. If the read arities do not form a formula, no answer is certified:
some arity decision is certainly wrong.

**Weights.** For a word evaluated in the certificate, the weight is the risk
of its full decision. For a skipped word, it is the risk of its arity
decision. `bestCert` is then the least-risk certificate, computed bottom-up in
one pass over the words. Its bound never exceeds the static bound that
decides every word fully (Theorem 18.5).

## 18.6 How certificates scale

**Theorem 18.7.** Every complete alternating
`and`/`or` tree of depth `d`, whatever its leaf values, has a valid certificate
evaluating at most `2^⌈d/2⌉` of its `n = 2^d` leaves: about `√n`.

*Proof idea.* Write `L(d)` for the number of leaves needed. An `and` node
reading `true` needs both children. Each child is an `or` reading `true`, so
it needs one child, an `and` two levels down. An `and` node reading `false`
needs one child. That child is an `or` reading `false`, so it needs both of
its children. Either way `L(d) ≤ 2 · L(d − 2)`, with `L(0) = 1` and
`L(1) ≤ 2`. `or` nodes are dual. Negated leaves leave this unchanged: a
negation sits on a leaf and is evaluated with it.

The evaluated connectives along these paths number `O(√n)` as well. So for
per-word risks `ρ_full` (full decision) and `ρ_shape` (arity decision), the
certificate bound on a formula with `m ≈ 2.25 n` words is about

> `m · ρ_shape + c √n · ρ_full`,

against `m · ρ_full` for static demand. The length limit of §16
(Theorem 16.3) changes from `n ≲ δ / ρ_full` to roughly
`n ≲ (δ / ρ_full)²`, until the shape term dominates at
`n ≈ δ / ρ_shape`. Arity decisions are easy: `true`/`false` look nothing like
the connectives. So `ρ_shape ≪ ρ_full`, and the gain is large exactly where
static demand fails.

**Control.** `xor` has no absorbing value, so on all-`xor` formulas every
valid certificate evaluates everything, and the certificate bound equals the
static bound, which makes the `xor` variant a control.

## 18.7 Refinement with certificates

`refine` (§16) generalizes as follows:

1. Read every item on its bottom rung.
2. Ask the consumer for its least-risk certificate of the current readings.
   The consumer receives the readings and a function returning any item's
   risk under any decision.
3. If the certificate's bound is at most `δ`, answer.
4. Otherwise climb the item with the largest contribution to the bound among
   the certificate's items that have a rung left.
5. If none has, abstain. If the readings determine no answer, climb the
   riskiest item.

A consumer that declares no certificate gets the static certificate: every
item with its fixed decision. That is the old procedure, step for step.

Remarks:

- **Termination.** Every iteration climbs a rung, and ladders are finite.
- **Certificates move.** Climbing an item can change its reading, and
  therefore the certificate. A child read `false` may now read `true`, and
  its sibling, skipped until then, becomes needed. The bound is always
  recomputed from the current readings, so the decision to answer is a
  function of the final reading, and §18.4 applies to it. As in §16, the
  latest reading of an item is used, never the least risky one.
- **Efficiency.** The certificate costs one bottom-up pass over the words
  per climb. That is symbolic work, small next to an expert call. Items
  outside the certificate are never climbed, which is where the compute
  saving comes from.

[Theory index](../THEORY.md)
