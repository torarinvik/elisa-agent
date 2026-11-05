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

## 46.20 Refusal during whole-policy admission

A route that cannot resolve a requested subproblem returns no vote. Like an
exhausted route, it remains in the majority denominator; a single-route gate
therefore scores that case as failure. This rule applies to explicit runtime
refusals, not arbitrary implementation exceptions. It changes no confidence
allocation and does not turn untested candidates into admitted policies.

## 46.21 Early rejection and coverage

A zero-error gate may reject a proposed policy after its first refused episode.
That establishes failure of that admission attempt, not an estimate of the
policy's success rate or the fraction of goals it can reach. A deeper-goal
filter establishes the minimum distance of sampled episodes in the evaluator's
fixed transition graph, but does not reveal whether failure came from missing
observations, the hypothesis class, or the planner's work bound. Distinguishing
those causes requires an explicitly designed diagnostic with its own evidence.
The gate and any new proposal must use fresh draws after the prior test closes.

## 46.22 Distinguishing unsupported paths from search exhaustion

For a finite model graph with at most N distinct states and K supplied actions,
a breadth-first search that visits each state at most once makes at most N K
prediction calls. With at least that call budget and N retained-state slots,
and assuming faithful state identities, deterministic predictions and finite
calls, a returned refusal after complete traversal means there is no path in
that model's supported graph. It does not imply that the true environment has
no path. Comparing supported edges with independently supplied environment
transitions can identify model refusals, but those diagnostic environment
lookups are separate from policy certification and must be counted.

## 46.23 Ambiguous transitions as a planning bottleneck

If a model retains several consistent hypotheses for an action, its unanimous
predictor refuses at inputs where those hypotheses disagree. Such refusals can
remove paths even when every supported edge is correct. An informative
reachable observation may shrink the version space (§46.9), but one observation
need not identify a hypothesis: the number retained is the size of the observed
answer's partition. Repeated observations preserve soundness only under the
same realizability and truthful-observation assumptions. Whole-policy
admission remains a separate fresh test after the final model is fixed.

## 46.24 Adaptive exploration before policy admission

An observation strategy may choose actions and refine the model using earlier
interaction outcomes. Once exploration stops, freeze the resulting model and
policy before drawing an independent IID gate stream. Existing fresh-case
admission applies conditionally on all exploration history; the observations
used to choose the policy must not be reused as gate examples. A separate audit
is drawn after admission. Resets, navigation actions, observation actions,
goal-discovery lookups, gate and audit labels, and policy execution are counted
separately. This separation controls evaluation reuse; it does not prove that
the hypothesis family is realizable or that exploration terminates successfully.

## 46.25 What a restricted deep-goal gate establishes

After adaptive exploration, a successful whole-policy gate can cover a
predeclared distribution of goals with minimum path length at least two in a
particular fixed world. The guarantee remains conditional on fresh IID gate
sampling, the frozen policy and faithful episode execution. Supplying the
candidate-state universe, reset distribution and a host-filtered goal set are
explicit environment capabilities; the gate does not establish that an agent
can discover those capabilities, transfer its learned model to another world,
or succeed for goals outside the declared distribution. A finite independent
audit measures that same distribution and does not strengthen the theorem to
universal correctness.

## 46.26 Fixed families of policy tests

For m policies fixed before their respective fresh-case tests, allocate each a
failure probability at most α/m. The union bound limits the probability of
any false admission to α, without requiring different policy tests to be
independent. Each test still requires IID episodes conditional on everything
used to choose that policy. Paired candidate policies may use identical fresh
episode draws when both are frozen before either draw is examined; sharing
those draws does not remove the need to allocate confidence across tests.
The independent audit is descriptive evidence, not a replacement for that
allocation. A finite family of similar development environments measures
robustness within that family, not general transfer to arbitrary dynamics.

## 46.27 Sample size and what the gate actually guarantees

Fix the complete exploration history and one policy. Let its episode failure
probability under the declared fixed-world distribution be q. If fresh episode
outcomes are conditionally IID, the probability of observing zero failures in m
cases is (1 − q)^m. For q > ε this is at most exp(−εm). Therefore a zero-loss
gate with m ≥ ln(1/δ)/ε has false-admission probability at most δ for that
policy. This is a frequentist bound on the procedure, not the posterior
probability that an admitted policy is correct. The rule treats refusal as a
failure. Finite-precision implementation assumptions remain those of
`required_cases` and the existing admission theorem.

