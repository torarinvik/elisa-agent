# Diary

Experiments, predictions and measurements, filed under the section of
THEORY.md they test. Predictions are recorded before their experiment is run
and kept afterwards. Unless stated otherwise, results come from the `test`
split with the seeds and sample counts given in each entry.

## 8. Explicit route upgrades

`nca.accumulation --scenario conflict` applies this rule to the route `plan`
proposes after the encoder is installed: it rejects a weaker symbol
classifier and accepts a stronger one, and only the arithmetic route changes.
Validation samples are drawn with a different seed from the reported test
samples.

## 9. Module substitution

`nca.substitution` swaps independently trained digit recognizers (different
architectures, disjoint halves of the training data) into the frozen system
and reports route shape, type check, accuracy, changed-answer rate, `Σ d`, and
accuracy drop relative to the reference.

## 11. Evaluation methodology

**Data separation** (`nca.expressions`). Training splits draw digit images
from the MNIST training set. The MNIST test set is divided: its first half
supplies the `validation` split, used for every decision taken from data
(such as accepting route upgrades); its second half supplies `test` and
`test_unseen`, used only for reporting. No digit image is shared between
what decisions are made on and what is reported. `test_unseen` additionally
holds out digit pairs never seen in training.

**Deliberate shift.** The `hard` style renders operators with three times the
usual geometric jitter and thickens or thins digit strokes (3×3 max or min
filter). Evaluating on it measures robustness to a shift that no module was
trained on; by §5 the accuracy loss is bounded by the induced shifts of the
affected modules.

## 12. Lazy loading and scalable discovery

**Measured cost structure** (`nca.scaling`). Among up to 100,000 unusable decoy
experts, the loaded set always equals the route's working set and every answer
is unchanged, as the theorems require. Without pruning, planning time grew with
the number of dormant producers of relevant types (1.6 s at 100,000 experts);
with pruning it is 6.8 ms. The remaining growth is one constant-time check per
dormant producer of the goal type, removable by indexing producers by
reachability.

**Grouping by route.** Measured (`nca.scaling`, 200 arithmetic and 200
comparison tasks, budget equal to the larger route, so both routes do not fit
together):

| order | eviction | loads | MB loaded |
|---|---|---:|---:|
| alternating | least recently used | 1602 | 677.8 |
| alternating | route-aware | 1602 | 677.8 |
| grouped by route | route-aware | 10 | 5.1 |

Here least-recently-used eviction already meets the lower bound (each route
runs its shared experts first, so they stay recent): 400 switches times the
1.69 MB the routes do not share. The cost of alternation is unavoidable for
any eviction policy; only reordering removes it. Accuracy is unchanged
(0.985) in every configuration.

## 14. Kernel-mediated requests and refinement

**Demand gate.** With the cheap/expensive pair at `τ = 0.9` (300 test
expressions):

| glyphs | ungated cost | heuristic gate cost, changed | demand gate cost, changed |
|---:|---:|---:|---:|
| 3 | 31.4 | 27.4, 0 | 27.0, 0 |
| 15 | 150.1 | 126.7, 1 | 123.6, 0 |
| 63 | 519.4 | 434.8, 13 | 425.4, 0 |

Cost is MFLOPs per expression; error is identical to ungated refinement
(0.030, 0.147, 0.503) and the expensive recognizer (0.033, 0.143, 0.500). The
demand gate is both exact and cheaper than the heuristic one, because it skips
the cheap recognizer as well as the request on operator positions.

**Consulting.** `ConsultingRecognizer` uses continuations to combine opinions
rather than defer: when its confidence is below `τ` it asks for a second
opinion on the glyph and answers `(1 − w) · own + w · second`. Under the
demand gate, at `τ = 0.9` with the same 300 expressions and the same cost as
demand-gated refinement:

| glyphs | refine (replace) | consult `w = 0.3` | `w = 0.5` | `w = 0.7` |
|---:|---:|---:|---:|---:|
| 3 | 0.030 | 0.047 | 0.033 | 0.033 |
| 15 | 0.147 | 0.193 | 0.150 | 0.143 |
| 63 | 0.503 | 0.577 | 0.510 | 0.503 |

Mixing does not beat replacement: below `τ` the cheap recognizer is the less
reliable opinion, so weight on it costs accuracy and `w → 1` recovers
delegation. Ensembles help only when the opinions' errors are complementary
on the deferred set; for these two recognizers they are not.

## 15. Normalization against shift

**Diagnosis of the hard style** (2000 expressions, failure rates per
expression; before the fixes):

| | segmentation | first digit | operator | second digit | accuracy |
|---|---:|---:|---:|---:|---:|
| test | 0.031 | 0.006 | 0.002 | 0.005 | 0.958 |
| test (hard) | 0.123 | 0.157 | 0.257 | 0.161 | 0.428 |

Segmentation failures on the hard style are almost all *extra* glyphs:
thinned strokes break into pieces separated by narrow blank gaps. Thinning
also erases 7% of digit glyphs completely, which nothing downstream can undo.
For operators, a recognizer trained directly on the hard style reaches only
80% among operators: rotation by up to ~20° with three times the endpoint
noise makes `+` and `×` overlap, a floor of about 20% that no normalizer can
remove.

**Results** (2000 expressions; segmentation gap 4):

| system | test | test_unseen | test (hard) | test_unseen (hard) |
|---|---:|---:|---:|---:|
| before (gap 2, raw recognizers) | 0.958 | 0.965 | 0.428 | 0.449 |
| gap 4, raw recognizers | 0.977 | 0.984 | 0.446 | 0.463 |
| gap 4, normalized digits | 0.968 | 0.963 | 0.501 | 0.509 |
| gap 4, normalized digits and operators | 0.967 | 0.962 | 0.478 | 0.495 |

With normalization the digit failure rate on the hard style falls from 0.19 to
0.15 per position and the digit shift lower bound from 0.14 to 0.10 (the
normalized operator recognizer is worse on hard operators, 0.305 vs 0.280,
since rescaling does not undo rotation). The cost is about 0.5% digit
error on the normal style. Remaining hard-style errors are dominated by the
operator floor and erased digits. Choosing between the raw and normalized
digit recognizer is a route decision (§8): on normal-style validation data the
raw one wins, so the normalized route is adopted only when the deployment
distribution is known to include such styles.

**Monolithic baseline under the same shift** (`nca.baseline`, one CNN trained
end to end on 60,000 normal-style expressions, 5 epochs; 2000 expressions per
split):

| system | test | test_unseen | test (hard) | test_unseen (hard) |
|---|---:|---:|---:|---:|
| monolithic | 0.948 | 0.105 | 0.304 | 0.064 |
| modular, raw recognizers | 0.977 | 0.984 | 0.446 | 0.463 |
| modular, normalized digits | 0.968 | 0.963 | 0.501 | 0.509 |

On seen digit pairs the shift costs the monolithic model 64 points and the
modular pipeline 53 (47 with normalization). On unseen pairs the shift
compounds with the monolithic model's failure to compose. The modular system's
loss is also diagnosable, since per-module failure rates and shift lower
bounds locate it, and it can be fixed by replacing a single module.

## 16. Knowing when to be unsure

**Results** (300 test expressions per length; MFLOPs per expression; decision
demand and decision-relative risk):

| glyphs | ladder | system | coverage | error answered | error forced | MFLOPs |
|---:|---|---|---:|---:|---:|---:|
| 3 | base | bottom rungs | 1.000 | 0.037 | 0.037 | 9 |
| 3 | base | top rungs | 1.000 | 0.010 | 0.010 | 153 |
| 3 | base | δ = 0.05 | 0.950 | 0.004 | 0.007 | 18 |
| 15 | base | top rungs | 1.000 | 0.063 | 0.063 | 768 |
| 15 | base | δ = 0.2 | 0.933 | 0.064 | 0.080 | 114 |
| 15 | + strong | δ = 0.05 | 0.903 | 0.030 | 0.050 | 598 |
| 63 | base | bottom rungs | 1.000 | 0.523 | 0.523 | 278 |
| 63 | base | top rungs | 1.000 | 0.280 | 0.280 | 3221 |
| 63 | base | δ = 0.2 | 0.493 | 0.155 | 0.293 | 1785 |
| 63 | + strong | top rungs | 1.000 | 0.193 | 0.193 | 20661 |
| 63 | + strong | δ = 0.2 | 0.800 | 0.142 | 0.213 | 4498 |
| 63 | + strong | δ = 0.05 | 0.450 | 0.074 | 0.190 | 11701 |

*Error forced* is the error when the system must answer after refining as
far as the target asks.

- **Reliability.** Every interval for error among answered expressions
  contains its target, though at strict targets on long inputs the estimates
  lean above it (63 glyphs, strong ladder: 0.074 at `δ = 0.05`, interval
  `[0.041, 0.131]`). Calibration is fitted on the validation half of the
  MNIST test set, which is easier than the half used for testing, and this
  shift is the likely cause.
- **Efficiency.** Targeted refinement matches refining everything at a
  fraction of the compute: 8× cheaper at 3 glyphs (and more accurate), and
  7× cheaper at 15 glyphs for 1.7 points more error.
- **Long inputs.** Second looks and segmentation repair cut forced error at 63
  glyphs from 0.523 to 0.280, and a stronger rung lowers the floor
  (`length_limit`) to 0.193. At `δ = 0.2` the strong ladder answers 80% of
  63-glyph expressions with 0.142 error, at 22% of the compute of reading
  everything with it.
