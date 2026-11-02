mock_provider "aws" {
  mock_resource "aws_kms_key" {
    override_during = plan

    defaults = {
      arn    = "arn:aws:kms:us-east-1:123456789012:key/managed-jwt-signing"
      key_id = "managed-jwt-signing"
    }
  }

  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"*\"],\"Resource\":\"*\"}]}"
    }
  }
}

variables {
  aws_region          = "us-east-1"
  expected_account_id = "123456789012"
  environment         = "hml"
  lambda_package_path = "README.md"
  database_secret_id  = "auto-shop/staging/hml/lambda-auth"
  jwt_kms_key_arn     = "arn:aws:kms:us-east-1:123456789012:key/00000000-0000-0000-0000-000000000000"
  jwt_kid             = "unit-test-key"
  jwt_issuer          = "https://api.example.test"
  jwt_audience        = "auto-shop-api"
  private_subnet_ids  = ["subnet-0123456789abcdef0"]
  security_group_ids  = ["sg-0123456789abcdef0"]
}

run "does_not_publish_by_default" {
  command = plan

  assert {
    condition     = length(aws_ssm_parameter.function_arn) == 0
    error_message = "the Lambda ARN SSM parameter must remain disabled by default."
  }
}

run "uses_stable_hml_secret_name_and_dynamic_arn_suffix" {
  command = plan

  assert {
    condition     = local.database_secret_resource_arn == "arn:aws:secretsmanager:us-east-1:123456789012:secret:auto-shop/staging/hml/lambda-auth-*"
    error_message = "the Lambda policy must cover only the stable HML secret name and its generated ARN suffix."
  }

  assert {
    condition     = aws_lambda_function.function.environment[0].variables["DATABASE_SECRET_ID"] == var.database_secret_id
    error_message = "the Lambda must resolve the stable HML secret name at runtime."
  }
}

run "creates_managed_hml_signing_key_by_default" {
  command = plan

  variables {
    jwt_kms_key_arn = ""
  }

  assert {
    condition     = length(aws_kms_key.jwt_signing) == 1
    error_message = "HML must create a Terraform-managed signing key when no external ARN is supplied."
  }

  assert {
    condition = (
      aws_kms_key.jwt_signing[0].customer_master_key_spec == "RSA_2048" &&
      aws_kms_key.jwt_signing[0].key_usage == "SIGN_VERIFY" &&
      aws_kms_key.jwt_signing[0].deletion_window_in_days == 7
    )
    error_message = "the managed signing key must use RSA_2048/SIGN_VERIFY and a seven-day deletion window."
  }

  assert {
    condition = (
      aws_kms_key.jwt_signing[0].tags["Project"] == "auto-shop-system" &&
      aws_kms_alias.jwt_signing[0].name == "alias/auto-shop/hml/lambda-auth/jwt-signing" &&
      aws_kms_alias.jwt_signing[0].target_key_id == aws_kms_key.jwt_signing[0].key_id
    )
    error_message = "the managed HML signing key must have project tags and its stage-specific alias."
  }

  assert {
    condition = (
      local.effective_jwt_kms_key_arn == aws_kms_key.jwt_signing[0].arn &&
      aws_lambda_function.function.environment[0].variables["JWT_KMS_KEY_ID"] == local.effective_jwt_kms_key_arn &&
      output.jwt_signing_key_arn == local.effective_jwt_kms_key_arn
    )
    error_message = "the managed HML key ARN must configure the Lambda and be exposed as a Terraform output."
  }
}

run "uses_managed_prd_signing_key_by_default" {
  command = plan

  variables {
    environment        = "prd"
    database_secret_id = "auto-shop/staging/prd/lambda-auth"
    jwt_kms_key_arn    = ""
  }

  assert {
    condition = (
      length(aws_kms_key.jwt_signing) == 1 &&
      aws_kms_key.jwt_signing[0].customer_master_key_spec == "RSA_2048" &&
      aws_kms_key.jwt_signing[0].key_usage == "SIGN_VERIFY" &&
      aws_kms_key.jwt_signing[0].deletion_window_in_days == 7
    )
    error_message = "PRD must remain compatible with a Terraform-managed RSA_2048/SIGN_VERIFY key and seven-day deletion window."
  }

  assert {
    condition = (
      aws_kms_key.jwt_signing[0].tags["Project"] == "auto-shop-system" &&
      aws_kms_alias.jwt_signing[0].name == "alias/auto-shop/prd/lambda-auth/jwt-signing" &&
      local.effective_jwt_kms_key_arn == aws_kms_key.jwt_signing[0].arn &&
      output.jwt_signing_key_arn == local.effective_jwt_kms_key_arn
    )
    error_message = "the managed PRD key must have project tags, its PRD alias, and an effective ARN output."
  }
}

run "preserves_an_external_signing_key" {
  command = plan

  assert {
    condition = (
      length(aws_kms_key.jwt_signing) == 0 &&
      length(aws_kms_alias.jwt_signing) == 0 &&
      local.effective_jwt_kms_key_arn == var.jwt_kms_key_arn &&
      output.jwt_signing_key_arn == var.jwt_kms_key_arn
    )
    error_message = "an explicit external signing key must remain supported without creating a managed key."
  }
}

run "dev_requires_an_external_signing_key" {
  command = plan

  variables {
    environment        = "dev"
    database_secret_id = "local/lambda-auth"
    jwt_kms_key_arn    = ""
    private_subnet_ids = []
    security_group_ids = []
  }

  expect_failures = [var.jwt_kms_key_arn]
}

