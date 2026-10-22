"""Adaptador RS256 que usa AWS KMS e publica a chave pública como JWKS."""

import base64
import json
from collections.abc import Mapping
from typing import Any

from botocore.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_KMS_SIGNING_ALGORITHM = "RSASSA_PKCS1_V1_5_SHA_256"
_AWS_CLIENT_CONFIG = Config(
    connect_timeout=1,
    read_timeout=3,
    retries={"mode": "standard", "total_max_attempts": 1},
)


class KmsTokenSigner:
    def __init__(
        self,
        kms_key_id: str,
        jwt_kid: str,
        region: str,
        kms_client: Any | None = None,
        *,
        additional_public_keys: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self._kms_key_id = kms_key_id
        self._jwt_kid = jwt_kid
        self._region = region
        self._kms_client = kms_client
        self._public_keys = (
            (self._jwt_kid, self._kms_key_id),
            *tuple(sorted(additional_public_keys, key=lambda key: key[0])),
        )
        self._public_jwks: dict[tuple[str, str], dict[str, str]] = {}

    def issue(self, claims: Mapping[str, object]) -> str:
        self._ensure_configured()
        header = {"alg": "RS256", "kid": self._jwt_kid, "typ": "JWT"}
        encoded_header = _base64url(_json_bytes(header))
        encoded_claims = _base64url(_json_bytes(dict(claims)))
        signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
        result = self._client().sign(
            KeyId=self._kms_key_id,
            Message=signing_input,
            MessageType="RAW",
            SigningAlgorithm=_KMS_SIGNING_ALGORITHM,
        )
        signature = result.get("Signature")
        if not isinstance(signature, bytes):
            raise RuntimeError("KMS did not return a signature")
        return f"{signing_input.decode('ascii')}.{_base64url(signature)}"

    def get_jwks(self) -> Mapping[str, object]:
        self._ensure_configured()
        keys = [self._public_jwk(kid, kms_key_id) for kid, kms_key_id in self._public_keys]
        return {"keys": [key.copy() for key in keys]}

    def _public_jwk(self, kid: str, kms_key_id: str) -> dict[str, str]:
        cache_key = (kid, kms_key_id)
        cached = self._public_jwks.get(cache_key)
        if cached is not None:
            return cached

        result = self._client().get_public_key(KeyId=kms_key_id)
        der_public_key = result.get("PublicKey")
        if not isinstance(der_public_key, bytes):
            raise RuntimeError("KMS did not return a public key")

        public_key = serialization.load_der_public_key(der_public_key)
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise RuntimeError("KMS key must be an RSA public key")

        public_numbers = public_key.public_numbers()
        jwk = {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": kid,
            "n": _base64url(
                public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, "big")
            ),
            "e": _base64url(
                public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, "big")
            ),
        }
        self._public_jwks[cache_key] = jwk
        return jwk

    def _ensure_configured(self) -> None:
        if not self._kms_key_id or not self._jwt_kid or not self._region:
            raise RuntimeError("KMS signing configuration is incomplete")

    def _client(self) -> Any:
        if self._kms_client is None:
            import boto3

            self._kms_client = boto3.client(
                "kms",
                region_name=self._region,
                config=_AWS_CLIENT_CONFIG,
            )
        return self._kms_client


def _json_bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
