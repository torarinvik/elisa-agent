# 32. Trust

## 32.1 Signed claims

Content addressing (§28.1) proves which bytes an object is, not who stands
behind a claim about it. An attestation's issuer is therefore a public key
of a signature scheme, and a *signed* attestation carries a signature on
its unsigned contents: subject, kind, claim and issuer. Changing any of
them invalidates the signature, and producing a valid signature for a key
requires its private key. These are the scheme's assumptions
(unforgeability), not theorems here.

A *trust* is a finite set of keys, chosen by the deployment. It *accepts* an
attestation when the issuer is in the set and the signature verifies.
Unsigned attestations, unknown schemes and failed signatures are never
accepted; they may be stored, since storing a claim asserts nothing.

## 32.2 Isolation

Every use of evidence, promotion (§30) and risk bounds (§31), reads only
accepted attestations.

**Theorem 32.1 (isolation).** Adding attestations that a trust does not
accept changes no decision made under that trust.

*Proof.* Each decision is a function of the accepted attestations, and
filtering a list extended by unaccepted elements gives the filtering of the
original list. ∎

So anyone may publish evidence about any expert, honest or not, without
being able to move a deployment that does not trust them. What trust
cannot do is make a trusted issuer honest: a trusted key that signs false
outcomes defeats Theorems 30.1 and 31.1 as any false premise does. Two
trusted evaluations of one expert on one benchmark that disagree are
therefore an error, not a choice. Keeping caches honest under false purity
claims (§28.5) needs evidence of a different kind, such as recomputation of
sampled entries, which this section does not provide.

## 32.3 Checking purity

A purity declaration (§28.5) is a claim like any other, and a false one
makes a shared cache return values the expert would no longer compute.
It can be tested where the cache is read: on each hit, with probability
`q` and independently of everything else, the expert is invoked anyway and
its output compared with the stored one.

A single mismatch refutes the declaration outright: the inputs have equal
digests, so, unless the digest collides, a function would have returned
the same value. A refuted expert's entries are dropped and it is never
cached again. Without a mismatch the evidence is statistical. Let a
fraction `f` of an expert's hits return a value that recomputation would
not reproduce.

**Theorem 32.2 (detection).** The probability that `N` hits pass without a
detected mismatch is `(1 − q f)^N ≤ exp(−q f N)`.

So detection needs about `1 / (q f)` hits, and `n` checks without a
mismatch bound `f` above at confidence `1 − β` by the binomial (Clopper–
Pearson) limit for zero failures in `n`. A *purity* attestation records an
expert's checks and mismatches, so that one deployment's checks become
evidence for others, read under trust like every other claim. Bitwise
comparison makes any nondeterminism, such as unordered floating-point
reductions, a refutation: such an expert is not pure in the sense §28.5
needs.
