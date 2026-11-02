"""Signed attestations and the keys a deployment trusts (THEORY §32).

An issuer is a public key written ``scheme:key`` (hexadecimal), and a
signature signs the canonical encoding of an attestation's unsigned data.
Schemes are registered by name, so the core depends on none; Ed25519 is
registered when the optional ``cryptography`` package is installed
(``pip install nca[trust]``). A ``Trust`` accepts an attestation only if its
issuer is one of the trusted keys and its signature verifies under a
registered scheme; anything else, including an unsigned attestation or an
unknown scheme, is not accepted.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace

from nca.objects import Attestation, canonical

Verify = Callable[[bytes, bytes, bytes], bool]
"""``verify(public_key, message, signature)``."""

_SCHEMES: dict[str, Verify] = {}


def register(scheme: str, verify: Verify) -> None:
    """Make signatures of ``scheme`` verifiable."""
    _SCHEMES[scheme] = verify


def verified(attestation: Attestation) -> bool:
    """Whether ``attestation`` is signed by its issuer under a registered scheme."""
    scheme, _, key = attestation.issuer.partition(":")
    verify = _SCHEMES.get(scheme)
    if verify is None or attestation.signature is None:
        return False
    try:
        return verify(bytes.fromhex(key), canonical(attestation.unsigned()),
                      bytes.fromhex(attestation.signature))
    except ValueError:
        return False


class Trust:
    """The issuers whose verified attestations a deployment accepts."""

    def __init__(self, issuers: Iterable[str]) -> None:
        self.issuers = frozenset(issuers)

    def accepts(self, attestation: Attestation) -> bool:
        return attestation.issuer in self.issuers and verified(attestation)


try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (Ed25519PrivateKey,
                                                                   Ed25519PublicKey)
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
except ImportError:  # Ed25519 is unavailable; other schemes may still be registered.
    Ed25519PrivateKey = None
else:
    def _verify_ed25519(key: bytes, message: bytes, signature: bytes) -> bool:
        try:
            Ed25519PublicKey.from_public_bytes(key).verify(signature, message)
        except (InvalidSignature, ValueError):
            return False
        return True

    register("ed25519", _verify_ed25519)


class Ed25519Signer:
    """An Ed25519 key pair that signs attestations as issuer ``ed25519:<key>``."""

    def __init__(self, private: bytes | None = None) -> None:
        if Ed25519PrivateKey is None:
            raise RuntimeError("Ed25519 signing needs the cryptography package")
        self._key = (Ed25519PrivateKey.generate() if private is None
                     else Ed25519PrivateKey.from_private_bytes(private))
        public = self._key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.issuer = f"ed25519:{public.hex()}"

    def sign(self, attestation: Attestation) -> Attestation:
        """``attestation`` issued and signed by this key."""
        unsigned = replace(attestation, issuer=self.issuer, signature=None)
        return replace(unsigned, signature=self._key.sign(canonical(unsigned.unsigned())).hex())