For six worlds and two fixed arms, choosing total α=.05 and passing α/12 to
each independent gate bounds the family probability by α via §46.26. The
current implementation also spends its first-decision share 1/2, so each
single-stage gate uses at most α/24 and requires 124 zero-loss episodes for
ε=.05. It may reject early. This calculation does not require independent
worlds or independent arms, but each gate's fresh cases must be IID conditional
on both policies' fixed pre-gate histories. Paired gate draws are valid only if
both candidates are frozen before either candidate's result is inspected.

## 46.28 Refinement preserves supported plans under explicit conditions

Suppose the refined model preserves every previously supported prediction,
including its output, and neither model changes while planning. By induction
on an action sequence, every rollout supported by the original model has the
same result under the refinement (`refinement_preserves_rollout`). With a
finite model graph, faithful state identities and enough work to complete
breadth-first search in both models (§46.22), every originally reachable goal
remains reachable. This is a path-existence and complete-search statement: it
does not guarantee that an arbitrary work-limited scheduler, a changed world,
or a gate using different samples has no losses. Correct observations and a
realizable hypothesis family provide sufficient conditions for unanimity to be
preserved, but those conditions must be checked or stated separately.

## 46.29 What six related worlds can and cannot show

The six ordered pairs of distinct three-field transpositions are an exhaustive
finite development family, not six independent draws from a population of
arbitrary worlds. Per-world paired gains and losses describe this fixed family;
a numerical sign test interpreted as a population claim additionally needs an
appropriate randomization or sampling model, which this enumeration does not
supply. Shared gate cases allow direct comparison of two fixed policies on the
same episodes, but shared cases do not make worlds independent. The 64-case
audit per admitted policy estimates success only for that world's declared
goal distribution; it does not certify unseen action semantics, sensory input,
or cross-world transfer. A broader claim needs a separately sampled or
external family and a predeclared sampling and testing protocol.

## 46.30 Information gained per reachable observation

For a nonempty version space V of size n, a candidate observation partitions V
by predicted outcome. The worst-case survivors are the largest partition, so
§46.9's minimax rule is optimal for that one observation among the supplied
reachable candidates. It does not optimize the number of newly reachable goals
or future navigation cost. If every selected observation has largest partition
at most ceil(n/2), truthful observations retain the true hypothesis, and the
predictors are fixed, induction yields at most ceil(n₀/2^k) survivors after k
observations. Thus ceil(log₂ n₀) observations suffice to reach one survivor
under this strong balanced-split assumption. It need not hold: reachable
candidates can all be unanimous, or all available splits can be unbalanced.
The conclusion concerns identification within the supplied family, not whether
the true dynamics are in that family.

Ranking C supplied inputs against V predictors makes C·V predictor calls when
all calls complete. With equality-based grouping, it can additionally require
quadratically many output comparisons per input. Finding the candidate inputs
by independent complete breadth-first searches can cost up to C·N·K model
calls for N states and K actions, before ranking or taking an observation.
A selected observation also incurs its navigation path, one actual action and
any reset needed to obtain the start. These are different resources from gate
and audit labels. The bound assumes finite caller-supplied C, N and K; it is
not a wall-clock or physical-interaction guarantee.

## 46.31 Interpreting a perfect finite audit

For a fixed admitted policy, suppose an independent audit draws m IID episodes
from its declared operating distribution and observes m successes. The exact
one-sided lower confidence bound on its success probability at level 1 − γ is
γ^(1/m): a policy with success probability below that bound would produce m
successes with probability below γ. Thus 64/64 successes give a one-sided
95% lower bound of about .954, not proof of perfect accuracy. For twelve
preallocated audit claims sharing total γ=.05, a union-bound allocation of
γ/12 gives an individual lower bound of about .918. These audit intervals are
additional descriptive claims; the preregistered admission gate has its own
confidence allocation. They assume the fixed policy and IID sampling from the
same declared distribution; neither interval generalizes to new worlds.

## 46.32 Local information gain is not a global exploration policy

The implemented selector minimizes the largest surviving partition only
within a supplied set of states for one action. The current simulated explorer
tries actions in their supplied order and stops at the first action with a
reachable disagreement; it does not compare information gain across actions.
For example, with four consistent hypotheses per action, a reachable first
action might split its family 3:1 while a later action splits its family 2:2.
Assuming independent combinations of the two action families, the worst-case
joint family sizes after those observations are 12 and 8 respectively. The
first-available rule chooses the former despite its weaker information bound.
A smaller version space also need not yield more goal-reaching plans: the
eliminated hypotheses may disagree only on states unrelated to the goals.
Information gain, navigation cost and task reach are distinct objectives.

