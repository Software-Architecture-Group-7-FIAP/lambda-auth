locals {
  deployed_function_name             = "${var.function_name}-${var.environment}"
  cors_allowed_origin_by_environment = {
    hml = "https://app-hml.oficina-workshop.com.br"
    prd = "https://app.oficina-workshop.com.br"
  }
  jwt_public_key_arns                = distinct(concat(
    [var.jwt_kms_key_arn],
    [for key in var.jwt_additional_public_keys : key.kms_key_id],
  ))
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
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
    resources = [var.database_secret_arn]
  }

  statement {
    sid       = "SignTokens"
    actions   = ["kms:Sign"]
    resources = [var.jwt_kms_key_arn]
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
  name               = "${local.deployed_function_name}-execution"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
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
      DATABASE_SECRET_ARN             = var.database_secret_arn
      CORS_ALLOWED_ORIGIN             = local.cors_allowed_origin_by_environment[var.environment]
      JWT_AUDIENCE                    = var.jwt_audience
      JWT_ADDITIONAL_PUBLIC_KEYS_JSON = jsonencode(var.jwt_additional_public_keys)
      JWT_ISSUER                      = var.jwt_issuer
      JWT_KID                         = var.jwt_kid
      JWT_KMS_KEY_ID                  = var.jwt_kms_key_arn
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

resource "aws_ssm_parameter" "customer_token_function_arn" {
  name        = "/auto-shop/staging/auth/customer-token/function-arn/${var.environment}"
  description = "ARN da Lambda de token cliente no stage ${var.environment}."
  type        = "String"
  value       = aws_lambda_function.function.arn
}