- **Cost of genericity.** Decision demand brought compute near a controller
  hand-written for this task (278 against 248 MFLOPs at 63 glyphs on the
  bottom rungs; the rest is the generic second look's re-read of the
  original view). Decision-relative risk then raised coverage past it
  (0.49 against 0.42 at 63 glyphs and `δ = 0.2`). The hand-written
  controller also restricted operator decisions, so the difference lies
  elsewhere, plausibly in per-rung temperatures for the averaged second
  looks; it was not isolated.
- **Limit.** Targets below about 0.15 at 63 glyphs remain infeasible for most
  expressions: per-glyph floors are still too high for `L · ρ ≤ δ`.

**Experiment.** The expensive recognizer (calibrated on the normal style)
reads 4000 `train`-split expressions in the unseen hard style: 7878 digit
glyphs, 27% misread. For a label budget `k` the queue takes the `k` riskiest
glyphs, compared with `k` random glyphs from the same stream. Results on
2000 test expressions per style (seed 0):

| practice | labels | misread among labeled | digit error hard | accuracy normal | accuracy hard | sign test |
|---|---:|---:|---:|---:|---:|---|
| none | 0 | — | 0.211 | 0.977 | 0.446 | — |
| queue | 100 | 91% | 0.173 | 0.981 | 0.485 | adopted, p = 2e-6 |
| random | 100 | 27% | 0.201 | 0.981 | 0.455 | adopted, p = 0.003 |
| proportional | 100 | 67% | 0.178 | 0.980 | 0.484 | adopted |
| queue | 300 | 89% | 0.157 | 0.979 | 0.503 | adopted |
| random | 300 | 27% | 0.152 | 0.980 | 0.514 | adopted |
| proportional | 300 | 62% | 0.140 | 0.979 | 0.525 | adopted |
| queue | 1000 | 82% | 0.130 | 0.974 | 0.536 | adopted |
| random | 1000 | 27% | 0.128 | 0.978 | 0.538 | adopted |
| proportional | 1000 | 63% | 0.099 | 0.976 | 0.569 | adopted |
| everything | 7878 | 27% | 0.074 | 0.975 | 0.594 | adopted |
| replay only (budget 0) | 0 | — | 0.234 | 0.978 | 0.418 | rejected, p = 0.16 |

- **Finding errors.** Risk ranks errors well: 91% of the 100 riskiest glyphs
  are misread against 27% of random ones, and the expected errors in the
  queue (82, 243, 778) track the observed ones (91, 267, 824). The small
  excess comes from calibrating on the normal style.
- **Learning from them.** Queued labels help most when labels are scarce:
  with 100 labels the queue gains 3.9 points of hard-style accuracy, random
  labels 0.9. From 300 labels on, queue and random are equal within noise.
  The riskiest glyphs are the most distorted, so their value as training
  examples saturates while random labels add diversity.
- **Risk with diversity.** Sampling with probability proportional to risk
  keeps most of the queue's error-finding (62–67% of labels misread) and the
  diversity of random labels. It ties the top-risk queue at 100 labels and
  beats both alternatives from 300 on. At 1000 labels it reaches 0.569
  hard-style accuracy, 83% of the gain from labeling all 7878 glyphs with 13%
  of the labels. On a second seed it is again best at 300 and 1000 labels
  (0.527 and 0.553, against at most 0.511 and 0.538).
- **Safety.** Every adopted version keeps normal-style accuracy within its
  interval. The one version that made things worse (replay without practice
  data) was rejected by the sign test, as the upgrade rule intends.

**Decision-relative risk.** Renormalizing the full output's calibrated
probabilities was not enough: in a trial, error among answered expressions
exceeded the target (0.084 at `δ = 0.05`, interval `[0.050, 0.138]`) because
the restricted decision was over-confident. Per-decision temperatures fixed
it.

## 17. Calibration under distribution shift

### 17.7 Expected outcomes

The theory makes falsifiable predictions for the experiment.

1. **Validity.** With risk control at level `α`, the error rate among
   answered test expressions stays at or below `δ` in at least a fraction
   `1 − α` of independent audit draws, at every length and target. With
   reference calibration alone it does not, at strict targets on long inputs.
2. **Price.** Risk control costs coverage relative to the uncontrolled
   controller at the same `δ`. The cost is largest where the uncontrolled
   controller was violating the target.
3. **Recovery.** Recalibrating on audit glyphs lowers the deficit
   (mean bound closer to observed error) and returns coverage under risk
   control.
4. **Labels.** Certification fails at strict targets when too few answered
   audit expressions remain (§17.6), and the controller then abstains on
   everything. This is the honest answer when evidence is insufficient.

### 17.8 Results

`nca.certify`, with the base ladder (cheap, expensive and second-look
digit readers; operator reader and its second look). Calibration uses 2000
reference glyphs. The `test` half of the MNIST test set is divided by image
index into an audit part and an evaluation part (300 expressions). Each audit
draw holds 200 + 200 expressions: the first half recalibrates the rungs (for
the *audit* calibration) and orders the candidates, the second half tests
them. Inflations are `λ ∈ {4, 2, 1.5, 1.25, 1, 0.75, 0.5}` with `α = 0.1`,
over three independent audit draws.

| glyphs | δ | calibration | uncontrolled: coverage, error answered | risk control: λ per draw | coverage | error answered |
|---:|---:|---|---|---|---|---|
| 15 | 0.2 | reference | 0.917, 0.102 | 0.5, 0.5, 0.5 | 0.980 | 0.112 |
| 15 | 0.2 | audit | 0.87–0.95, 0.07–0.11 | 0.5, 0.5, 0.5 | 0.97–0.99 | 0.110–0.125 |
| 15 | 0.05 | reference | 0.793, 0.046 | 1, 1.5, 0.5 | 0.79, 0.71, 0.86 | 0.046, 0.038, **0.070** |
| 15 | 0.05 | audit | 0.57–0.87, 0.029–**0.065** | 0.75, 4, 0.5 | 0.66, 0.55, 0.90 | 0.030, 0.036, **0.071** |
| 63 | 0.2 | reference | 0.480, 0.139 | –, 1, 1 | 0, 0.48, 0.48 | –, 0.139, 0.139 |
| 63 | 0.2 | audit | 0.25–0.51, 0.08–0.15 | –, 0.75, 0.75 | 0, 0.47, 0.38 | –, 0.141, 0.106 |
| 63 | 0.05 | reference | 0.143, **0.070** | –, –, – | 0 | – |
| 63 | 0.05 | audit | 0.01–0.17, 0–**0.080** | –, –, – | 0 | – |

Bold marks error above `δ` on the evaluation set; "–" means no candidate was
certified, so the system abstained on everything. The reference-calibrated
uncontrolled policy does not depend on the audit.

Against the predictions of §17.7:

1. **Validity: confirmed.** Uncontrolled, reference calibration violates the
   target at 63 glyphs and `δ = 0.05` (0.070), as §16 suggested. Under risk
   control 22 of 24 configurations meet the target. Both misses come from one
   audit draw (draw 2, 15 glyphs, `δ = 0.05`: 0.070 and 0.071), and their
   intervals (`[0.044, 0.107]`, `[0.046, 0.108]`) include the target. Each
   draw may fail with probability up to `α = 0.1`, and a draw's failures are
   correlated because all its tests share one audit.
2. **Price: confirmed, and it depends on the order.** With the
   most-cautious-first order, risk control at 63 glyphs abstained on
   everything in 4 of 6 configurations at `δ = 0.2`. Cautious candidates
   answered too few audit expressions to be certified, and testing stopped
   there. Ordering on the first audit half certifies a policy in 4 of 6, at
   the uncontrolled coverage. At 15 glyphs and `δ = 0.2` it certifies
   `λ = 0.5` in every draw and *raises* coverage from 0.92 to 0.98, because
   the bound is conservative there.
3. **Recovery: refuted.** Recalibrating on 200 audit expressions did not
   reliably help. Its coverage varied widely between draws (0.25–0.51 at
   63 glyphs, `δ = 0.2`). Uncontrolled, it *caused* violations at 15 glyphs
   and `δ = 0.05` (0.061, 0.065) where reference calibration had none. This
   is the distinction §17.4 drew: refitting temperatures moves calibration
   on average over `Q`, which is not the pointwise validity that the
   selected, answered inputs need. Only the test-based guarantee is robust.
4. **Labels: confirmed.** At 63 glyphs and `δ = 0.05` no candidate is ever
   certified. A pass needs about 59 answered audit expressions with no errors
   (§17.6), and at that strictness candidates answer 15–30 of the 200.
   Abstaining is the correct outcome: the evidence does not support the
   claim.

**Conclusion.** The guarantee on deployment comes from testing, not from
calibration. Calibration (reference or recalibrated) determines only how
much is certified. A label-efficient path to strict targets on long inputs
needs larger audits, or better calibrated risks so that fewer candidates
answer near the boundary.

**Motivation.** Calibration was fitted on the `validation` half of the MNIST
test set and tested on the other half, written by different people. At 63
glyphs with the strong ladder (§16), the error among answered expressions was
0.074 at `δ = 0.05` (interval `[0.041, 0.131]`) and 0.053 at `δ = 0.01`:
consistent with the target only because the intervals are wide, and leaning
above it.

## 18. A second domain: noisy Boolean formulas

### 18.9 Predictions

1. **Validity.** At the calibration noise level, the error among answered
   formulas is at most `δ` with the certificate bound, as with the static
   one.