Comparing exploration with a passive model measures the combined effect of
extra evidence and the selection procedure at its additional interaction cost.
It does not establish that disagreement-based selection is better than another
strategy given the same number of observations, resets and navigation actions.
Such an attribution requires a separately preregistered, label- and
interaction-matched comparison and fresh evaluation. It is not supplied by a
paired passive/active gate alone.

## 46.33 What exploratory actions assume

A selected observation action is taken precisely where the retained hypotheses
do not all predict the same successor. Supported-rollout correctness therefore
does not predict that action's outcome. The environment must actually allow
the action and return a usable observation; a reset or later episode is a
separate supplied capability. In an irreversible or terminating environment,
one observation may remove future options. The finite toy control assumes
stationary deterministic transitions, complete observations, sampled resets
and a supplied finite candidate-state universe; its gate for the subsequent
frozen policy does not certify the exploration procedure or its interaction
cost in a different environment.

## 46.34 Fresh randomness is an assumption, not a seed label

A deterministic, publicly fixed sequence of test cases is not itself an IID
random sample after conditioning on that sequence. The gate's probability
statement therefore needs an explicit random sampling mechanism that remains
independent of policy selection. For paired tests, both policies can use the
same sequence of independently drawn uniform case indices, provided both are
frozen before the first index is exposed; their test outcomes may be dependent.
The audit must use a separate stream. Operating-system entropy, uniform-index
sampling and faithful implementation are empirical platform assumptions, not
consequences of the Lean proof. Recording the realized indices supports
reproduction but does not make the now-visible cases fresh for future tuning.

## 46.35 When observations identify a projection rule

In a tuple-field-copy family, each output position chooses one input field.
For each input field, form its observation signature: its sequence of values
across the training states for a particular action. A candidate field is
consistent with an output position exactly when its signature matches that
position's observed output signature. Consequently the number of consistent
whole rules is the product of the numbers of matching fields at each output
position. If all input-field signatures are distinct and the true rule is in
the family, every output position identifies its field and the fitted rule
agrees on every state of the declared representation. Lean proves this
conditional generalization as `projection_model_identified`; the finite
implementation check also exercises candidate enumeration and runtime routes.
This is an identifiability theorem for supplied tuple fields, not a theorem
that raw observations reveal a useful representation.

For three fields over three values, two uniformly sampled distinct training
states give pairwise-distinct field signatures with probability 498/702 =
83/117: of 9·8·7 ordered distinct signature triples, six correspond to two
identical training states and must be excluded. With a bijective true rule,
this condition is also necessary for uniqueness in the family of all field
copies. This probability assumes the stated ideal uniform sampling, not fixed
public pseudorandom seeds. In the six-world control, all twelve action-specific
training sets happened to have distinct signatures, so no additional
observation could shrink any version space. The result is not evidence that
the exploration strategy chose well.

## 46.36 Testing exploration when there is something to learn

An evaluation of information-seeking should state whether initial ambiguity is
part of the target distribution. Stratifying on a model's pre-intervention
version space can isolate cases with unresolved rules, but the resulting
performance claim applies only to that conditional distribution. All arms must
be fixed before fresh gate draws. A label- and interaction-matched alternative
is needed to attribute gains to the disagreement selector rather than to
additional evidence. If no informative reachable action exists in a sampled
episode, that refusal is part of the outcome, not a reason to silently replace
the episode. Realizability, supplied candidate states and reset access remain
separate assumptions.

## 46.37 Conditional sample bounds for supplied fields

For d supplied input fields taking q values, m independently uniform training
states drawn with replacement give each field a signature in a set of q^m
possible signatures. If d > q^m, the pigeonhole principle forces a collision,
so every bijective field-copy rule has at least two consistent explanations.
Under the stronger assumption that all field values are independent and
uniform across states and fields, the signatures are independent and uniform:
the probability that all d are distinct is the falling factorial
(q^m)(q^m−1)…(q^m−d+1)/(q^m)^d when d ≤ q^m, and zero otherwise. A union
bound gives collision probability at most d(d−1)/(2q^m). These are conditional
bounds for an already supplied representation and this sampling model, not a
representation-learning rate. Reachable-state samples can be highly correlated
or concentrated; observations selected without replacement need a different
calculation, as in §46.35. Every action-specific observation is counted.

## 46.38 The hypothesis-enumeration barrier

