import re
from pathlib import Path

from scripts.check_aws_credentials_absent import main as check_aws_credentials_absent

WORKFLOW_PATH = Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml"


def terraform_job() -> str:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"(?ms)^  terraform-static-validation:\n(?P<job>.*?)(?=^  [A-Za-z0-9_-]+:|\Z)",
        workflow,
    )
    assert match is not None, "Terraform validation job key must remain stable"
    return match.group("job")


def test_terraform_job_is_restricted_to_offline_static_validation() -> None:
    job = terraform_job()

    assert re.search(r"(?m)^    permissions:\n      contents: read\s*$", job)
    assert "persist-credentials: false" in job
    assert "run: python ../../scripts/check_aws_credentials_absent.py" in job
    assert re.search(r"(?m)^\s+run: terraform init -backend=false\b", job)

    assert not re.search(r"(?i)\bterraform\s+(?:plan|apply|destroy)\b", job)
    assert not re.search(r"(?im)(?:^|[;&|]\s*)aws(?:\s|$)", job)
    assert not re.search(r"(?i)aws-actions/[^\s]+|configure-aws-credentials", job)
    assert not re.search(r"(?m)^\s+id-token:\s*write\s*$", job)


def test_credential_guard_rejects_aws_credential_environment_variables(tmp_path: Path) -> None:
    assert check_aws_credentials_absent({"AWS_ACCESS_KEY_ID": "placeholder"}, tmp_path) == 1


def test_credential_guard_rejects_aws_credentials_files(tmp_path: Path) -> None:
    credentials_file = tmp_path / ".aws" / "credentials"
    credentials_file.parent.mkdir()
    credentials_file.write_text("profile placeholder\n", encoding="utf-8")

    assert check_aws_credentials_absent({}, tmp_path) == 1


def test_credential_guard_allows_an_empty_environment_and_home(tmp_path: Path) -> None:
    assert check_aws_credentials_absent({}, tmp_path) == 0
