variable "aws_region" {
  description = "AWS region selected by the platform team for this environment."
  type        = string
  nullable    = false

  validation {
    condition     = length(trimspace(var.aws_region)) > 0
    error_message = "aws_region must be selected before provisioning."
  }
}

variable "expected_account_id" {
  description = "AWS account ID allowed to receive these resources."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id must contain exactly 12 digits."
  }
}

variable "environment" {
  description = "Deployment environment name used in resource names and tags."
  type        = string
  nullable    = false

  validation {
    condition     = contains(["dev", "homolog", "prod"], var.environment)
    error_message = "environment must be dev, homolog, or prod."
  }
}

variable "function_name" {
  description = "Base name for the Lambda function. The environment is appended."
  type        = string
  default     = "customer-cpf-auth"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{1,46}$", var.function_name))
    error_message = "function_name must use 1 to 46 letters, digits, hyphens, or underscores."
  }
}

variable "lambda_package_path" {
  description = "Path to the Python 3.12 Lambda zip, relative to this Terraform directory."
  type        = string
  nullable    = false

  validation {
    condition     = length(trimspace(var.lambda_package_path)) > 0
    error_message = "lambda_package_path must point to a built deployment zip."
  }
}

variable "database_secret_arn" {
  description = "ARN of the existing Secrets Manager secret containing DATABASE_URL."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^arn:[^:]+:secretsmanager:[^:]+:[0-9]{12}:secret:.+$", var.database_secret_arn))
    error_message = "database_secret_arn must be a Secrets Manager secret ARN."
  }
}

variable "database_secret_kms_key_arn" {
  description = "Optional ARN of the customer-managed KMS key encrypting the database secret."
  type        = string
  default     = ""
  nullable    = false

  validation {
    condition     = var.database_secret_kms_key_arn == "" || can(regex("^arn:[^:]+:kms:[^:]+:[0-9]{12}:key/.+$", var.database_secret_kms_key_arn))
    error_message = "database_secret_kms_key_arn must be empty or a KMS key ARN."
  }
}

variable "jwt_kms_key_arn" {
  description = "ARN of the existing asymmetric RSA KMS key used for RS256 signing."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^arn:[^:]+:kms:[^:]+:[0-9]{12}:key/.+$", var.jwt_kms_key_arn))
    error_message = "jwt_kms_key_arn must be a KMS key ARN."
  }
}

variable "jwt_kid" {
  description = "Public key identifier published in the JWT header and JWKS."
  type        = string
  nullable    = false

  validation {
    condition     = length(trimspace(var.jwt_kid)) > 0
    error_message = "jwt_kid must be selected and match the public JWKS contract."
  }
}

variable "jwt_additional_public_keys" {
  description = "Additional KMS public keys published during JWT key rotation; never used to sign."
  type = list(object({
    kid        = string
    kms_key_id = string
  }))
  default  = []
  nullable = false

  validation {
    condition = (
      length(distinct([for key in var.jwt_additional_public_keys : trimspace(key.kid)])) == length(var.jwt_additional_public_keys) &&
      alltrue([for key in var.jwt_additional_public_keys : length(trimspace(key.kid)) > 0]) &&
      alltrue([for key in var.jwt_additional_public_keys : can(regex("^arn:[^:]+:kms:[^:]+:[0-9]{12}:key/.+$", key.kms_key_id))])
    )
    error_message = "jwt_additional_public_keys must contain unique non-empty kids and KMS key ARNs."
  }
}

variable "jwt_issuer" {
  description = "Issuer claim agreed with the platform and token consumers."
  type        = string
  nullable    = false

  validation {
    condition     = length(trimspace(var.jwt_issuer)) > 0
    error_message = "jwt_issuer must be agreed before provisioning."
  }
}

variable "jwt_audience" {
  description = "Audience claim agreed with the platform and token consumers."
  type        = string
  nullable    = false

  validation {
    condition     = length(trimspace(var.jwt_audience)) > 0
    error_message = "jwt_audience must be selected before provisioning."
  }
}

variable "jwt_ttl_seconds" {
  description = "Lifetime of issued JWTs, limited to 900 seconds by the application."
  type        = number
  default     = 900
  nullable    = false

  validation {
    condition     = var.jwt_ttl_seconds >= 1 && var.jwt_ttl_seconds <= 900 && floor(var.jwt_ttl_seconds) == var.jwt_ttl_seconds
    error_message = "jwt_ttl_seconds must be an integer from 1 through 900."
  }
}

variable "private_subnet_ids" {
  description = "Existing private subnet IDs for database access. Empty means no VPC attachment."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "security_group_ids" {
  description = "Existing security groups for Lambda VPC access. Required with private_subnet_ids."
  type        = list(string)
  default     = []
  nullable    = false

  validation {
    condition = (
      (length(var.private_subnet_ids) == 0 && length(var.security_group_ids) == 0) ||
      (length(var.private_subnet_ids) > 0 && length(var.security_group_ids) > 0)
    )
    error_message = "Provide both private_subnet_ids and security_group_ids, or leave both empty."
  }
}

variable "lambda_memory_size" {
  description = "Lambda memory in MiB."
  type        = number
  default     = 256
  nullable    = false

  validation {
    condition     = var.lambda_memory_size >= 128 && var.lambda_memory_size <= 10240 && var.lambda_memory_size % 64 == 0
    error_message = "lambda_memory_size must be from 128 through 10240 MiB in 64 MiB increments."
  }
}

variable "lambda_timeout_seconds" {
  description = "Maximum Lambda execution duration in seconds."
  type        = number
  default     = 15
  nullable    = false

  validation {
    condition     = var.lambda_timeout_seconds >= 1 && var.lambda_timeout_seconds <= 900
    error_message = "lambda_timeout_seconds must be from 1 through 900."
  }
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for this function."
  type        = number
  default     = 14
  nullable    = false

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.log_retention_days)
    error_message = "log_retention_days must be a CloudWatch Logs retention value."
  }
}
