# 29. Types as objects

## 29.1 Constructors as objects

Experts compose only where their types are equal (§1.1), so a library of
independently contributed experts is only as coherent as its authors'
agreement on types. A qualified name such as `image.rgb.v1` makes accidental
collisions unlikely but binds nothing to it: two authors may use one name
for different things, and one thing may receive many names.

A *constructor object* is a content-addressed object (§28.1) stating a
constructor: a human-readable name and version, its arity, its *meaning* (a
statement of what its values are and how they are represented), and the
constructors it refines (§29.2). The constructor's identity is the object's
reference. Equal references are equal constructors, including their
meaning; authors who agree on a constructor share its reference, and
authors who disagree obtain different references and so never collide. The
name and version are labels, resolved through names (§28.6) like any other
object.

Type terms are unchanged (§1.1): a constructor is now either a reference or,
as before, a textual name whose identity is its text. A store admits an
expert or composite whose contracts mention a referenced constructor only
after that constructor, so every reference in an admitted contract
resolves.

## 29.2 Refinement

A constructor `S` may declare that it *refines* constructors `T₁, …, Tₖ` of
the same arity: for all arguments, every value of `S(t₁, …, tₙ)` is a value
of `Tᵢ(t₁, …, tₙ)` with the same representation. The declaration is part of
`S`'s contents, so only `S`'s author can make it, nobody can later declare
an existing constructor to refine theirs, and, as for composites (§28.1),
the refinement graph is acyclic unless the digest has a collision.

*Subtyping* `≤` on ground terms is the reflexive–transitive closure of
`S(ts) ≤ T(ts)` for declared refinements. Arguments must be equal: no
variance is claimed, since whether `seq(S) ≤ seq(T)` follows depends on the
representation of sequences, which a refinement of `S` cannot speak for.

Section 1.1 rejects subtyping as an unverifiable claim that one author can
make wrongly for every route crossing it. A refinement is narrower: it is
made by the owner of the refining constructor, about values only that
constructor's experts produce, and it is realized by adapters (§29.3), so
it is planned, costed and replaceable by evidence (§8) like any other
module.

## 29.3 Subsumption is coercion

For each declared refinement of `S` by `T`, the *upcast* is an adapter with
contract `S(α₁, …, αₙ) → T(α₁, …, αₙ)` that returns its input. A plan is
typed *with subsumption* if, besides the rules of §1, a plan of type `s`
also has type `t` whenever `s` refines `t` in one step; chains of steps
give `≤`. *Erasure* removes every application of an upcast, keeping its
argument.

**Theorem 29.1 (subsumption is coercion).** Let the upcasts include one
adapter for every refinement step, and let no installed module be an
upcast. Every plan typed with subsumption over a library is the erasure of
a plan typed without subsumption over the library followed by the upcasts.

So the planner needs no subtyping rule: installing a constructor's upcasts
lets ordinary planning find every route that subsumption allows.

**Theorem 29.2 (coherence).** If every upcast computes the identity, a plan
and its erasure compute the same value. Hence any two plans with the same
erasure, in particular any two ways of inserting upcasts into one plan,
compute the same value.

*Proof.* By induction on the plan: an upcast application computes the value
of its argument, and every other node computes the same function of its
children in both plans. ∎

**Theorem 29.3 (refinements are local).** Installing a constructor's upcasts
after a library keeps every route the library already had (Theorem 3.3).
An upcast consumes only values of the refining constructor, so a wrong
refinement can affect only routes through such values, all of which pass
through experts that use the refining constructor.

## 29.4 Hub types

Refinement (§29.2) relates a constructor to more general ones its author names.
It does not connect independently designed types that mean the same thing. A
*hub* is a constructor `H` chosen by contributors as a shared medium: each
contributor type `Tᵢ` supplies an encoder `Tᵢ → H` and a decoder `H → Tᵢ`. The
core defines no hub; it is an ordinary constructor, and its connectors are
ordinary experts, planned, costed and replaced by evidence.

**Theorem 29.4 (hub connectors).** For a set `S` of contributor types:

1. the hub connectors number exactly `2|S|`;
2. every ordered pair `(Tᵢ, Tⱼ)` is joined by a two-step route
   `Tᵢ → H → Tⱼ`;
3. without a shared type, single-step translators joining every ordered pair
   of distinct types number at least `|S|(|S| - 1)`;
4. adding a contributor type adds only connectors touching it, so every
   existing connector and route remains (with Theorem 3.3);
5. a hub route fails only if its encoder or its decoder fails, so its risk is
   at most the sum of theirs, whatever `|S|` is.

*Proof.* (1) The encoders and decoders are images of `S` under injective maps
with disjoint ranges. (2) Both connectors are present. (3) The required
translators contain the off-diagonal pairs of `S`. (4) The connector set is
monotone in `S`. (5) Union bound. ∎

A hub trades quadratic growth for one extra hop: every translation composes
two connectors, so its error is roughly that of two hops rather than one. A
lossy hub (an encoder that is not injective on the values that matter) cannot
be repaired downstream; whether a hub is adequate for a pair of types is an
empirical question for its connectors' evidence.
