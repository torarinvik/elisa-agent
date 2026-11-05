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
The first control instead checks complete finite deterministic support, then
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

[Theory index](../../THEORY.md)
