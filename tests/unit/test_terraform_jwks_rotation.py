from pathlib import Path

TERRAFORM_DIR = Path(__file__).parents[2] / "infra" / "terraform"


def test_terraform_separates_signing_from_public_key_permissions() -> None:
    main = (TERRAFORM_DIR / "main.tf").read_text(encoding="utf-8")

    assert 'sid       = "SignTokens"' in main
    assert 'actions   = ["kms:Sign"]' in main
    assert "resources = [local.effective_jwt_kms_key_arn]" in main
    assert 'sid       = "PublishPublicKeys"' in main
    assert 'actions   = ["kms:GetPublicKey"]' in main
    assert "local.jwt_public_key_arns" in main


def test_terraform_injects_additional_keys_as_json() -> None:
    main = (TERRAFORM_DIR / "main.tf").read_text(encoding="utf-8")
    variables = (TERRAFORM_DIR / "variables.tf").read_text(encoding="utf-8")

    assert 'variable "jwt_additional_public_keys"' in variables
    assert "JWT_ADDITIONAL_PUBLIC_KEYS_JSON = jsonencode(var.jwt_additional_public_keys)" in main
