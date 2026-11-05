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

## 46.11 Observations reachable from the current state

For each supplied candidate state, use a bounded supported-plan search from the
current state. Rank disagreements only among candidates for which a plan was
found. Under the supported-correctness assumptions of §46.2, executing the
selected plan reaches the selected state; the subsequent action is an actual
interaction whose outcome can refine the model. No reset or arbitrary-state
oracle is assumed. Search refusal does not establish unreachability. A plan
consumes one real interaction per action, in addition to the observation action.

## 46.12 The supported-exploration barrier

If every disagreement is outside the current supported reachable set, a
strategy that only travels along unanimous predictions and only observes
reachable disagreements must refuse without acquiring evidence. Escaping that
barrier requires an additional mechanism, such as a permitted exploratory
action or observations from an external process. Its possible consequences,
budget and any refusal policy must be represented; supported-rollout soundness
alone cannot guarantee the result of an unsupported exploratory action.

## 46.13 Absorbing starts and the limits of exploration

Suppose every available action leaves the current environment state unchanged.
Induction over any finite action sequence shows that every executed trajectory
remains at that state, whether or not the model predicts the actions. Neither
uncertainty-guided action choice nor a longer interaction budget can access a
different state in that episode. Progress needs additional environment
capability, such as a supplied reset distribution, another initial episode, or
an action that actually leaves the state. This is an environment condition,
not a claim that every unsuccessful search begins in an absorbing state.

## 46.14 Independent initial episodes

Suppose a fixed model and candidate-search budget classify an initial state as
informative when an observation with at least two predicted outcomes is
reachable through supported transitions. If independent resets draw from a
fixed distribution with informative probability p, the probability of finding
at least one informative episode in k attempts is 1 − (1 − p)^k. This statement
requires independent draws and a fixed model until the first success; it gives
no positive bound when p is unknown or zero. Each reset and every executed
transition remains a separately counted interaction. Adaptation after a
successful observation requires a new conditional argument.

## 46.15 Episode access and inference

Multiple starts expand the available observation set only when the environment
actually grants resets or independently supplies new episodes. A sampled start
is an environment outcome, not an arbitrary state selected by the learner.
The probability formula in §46.14 does not certify a policy and a single
successful reset does not estimate its success rate reliably. The admitted
behaviour still requires fresh episode-level evaluation under its target
initial-state and goal distributions.

## 46.16 Misspecification and fresh tests

Unanimity across an incomplete hypothesis family is not evidence that the true
transition belongs to that family. If every retained hypothesis agrees on an
unseen input but the environment differs there, the proposal is confidently
wrong. A gate using fresh examples drawn after the proposal is fixed can reject
such a candidate according to its declared error criterion. A finite gate may
still miss rare errors; its confidence guarantee applies to its sampling
distribution and assumptions, not to every input or to adaptively selected
trajectories. Consequently, transition-level admission does not replace a fresh
whole-policy gate for an adaptive planner. Query, gate and audit streams must
remain separate, and failures must not be reported as certified predictions.

## 46.17 Fresh evaluation of a whole simulated policy

Fix the learned model and all planner and execution semantics before sampling
fresh IID episodes. Each episode supplies an initial state and goal, runs the
fixed policy against the environment, and labels success by its actual final
state. An independent admission gate can bound the policy's episode error on
that declared joint distribution under the existing gate assumptions; refusal
is an error. It does not certify other goal or start distributions, live-world
effect safety, or each intermediate prediction. Generating reachable goals by
simulated actions supplies task goals rather than demonstration plans, but the
actions used to create them and those used in policy execution must both be
counted. An independent post-admission audit is separate from the gate.

## 46.18 Episode distributions can hide planning depth

A distribution generated by several actions need not require several actions
to reach its goals. For example, identity and an involution generate only the
initial state and its one-step successor, however many actions are sampled.
A whole-policy gate over those episodes therefore tests at most one-step
reachability. To make a longer-horizon claim, the target distribution must
include goals whose shortest paths are longer, and those cases must be counted
and scored without using the gate data to choose the policy. Even then the
result remains specific to its sampled environment and distribution.

## 46.19 Testing a minimum required path length

For a finite deterministic evaluation environment, breadth-first traversal of
its transition graph computes shortest path lengths. A host can define an
episode distribution by uniformly sampling start/goal pairs with distance at
least d, and keep the graph and paths private from the learner. A fresh gate
on that fixed distribution tests policies on goals requiring at least d real
actions; a separate audit can estimate success under the same distribution.
The traversal uses environment transitions and must be included in the
interaction accounting. Selecting this distribution using the actual graph is
an evaluation capability, not a skill acquired by the agent. Admission is
conditional on the gate's sampling and fixed-policy assumptions and says
nothing about other environments or longer distances.

[Theory index](../../THEORY.md)
