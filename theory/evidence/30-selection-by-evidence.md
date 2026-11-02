# 30. Selection by evidence

## 30.1 Evaluation evidence

Stable planning (§3) prefers experts by installation order, which keeps
routes fixed but says nothing about which of several interchangeable
experts is better. Experts with identical contracts are *substitutes*
(§9); among them, the first installed is the *incumbent*, the expert every
route through that contract uses.

A *benchmark* is a finite sequence of labeled inputs of a contract,
identified by the digest of its contents. An *evaluation* is an
attestation (§28.4) about an expert stating, for each sample of a
benchmark in order, whether the expert's output was correct. Two
evaluations on the same benchmark pair their outcomes sample by sample.

Selection rests on three assumptions, which no attestation can establish:
the benchmark's samples are independent draws from the distribution the
deployment cares about, no evaluated expert was fitted on them, and the
issuers whose evaluations are read report outcomes truthfully. Which
issuers to trust is the deployment's choice.

## 30.2 Promotion

A challenger is *better* than the incumbent if, on a sample from the
benchmark's distribution, it is more likely to be right where the
incumbent is wrong than the reverse. For the `k` challengers of one
incumbent with evaluations on a benchmark, each is tested by the exact
one-sided sign test of §8 on its discordant samples at level `α / k`. If
any test rejects, the challenger with the smallest p-value, ties broken by
installation order, is *promoted*: it exchanges places with the incumbent
in the library.

**Theorem 30.1 (family-wise error).** Under the assumptions of §30.1, the
probability that promotion replaces an incumbent by a challenger that is
not better is at most `α`.

*Proof.* Conditionally on the number of discordant samples, the sign test
of a challenger that is not better rejects at level `α / k` with
probability at most `α / k`. Promoting a challenger that is not better
requires such a rejection among at most `k` tests, so by the union bound
the probability is at most `k · α / k = α`. ∎

A deployment promoting along several contracts at once splits its budget
among them in the same way.

## 30.3 Promotion is substitution

Promotion changes the library's order, so stable planning could in
principle choose different routes for every goal. It does not.

**Theorem 30.2 (planning commutes with substitution).** Let `σ` map
contracts to contracts with the same inputs and output. Planning over the
library with `σ` applied to each contract returns the plan found over the
original library with `σ` applied to each of its contracts; this holds for
depth-bounded, shallow and stable planning.

Promotion applies the `σ` that exchanges the incumbent and the challenger.
Hence after a promotion every route that used the incumbent uses the
challenger in the same place, every other route is unchanged, and every
route remains well-typed. Since this `σ` is its own inverse, promoting the
incumbent back restores every route exactly.

What changes is behavior, and §9 bounds how much. Theorem 30.1 controls
the probability that the change is for the worse on the benchmark's
distribution; it says nothing about other distributions (§5).
