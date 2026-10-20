"""Fail preparation-only CI when AWS credential material is available."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

AWS_CREDENTIAL_ENV_VARS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_ACCESS_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SECRET_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_SECURITY_TOKEN",
    "AWS_PROFILE",
    "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_CONFIG_FILE",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "AWS_ROLE_ARN",
    "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "AWS_CONTAINER_AUTHORIZATION_TOKEN",
)

AWS_CREDENTIAL_PATHS = (
    ".aws/credentials",
    ".aws/config",
    ".aws/sso/cache",
    ".aws/cli/cache",
)


def find_aws_credential_material(environment: Mapping[str, str], home: Path) -> tuple[str, ...]:
    """Return identifiers for configured AWS credentials without reading their contents."""
    matches = [name for name in AWS_CREDENTIAL_ENV_VARS if name in environment]
    matches.extend(
        f"~/{relative_path}"
        for relative_path in AWS_CREDENTIAL_PATHS
        if (home / relative_path).exists()
    )
    return tuple(matches)


def main(environment: Mapping[str, str] | None = None, home: Path | None = None) -> int:
    credential_environment = os.environ if environment is None else environment
    home_directory = Path.home() if home is None else home
    matches = find_aws_credential_material(credential_environment, home_directory)
    if matches:
        print(
            "::error::AWS credential material/configuration is present; "
            "preparation-only CI cannot continue.",
            file=sys.stderr,
        )
        return 1

    print("Preparation-only credential guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