2. **Coverage.** At the same `δ`, certificates answer more formulas than
   static demand. The gap grows with depth, and vanishes on all-`xor`
   formulas (the control).
3. **Scaling.** The number of fully decided words grows like `√n`, not `n`:
   on alternating trees at most `2^⌈d/2⌉` leaves are evaluated.
4. **Compute.** At the same `δ`, certificates spend less: items outside the
   certificate are never climbed.
5. **Shift.** At a higher noise level in use, the uncontrolled error among
   answered formulas can exceed `δ`, and the risk control of §17 restores the
   target, with `certify` unchanged.

### 18.10 Results

`nca.logic`, calibration noise `ν = 0.1`. The edit reader (650 operations
per word) and the character reader (103k FLOPs per word, trained on 6000
depth-4 training formulas) form the ladder. Calibration uses the words of
100 depth-4 validation formulas, and evaluation 300 test formulas per depth.
On noisy words of uniformly drawn vocabulary words, the edit reader errs on
1.8% of words (0.29% in arity), the character reader on 0.8% (0.32%). A
wider character reader (807k FLOPs) did no better, so the character reader
sits at the channel's floor. Arithmetic output of `nca.selective` is
identical before and after the two generic extensions.

**Certificate size** (true formulas, fewest leaves a valid certificate
evaluates): 2, 4, 8 and 16 leaves at depths 2, 4, 6 and 8, for every one of
the 300 formulas. This is exactly `2^⌈d/2⌉` (`alternating_cert_leaves` is
tight at even depths). On all-`xor` formulas it is all `2^d` leaves.

**Selective answering**, `and`/`or` formulas (coverage; compute in kFLOPs per
formula):

| depth | words | δ | static coverage | certificate coverage | static compute | certificate compute |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 8 | 0.2 / 0.05 / 0.01 | 0.977 / 0.957 / 0.927 | 0.977 / 0.957 / 0.927 | 31 / 47 / 87 | 31 / 47 / 86 |
| 4 | 35 | 0.2 | 0.900 | 0.910 | 409 | 370 |
| 4 | 35 | 0.05 | 0.813 | 0.843 | 720 | 608 |
| 4 | 35 | 0.01 | **0** | **0.267** | 3641 | 2719 |
| 6 | 143 | 0.2 | 0.497 | 0.557 | 7602 | 6721 |
| 6 | 143 | 0.05 | **0** | **0.213** | 14892 | 11864 |
| 8 | 575 | 0.2 | 0 | 0.017 | 59800 | 58883 |

Across every row, no answered formula was wrong. The upper ends of the 95%
intervals are below each `δ` wherever more than 100 formulas were answered.
When forced to answer, error is 0.02, 0.04, 0.23 and 0.58 at depths 2 to 8.

**Control**, all-`xor` formulas: the two systems agree to within one or two
formulas at every depth and target. Coverage is 0.877/0.877 at depth 2 and
`δ = 0.2`, and 0.383/0.390 at depth 4. The error among answered formulas
stays within `δ` (at most 0.060 at `δ = 0.2`). The tiny differences come
from `xor` words misread as `and`/`or`, which allow a skip. Here the
character reader matters: it halves the depth-4 error when forced to answer
(0.38 → 0.19), because `xor` and `or` differ by one letter.

**Shift**, noise 0.2 in use with the certificate system, three audit draws
of 200 + 200 formulas at the deployment noise:

| depth | δ | uncontrolled: coverage, error answered | risk control: λ per draw | coverage | error answered |
|---:|---:|---|---|---|---|
| 4 | 0.2 | 0.687, 0.024 | 0.5, 0.5, 0.5 | 0.757 | 0.026 |
| 4 | 0.05 | 0.520, 0.013 | 0.5, 0.5, 0.75 | 0.58, 0.58, 0.56 | 0.023, 0.023, 0.024 |
| 6 | 0.2 | 0.157, 0 | 0.5, 0.5, 0.5 | 0.313 | 0.011 |
| 6 | 0.05 | 0.007, 0 | –, –, – | 0 | – |

Against the predictions of §18.9:

1. **Validity: confirmed.** Error among answered formulas is within `δ`
   everywhere, and far below it in the `and`/`or` family.
2. **Coverage: confirmed.** Certificates answer at least as many formulas
   everywhere. The gap grows with depth and strictness: where static demand
   answers nothing (depth 4 at `δ = 0.01`, depth 6 at `δ = 0.05`),
   certificates answer 27% and 21%. The gap vanishes on the `xor` control.
3. **Scaling: confirmed, exactly.** Evaluated leaves are `2^⌈d/2⌉ = √n` on
   every formula.
4. **Compute: confirmed.** At equal targets certificates spend 10–16% less
   where both answer, because skipped words are never climbed.
5. **Shift: refuted as stated.** At double the noise, the uncontrolled
   policy never exceeded `δ`: the bound is conservative here, unlike for
   handwriting (§17.8). Risk control, unchanged, therefore did the opposite
   of repair: it certified the boldest candidate (`λ = 0.5`) and *raised*
   coverage, from 0.16 to 0.31 at depth 6. Where the audit could not support
   the claim (depth 6, `δ = 0.05`), it abstained.

**The arity term limits depth.** The theory assumed `ρ_shape ≪ ρ_full`
because `true`/`false` look nothing like connectives. That holds for them,
but `not` looks like `and`, `or` and `xor` (`xor` → `not` is the commonest
arity confusion). Measured arity error is a third (edit reader) to
two-fifths (character reader) of word error, not orders of magnitude below
it. The arity term `m · ρ_shape` grows with all `m` words. At depth 8
(575 words) it alone nearly exhausts `δ = 0.2`, and only 1.7% of formulas
are certified.

**Why the bound is conservative.** Prefix notation is an error-detecting
code. A single wrong arity changes `Σ (arity − 1)`, so the words no longer
parse, the certificate reports no answer, and the controller climbs or
abstains. A wrong arity can go undetected only if at least one other
compensates, so the arity term, summed as if every arity error were silent,
overstates the risk roughly quadratically. §19 builds the bound that credits
this detection, charging the arity term only for pairs of errors, and §19.9
measures its gain. §21.11 tests its premise of uncorrelated word errors.

**Conclusion.** The kernel, planner, ladders, calibration, refinement and
certification carried over to a task with different inputs, different
experts and a different dependency structure. The new domain needed two
generic extensions, grouped decisions and value-dependent certificates.
Both reduce exactly to the old behavior on arithmetic. Certificates turn
the union bound's `n` into `√n` for the decisions that matter, and that
makes formulas answerable where static demand must abstain.

## 19. Error detection by the format

### 19.8 Predictions

1. **Validity.** The Markov account needs no new premise: the error among
   answered formulas stays within `δ`. The pairs account stays within `δ` if
   its premise holds; the experiment tests this.
2. **Coverage.** Markov raises coverage modestly. Pairs raises it strongly
   where the arity term dominates: depths 6 and 8, where §18 certified 21%
   (depth 6, `δ = 0.05`) and 1.7% (depth 8, `δ = 0.2`).
3. **Tightness.** The mean bound among answered formulas moves toward the
   observed error.
4. **Compute.** Less: arity charges no longer force climbs on words whose
   arity is merely uncertain.

### 19.9 Results

`nca.logic`, with the setup of §18.10 (same readers, calibration and 300
test formulas per depth). Coverage, with compute in kFLOPs per formula in
brackets:

| depth | δ | static | certificate | Markov | pairs |
|---:|---:|---:|---:|---:|---:|
| 2 | 0.01 | 0.927 (87) | 0.927 (86) | 0.940 (75) | 0.970 (32) |
| 4 | 0.2 | 0.900 (409) | 0.910 (370) | 0.923 (322) | 0.973 (124) |
| 4 | 0.05 | 0.813 (720) | 0.843 (608) | 0.857 (559) | 0.963 (162) |
| 4 | 0.01 | 0 | 0.267 (2719) | 0.713 (1158) | 0.937 (274) |
| 6 | 0.2 | 0.497 (7602) | 0.557 (6721) | 0.687 (4798) | 0.817 (2833) |
| 6 | 0.05 | 0 | 0.213 (11864) | 0.440 (8514) | 0.707 (4497) |
| 6 | 0.01 | 0 | 0 | 0.113 (13302) | 0.557 (6764) |
| 8 | 0.2 | 0 | 0.017 (58883) | 0.097 (54236) | 0.247 (45391) |
| 8 | 0.05 | 0 | 0 | 0.003 (59614) | 0.080 (55227) |
| 8 | 0.01 | 0 | 0 | 0 | 0.007 (59426) |

No answered formula was wrong under any account. The mean bound among
answered formulas at `δ = 0.2` falls from 0.032 (certificate) to 0.025
(Markov) and 0.006 (pairs) at depth 4, and from 0.103 to 0.092 and 0.048 at
depth 6.

**Shift**, noise 0.2 in use with the pairs account, audits as in §18.10:

| depth | δ | uncontrolled: coverage, error answered | risk control: λ per draw | coverage | error answered |
|---:|---:|---|---|---|---|
| 6 | 0.2 | 0.410, 0.008 | 0.5, 0.5, 0.5 | 0.460 | 0.029 |
| 6 | 0.05 | 0.257, 0 | –, 0.5, – | 0, 0.353, 0 | –, 0.009, – |
| 8 | 0.2 / 0.05 | 0, – | –, –, – | 0 | – |

At depth 6 the certificate account answered 0.157 and 0.007 of these
formulas uncontrolled (§18.10).

Against the predictions of §19.8:

