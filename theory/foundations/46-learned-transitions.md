# 46. Learning consequences and planning

## 46.1 Experience is not yet a policy

Contributors supply states S, actions A and a stationary deterministic
transition T : S × A → S. An interaction supplies (s,a,T(s,a)), without
supplying a plan or a decomposition. A learned partial model
M : S × A → Option S refuses outside its observed support. Conflicting
observations invalidate a pair instead of selecting an answer. This first
mechanism is exact recall, not unseen-state generalization. Hidden state,
observation errors and stochastic effects violate its assumptions.

## 46.2 Supported rollout

Define R(M,s,[]) = Some s. For a::as, obtain M(s,a); on refusal return None,
otherwise continue from the predicted successor. Assume supported correctness:
M(s,a)=Some t implies T(s,a)=t, for every s,a,t. A sample alone does not prove
this assumption.

**Theorem 46.1 (supported rollout).** If supported correctness holds and
R(M,s,p)=Some t, executing p in T from s ends at t. Induct on p: the first
supported step agrees with T, then apply the induction hypothesis to its suffix.
The plan may be chosen adaptively using M. Unsupported steps refuse; execution
failures and changes in T are outside this statement.

## 46.3 Planning over supported predictions

Breadth-first search over a finite supplied action collection retains the
predicted state and action prefix of each entry. Every entry satisfies
R(M,s,p)=Some t by construction. Returning a state satisfying the supplied
goal predicate therefore gives a valid goal-reaching plan under Theorem 46.1.
A faithful state identity, stationarity and state-dependent goals justify
visiting each state once and retaining a shortest supported plan. Bounded
search can refuse despite an existing plan: exhaustion is not impossibility.
Model calls, including refused calls, consume the declared work allowance.
No task, action meaning or state representation is fixed by this mechanism.

## 46.4 Certification and the next limitation

Marginal one-step IID accuracy does not certify an adaptively selected plan:
search may select the model's errors. Conditional error bounds e_i valid at
every reached history give an any-error bound of sum e_i by the union bound;
marginal bounds without a shift or conditional guarantee cannot substitute.
The first control instead checks observed finite deterministic support, then
measures new planning episodes using only that learned model. Whole executed
episode success can separately use the existing fresh admission gate, covering
only its declared episode distribution. Model changes require new policy
certification unless the existing retention conditions justify reuse.
The remaining weakness is learning useful dynamics outside observed support;
exact recall and finite-state planning do not establish that capability.

## 46.5 What must be learned beyond recall

Let D be the observed state-action support and let (s,a) lie outside D.
If at least two successor states are possible and no further restriction is
placed on the transition class, there are two deterministic environments
agreeing on all observations but disagreeing at (s,a): retain every observed
edge and choose different successors only at that unobserved pair. Any learner
receiving those observations alone has the same evidence in both environments.
It cannot guarantee the correct unseen transition in both. More recall or more
planning over the same support does not remove this ambiguity.

Thus the next capability needs either new interactions or an explicit,
testable inductive restriction shared across transitions. A structured
transition learner must state that restriction and be tested on withheld
state-action pairs, with whole executed plans checked separately. This
identifiability argument is analytic; the formal theorem above establishes
supported rollout only, not a representation-learning or exploration rate.

## 46.6 Generalization through an explicit hypothesis family

Let H be a finite supplied family of deterministic transition predictors.
After observing D, retain V = {h in H : h agrees with every observation}.
Predict at x only if V is nonempty and every retained h returns the same
answer y. Refusals or disagreements cause refusal, never an arbitrary tie.
Candidate enumeration must finish: truncating H can silently remove the truth.

**Theorem 46.2 (realizable unanimous prediction).** Suppose observations are
correct and the true transition belongs to H with the declared execution
budget. Filtering retains it. Every unanimous prediction therefore agrees
with it, including on unobserved inputs. Applying Theorem 46.1 gives correct
supported plans. This is a conditional generalization result, not a claim
that the chosen H contains an arbitrary environment or that agreement makes
an unrealizable family correct. Differential tests must include a missing-truth
family to expose this limitation. No label-efficiency rate follows.

A first external proposer enumerates bounded tuple-field copy constructions,
using the existing expression-to-route compiler and a separate family for each
observed action identifier. This is a declared structural bias; the core knows
neither tuple fields nor action meanings. The experiment holds out state-action
pairs, not just plans over remembered edges. All output observations and
execution interactions are counted independently of hypothesis evaluations.

## 46.7 Agreement and reach

Unanimity may establish many previously unseen one-step transitions while
still refusing the intermediate steps needed for a longer plan. Thus coverage
of transitions does not imply coverage of paths: planning requires agreement
at every state-action pair encountered. More diverse observations can eliminate
remaining consistent hypotheses, but improve coverage only under the stated
realizability assumption; they do not certify an incorrect hypothesis family.

## 46.8 Refining a version space

Adding correct observations filters the existing consistent family to a
subset. If the true predictor remains in that subset, any previously
unanimous prediction remains unanimous with the same answer, while some
previous disagreements may disappear. Thus additional observations cannot
remove an existing supported edge under realizability and deterministic,
unchanged predictors. Which observation expands reach most is a separate
search problem; no reduction per observation is guaranteed.

## 46.9 Choosing a disagreement

For each supplied candidate input, partition the retained predictors by their
predicted answer. If an observed answer belongs to a partition, refinement
retains exactly that partition. Selecting an input whose largest partition is
smallest maximizes the worst-case number eliminated among the supplied inputs.
It requires no oracle call to rank inputs; observing an answer is separate and
must be counted. If all predictors agree, no such observation reduces this
family. Realizability and correct observations remain assumptions, and the
rule does not promise that the most informative input is reachable or best for
a particular goal.

## 46.10 Reachability and observation access

When refinement preserves every previously supported edge, it also preserves
every plan using those edges. Newly supported edges can connect previously
disconnected paths. This conclusion assumes unchanged transition semantics,
faithful state identities and enough search budget: with finite budgets a
larger graph may change expansion order and lose a previously found plan.
Informative input selection also assumes an environment can be reset or
otherwise brought to the selected state; arbitrary-state access is not a
consequence of the model or of this result.

[Theory index](../../THEORY.md)
