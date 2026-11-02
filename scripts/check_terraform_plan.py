"""Reject Terraform plans outside the guarded lambda-auth resource contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ALLOWED_RESOURCE_TYPES = {
    "aws_cloudwatch_log_group",
    "aws_iam_role",
    "aws_iam_role_policy",
    "aws_kms_alias",
    "aws_kms_key",
    "aws_lambda_function",
    "aws_ssm_parameter",
}
ALLOWED_ACTIONS = {("no-op",), ("create",), ("update",)}
ALLOWED_DATA_SOURCE = (
    "data.aws_iam_policy_document.lambda_runtime",
    "aws_iam_policy_document",
    ("read",),
)


class PlanRejected(ValueError):
    """Raised when a Terraform plan is outside the Lambda-only safety contract."""


def validate_plan(plan: dict[str, Any]) -> None:
    """Validate a Terraform JSON plan before the workflow applies it."""
    if plan.get("errored") is True:
        raise PlanRejected("Terraform reported an errored plan")
    if plan.get("complete") is False:
        raise PlanRejected("incomplete plans require a fresh manual review")

    resource_changes = plan.get("resource_changes")
    if not isinstance(resource_changes, list):
        raise PlanRejected("resource_changes must be a list")

    resource_drift = plan.get("resource_drift", [])
    if not isinstance(resource_drift, list):
        raise PlanRejected("resource_drift must be a list")
    if resource_drift:
        raise PlanRejected("out-of-band resource drift requires manual review")

    for resource_change in resource_changes:
        if not isinstance(resource_change, dict):
            raise PlanRejected("resource change entry must be an object")

        resource_type = resource_change.get("type")
        address = resource_change.get("address", "unknown address")
        mode = resource_change.get("mode", "managed")

        change = resource_change.get("change")
        if not isinstance(change, dict):
            raise PlanRejected(f"change data is missing for {address}")

        actions = change.get("actions")
        if not isinstance(actions, list) or not all(isinstance(action, str) for action in actions):
            raise PlanRejected(f"destructive or unsupported action for {address}: {actions}")

        action_tuple = tuple(actions)
        if mode == "data":
            if (address, resource_type, action_tuple) != ALLOWED_DATA_SOURCE:
                raise PlanRejected(f"data source is outside the Lambda module: {address}")
            continue

        if mode != "managed":
            raise PlanRejected(f"unsupported resource mode for {address}: {mode}")
        if not isinstance(resource_type, str) or resource_type not in ALLOWED_RESOURCE_TYPES:
            raise PlanRejected(f"resource type is outside the Lambda module: {resource_type}")
        if action_tuple not in ALLOWED_ACTIONS:
            raise PlanRejected(f"destructive or unsupported action for {address}: {actions}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_json", type=Path, help="Path to terraform show -json output")
    args = parser.parse_args()

    try:
        plan = json.loads(args.plan_json.read_text(encoding="utf-8"))
        if not isinstance(plan, dict):
            raise PlanRejected("plan document must be an object")
        validate_plan(plan)
    except (OSError, json.JSONDecodeError, PlanRejected) as error:
        print(f"Terraform plan rejected: {error}", file=sys.stderr)
        return 1

    print("Terraform plan passed the Lambda-only, non-destructive guard.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