1. **Validity: confirmed.** The Markov account, which needs no premise,
   made no error. Neither did the pairs account in distribution. Under shift
   it made one error in 123 answered formulas at `δ = 0.2`, far within `δ`.
   This does not establish the pairs premise: with no errors anywhere, every
   account is conservative, and a mild positive correlation would go
   unseen. It shows only that, if the premise fails here, it fails by less
   than the slack the bound already has.
2. **Coverage: confirmed, more strongly than predicted for Markov.** At
   depth 6 and `δ = 0.05`, coverage rises from 0.213 to 0.440 (Markov) and
   0.707 (pairs). At depth 4 and `δ = 0.01`, Markov alone lifts it from 0.267
   to 0.713, because halving the arity term is decisive where that term
   barely exceeds `δ`. At depth 8 and `δ = 0.2`, pairs certifies 0.247
   against 0.017.
3. **Tightness: confirmed in direction.** Mean bounds fall severalfold,
   while the observed error stays at zero, so the bound remains conservative.
4. **Compute: confirmed.** Pairs spends 2.4–10× less than the certificate
   account where both answer, and Markov 10–57% less. Words whose arity is
   merely uncertain are no longer climbed.

When forced to answer, the pairs account also errs less (0.040 → 0.027 at
depth 4 and 0.223 → 0.163 at depth 6, at `δ = 0.2`). Its charges direct the
climbs to different words; why that helps the readings was not
investigated.

**Depth 8 is still limited, as §19.7 predicts.** On 30 depth-8 formulas,
the top rung gives `S ≈ 0.71` per formula, so `e₂ ≈ 0.28` alone exceeds
`δ = 0.2`. The evaluated words' restricted risk is about 0.02. Most readings
(18 of 30) do not parse even at the top rung. With the measured per-word
arity risk, the length limit `√(2δ) / ρ` is about 520 words, below the 575
of depth 8. Pairs helps only while `S < 1`. Beyond that, what limits depth
is the readers' arity error itself, not the account. §21 lifts this limit by
correcting arity errors instead of only detecting them (results in §21.11).

**Conclusion.** Prefix notation detects every single arity error, a fact
proved once in Lean and used by the evaluator alone. Crediting it turns the
arity term from linear in the number of words into half of that with no
premise, or quadratic under a premise of uncorrelated failures. The kernel
needed one generic change: certificates return per-item charges instead of
demands. That roughly doubles to triples certified coverage at depth 6,
cuts compute severalfold, and keeps every answered formula correct.

## 20. Higher-order experts and budgeted requests

### 20.7 Predictions

1. **Exactness.** With `map` moved from the kernel into the library, routes,
   outputs and costs of the arithmetic tasks are identical (`embed_wellTyped`).
2. **Planner optimality.** The slot-aware cost and Pareto planners agree
   with exhaustive enumeration of searchable plans on random libraries,
   including libraries where the cheapest route uses a higher-order expert.
3. **Automatic cascades.** Given the digit recognizers and the fallback
   expert, the planner's cheapest route within the error target is the
   cascade that §14 built by hand, with matching cost and error.
4. **Budgets.** A recursive expert (one that asks its own question on
   subinputs) runs within its declared budget, and is refused rather than
   wrong when the budget is too small.

### 20.8 Results

Slots are implemented in the ABI (`Contract.slots`, with `Manifest.calls`
and `Manifest.expected_calls` for `ν` and `ν̄`), in the stable, cost and
Pareto planners (`nca.planner`, `nca.optimize`), in type checking
(`nca.router.infer`) and in the runtime, which passes each filling to its
expert as a callable run through the kernel (`nca.runtime.Filling`).
`nca.modules.combinators` holds `MapExpert` and `Fallback`. Budgets in cost
units are `execute(..., cost_budget=...)`, with `attempt` reporting a
refusal as no answer and `Kernel(recursive=True)` lifting chain exclusion.

Against the predictions of §20.7:

1. **Exactness: confirmed.** With a library `MapExpert` installed, the
   stable planner returns exactly the built-in plan rewritten by
   `embed_maps`, and the arithmetic pipeline gives the same answers at the
   same cost (`tests/test_pipeline.py`). Demand passes through: the digit
   recognizer still never runs on operator positions. The built-in `Map`
   node stays, so no experiment changed. The only difference is that the
   library `map` counts one invocation against the invocation budget.
2. **Planner optimality: confirmed.** On 300 random libraries with
   higher-order experts (one or two slots, fixed and per-element call
   bounds, declared expected calls in half), the cost planner agrees with
   exhaustive enumeration under worst-case and expected calls, every Pareto
   option type-checks, and the frontier covers every enumerated plan. The
   stable planner finds a plan exactly when one exists. The cheapest plan
   used a higher-order expert in more than 20 cases.
3. **Automatic cascades: confirmed, with one correction to the theory.**
   `nca.cascade` Part C installs the cheap and expensive digit recognizers
   and `Fallback` at six thresholds, measures errors on 2000 validation
   digit glyphs, and plans with depth 3. For each error target, the planner
   chooses `Fallback(cheap, expensive)` at some threshold. On 3958 test
   glyphs, its error and cost equal the hand-built requesting recognizer's
   exactly:

   | target (validation error) | chosen | test error | FLOPs per glyph |
hand-built error | hand-built FLOPs |    |---:|---|---:|---:|---:|---:|    |
0.0245 | fallback τ=0.99 (cheap, expensive) | 0.0063 | 2,312,551 | 0.0063 |
2,312,551 |    | 0.0270 | fallback τ=0.95 (cheap, expensive) | 0.0066 |
1,290,303 | 0.0066 | 1,290,303 |    | 0.0368 | fallback τ=0.7 (cheap,
expensive) | 0.0121 | 677,383 | 0.0121 | 677,383 |    | 0.0490 | fallback
τ=0.5 (cheap, expensive) | 0.0189 | 501,650 | 0.0189 | 501,650 |    | 0.0980 |
cheap | 0.0217 | 469,504 | – | – |

   The expensive recognizer alone (error 0.0058, 8.48M FLOPs) is never
   chosen: τ=0.99 reaches nearly its error at 27% of its cost. Validation
   glyphs (the first half of the MNIST test set) are harder than test
   glyphs, with errors about 2.5 and 4 times higher for the two
   recognizers, so targets are in validation units.

   **The correction.** At depth 4 the planner first chose
   `Fallback(cheap, Fallback(cheap, expensive))`. It predicted 2.01M FLOPs
   per glyph, but the plan cost 2.41M on test, more than the depth-3
   cascade. The expected-cost formula of §20.4 multiplies the second
   filling's expected cost by `P(unsure)`. That assumes the filling's cost
   does not depend on whether it is called. Here the inner cascade defers
   on exactly the glyphs where the outer one does, so its cost on the
   deferred glyphs is far above its average. `Fallback.assess` now charges
   the second filling its audit cost on the inputs where it is actually
   called. With that, nested re-checks of the cheap recognizer are
   correctly dominated. Depth 4 still finds deeper compositions whose
   validation gains (at most 0.0015, three glyphs in 2000) do not carry to
   test (for example 0.0068 against 0.0066 at the first target). Selecting
   among many candidates on one audit overfits it, as §17 would predict.
4. **Budgets: confirmed.** A divide-and-conquer summing expert asks the
   kernel for the sums of both halves of its input, so it requests its own
   question. On 16 numbers with cost 2 per invocation, it needs 62 cost
   units. With budget 62 or 69, it answers correctly and spends exactly 62.
   With budget 0, 1 or 60, `attempt` returns no answer, never a wrong one,
   and spends at most the budget. With the default kernel (chain
   exclusion), the same request is unresolved.

## 21. Decoding by the format

### 21.10 Predictions

1. **Coverage.** Correction answers formulas whose readings do not parse.
   At depth 8, where 18 of 30 top-rung readings fail to parse, coverage
   rises well above detection's (0.247 at `δ = 0.2`), and readings refused
   for not parsing disappear.
2. **Error when forced.** The decoded formula is right more often than the
   per-word reading. Error when forced to answer falls at every depth, most
   at depth 8 (0.57 for pairs).
3. **Validity.** If (P) is calibrated (§21.8), the error among answered
   formulas stays within `δ`. (P) is the strongest premise used so far, so
   this is the prediction most likely to fail. Risk control under shift is
   the remedy if it does.
4. **Compute.** Decoding adds about 1% to a top-rung pass. Climbs go to
   words that are likely wrong given the format, so fewer are needed.

### 21.11 Results

`nca.logic` with the setup of §18.10 and §19.9: the same readers,
calibration and 300 test formulas per depth. The correction account decodes
in `FormulaEvaluator(decode=True)`. The answered formula is decoded from the
readings' arity masses, and the certificate evaluates that same formula
under the calibrated arity distributions (premise P), so the bound concerns
exactly the answer given.

Coverage, with compute in kFLOPs per formula in brackets, and error when
forced to answer:

| depth | δ | pairs (§19) | correction | forced error: pairs / correction |
|---:|---:|---:|---:|---:|
| 2 | 0.2 | 0.980 (23) | 1.000 (6) | 0.020 / 0 |
| 2 | 0.01 | 0.970 (32) | 0.990 (14) | 0.023 / 0 |
| 4 | 0.2 | 0.973 (124) | 0.997 (38) | 0.027 / 0.003 |
| 4 | 0.05 | 0.963 (162) | 0.993 (51) | 0.027 / 0.003 |
| 4 | 0.01 | 0.937 (274) | 0.973 (132) | 0.037 / 0.003 |
| 6 | 0.2 | 0.817 (2833) | 0.937 (1046) | 0.163 / 0.010 |
| 6 | 0.05 | 0.707 (4497) | 0.870 (2063) | 0.217 / 0.013 |
| 6 | 0.01 | 0.557 (6764) | 0.727 (4211) | 0.223 / 0.013 |
| 8 | 0.2 | 0.247 (45391) | 0.607 (23958) | – / 0.063 |
| 8 | 0.05 | 0.080 (55227) | 0.280 (43443) | – / 0.063 |
| 8 | 0.01 | 0.007 (59426) | 0.077 (55353) | – / 0.063 |

