# 28. Packages as experts

## 28.1 Objects and references

A system built from many independently contributed experts needs a unit of
distribution larger than one expert, and an identity for each unit that does
not depend on who holds it. Every unit here is an immutable *object*, and its
identity is a cryptographic digest of its canonical encoding, its
*reference*. There are three kinds of object:

- a **primitive**: one expert, given by its manifest (contract, cost,
  declared slot calls and effects) and how to load its implementation,
  including the digest of its weights;
- a **composite**: an ordered list of member references, the slots it
  requires and the contracts it exports;
- an **attestation**: a claim about another object (§28.4).

A composite names its members by reference, so composites form a directed
graph whose nodes may be shared by many parents. Since a reference is
computed from contents that include the members' references, a composite
cannot contain itself, directly or through others, unless the digest has a
collision. Under the usual assumption that collisions are infeasible to
find, the graph is acyclic, and equal references mean equal objects.

## 28.2 Composites and their order

A package is an expert or an ordered list of packages. Its *flattening* lists
the contracts of its experts in member order:

> `flatten(expert c) = [c]`, `flatten(composite ps) = flatten(p₁) ++ … ++ flatten(pₙ)`.

**Theorem 28.1 (flattening respects order).** Flattening a concatenation of
member lists concatenates their flattenings.

Installation order is the stable planner's priority (§3): a task's route is
planned in the shortest library prefix that solves it. A *transparent*
composite exports every member, and installing it appends its flattening.

**Theorem 28.2 (installing a package keeps every route).** If a library
solves a task, appending the flattening of any package does not change the
task's route.

*Proof.* Theorem 3.3 applied to the flattening. ∎

An implementation may drop later repetitions of an expert already present;
the planner reads the first occurrence first, so the order of first
occurrences is what it sees. That removal is not part of the formal model.

## 28.3 Exports: packages are experts

An *exporting* composite offers contracts `c₁, …, cₖ` and hides its members.
Each exported contract `c` has an implementation: a plan for `c.output` from
`c.inputs` over the composite's members and the experts its surroundings
supply. The composite *requires* those as slots `σ₁, …, σₘ`, and seen from
outside, export `c` is the higher-order contract `c` with slots `σ₁, …, σₘ`
(§20). The surrounding planner fills the requirements exactly as it fills any
slot, and nothing else about the composite is visible.

*Inlining* replaces each application of `c` in a plan by its implementation
with the implementation's inputs instantiated by the application's
arguments. An input of type `t` is read as the first argument of type `t`, as
everywhere else in the type-keyed model; map bodies read only their element
and are left unchanged.

**Theorem 28.3 (packages are experts).** Let `c` be implemented by a plan
well-typed over `inner ++ lib` from `c.inputs` to `c.output`. Every plan
well-typed over `c :: lib` inlines to a plan of the same type over
`inner ++ lib`.

So a library may hold a composite in place of its members without changing
which tasks it can serve: every route through an export is a route through
the members. The converse fails by design. The members' intermediate types
are private, so a plan that needs one of them is not available outside, and
a composite whose authors want its members visible makes itself
transparent.

**Scoped planning.** Since exports hide their members, the outer planner's
index holds one entry per export rather than one per member. Each export's
route is planned once, in its own scope, by the stable planner, so
Theorem 28.2 also holds inside every composite. Requests made inside are
resolved by a kernel over the composite's own library (§14). Planning cost in
the outer scope depends on the number of exports, not the number of experts
behind them.

**Declared cost.** An export's cost is its route's cost: each invocation's
declared cost, a map body once per element, and an internal slot filling by
its declared calls, at an assumed sequence length. The number of calls to a
requirement is declared exactly when it is affine in the length, that is,
when no requirement is called inside nested maps.

## 28.4 Attestations

Calibration temperatures, audit results, measured costs and failure rates,
and signatures are *claims about* an expert, not part of it. An attestation
is an object naming its subject's reference, the kind of claim and the
claim. The subject stays immutable while evidence about it accumulates, any
party may publish evidence, and selecting among experts, as in route
upgrades (§8) or calibrated ladders (§16), reads attestations. An
attestation is evidence under its stated assumptions; its presence does not
make a claim true.

## 28.5 Effects and caching

A manifest may declare an expert's *effects*: what an invocation may do
besides computing its output from its inputs, such as drawing randomness or
reading the outside world. The empty declaration states that the expert is
*pure*: a function of its inputs. An undeclared expert promises nothing. A
composite must declare at least the effects of its members, so a pure
composite contains only pure experts.

A pure expert identified by reference `e` defines a function, and the pair
of `e` and the digest of an input determines the output. A *result cache*
maps such pairs to outputs.

**Theorem 28.4 (caching is invisible).** If every entry of a cache is the
function's value, reading through the cache and computing on a miss returns
the function's value, and storing a computed value or evicting entries
keeps every entry the function's value.

Caches can therefore be shared between machines and runs without changing
any answer, provided the declarations are true. A false purity declaration,
or a digest collision, breaks the premise, not the theorem; attestations
(§28.4) are where evidence of either is recorded.

## 28.6 Names and discovery

References identify contents; *names* are a separate, mutable map from
human-readable strings to references, so a name can move to a new version
while every reference stays valid. Contributions are found by name: each
installed distribution may offer packages under names of its choosing, and
discovery puts every offered package into the store and binds its name.

Discovered packages are installed after the library already present, in
name order, as the members of one transparent composite. By Theorem 28.2,
discovery never changes a route the library already had, whatever is
discovered. Among the discovered packages, name order is the planner's
priority: deterministic, so every installation of the same contributions
yields the same library, but a policy and not a measure of quality.
Selecting by evidence instead reads attestations (§28.4). A name offered
twice is ambiguous and is refused rather than resolved by an arbitrary
rule.
