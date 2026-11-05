# 47. Product hypothesis implementation

## 47.1 Declaring a complete product

A product version space is constructed explicitly from an ordered finite set
of alternative predictors for each output component. Its hypothesis family
contains every combination of one predictor per component, including repeated
or extensionally equal predictors as distinct choices. It returns an ordinary
host tuple of component values; it creates no NCA value type or task-specific
contract. Coupled joint families continue to use the general version space;
they must never be silently replaced by the product of their projections.

Under total deterministic predictors, fixed call semantics and faithful
component/output equality, filtering component j by the j-th observed output
produces exactly the joint version retained by filtering whole hypotheses
(`training_version_eq`). The product count is the exact number of retained
joint hypotheses. A prediction is returned only when every component agrees;
otherwise it refuses. For a complete supplied input list, the largest joint
outcome partition is the product of per-component maxima
(`largest_output_partition`). Minimize that exact score, retaining input order
on ties. Empty output has one empty joint hypothesis. Empty component choice
sets, malformed output arity, incomplete candidate families and exhausted
budgets are errors or refusals, never evidence of a unique correct hypothesis.

## 47.2 Operational assumptions and accounting

The external structural transition library declares this product by
construction, compiles individual field projections as ordinary routes and
retains the original logical joint-family cap. Its supplied execution budget
is checked by compiling and executing one representative original whole route
on a training input; the current compiler gives all members the same route
shape and invocation cost. Component execution counts are reported separately
from logical candidates. This check depends on the compiler and runtime
retaining that equal-cost property across members.

The algebra establishes equality of results, not equality of evaluation order,
side effects, exceptions, numerical values with non-equivalence equality, or
intermediate runtime budgets. Predictors must be pure and total on the declared
input domain, output equality must be faithful, and whole-route and component
execution budgets must be sufficient for every evaluated route. A caller
whose domain cannot satisfy these assumptions must use the explicit joint
version space. These are explicit representation and execution assumptions,
not claims derived from a few training cases.

A logical joint-hypothesis cap is distinct from the physical number of stored
component choices. Work counters report component predictor calls rather than
pretending they are whole-route evaluations. No real-world result becomes
certified by this representation change: an eventual fixed whole policy still
uses independent fresh gate and audit streams. Differential checks against
explicit enumeration cover predictions, refusals, refinement and ranking on
finite product families; coupled and noninjectively assembled output examples
remain counterexamples to applying the shortcut outside its declared scope.

## 47.3 Representation is not capability

A product representation stores a joint version without listing its members;
it does not reduce the number of logically possible joint rules or prove that
the true rule lies in the declared family. It therefore changes neither the
realizability assumption nor the need for independent admission. A small
number of retained components after fitting is evidence about those observations,
not evidence that arbitrary future states or tasks will be represented. A
coupled or noninjectively assembled family remains outside this exact shortcut.

[Theory index](../../THEORY.md)