At depths 2–6 no answered formula was wrong under any account. At depth 8
and `δ = 0.2`, 2 of the 182 answered formulas were wrong (0.011, 95% CI
[0.003, 0.039]), within `δ`. At the tighter targets none were. The mean
bound among answered formulas at `δ = 0.2` is 0.0031 at depth 4, 0.030 at
depth 6 and 0.146 at depth 8, against 0.0059 and 0.048 for pairs at depths
4 and 6. When forced to answer at depth 8, the top-rung per-word readings
err on 0.58 of formulas.

**Shift**, noise 0.2 in use with the correction account, audits as in §18.10
(two audit draws, which chose the same `λ`; the third was not run):

| depth | δ | uncontrolled: coverage, error answered | risk control: λ | coverage | error answered |
|---:|---:|---|---|---|---|
| 6 | 0.2 | 0.750, 0.049 | 0.5 | 0.893 | 0.071 |
| 6 | 0.05 | 0.523, 0.006 | 0.5 | 0.627 | 0.027 |

Pairs answered 0.410 and 0.257 of these formulas uncontrolled (§19.9).
Depth 8 under shift has not been run.

**Premise tests** (§21.8), bottom rung, 1000 test formulas per row. `O` is the
number of formulas whose decoded arity sequence is wrong, compared with
`Σ R`. `O₂` is the number with at least two per-word arity failures,
compared with `Σ e₂`. The last column is the observed number of per-word
arity failures over the predicted `Σ ρ`:

| noise | depth | `O` | `Σ R` | `P(X ≤ O)` | `O₂` | `Σ e₂` | failures / `Σ ρ` |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | 4 | 5 | 7.8 | 0.13 | 7 | 11.8 | 0.45 |
| 0.1 | 6 | 55 | 78.5 | 10⁻⁴ | 36 | 218 | 0.41 |
| 0.1 | 8 | 349 | 516 | 10⁻³⁹ | 312 | 3481 | 0.43 |
| 0.2 | 4 | 34 | 42.1 | 0.05 | 29 | 116 | 0.53 |
| 0.2 | 6 | 305 | 360 | 10⁻⁶ | 299 | 1864 | 0.57 |
| 0.2 | 8 | 939 | 961 | 3·10⁻⁴ | 953 | 31359 | 0.58 |

`P(X ≥ O)` is at least 0.95 in every row, so `R` never underestimates.
Binned by `R`, formulas with `R < 0.01` (about 1600 in all) had no wrong
decoded sequence. In `[0.01, 0.1)` the observed rate is 0.014–0.022 against
mean `R` 0.023–0.057. In `[0.1, 1)` it is 0.33–0.43 against 0.43–0.57.

Joint failures of word pairs at least 10 words apart, over the predicted
`Σ ρᵢρⱼ`, match the square of the marginal ratio in five of six rows: 0.16
against 0.17, 0.18 against 0.18, 0.33 against 0.28, 0.33 against 0.32, and
0.33 against 0.34. That is, failures are independent at their actual rates.
The exception is depth 4 at noise 0.1, with 7 joint failures where
independence at the observed rates predicts 1.3. Adjacent pairs fail
together no more often than independence predicts: 42 joint failures in
all, against about 50.

Against the predictions of §21.10:

1. **Coverage: confirmed.** Correction answers 99–100% of formulas at
   depths 2 and 4. At depth 6 it lifts coverage over pairs by 0.12–0.17 at
   every target, for example from 0.707 to 0.870 at `δ = 0.05`. At depth 8,
   the depth the prediction was about, it multiplies coverage by 2.5–11:
   from 0.247 to 0.607 at `δ = 0.2`, 0.080 to 0.280 at `δ = 0.05`, and
   0.007 to 0.077 at `δ = 0.01`. Depth 8 at tight targets stays limited.
2. **Error when forced: confirmed, strongly.** The decoded formula is wrong
   on 1.0–1.3% of depth-6 formulas, against 16–22% for per-word readings,
   on 0.3% at depth 4 against 2.7–3.7%, and on 6.3% at depth 8 against 58%
   for the top-rung readings. Most per-word errors are arity
   errors that the format corrects.
3. **Validity: confirmed, and the premise test says why.** The error among
   answered formulas stayed within `δ` everywhere: zero at depths 2–6 and
   0.011 at depth 8 and `δ = 0.2`. Under shift, the error among answered
   formulas stayed within `δ`, uncontrolled and with risk control. `R` is
   calibrated or conservative in every row and never significantly too
   small. Its conservatism comes from the per-word arity risks, which
   overstate the failure rate about twofold (column 8), not from the
   format. The pairs premise of §19, tested for the first time, holds in its
   testable consequence: `O₂` stays far below `Σ e₂` in every row. Failures
   of distant words are independent at their actual rates in five of six
   settings. The one excess, 7 against 1.3 at depth 4, was still absorbed by
   the conservative risks (7 ≤ 11.8).
4. **Compute: confirmed.** Correction spends 1.6–3.8 times less than pairs
   at depths 2–6, and 1.1–1.9 times less at depth 8 while answering far
   more. At depth 2 it needs barely more than the bottom rung (6
   against 5 kFLOPs), because it rarely climbs.

**Decoding cost per climb.** The account reruns the exact dynamic program
after every climb, at about 30 ms per decode at depth 8 in NumPy. With
hundreds of climbs per formula, a depth-8 evaluation with all targets did
not finish in over an hour. With the native kernel of §23.7 (0.9 ms per
decode) it takes 21 minutes for all three targets. The recursion is still
repeated in full where one word changed, which §23's banded, incremental
decoding would avoid.

## 22. Abstaining early

### 22.5 Predictions

1. **Identical answers under sound floors.** For the detection, certificate
   and arithmetic accounts, early abstention by floor gives the same answers
   with less compute.
2. **Savings where abstention dominates.** Savings are largest at depth 8
   and strict targets. At about `10⁻³` arity risk per fixed word, the pairs
   floor reaches `δ = 0.01` once roughly 140 words are fixed, against 575
   climbed now. That predicts several-fold less compute on abstained
   formulas.
3. **Hard style.** Glyphs whose top-rung risk alone exceeds `δ` end
   refinement at once. That accounts for most of the compute saved on hard
   expressions.

### 22.6 Results

`refine` takes a consumer's `floor(readings, risk, fixed)`, or, for the
default additive account, sums the fixed items' charges
(`additive_floor`). `FormulaEvaluator.floor` implements §22.3. For the
certificate account it charges each fixed word the smaller of its full and
arity risks, because under separately fitted temperatures either may be the
smaller (§18.3). A generic stopping rule (`nca.ladder.stopping_rule`) bins
refinement states by `log₁₀(bound / δ)`. It abstains in a bin where the
fraction of fitted states that went on to answer is below `λ` times their
mean remaining cost.

**Formulas** (`nca.logic --floors`, setup of §19.9): compute per formula in
kFLOPs, without and with floors.

| depth | δ | certificate | Markov | pairs |
|---:|---:|---:|---:|---:|
| 4 | 0.2 | 370 → 181 | 322 → 180 | 124 → 124 |
| 4 | 0.05 | 608 → 132 | 559 → 96 | 162 → 128 |
| 4 | 0.01 | 2719 → 1697 | 1158 → 247 | 274 → 193 |
| 6 | 0.2 | 6721 → 2619 | 4798 → 2377 | 2833 → 2450 |
| 6 | 0.05 | 11864 → 2876 | 8514 → 837 | 4497 → 2595 |
| 6 | 0.01 | 14892 → 1738 | 13302 → 616 | 6764 → 2201 |
| 8 | 0.2 | 58883 → 4127 | 54236 → 3545 | 45391 → 15542 |
| 8 | 0.05 | 59800 → 728 | 59614 → 731 | 55227 → 3026 |
| 8 | 0.01 | 59800 → 550 | 59800 → 547 | 59426 → 1612 |

Every row answered the same formulas with the same values, all 27 of them.
On abstained formulas the compute falls, for example, from 59,862 to 20,239
(pairs, depth 8, `δ = 0.2`) and from 59,805 to 1,602 (pairs, depth 8,
`δ = 0.01`).

**Arithmetic** (`nca.selective --floors`, additive floor, 300 expressions
per length): MFLOPs per expression.

| glyphs | δ = 0.2 | δ = 0.05 | δ = 0.01 |
|---:|---:|---:|---:|
| 3 | 11.6 → 10.7 | 18.2 → 13.8 | 29.6 → 19.4 |
| 15 | 114 → 70 | 232 → 84 | 424 → 106 |
| 63 | 1785 → 328 | 2720 → 356 | 3204 → 367 |

Answers are again identical in every row. With `--hard` (same library and
calibration, hard-style test expressions), compute falls from 93 to 45 MFLOPs
(3 glyphs, `δ = 0.2`), from 767 to 117 (15 glyphs, `δ = 0.01`) and from
3227 to 339 (63 glyphs, every `δ`), with identical answers.