run "scopes_hml_execution_role" {
  command = plan

  assert {
    condition     = aws_iam_role.function.path == "/auto-shop/"
    error_message = "the HML Lambda execution role must use the auto-shop IAM path."
  }

  assert {
    condition     = aws_iam_role.function.permissions_boundary == "arn:aws:iam::123456789012:policy/auto-shop/auto-shop-boundary"
    error_message = "the HML Lambda execution role must use the existing auto-shop permissions boundary."
  }

  assert {
    condition     = local.deployed_function_arn == "arn:aws:lambda:us-east-1:123456789012:function:lambda-auth-hml"
    error_message = "the HML Lambda trust policy must be scoped to the deployed HML function ARN."
  }

  assert {
    condition = (
      anytrue([
        for condition in data.aws_iam_policy_document.lambda_assume_role.statement[0].condition :
        condition.variable == "aws:SourceAccount" &&
        length(condition.values) == 1 &&
        condition.values[0] == var.expected_account_id
      ]) &&
      anytrue([
        for condition in data.aws_iam_policy_document.lambda_assume_role.statement[0].condition :
        condition.variable == "aws:SourceArn" &&
        length(condition.values) == 1 &&
        condition.values[0] == local.deployed_function_arn
      ])
    )
    error_message = "the HML Lambda trust policy must require the account and exact deployed function ARN."
  }
}

run "rejects_secret_name_for_another_environment" {
  command = plan

  variables {
    database_secret_id = "auto-shop/staging/prd/lambda-auth"
  }

  expect_failures = [var.database_secret_id]
}

run "rejects_hml_without_private_vpc_attachment" {
  command = plan

  variables {
    private_subnet_ids = []
    security_group_ids = []
  }

  expect_failures = [var.security_group_ids]
}

run "rejects_prd_without_private_vpc_attachment" {
  command = plan

  variables {
    environment        = "prd"
    database_secret_id = "auto-shop/staging/prd/lambda-auth"
    private_subnet_ids = []
    security_group_ids = []
  }

  expect_failures = [var.security_group_ids]
}

run "allows_dev_without_vpc_attachment" {
  command = plan

  variables {
    environment        = "dev"
    database_secret_id = "local/lambda-auth"
    private_subnet_ids = []
    security_group_ids = []
  }

  assert {
    condition     = length(aws_lambda_function.function.vpc_config) == 0
    error_message = "dev may run without a private VPC attachment."
  }
}

run "supports_dev_secret_arn_with_generated_suffix" {
  command = plan

  variables {
    environment        = "dev"
    database_secret_id = "arn:aws:secretsmanager:us-east-1:123456789012:secret:local/lambda-auth-abc123"
    private_subnet_ids = []
    security_group_ids = []
  }

  assert {
    condition     = local.database_secret_resource_arn == "arn:aws:secretsmanager:us-east-1:123456789012:secret:local/lambda-auth-*"
    error_message = "a dev secret ARN must retain its scope while allowing the generated Secrets Manager suffix."
  }
}

run "publishes_hml_path_for_hml" {
  command = plan

  variables {
    function_arn_ssm_parameter_name = "/auto-shop/staging/auth/customer-token/function-arn/hml"
  }

  assert {
    condition     = aws_ssm_parameter.function_arn[0].name == var.function_arn_ssm_parameter_name
    error_message = "hml must publish only to the hml application contract path."
  }
}

run "rejects_prd_path_for_hml" {
  command = plan

  variables {
    function_arn_ssm_parameter_name = "/auto-shop/staging/auth/customer-token/function-arn/prd"
  }

  expect_failures = [aws_ssm_parameter.function_arn]
}

run "rejects_hml_path_for_dev" {
  command = plan

  variables {
    environment                     = "dev"
    function_arn_ssm_parameter_name = "/auto-shop/staging/auth/customer-token/function-arn/hml"
  }

  expect_failures = [aws_ssm_parameter.function_arn]
}

run "rejects_prd_path_for_dev" {
  command = plan

  variables {
    environment                     = "dev"
    function_arn_ssm_parameter_name = "/auto-shop/staging/auth/customer-token/function-arn/prd"
  }

  expect_failures = [aws_ssm_parameter.function_arn]
}

run "publishes_prd_path_for_prd" {
  command = plan

  variables {
    environment                     = "prd"
    database_secret_id              = "auto-shop/staging/prd/lambda-auth"
    function_arn_ssm_parameter_name = "/auto-shop/staging/auth/customer-token/function-arn/prd"
  }

  assert {
    condition     = aws_ssm_parameter.function_arn[0].name == var.function_arn_ssm_parameter_name
    error_message = "prd must publish only to the prd application contract path."
  }

  assert {
    condition     = local.deployed_function_arn == "arn:aws:lambda:us-east-1:123456789012:function:lambda-auth-prd"
    error_message = "the PRD Lambda trust policy must be scoped to the deployed PRD function ARN."
  }

  assert {
    condition = (
      anytrue([
        for condition in data.aws_iam_policy_document.lambda_assume_role.statement[0].condition :
        condition.variable == "aws:SourceAccount" &&
        length(condition.values) == 1 &&
        condition.values[0] == var.expected_account_id
      ]) &&
      anytrue([
        for condition in data.aws_iam_policy_document.lambda_assume_role.statement[0].condition :
        condition.variable == "aws:SourceArn" &&
        length(condition.values) == 1 &&
        condition.values[0] == local.deployed_function_arn
      ])
    )
    error_message = "the PRD Lambda trust policy must require the account and exact deployed function ARN."
  }
}

run "rejects_hml_path_for_prd" {
  command = plan

  variables {
    environment                     = "prd"
    database_secret_id              = "auto-shop/staging/prd/lambda-auth"
    function_arn_ssm_parameter_name = "/auto-shop/staging/auth/customer-token/function-arn/hml"
  }

  expect_failures = [aws_ssm_parameter.function_arn]
}
