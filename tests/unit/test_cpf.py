import pytest

from lambda_auth.application.cpf import normalize_valid_cpf


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("52998224725", "52998224725"),
        ("529.982.247-25", "52998224725"),
        ("529-982-247 25", "52998224725"),
    ],
)
def test_valid_cpf_is_normalized(value: str, expected: str) -> None:
    assert normalize_valid_cpf(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "11111111111",
        "52998224724",
        "5299822472",
        "cpf 52998224725",
        "52998224725" * 4,
        52998224725,
    ],
)
def test_invalid_cpf_is_rejected(value: object) -> None:
    assert normalize_valid_cpf(value) is None
