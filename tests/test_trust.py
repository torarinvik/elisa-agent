"""Signed attestations and trusted evidence (§32)."""

from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("cryptography")

from nca.evidence import evaluation, outcomes, promote  # noqa: E402
from nca.objects import Store  # noqa: E402
from nca.trust import Ed25519Signer, Trust, verified  # noqa: E402
from test_evidence import BENCH, library  # noqa: E402


def test_signatures_bind_claims_to_keys(tmp_path: Path) -> None:
    store = Store()
    reader = library(store, 1)[0]
    lab = Ed25519Signer()
    claim = lab.sign(evaluation(reader.identity, BENCH, [True, False]))
    assert claim.issuer == lab.issuer and verified(claim)
    assert not verified(replace(claim, claim={**claim.claim, "outcomes": "11"}))
    assert not verified(replace(claim, issuer=Ed25519Signer().issuer))
    assert not verified(replace(claim, signature=None))
    assert not verified(replace(claim, issuer="unknown:00"))
    same = Ed25519Signer(lab._key.private_bytes_raw())
    assert same.sign(evaluation(reader.identity, BENCH, [True, False])) == claim
    store.put(claim)
    store.save(tmp_path)
    (reopened,) = Store.open(tmp_path).attestations(reader.identity)
    assert reopened == claim and verified(reopened)


def test_only_verified_evaluations_by_trusted_keys_count() -> None:
    store = Store()
    modules = library(store, 2)
    lab, rival = Ed25519Signer(), Ed25519Signer()
    trust = Trust({lab.issuer})
    good = [i < 20 for i in range(40)]
    store.put(lab.sign(evaluation(modules[0].identity, BENCH, good)))
    store.put(lab.sign(evaluation(modules[1].identity, BENCH, good)))
    # Glowing evidence from an untrusted key, a forgery claiming the lab's
    # key, and an unsigned claim in the lab's name change nothing.
    perfect = [True] * 40
    store.put(rival.sign(evaluation(modules[1].identity, BENCH, perfect)))
    forged = rival.sign(evaluation(modules[1].identity, BENCH, perfect))
    store.put(replace(forged, issuer=lab.issuer))
    store.put(evaluation(modules[1].identity, BENCH, perfect, lab.issuer))
    assert outcomes(store, modules[1].identity, BENCH, trust) == tuple(good)
    assert promote(modules, store, BENCH, trust) == (modules, [])
    assert promote(modules, store, BENCH, Trust({rival.issuer}))[1] == []
