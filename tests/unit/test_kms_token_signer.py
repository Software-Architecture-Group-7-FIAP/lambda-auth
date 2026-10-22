import base64
import json
from collections.abc import Mapping

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from lambda_auth.adapters.kms_token_signer import KmsTokenSigner


class FakeKmsClient:
    def __init__(self, private_keys: Mapping[str, rsa.RSAPrivateKey]) -> None:
        self.private_keys = private_keys
        self.sign_request: dict[str, object] | None = None
        self.public_key_calls: list[str] = []

    def sign(self, **request: object) -> Mapping[str, object]:
        self.sign_request = request
        message = request["Message"]
        assert isinstance(message, bytes)
        key_id = request["KeyId"]
        assert isinstance(key_id, str)
        signature = self.private_keys[key_id].sign(
            message,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return {"Signature": signature}

    def get_public_key(self, **request: object) -> Mapping[str, object]:
        key_id = request["KeyId"]
        assert isinstance(key_id, str)
        self.public_key_calls.append(key_id)
        public_key = (
            self.private_keys[key_id]
            .public_key()
            .public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        return {"PublicKey": public_key}


@pytest.fixture
def private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _decode_segment(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def test_signer_issues_verifiable_rs256_jwt(private_key: rsa.RSAPrivateKey) -> None:
    kms_client = FakeKmsClient({"test-kms-key": private_key})
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
    kms_client = FakeKmsClient({"test-kms-key": private_key})
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
    assert kms_client.public_key_calls == ["test-kms-key"]


def test_signer_publishes_active_then_sorted_additional_keys_and_caches_each() -> None:
    keys = {
        key_id: rsa.generate_private_key(public_exponent=65537, key_size=2048)
        for key_id in ("kms-active", "kms-old", "kms-next")
    }
    kms_client = FakeKmsClient(keys)
    signer = KmsTokenSigner(
        "kms-active",
        "active",
        "us-east-1",
        kms_client,
        additional_public_keys=(("old-z", "kms-old"), ("next-a", "kms-next")),
    )

    first = signer.get_jwks()
    first["keys"][0]["kid"] = "mutated"
    second = signer.get_jwks()

    assert [key["kid"] for key in second["keys"]] == ["active", "next-a", "old-z"]
    assert all(set(key) == {"kty", "use", "alg", "kid", "n", "e"} for key in second["keys"])
    assert kms_client.public_key_calls == ["kms-active", "kms-next", "kms-old"]

    signer.issue({"sub": "42"})
    assert kms_client.sign_request is not None
    assert kms_client.sign_request["KeyId"] == "kms-active"


def test_signer_fails_complete_jwks_when_any_public_key_cannot_be_loaded() -> None:
    active = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    kms_client = FakeKmsClient({"kms-active": active})
    signer = KmsTokenSigner(
        "kms-active",
        "active",
        "us-east-1",
        kms_client,
        additional_public_keys=(("missing", "kms-missing"),),
    )

    with pytest.raises(KeyError):
        signer.get_jwks()


def test_signer_rejects_incomplete_configuration() -> None:
    signer = KmsTokenSigner("", "", "")

    with pytest.raises(RuntimeError, match="configuration"):
        signer.issue({"sub": "42"})


def test_aws_client_uses_bounded_network_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    import boto3

    captured: dict[str, object] = {}

    class Client:
        def sign(self, **request: object) -> Mapping[str, object]:
            assert request["KeyId"] == "test-kms-key"
            return {"Signature": b"signature"}

    def create_client(service_name: str, **kwargs: object) -> Client:
        captured["service_name"] = service_name
        captured.update(kwargs)
        return Client()

    monkeypatch.setattr(boto3, "client", create_client)

    KmsTokenSigner("test-kms-key", "test-kid", "us-east-1").issue({"sub": "42"})

    config = captured["config"]
    assert captured["service_name"] == "kms"
    assert config.connect_timeout == 1
    assert config.read_timeout == 3
    assert config.retries["total_max_attempts"] == 1
