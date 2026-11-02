# 11. Evaluation methodology

**Accuracy intervals.** For `k` successes in `n` samples
the 95% Wilson score interval is
`(p̂ + z²/2n ± z·√(p̂(1−p̂)/n + z²/4n²)) / (1 + z²/n)` with `z ≈ 1.96`. It stays
inside `[0, 1]` and generally performs better near 0 and 1 than the simple
normal interval. It is an approximate interval, not a guaranteed bound for
every sample size. An empty sample is reported as `[0, 1]`.

**Paired differences.** Systems are compared
on the same samples, so their difference is estimated from per-sample
differences `dᵢ = 1[second correct] − 1[first correct]`: mean `d̄`, interval
`d̄ ± z·s_d/√n`, with the sample standard deviation `s_d`. This requires
equally sized matched samples and at least two pairs. Shared successes and
failures contribute zero, which can reduce uncertainty relative to treating
the systems as independent. The normal approximation can be unreliable with
few discordant pairs; in particular it becomes a zero-width interval when
all observed differences agree. It is descriptive, not a certified risk bound.

[Theory index](../THEORY.md)