**Predictive abstention** (pairs, depth 8, rule fitted on 150 validation
formulas): coverage and kFLOPs per formula, compared with floors alone.

| δ | floors | λ = 10⁻¹⁰ | λ = 10⁻⁸ | λ = 3·10⁻⁸ | λ = 10⁻⁷ |
|---:|---|---|---|---|---|
| 0.2 | 0.247, 15542 | 0.163, 1246 | 0.163, 1246 | 0.097, 651 | 0.043, 384 |
| 0.05 | 0.080, 3026 | 0.050, 1064 | 0.000, 413 | 0.000, 377 | 0.000, 374 |

No answered formula was wrong at any `λ`.

Against the predictions of §22.5:

1. **Identical answers: confirmed.** All 27 formula rows and all 9
   arithmetic rows, plus the 9 hard-style rows, answered exactly the same
   inputs with the same values.
2. **Savings where abstention dominates: confirmed, and larger than
   predicted.** At depth 8 compute falls 14× (certificate, `δ = 0.2`) to
   109× (certificate and Markov, `δ = 0.01`), and 37× for pairs at
   `δ = 0.01`. The prediction that about 140 words must be fixed was too
   pessimistic. The controller climbs the riskiest words first, whose
   top-rung arity risks are well above the average `10⁻³`. So the pairs floor
   passes `δ = 0.01` after about a dozen climbs (1.6M FLOPs on abstained
   formulas, against 0.37M for the bottom pass). The floor is weakest for
   pairs at loose targets: `min(S_F / 2, e₂)` is quadratic in `S_F`, so at
   depth 4 and `δ = 0.2` it never reaches `δ` and saves nothing.
3. **Hard style: confirmed for compute, but calibration fails.** At 15 and
   63 glyphs, floors cut compute by 6.5× and 9.5× at strict targets. They
   cannot repair what hard style breaks. This library's recognizers are not
   the normalized ones of §15, and its ladders are calibrated on the
   standard style, so the error
   among answered expressions is far above `δ` (0.40 at 3 glyphs,
   `δ = 0.2`), the shift failure of §17. Floors make that failure cheap, not
   correct.

**Predictive abstention.** The frontier is coarse. With 150 fitted formulas
most bins contain no state that went on to answer, so any `λ > 0` stops in
them. Its first step is still useful: at `δ = 0.2` it keeps two thirds of
the coverage (0.163 of 0.247) for one twelfth of the floors' compute (1.2M
against 15.5M FLOPs). Every answer stays within its bound, as §22.2
guarantees.

## 23. Efficient decoding

### 23.6 Predictions

1. **Same answers.** Banded decoding with `η = 10⁻⁴` returns the same
   decoded sequence as exact decoding on every formula where the exactness
   certificate `x ≥ U_j` holds, and that certificate holds on nearly all
   formulas at the top rung. The reported risk exceeds the exact risk by at
   most `U_j / Z_band`.
2. **Decoding cost per formula.** Over a full refinement at depth 8,
   exact-from-scratch decoding costs more than the reading it guides.
   Incremental banded decoding costs a small fraction of it, close to the
   counts above.
3. **Coverage unchanged.** With charges refreshed every `√m` climbs,
   coverage and error among answered formulas match per-step exact
   decoding within sampling noise, because only the climb order changes.

**Banded decoding, prediction 1** (NumPy reference, `η = 10⁻⁴`, 100 test
formulas per row, noise 0.1, readers calibrated on 100 validation formulas):

| rung | depth | words | same answer | certified exact | `j` mean, max | `W` max | risk slack max, mean |
|---|---:|---:|---:|---:|---|---:|---|
| bottom | 4 | 36 | 100 | 100 | 3.4, 8 | 29 | 5.9e-3, 9.3e-5 |
| bottom | 6 | 142 | 100 | 99 | 5.7, 11 | 41 | 2.9e-2, 5.4e-4 |
| bottom | 8 | 575 | 100 | 90 | 11.5, 18 | 69 | 0.38, 1.1e-2 |
| top | 4 | 36 | 100 | 100 | 2.7, 7 | 25 | 1.2e-4, 2.3e-5 |
| top | 6 | 142 | 100 | 100 | 4.2, 8 | 29 | 3.0e-3, 1.3e-4 |
| top | 8 | 575 | 100 | 98 | 7.1, 11 | 41 | 0.11, 1.9e-3 |

Every banded answer equals the exact one, including the formulas the
certificate leaves open. The slack prediction fails: the slack is bounded by
`U_j / Z_band`, not by `η`, and `Z` (the weight of all parseable sequences) is
far below 1 at depth 8. A slack chosen in absolute terms is too loose there.
The top rung needs `j ≈ 7` at depth 8, as THEORY §23.3 predicted for `S = 0.71`.

**Relative slack** (THEORY §23.3, Theorem 23.6; same formulas and readers).
Widening the band until `U_j ≤ η · Z_band`:

| rung | depth | same answer | certified exact | `j` mean, max | `W` max | risk slack max, mean |
|---|---:|---:|---:|---|---:|---|
| bottom | 4 | 100 | 100 | 3.5, 9 | 33 | 9.4e-5, 2.6e-5 |
| bottom | 6 | 100 | 100 | 6.3, 13 | 49 | 1.0e-4, 2.7e-5 |
| bottom | 8 | 100 | 100 | 13.6, 22 | 85 | 7.5e-5, 2.1e-5 |
| top | 4 | 100 | 100 | 2.7, 7 | 25 | 9.9e-5, 1.9e-5 |
| top | 6 | 100 | 100 | 4.3, 9 | 33 | 1.0e-4, 2.7e-5 |
| top | 8 | 100 | 100 | 8.1, 14 | 53 | 8.4e-5, 2.7e-5 |

The slack stays below `η` everywhere, as Theorem 23.6 guarantees, and every
answer is now certified exact. The price is a wider band: at depth 8 the top
rung averages `j = 8.1` (`W ≈ 29`) against 7.1 before, and the bottom rung
13.6. Prediction 1 of §23.6 holds with the slack read as relative.

**Splitting at the climbed word** (THEORY §23.4, Theorems 23.7 and 23.8;
NumPy, exact, unbanded). On 20 depth-8 test formulas, read on the bottom
rung, 5 random words each were climbed to the top rung. Scores from the
cached vectors match a full decode: `log Z` within 1.8e-14 and the best log
weight within 2.5e-14 over 100 climbs. Rescoring one climb takes 0.032 ms,
against 23.9 ms for a full decode, a factor of about 750. Building the
vectors once takes 12.7 ms per formula. Keeping them valid as the climbed
word moves (the cursor of §23.4) is not yet implemented.

**Cursor** (THEORY §23.4, Theorem 23.9; NumPy, exact, unbanded). On 20
depth-8 test formulas (`m ≈ 566` words), 100 words each were climbed from the
bottom to the top rung. Climbing in order of bottom-rung arity risk (a
stand-in for charge order) and in random order:

| order | mean sweep per climb | `m / 3` | time per climb | final `|Δ log Z|` |
|---|---:|---:|---:|---:|
| risk | 186.4 | 189 | 2.10 ms | 2.5e-14 |
| random | 185.8 | 189 | 2.11 ms | 8.9e-15 |

Risk order is spatially unordered, as §23.4 assumed: its sweep equals the
uniform prediction of Theorem 23.9. A climb with a moving cursor costs 2.1 ms
against 23.9 ms for a full decode, 11 times less; §23.5 counted 4.5 times
fewer operations for the incremental exact program, and the rest is the
backtracking and marginals the full decode also does. Banding the swept
vectors (`W ≈ 29` states instead of up to `m / 4`) is the remaining factor.

**Banded cursor** (THEORY §23.4, fixed reference; NumPy). Same 20 depth-8
formulas and 100 risk-ordered climbs from the bottom rung, `η = 10⁻⁴`, band
widened and rebuilt whenever `U_j > η · Z_band`. The final certified risk
exceeds the exact one by between 1.0e-7 and 1.9e-5, within `η`. A climb costs
1.52 ms including 87 rebuilds (about 4 per formula), against 2.1 ms for the
unbanded cursor. The final band averages `W = 62`, because readings start
on the bottom rung, where `S` is large. The gain is small because in NumPy
the cost per swept position is mostly call overhead, about 11 µs, nearly
independent of the number of states. The operation counts of §23.5 apply
only where the per-state work dominates, which means native code.

**Native cursor** (THEORY §23.4; Elisa kernel, log space). The same two
experiments with `Split` running its sweeps and rescoring in
`nca.native.decoding`, which updates the NumPy tables in place:

| cursor | time per climb, depth 8 | NumPy |
|---|---:|---:|
| exact, unbanded | 0.78 ms | 2.1 ms |
| banded, `η = 10⁻⁴`, including rebuilds | 0.17 ms | 1.52 ms |

Results are unchanged (final `|Δ log Z|` ≤ 2.7e-14; banded slack 1.0e-7 to
1.9e-5). Banding now pays: 4.6 times fewer milliseconds than the unbanded
native cursor, against 1.4 times in NumPy, because per-state work dominates
in native code. Against one native full decode (0.9 ms) a banded climb is
5.3 times cheaper, short of the 26 times of §23.5. The rest is the rebuilds
(about 4 per formula, each a full banded pass) and the log-space additions,
each an exponential and a logarithm.

**Rescaled native cursor** (THEORY §23.7, cursor paragraph). The kernel's
sum tables in linear space, each row of total 1 with its log scale; the max
tables stay in log space. Same experiments:

