import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[2]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "deploy-lambda.yml"


def test_lambda_promotion_requires_main_dispatch_and_explicit_readiness() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert re.search(r"(?m)^  workflow_dispatch:", workflow)
    assert re.search(r"(?m)^      stage:\s*$", workflow)
    assert "options: [hml, prd]" in workflow
    assert "confirmation:" in workflow
    assert 'test "$GITHUB_REF" = "refs/heads/main"' in workflow
    assert 'test "$CONFIRMATION" = "PROMOTE"' in workflow
    assert 'test "$DEPLOYMENT_READY" = "true"' in workflow
    assert "environment: ${{ inputs.stage }}" in workflow
    assert "workflow_dispatch" in workflow
    assert "pull_request:" not in workflow


def test_aws_oidc_is_only_available_to_the_gated_deployment_job() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    jobs = re.search(r"(?ms)^jobs:\n(?P<jobs>.*)\Z", workflow)
    assert jobs is not None
    jobs_text = jobs.group("jobs")

    assert re.search(r"(?ms)^  preflight:\n(?P<job>.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", jobs_text)
    preflight = re.search(
        r"(?ms)^  preflight:\n(?P<job>.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", jobs_text
    ).group("job")
    deploy = re.search(r"(?ms)^  deploy:\n(?P<job>.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", jobs_text)
    assert deploy is not None

    assert "id-token: write" not in preflight
    assert "needs: preflight" in deploy.group("job")
    assert "id-token: write" in deploy.group("job")
    assert "persist-credentials: false" in deploy.group("job")
    assert "aws-actions/configure-aws-credentials@" in deploy.group("job")
    assert "secrets.AWS_DEPLOY_ROLE_ARN" not in workflow


def test_deployment_plan_is_guarded_and_never_uploaded_as_an_artifact() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    deploy = re.search(r"(?ms)^  deploy:\n(?P<job>.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", workflow)
    assert deploy is not None
    job = deploy.group("job")

    assert "terraform plan -input=false -no-color -out=tfplan" in job
    assert "terraform show -json tfplan" in job
    assert "scripts/check_terraform_plan.py" in job
    assert "terraform apply -input=false -no-color -auto-approve tfplan" in job
    assert "actions/upload-artifact" not in workflow
    assert "LAMBDA_TF_STATE_BUCKET" in job
    assert "LAMBDA_TF_STATE_KEY" in job


def test_signing_key_arn_is_an_optional_external_override() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    preflight = re.search(
        r"(?ms)^  preflight:\n(?P<job>.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", workflow
    )
    deploy = re.search(r"(?ms)^  deploy:\n(?P<job>.*?)(?=^  [A-Za-z0-9_-]+:|\Z)", workflow)
    assert preflight is not None
    assert deploy is not None

    assert 'test -n "$JWT_KMS_KEY_ARN"' not in preflight.group("job")
    assert "TF_VAR_jwt_kms_key_arn: ${{ vars.LAMBDA_JWT_KMS_KEY_ARN }}" in deploy.group("job")


def test_ci_remains_offline_and_backend_free() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert re.search(r"(?m)^  terraform-static-validation:", workflow)
    assert "terraform init -backend=false" in workflow
    assert "id-token: write" not in workflow
