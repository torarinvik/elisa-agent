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