| cursor | log space | rescaled linear |
|---|---:|---:|
| exact, unbanded | 0.78 ms | 0.43 ms |
| banded, including rebuilds | 0.17 ms | 0.10 ms |

Final `|Δ log Z|` ≤ 1.2e-14 and banded slack 1.0e-7 to 1.9e-5, unchanged.
A banded climb is now 9 times cheaper than one native full decode (0.9 ms)
and 240 times cheaper than a NumPy full decode. The unbanded cursor does
about 78k transitions per climb in 0.43 ms, 5.5 ns each, so the
transcendental functions were less than half the cost; the rest is the max
pass, bounds-checked indexing, and the Python side of each climb.

**Where a depth-8 correction run spends its time** (profile, 3 test
formulas, `δ = 0.05`, native full decoding). 605 climbs took 3.26 s, 5.4 ms
per climb: two full native decodes 0.84 s (26%); rebuilding every word's
calibrated arity distribution 0.37 s and every word's risk 0.27 s, through
350k Python calls; the certificate pass over the decoded tree 0.38 s; the
rest Python bookkeeping in the account and controller. Each climb changes one
word's reading, but every per-word quantity is recomputed for all `m` words.
Replacing the decodes by the banded cursor would remove at most a quarter of
the time; the per-word work must become incremental as well.

**Traced decoded sequence** (THEORY §23.4, Theorem 23.10). The decoded
sequence read from the max vectors on either side of the climbed word,
predicted at `O(3 m)` comparisons, negligible beside the cursor's sweep.
Unbanded native cursor, 200 random climbs per size, Dirichlet(0.3) rows:

| words `m` | climb (sweep and rescore) | trace | full native decode |
|---:|---:|---:|---:|
| 35 | 0.005 ms | 0.004 ms | 0.009 ms |
| 143 | 0.028 ms | 0.012 ms | 0.065 ms |
| 575 | 0.451 ms | 0.042 ms | 0.738 ms |

The traced sequence equals the full decode's in all 600 climbs. At 575 words
the trace costs a tenth of the climb, so a climb with its decoded sequence
stays at 0.49 ms unbanded, against 0.74 ms for a full decode, which also
yields the marginals that the cursor does not.

**Native decoder (§23.7).** Over random inputs of up to 1200 words, both give
the same decoded sequence, `log Z` within relative 10⁻⁹ and marginals within
10⁻⁹. At depth 8 (575 words) a full decode takes 0.9 ms, against 30 ms in
NumPy: the 744k operations of §23.5 at about one per nanosecond. The
operation count per step is unchanged, still about seven top-rung word
readings, so banding and splitting (§23.2–23.4) would still cut it 26-fold.

The `S` values of THEORY §23.3 come from the measured top-rung value 0.71 at
depth 8 (§19.9), scaled by word count to depths 6 and 4.

**Risk allocation with stale priorities** (Theorem 23.11). A numerical
check reused each of 1,000 lognormal priority vectors of length 575 at current
risks 0.001, 0.05 and 0.2 (seed 23). Across 3,000 allocations the largest
absolute difference between the total charge and current risk was
2.78e-17. Tests also cover zero priorities, subnormal priorities and values
whose unscaled sum would overflow. This checks allocation only; it does not
measure refinement coverage or speed with cached priorities.

**Per-solve correction state.** A deterministic synthetic depth-6 formula
(seed 24, 143 words), initially assigning 0.9 extra probability to each true
word, received 40 random Dirichlet reading replacements. Fresh and cached
accounts differed in total bound by at most 8.89e-16. Elapsed times were
0.0280 s fresh and 0.0273 s cached, one run each: no meaningful speedup is
established. Cursor updates and periodic marginal refreshes now work, but
full distribution preparation and raw answer decoding remain. A separate
regression checks 30 changes and independent session initialization. It found
marginals slightly above 1 from rounding; priorities now clamp their resulting
negative risks to zero before normalization. These are synthetic account
checks, not deployment coverage measurements.

**Cache validity follow-up.** An experimental cache keyed by raw readings
reduced distribution callbacks from 5,720 to 182 over the same 40 updates,
but was removed before integration: unchanged raw scores can come from a new
rung with different calibration. The current implementation checks calibrated
weights and keeps current within-group risks. Skipping these checks requires
explicit rung revisions in the generic session interface. Cursor scoring now
stays at the changed position instead of returning to position zero, avoiding
an unnecessary sweep. No end-to-end speedup is claimed for this change.

**Revision identities.** A two-rung controlled refinement returns identical
raw distributions at both rungs. Its observed distribution revisions are
`[0, 1]` while the raw tensors compare equal. The generic distribution
accessor and selective adapter now expose rung revisions within a solve.
The correction cache does not yet consume these identities; this increment
establishes the invalidation interface before bypassing calibration work.

**Revision-keyed correction cache.** Repeating the synthetic seed-24,
143-word, 40-update experiment with explicit revisions reduced distribution
callbacks from 5,720 to 182 (143 initial rows plus 39 subsequent updates).
Single-run elapsed time was 0.02830 s fresh and 0.01593 s cached; maximum
total-bound difference was 8.89e-16. The regression changes calibration and
within-group risks while holding raw scores identical; the revised row alone
is recomputed and the total agrees with a fresh account. Plain callbacks
without revisions retain the full-recomputation path. These synthetic timings
do not establish deployment coverage or large-input speedups. Full raw
answer decoding, reading conversion and certificate traversal remain costs to
profile and move into the native execution path.

**Answer cursor integration.** On 575 synthetic Dirichlet reading rows
(seed 25), 40 single-row replacements produced exactly the same decoded words
as fresh decoding. Single-run times, including initialization, were 0.04945 s
fresh and 0.04075 s cached before removing redundant initial cursor updates.
The regression also checks 30 changes with native execution and with the
NumPy path forced. This measures word selection only, not full refinement
coverage. It reuses the splitting and tracing results (23.7–23.10); no new
mathematical premise is introduced. Tied maxima may select different
maximizers; the risk account always scores the actual selected sequence.

**Full refinement after cursor integration.** Using the existing character
reader checkpoint, calibration on 100 validation formulas of depth 4, noise
0.1, seed 0, and the first three depth-8 test formulas at target 0.05:

| execution | unprofiled seconds, two runs |
|---|---|
| fresh certificates | 2.0294, 1.9675 |
| per-solve cached certificates | 0.8425, 0.8269 |

The order was fresh, cached, cached, fresh, with calibration shared. Both
versions produced false on all three formulas, abstained on the first only,
and returned bounds 0.952626, 0.042211 and 0.048530 (rounded). Declared expert
costs were identical: 60,050,698, 373,750 and 2,955,450. The cached run took
605 certificate evaluations. Its separate cProfile run took 1.628 s, of
which certificate selection (`evaluated`) consumed 0.381 s, word selection
0.251 s and parsing 0.151 s. Only 2,323 distribution callbacks remained.
Certificate selection is the next native-port target; its least-risk
recurrence is already covered by the certificate theory and proofs.

These three formulas establish a local runtime improvement, approximately
2.4 times, not a coverage or risk guarantee. Stale priorities can change
climb order on other formulas, and broader coverage comparisons remain due.
The checkpoint is a pre-existing temporary artifact outside the repository;
these timings are conditional on that trained reader, not a fresh-training
replication.

**Native certificate recurrence.** The Elisa implementation matches the
reference on 120 random formulas at depths 1–6 with xor probability 0.3,
for both random weights and all-zero weights (ties): 240 comparisons. On
one depth-8 formula of 568 words, seed 26, 1,000 selections took 0.3165 s
in the Python recurrence and 0.0673 s through the native wrapper, about
4.7 times faster including marshaling. Full refinement has not yet been
remeasured after this port. All 108 tests passed with the kernel built.

The installed compiler refused the ordinary build because its LLVM-toolchain
provenance fingerprint differed. The kernel was compiled for this experiment
with the explicit `ELISA_ALLOW_STALE_STAGE1=1` override. This does not change
the project's default build command. Repairing the compiler provenance check
remains a follow-up before relying on an ordinary reproducible native build.

**Provenance diagnosis and rebuilt certificate kernel.** The toolchain
artifacts were unchanged. The differing fingerprint was the effective linker
command: the inherited `LIBRARY_PATH` repeated the bdw-gc directory. Using
`LIBRARY_PATH=/opt/homebrew/opt/bdw-gc/lib:` and
`ELISA_TOOL_PYTHON=/opt/homebrew/bin/python3.14` for the build matched the
installed compiler's recorded environment and rebuilt the kernel without
`ELISA_ALLOW_STALE_STAGE1`. The trailing empty search-path entry is part of
that recorded environment, not a portable project requirement. The compiler
correctly detects this difference; no provenance bypass or source fix was
needed. The earlier proposed provenance repair is therefore resolved by
matching the build environment rather than weakening its check.

All 108 tests passed on the rebuilt kernel. Repeating the three-formula,
depth-8 cProfile experiment took 1.315 s (previously 1.628 s), again with
605 certificate calls and two answers. Certificate selection fell from
0.381 s to 0.086 s including native marshaling; parsing remained 0.147 s
and word selection 0.247 s. These are profiled single runs rather than a
controlled runtime benchmark. Parsing and word-selection marshaling are
now the clearest remaining full-sequence work for a subsequent native port.

