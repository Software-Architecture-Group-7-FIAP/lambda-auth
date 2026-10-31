locals {
  deployed_function_name = "${var.function_name}-${var.environment}"
  deployed_function_arn  = "arn:aws:lambda:${var.aws_region}:${var.expected_account_id}:function:${local.deployed_function_name}"
  effective_jwt_kms_key_arn = var.jwt_kms_key_arn != "" ? (
    var.jwt_kms_key_arn
  ) : aws_kms_key.jwt_signing[0].arn
  cors_allowed_origin_by_environment = {
    hml = "https://app-hml.oficina-workshop.com.br"
    prd = "https://app.oficina-workshop.com.br"
    dev = ""
  }
  jwt_public_key_arns = distinct(concat(
    [local.effective_jwt_kms_key_arn],
    [for key in var.jwt_additional_public_keys : key.kms_key_id],
  ))
  database_secret_resource_arn = startswith(var.database_secret_id, "arn:") ? (
    replace(var.database_secret_id, "/-[A-Za-z0-9]{6}$/", "-*")
  ) : "arn:aws:secretsmanager:${var.aws_region}:${var.expected_account_id}:secret:${var.database_secret_id}-*"
}

resource "aws_kms_key" "jwt_signing" {
  count = var.jwt_kms_key_arn == "" ? 1 : 0

  description              = "RS256 token signing key for ${var.environment} lambda-auth"
  customer_master_key_spec = "RSA_2048"
  key_usage                = "SIGN_VERIFY"
  deletion_window_in_days  = 7

  tags = {
    Name      = "auto-shop-${var.environment}-lambda-auth-jwt-signing"
    Project   = "auto-shop-system"
    Component = "lambda-auth"
    Purpose   = "rs256-signing"
  }
}

resource "aws_kms_alias" "jwt_signing" {
  count = var.jwt_kms_key_arn == "" ? 1 : 0

  name          = "alias/auto-shop/${var.environment}/lambda-auth/jwt-signing"
  target_key_id = aws_kms_key.jwt_signing[0].key_id
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [var.expected_account_id]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [local.deployed_function_arn]
    }
  }
}

data "aws_iam_policy_document" "lambda_runtime" {
  statement {
    sid       = "WriteFunctionLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.function.arn}:*"]
  }

  statement {
    sid       = "ReadDatabaseSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [local.database_secret_resource_arn]
  }

  statement {
    sid       = "SignTokens"
    actions   = ["kms:Sign"]
    resources = [local.effective_jwt_kms_key_arn]
  }

  statement {
    sid       = "PublishPublicKeys"
    actions   = ["kms:GetPublicKey"]
    resources = local.jwt_public_key_arns
  }

  dynamic "statement" {
    for_each = var.database_secret_kms_key_arn == "" ? [] : [var.database_secret_kms_key_arn]

    content {
      sid       = "DecryptDatabaseSecret"
      actions   = ["kms:Decrypt"]
      resources = [statement.value]
    }
  }

  dynamic "statement" {
    for_each = length(var.private_subnet_ids) == 0 ? [] : [true]

    content {
      sid = "ManageLambdaNetworkInterfaces"
      actions = [
        "ec2:AssignPrivateIpAddresses",
        "ec2:CreateNetworkInterface",
        "ec2:DeleteNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "ec2:UnassignPrivateIpAddresses",
      ]
      resources = ["*"]
    }
  }
}

resource "aws_cloudwatch_log_group" "function" {
  name              = "/aws/lambda/${local.deployed_function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "function" {
  name                 = "${local.deployed_function_name}-execution"
  path                 = "/auto-shop/"
  permissions_boundary = "arn:aws:iam::${var.expected_account_id}:policy/auto-shop/auto-shop-boundary"
  assume_role_policy   = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "function" {
  name   = "${local.deployed_function_name}-runtime"
  role   = aws_iam_role.function.id
  policy = data.aws_iam_policy_document.lambda_runtime.json
}

resource "aws_lambda_function" "function" {
  function_name = local.deployed_function_name
  description   = "Autenticação de clientes ativos por CPF para a oficina"
  role          = aws_iam_role.function.arn
  runtime       = "python3.12"
  handler       = "lambda_auth.handler.lambda_handler"
  architectures = ["x86_64"]

  filename         = var.lambda_package_path
  source_code_hash = filebase64sha256(var.lambda_package_path)
  memory_size      = var.lambda_memory_size
  timeout          = var.lambda_timeout_seconds

  environment {
    variables = {
      DATABASE_SECRET_ID              = var.database_secret_id
      CORS_ALLOWED_ORIGIN             = local.cors_allowed_origin_by_environment[var.environment]
      JWT_AUDIENCE                    = var.jwt_audience
      JWT_ADDITIONAL_PUBLIC_KEYS_JSON = jsonencode(var.jwt_additional_public_keys)
      JWT_ISSUER                      = var.jwt_issuer
      JWT_KID                         = var.jwt_kid
      JWT_KMS_KEY_ID                  = local.effective_jwt_kms_key_arn
      JWT_TTL_SECONDS                 = tostring(var.jwt_ttl_seconds)
      LOG_LEVEL                       = "WARNING"
    }
  }

  dynamic "vpc_config" {
    for_each = length(var.private_subnet_ids) == 0 ? [] : [true]

    content {
      subnet_ids         = var.private_subnet_ids
      security_group_ids = var.security_group_ids
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.function,
    aws_iam_role_policy.function,
  ]

  lifecycle {
    precondition {
      condition     = !contains([for key in var.jwt_additional_public_keys : trimspace(key.kid)], trimspace(var.jwt_kid))
      error_message = "jwt_kid must differ from every additional public key kid."
    }
  }
}

resource "aws_ssm_parameter" "function_arn" {
  count = var.function_arn_ssm_parameter_name == "" ? 0 : 1

  name        = var.function_arn_ssm_parameter_name
  description = "ARN da Lambda de autenticação de clientes."
  type        = "String"
  value       = aws_lambda_function.function.arn

  lifecycle {
    precondition {
      condition = (
        (var.environment == "hml" && var.function_arn_ssm_parameter_name == "/auto-shop/staging/auth/customer-token/function-arn/hml") ||
        (var.environment == "prd" && var.function_arn_ssm_parameter_name == "/auto-shop/staging/auth/customer-token/function-arn/prd")
      )
      error_message = "When publishing the Lambda ARN, hml must use the hml path and prd must use the prd path; dev cannot use either application path."
    }
  }
}
