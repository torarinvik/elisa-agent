# 1. Types and contracts

Semantic types `Ty` are abstract, with decidable equality and a sequence
former: `seq : Ty → Ty`, recognized by a partial inverse `elem?` with
`elem? u = some t ↔ u = seq t`.

A **contract** is a list of input types and one output type. Modules are known
to the system only through their contracts; two values are compatible exactly
when their types are equal.

A **plan** is a composition graph:

| Plan | Meaning |
|---|---|
| `given t` | a task input of type `t` |
| `apply c ps` | contract `c` applied to the outputs of sub-plans `ps` |
| `map a body src` | `body` run on each element (of type `a`) of the sequence `src` produces; inside `body` the element is the only input |

**Well-typedness** `WellTyped lib avail p t`: `p` uses
only installed contracts `lib` and available inputs `avail`, and produces `t`.

| Rule | Premises | Conclusion |
|---|---|---|
| given | `t ∈ avail` | `given t : t` |
| apply | `c ∈ lib`, `ps : c.inputs` pointwise | `apply c ps : c.output` |
| map | `body : e` under inputs `[a]`, `src : seq a` | `map a body src : seq e` |

**Theorem 1.1 (monotonicity).** If `lib ⊆ lib'`, every plan
well-typed under `lib` is well-typed under `lib'`. Installing modules never
invalidates an existing valid composition.

## 1.1 Type terms

Types are first-order terms. Fix a set of **constructors**, each a name with
an arity. A name is qualified by a namespace and a version, so names chosen
independently by different authors never coincide. Terms are built from
constructors and **type variables**:

> `t ::= α | C(t₁, …, tₙ)`, with `C` of arity `n`.

A term without variables is **ground**. Constants are constructors of arity
0, and `seq` is the constructor of arity 1 with `elem?(seq(t)) = t`. Since
distinct constructors build distinct terms and every constructor is injective
in its arguments, `elem?` satisfies the specification above, and terms are an
instance of `Ty`.

Compatibility stays equality of terms. A *subtyping* relation would claim
that every value of one type is a valid value of another. That is a property
of representations, which no contract can check and an author can claim
wrongly, and one wrong claim would change the meaning of every route that
crosses it. Conversions are instead modules: an **adapter** with contract
`A → B` is planned, accounted for and replaced by evidence (§8) like any other
module. Values cross versions and namespaces only through adapters.

Section 29 identifies constructors by content and admits one restricted
claim, refinement by the owner of the refining constructor, realized by
adapters; compatibility remains equality of terms.

## 1.2 Substitution

A **substitution** `σ` maps type variables to terms. It acts on a term by
replacing each variable, `σ(C(t₁, …, tₙ)) = C(σt₁, …, σtₙ)`, and on contracts,
plans and lists of types pointwise.

**Theorem 1.2 (typing is stable under substitution).** If
`WellTyped lib avail p t`, then `WellTyped σ(lib) σ(avail) σ(p) σ(t)`.

The proof is by induction on the typing derivation. The only fact it needs
beyond the pointwise action is `σ(seq(a)) = seq(σa)`. A composition built
over type variables is therefore valid at every instantiation of them: a
generic composition is checked once and holds for every type it is used at.

A contract with variables is **polymorphic** and stands for the set of its
instances `σ(c)`. A module that sorts sequences, for instance, declares
`seq(α) → seq(α)` once instead of once per element type.

[Theory index](../THEORY.md)
