import pytest
from scripts.check_terraform_plan import PlanRejected, validate_plan


def plan_with(*resource_changes: dict[str, object]) -> dict[str, object]:
    return {"resource_changes": list(resource_changes)}


def resource(resource_type: str, *actions: str) -> dict[str, object]:
    return {
        "address": f"{resource_type}.example",
        "type": resource_type,
        "change": {"actions": list(actions)},
    }


def data_source(address: str, resource_type: str, *actions: str) -> dict[str, object]:
    return {
        "address": address,
        "mode": "data",
        "type": resource_type,
        "change": {"actions": list(actions)},
    }


def test_accepts_only_lambda_module_resources_with_non_destructive_actions() -> None:
    validate_plan(
        plan_with(
            resource("aws_cloudwatch_log_group", "create"),
            resource("aws_iam_role", "update"),
            resource("aws_iam_role_policy", "no-op"),
            resource("aws_kms_key", "create"),
            resource("aws_kms_alias", "create"),
            resource("aws_lambda_function", "update"),
            resource("aws_ssm_parameter", "create"),
        )
    )


@pytest.mark.parametrize(
    "actions",
    [
        ("delete",),
        ("delete", "create"),
        ("create", "delete"),
        ("read",),
    ],
)
def test_rejects_deletes_replacements_and_unexpected_actions(actions: tuple[str, ...]) -> None:
    with pytest.raises(PlanRejected):
        validate_plan(plan_with(resource("aws_lambda_function", *actions)))


def test_rejects_resource_types_outside_the_lambda_module() -> None:
    with pytest.raises(PlanRejected, match="aws_db_instance"):
        validate_plan(plan_with(resource("aws_db_instance", "create")))


def test_accepts_the_local_lambda_runtime_policy_document_read() -> None:
    validate_plan(
        plan_with(
            data_source(
                "data.aws_iam_policy_document.lambda_runtime",
                "aws_iam_policy_document",
                "read",
            )
        )
    )


@pytest.mark.parametrize(
    "resource_change",
    [
        data_source(
            "data.aws_iam_policy_document.other",
            "aws_iam_policy_document",
            "read",
        ),
        data_source(
            "data.aws_iam_policy.example",
            "aws_iam_policy",
            "read",
        ),
        data_source(
            "data.aws_iam_policy_document.lambda_runtime",
            "aws_iam_policy_document",
            "update",
        ),
    ],
)
def test_rejects_unapproved_or_mutating_data_sources(
    resource_change: dict[str, object],
) -> None:
    with pytest.raises(PlanRejected):
        validate_plan(plan_with(resource_change))


def test_rejects_read_actions_for_managed_resources() -> None:
    managed_read = resource("aws_iam_policy_document")
    managed_read["change"] = {"actions": ["read"]}

    with pytest.raises(PlanRejected):
        validate_plan(plan_with(managed_read))


def test_rejects_unrecognized_resource_modes() -> None:
    unrecognized_mode = resource("aws_lambda_function", "update")
    unrecognized_mode["mode"] = "ephemeral"

    with pytest.raises(PlanRejected, match="unsupported resource mode"):
        validate_plan(plan_with(unrecognized_mode))


def test_rejects_malformed_plan_data() -> None:
    with pytest.raises(PlanRejected):
        validate_plan({"resource_changes": None})

    with pytest.raises(PlanRejected):
        validate_plan({"resource_changes": [], "complete": False})

    with pytest.raises(PlanRejected):
        validate_plan({"resource_changes": [], "errored": True})

    with pytest.raises(PlanRejected):
        validate_plan(
            {"resource_changes": [], "resource_drift": [resource("aws_lambda_function", "update")]}
        )


def test_accepts_a_no_change_plan() -> None:
    validate_plan({"resource_changes": []})