**Native prefix parsing.** The explicit-stack Elisa parser matches the
reference on every arity sequence of lengths 0–7 over `{0,1,2}` (3,280
cases), including incomplete and trailing-word inputs. A 2,001-word unary
chain also parses without the reference's recursion-depth limitation. The
implementation follows the prefix-format characterization (21.1–21.3),
with no change in the accepted binary-arity language.

On a 570-word depth-8 formula (seed 27), 1,000 parses took 0.0711 s in
the reference and 0.0686 s through the native wrapper. This single-run
microbenchmark shows only a marginal gain: child-list reconstruction remains
in Python. Passing native child arrays directly to certificate selection is
the next experiment, to avoid the round trip. The kernel rebuilt without a
stale override using the matched provenance environment recorded above.

**Fused parsing and certificate selection.** The correction path now calls
one Elisa export for both stages. Twelve random/tied-weight checks over
formulas at depths 1–6 match the reference, and empty, incomplete and
trailing-word cases are rejected. All 110 native-enabled tests pass.
The same three-formula depth-8 profile takes 1.106 s, down from 1.315 s;
605 certificate calls still produce two answers. Python recursive parsing
no longer appears among the leading costs. These single profiled runs do not
establish a general speedup or coverage equivalence.

During compilation, passing owned arrays implicitly to view parameters
produced invalid LLVM; `.view()` calls were also declined. Explicit borrowed
slices compile and pass the comparisons. The compiler conversion failure
remains a separate repair target; this port uses the supported slice form.

**Minimal compiler conversion reproduction.** A function `first(xs:
view[i64])` returning `xs[0]`, called with a local `darray[i64] = [7,9]`,
is enough to reproduce the native-port compiler failure. Passing the array
implicitly produces LLVM passing `{ptr,i64,i64}` to a `{ptr,i64}` parameter.
Calling `.view()` is declined by the backend. Passing `xs[0:xs.count]` builds
and executes with result 7. Temporary probes were created outside the
repository and removed after execution.

The direct-call emitter uses `emit_expression_coerced` in
`src/backend/codegen_convert.elisa`. Its current branches cover numeric and
structural-tuple conversion but no owned-array to borrowed-view conversion;
its fallback forwards the owned header unchanged. The repair target is now
isolated, but compiler source changes and regression qualification remain
pending. The NCA native port continues using explicit slices.

**Additional full-refinement sample.** With the same reader checkpoint and
100 depth-4 validation formulas, target 0.05, noise 0.1, test seed 1, six
formulas at each depth were evaluated with fresh then cached accounts:

| depth | fresh seconds | cached seconds | answered | wrong answered |
|---|---:|---:|---:|---:|
| 6 | 0.2069 | 0.0847 | 5/6 | 0 |
| 8 | 7.2952 | 3.0727 | 2/6 | 0 |

Answers and abstentions agreed on all 12 inputs. Total declared expert costs
also agreed: 15,662,804 at depth 6 and 244,163,586 at depth 8. This extends
the earlier three-input comparison and is consistent with about 2.4 times
less runtime, but remains a small, fixed-order experiment without confidence
intervals. It does not establish general coverage or reliability equivalence.

**Compiler conversion repaired.** Elisa compiler commit `18eb222b8` now
constructs a borrowed view from an owned dynamic array's data pointer and
count at call boundaries, excluding capacity. The new empty/nonempty call
regression and existing buffer-view and mutable-view smoke tests pass.
The installed compiler snapshot is updated. NCA's kernel rebuilt through it
without a stale override, and all 110 project tests pass. The separate
`.view()` method-lowering limitation has not been repaired; explicit slices
and implicit owned-array arguments cover the current kernel use case.

**Native grouped argmax.** The remaining per-word restricted argmax loop
now runs in Elisa. The generic kernel accepts class group ids, row scores
and row decisions. Tests compare 100 rows for random normal scores, zero
scores and negative-infinity scores, including nonconsecutive group ids and
first-class ties. All 111 native tests pass; disabling native execution gives
105 passes and six native-only skips.

On 575 prepared score rows, seed 29, 1,000 calls took 0.1245 s using the
former `max(ARITY_DECISION[d], key=row.__getitem__)` loop and 0.0029 s through
the native export. Input preparation and class-to-word conversion are excluded,
so this is a selection microbenchmark rather than a full-refinement speedup.
The operation is the existing restricted identity decision of §21.5; no new
risk assumption or mathematical algorithm is introduced.

## 24. When the prior is wrong

### 24.6 Predictions for the calibration test

These predictions are made before the premise tests of §21.8 are read.
Split the test formulas by whether the decoded arity sequence is a complete
tree (`â ∈ S_m`). The evaluator cannot do this, but the test can.

1. **Complete decodings: conservative.** Among formulas with `â ∈ S_m`, the
   number of wrong decoded arity sequences is at most `Σ R_f`, typically far
   below. (P) spreads posterior mass over competitors the generator never
   produces.
2. **Incomplete decodings: always wrong.** Every formula with `â ∉ S_m` has
   a wrong decoded arity sequence, whatever its `R`.
3. **Direction of the overall bias.** (P) is flatter than the generator: it
   has more support. A flatter prior overstates the risk where decoding
   lands in the generator's support and understates it, to the extreme,
   where it lands outside. Overall calibration therefore depends on how
   often decoding leaves `S_m`, which grows with the summed arity risk `S`.
   Expected pattern:
   - conservative (`O < Σ R`) at shallow depths and high rungs;
   - increasingly anti-conservative at depth 8, at the bottom rung and
     under noise 0.2;
   - excess errors concentrated at small `R` among incomplete decodings.
4. **Answered formulas.** Wherever incomplete decodings are answered (their
   `R` below `δ`), the error among answered formulas exceeds the model's
   prediction. Under shift, risk control (§24.5) is what restores the
   guarantee, at the cost of coverage.

## 25. Which word to climb, and when to stop

### 25.5 Predictions

1. **Climbs before the floor passes `δ`.** The number of top-rung words
   when the pairs floor first exceeds `δ` matches `1 + √(2δ) / a`, with `a`
   the measured top-rung risk of the words climbed first. It does not
   match the prediction from the mean risk.
2. **The order statistic.** The top-rung risks of the first dozen words
   climbed are about an order of magnitude above the per-word mean.
3. **A finer frontier.** Binning by (floor ratio, open mass / δ) instead of
   bound / δ gives a frontier with more distinct points, and, at equal
   compute, coverage at least that of the one-feature rule.
4. **Ratio order.** In ladders with unequal climb costs (the arithmetic
   ladder with second looks), climbing by charge per unit cost reaches `δ`
   with no more compute than climbing by charge.

**Explanation of the dozen climbs.** §22.5 put the per-word mean top-rung risk,
about `10⁻³`, in place of `a`, which gives `t ≈ 142` at `δ = 0.01`. The
observed dozen climbs corresponds to `a ≈ √0.02 / 11 ≈ 0.013`, about thirteen
times the mean (THEORY §25.2).

## 26. Composing cascades

### 26.6 Predictions

1. **Cost.** On the audit, the measured covariance `Cov(1_U, c)` of each
   nested fallback equals its gap between measured cost and the independent
   formula (§26.2). It is positive for every nested re-check of the same
   recognizer.
2. **Nesting rule.** A nested fallback beats a flat one exactly when
   `P(U' | U) < 1 − κ_{a'} / κ_b` on the audit. No re-check of the cheap
   recognizer by itself satisfies this.
3. **Selection margin.** Accepting a deeper composition only when its
   estimated gain exceeds `2ε(n, K)` removes the depth-4 choices that did
   not carry to test, and leaves the depth-3 cascades of §20.8 unchanged.

**The failure.** `Fallback(cheap, Fallback(cheap, expensive))` was predicted
at 2.01M FLOPs per glyph and measured at 2.41M (§20.8); THEORY §26 explains
the gap.

**Selection margin applied to §20.8** (THEORY §26.5). There, `e ≈ 0.025` on
validation glyphs and `n = 2000`. With `K ≈ 100` candidates and `β = 0.1`, `ε
≈ 0.014`, so candidates whose estimated errors differ by less than about `2ε ≈
0.03` cannot be told apart. The depth-4 gains of at most 0.0015 are far inside
that margin, which explains why they did not carry to test. Resolving a gain
of 0.0015 needs `n ≈ 8 e ln(2K/β) / Δ²`, about `7 · 10⁵` glyphs. Comparing two
candidates on the same glyphs (paired) replaces `e` by their disagreement
rate, typically a few times smaller, but the order of magnitude stays.

## 27. Priors as experts

### 27.6 Predictions

The experiment decodes with three prior experts: format only, height at most
`d + 1`, and complete trees of depth `d`. It runs at depths 4, 6 and 8, at
calibration noise and under noise 0.2.

1. **Calibration.** Under the complete-tree prior, the calibration test of
   §21.8 passes two-sided at every depth and rung in distribution
   (`R* = R`). No decoding falls outside `S_m`. Any residual miscalibration
   comes from the readers' per-word calibration and independence, not from
   the prior, and grows under noise 0.2 as the readers' calibration
   degrades.
2. **Coverage.** At depth 8, coverage under the complete-tree prior exceeds
   format-only correction at every target. Competitors outside `S_m` no
   longer contribute to `R`. The error among answered formulas stays within
   `δ`. The height-bounded prior lies between the two.
3. **Selection.** Label-free evidence over held-out readings ranks the
   priors complete trees, then height-bounded, then format only, at every
   depth, from a few dozen formulas.
4. **Cost.** Decoding under the complete-tree prior costs within a small
   factor of format-only decoding. Compute per formula is dominated by
   reading, as before.