With d input fields and r output positions, allowing each output to copy any
input produces d^r possible rules per action before filtering. The present
explicit joint-family implementation constructs these rules individually, so a
user-supplied candidate budget can refuse even though a suitable rule exists.
The declared-product implementation in §47 avoids constructing those joint
rules; coupled families still require their joint constraints. Increasing the
logical budget alone is not a scalable solution: d=r=32 already gives 2^160 combinations.
This is an algorithmic representation limit of the current learner, not a
measured CPU bottleneck or a reason to specialize the core to a task.

## 46.39 Exact factorization and its boundary

For the unrestricted copy family, observations constrain each output position
independently. Let Cⱼ be its remaining input-field choices. The full version
space is exactly the Cartesian product of the Cⱼ (`training_version_eq`),
with cardinality ∏ⱼ|Cⱼ| (`training_version_count`).
Assume each Cⱼ is nonempty; an empty set means the model has no consistent
rule and must refuse. An empty output tuple has one rule by the empty-product
convention. For a candidate state x and possible output y, let nⱼ(yⱼ) count fields in Cⱼ
whose value in x equals yⱼ. Exactly ∏ⱼ nⱼ(yⱼ) whole rules predict y
(`output_partition_count`). Since each output position is independently
chosen, the largest output partition is ∏ⱼ maxᵥ nⱼ(v)
(`largest_output_partition`). A model can therefore
compute the same unanimous answers and the same worst-case disagreement score
without constructing every whole rule. An output is unanimous exactly when
all remaining fields for every position agree on that state's value.

Storing the independent field sets requires at most r·d field references per
action instead of d^r rules; fitting m observations takes at most m·r·d field
comparisons under constant-cost access. Scoring C states uses at most C·r·d
field reads plus grouping comparisons and arbitrary-precision product costs.
This exact reduction assumes the candidate class is the full Cartesian product,
fields and outcomes are total and equality is faithful. Constraints coupling
output positions, such as requiring a permutation, break the product assumption;
a factorized result must not be used for such a restricted class without a
separate proof. The declared-product implementation is specified in §47; this
counting result is not by itself a measured scalability or task-service claim.

## 46.40 Coupled hypotheses cannot be silently factorized

The Cartesian assumption is substantive. Consider two allowed joint rules
(a,c) and (b,d). On a training state with field values a=b=c=0 and d=1,
the observed output (0,0) retains only (a,c). If the learner first replaces
the joint family by the product of its per-output projections, it also admits
(b,c); that extra rule fits the same observation. On a later state with a≠b,
the exact version is unanimous while the expanded family disagrees and refuses.
Thus factoring an arbitrary coupled family by taking marginals can change both
coverage and the disagreement score. Conversely, dropping combinations
without justification can remove the true rule and make unanimity unsound.

A factored representation must therefore be constructed from an explicitly
declared product family, not inferred from observed examples or assumed for
arbitrary experts. For coupled or incomplete candidate families,
retain their actual joint constraints or use the existing explicit version
space. This boundary also applies when a task's semantic requirements couple
fields, even if the runtime values happen to be tuples.

## 46.41 Opaque outputs and assembly

A generic mechanism may receive component predictors and a caller-supplied
assembly function instead of assigning a core type to a tuple. The product
partition formula still applies to assembled outputs if assembly is injective
on the relevant component outcomes (`assembled_partition_count`). Otherwise,
distinct component outcomes may assemble to the same value, and their
partitions merge: multiplying component maxima can underestimate the true
largest output partition and change the selected observation. An observed
round-trip check alone cannot prove global injectivity. A future generic
interface must state and justify this representation assumption, or compute
actual joint output partitions without the shortcut.

## 46.42 What adaptive interaction cannot identify

Fix a deterministic policy that selects each action from its current state and
all prior transition observations. If two deterministic worlds agree on every
state-action pair visited in the first world, induction on the interaction
length shows that their entire observed traces agree, even though actions are
chosen adaptively (`adaptive_trace_indistinguishable`). The same statement
holds for a randomized policy after conditioning on its random choices; it does
not imply that all random choices avoid the disputed transition.

If a state-action pair was never visited, and the state space has another
possible successor, changing only that transition yields an alternative world
with the identical trace but a different answer at that pair
(`unvisited_transition_alternative`). This alternative is relevant only if the
world class permits it and any initial history also avoids or agrees at that
pair: the theorem treats the initial history as fixed rather than verifying its
consistency. Structural assumptions can rule out the alternative. Conversely,
when the assumed family excludes the actual world, a singleton version can be
confident and wrong. Agreement inside that family does not establish that it is
complete; fresh whole-policy certification concerns its operating distribution
and does not prove the model correct everywhere.

