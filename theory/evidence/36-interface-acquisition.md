# 36. Interface alignment acquisition

Continuation of [Acquiring experts](36-acquisition.md); section numbers remain stable.

## 36.56 Searching compatible adapter/consumer families

Freeze supplied source, teacher and consumer families. For each compatible triple,
fit a bridge from source observations to paired teacher observations, then compose
with a unary slot-free consumer whose input is the teacher's interface and whose
output is the external task type. External source/teacher signatures must match
the task inputs, slots and relevance. Skip incompatible metadata; bound fitted
triples explicitly. Retain source/teacher type declarations, but no teacher
implementation in the completed inference graph. Types remain distinct.

If a bridge agrees pointwise with its teacher, every consumer in a finite family
agrees after composition; Lean proves the resulting ordered map equality. This
is conditional, not a guarantee from training pairs. Consumers can still be
wrong for the task, so freeze complete candidates before independent end-to-end
selection under §36.3. The fit limit does not bound library scanning or fitter
computation. Stable models/data, faithful factories and useful teacher coverage
remain assumptions. No consumer implementation or task catalog enters the core.


## 36.57 Reusable shared interface alignment

Fit a source-to-teacher bridge independently of any final consumer, retaining
only source and learned adapter. Optionally fit it once per source/teacher pair
and share that same model across compatible consumer candidates. Candidate
budgets still count completed routes; no bridge is fitted for a pair with no
compatible consumer. Independent fitting remains the default, since sharing
changes the candidate family for stochastic fitters. Expose the bridge as an
explicit retained root when later consumers should install it independently.

For n > 0 consumers and r paired rows, one alignment requires r external paired
observations instead of n*r. Lean proves this count inequality, not runtime or
memory savings. Inference values are not cached; each route still invokes the
source. Existing conditional family agreement applies, with stable functional
models, faithful factories and independent end-to-end selection as assumptions.
The teacher adds no separate inference dependency.
