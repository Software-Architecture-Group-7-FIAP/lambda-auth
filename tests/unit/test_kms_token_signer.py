import base64
import json
from collections.abc import Mapping

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from lambda_auth.adapters.kms_token_signer import KmsTokenSigner


class FakeKmsClient:
    def __init__(self, private_key: rsa.RSAPrivateKey) -> None:
        self.private_key = private_key
        self.sign_request: dict[str, object] | None = None
        self.public_key_calls = 0

    def sign(self, **request: object) -> Mapping[str, object]:
        self.sign_request = request
        message = request["Message"]
        assert isinstance(message, bytes)
        signature = self.private_key.sign(
            message,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return {"Signature": signature}

    def get_public_key(self, **request: object) -> Mapping[str, object]:
        self.public_key_calls += 1
        assert request["KeyId"] == "test-kms-key"
        public_key = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return {"PublicKey": public_key}


@pytest.fixture
def private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _decode_segment(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def test_signer_issues_verifiable_rs256_jwt(private_key: rsa.RSAPrivateKey) -> None:
    kms_client = FakeKmsClient(private_key)
    signer = KmsTokenSigner("test-kms-key", "test-kid", "us-east-1", kms_client)
    claims = {
        "sub": "42",
        "principal_type": "customer",
        "scope": "customer",
        "iss": "https://auth.example.invalid",
        "aud": "auto-shop-api",
        "iat": 1_800_000_000,
        "exp": 1_800_000_900,
        "jti": "token-id",
    }

    token = signer.issue(claims)
    header_segment, payload_segment, signature_segment = token.split(".")
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = _decode_segment(signature_segment)
    private_key.public_key().verify(
        signature,
        signing_input,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    assert json.loads(_decode_segment(header_segment)) == {
        "alg": "RS256",
        "kid": "test-kid",
        "typ": "JWT",
    }
    assert json.loads(_decode_segment(payload_segment)) == claims
    assert kms_client.sign_request is not None
    assert kms_client.sign_request["KeyId"] == "test-kms-key"
    assert kms_client.sign_request["MessageType"] == "RAW"
    assert kms_client.sign_request["SigningAlgorithm"] == "RSASSA_PKCS1_V1_5_SHA_256"


def test_signer_publishes_cached_rsa_jwks(private_key: rsa.RSAPrivateKey) -> None:
    kms_client = FakeKmsClient(private_key)
    signer = KmsTokenSigner("test-kms-key", "test-kid", "us-east-1", kms_client)

    jwks = signer.get_jwks()
    repeated_jwks = signer.get_jwks()

    key = jwks["keys"][0]
    assert key["kty"] == "RSA"
    assert key["use"] == "sig"
    assert key["alg"] == "RS256"
    assert key["kid"] == "test-kid"
    assert "n" in key
    assert "e" in key
    assert "d" not in key
    assert repeated_jwks == jwks
    assert kms_client.public_key_calls == 1


def test_signer_rejects_incomplete_configuration() -> None:
    signer = KmsTokenSigner("", "", "")

    with pytest.raises(RuntimeError, match="configuration"):
        signer.issue({"sub": "42"})