This distinguishes two gaps in the existing six-world control. All twelve
action versions were already singletons, so that experiment did not test
information-seeking. More broadly, any successful information-seeking claim
must specify its world class, observable actions and reachable starts; otherwise
an unvisited edge can remain indistinguishable. A next development comparison
should sample ambiguous but realizable initial histories, match interactions
and resets across selection strategies, and measure whether acquired evidence
improves independently tested goal service. Conditional selection and supplied
world structure limit the resulting claim; no discovery rate follows here.

## 46.43 When an observation makes progress

For a finite version space containing the true deterministic predictor, a
truthful observation at an input where retained predictors disagree preserves
truth and strictly decreases the number of retained hypotheses
(`disagreement_refinement_progress`). This is true for every possible answer
from that family. A query at a unanimous input leaves the version unchanged;
if the true predictor is absent, disagreement may disappear without making the
remaining predictors correct. A strict reduction is an information result, not
a guarantee of improved goal reachability or successful policy admission.

An interaction-matched comparison can use a single shared start per world and
one action per arm: select the first action whose retained predictors disagree
at that start, versus a baseline action sampled without consulting model
disagreement. If none disagrees, the information-seeking arm uses the same
baseline action. Both arms consume one transition observation and one reset;
the no-intervention arm consumes neither. All resulting policies must be fixed
before independently sampled admission and audit episodes. The theory predicts
strictly fewer hypotheses for the disagreement arm when a disagreement exists,
but does not predict its advantage over the baseline or any change in certified
goal service. Start selection, possible worlds, action order and case streams are
part of the experimental distribution and must be recorded.

## 46.44 Model size is not goal value

The matched finite control in §46.43 gives concrete examples: reducing the
joint version need not increase goal coverage, and two versions of the same
size can support different numbers of goals. Which state-action predictions
become unanimous matters to the planner, not just how many models survive.
The strict-shrink theorem therefore justifies counting information acquired; it
does not justify choosing the action by survivor count as an optimal method for
the user's goals. A goal-directed comparison needs an explicit distribution of
goals, reachable actions and interaction costs, with evidence separated from
the data used to choose the observation.

## 46.45 Goal-directed observation under explicit uncertainty

The selector derived here tied the simpler one on its control and was retired; coverage preservation remains valid.

Let a finite, caller-supplied set of start/goal tasks be fixed before selecting
an observation. Define model coverage as the number admitting a supported
finite route. If refinement preserves every supported transition, every old
route remains supported and coverage cannot decrease
(`refinement_preserves_goal_coverage`). This is an unbounded existence result;
resource-limited search may fail to rediscover a route after refinement, and
model coverage is not itself successful execution or certification.

For each available action, enumerate every outcome consistent with the current
finite version, form the hypothetical refined model for that outcome, and
score the action by its minimum coverage over those hypothetical models. With
complete outcome enumeration and exact coverage, choosing a maximum score
maximizes the worst-case model coverage among the supplied actions. Including
a fallback action in that same set makes the selected worst-case score no worse
than the fallback's. Hypothetical outcomes are computed from the model and are
not observed labels; the real action still costs an intervention. These claims
assume faithful equality, a fixed model and goal set, exhaustive outcomes and
coverage, and realizability for interpreting the actual outcome as one of the
enumerated branches. Bounded implementations must abort or refuse on any
incomplete branch instead of treating a partial minimum as exact.

The guarantee compares worst cases, not the two actions' realized outcomes;
the higher-scoring action can still fare worse in the actual world. It also
does not establish a useful goal distribution, raw-state representation,
interaction safety, or policy reliability. Development goals used to rank the
actions must be distinct from independently sampled evaluation episodes; a
simulation's oracle-derived reachability list is not a permissible hidden
source of task-specific information for the selector.

## 46.46 Ties and the cost of robust ranking

The first bounded goal-directed control produced the same selected action as
the simpler disagreement selector in all six development worlds. Five of the
six action-score comparisons tied, so tie-breaking alone preserved the earlier
choice in those cases. The minimax guarantee remains valid for the supplied
ranking goals and model branches; it does not imply a strict improvement or
justify the additional computation when the scores tie. A more informative
goal representation or objective needs an independently specified rationale
and a new comparison; choosing one because it fixes these six worlds would be
development tuning, not external evidence.

[Theory index](../../THEORY.md)
