mock_provider "aws" {
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
