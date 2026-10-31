output "function_name" {
  description = "Name of the deployed Lambda function."
  value       = aws_lambda_function.function.function_name
}

output "function_arn" {
  description = "ARN of the deployed Lambda function."
  value       = aws_lambda_function.function.arn
}

output "execution_role_arn" {
  description = "ARN of the Lambda execution role."
  value       = aws_iam_role.function.arn
}

output "jwt_signing_key_arn" {
  description = "ARN of the effective RS256 signing key for coordinating GitHub and application configuration; keep the override empty when this module manages the key."
  value       = local.effective_jwt_kms_key_arn
}

output "log_group_name" {
  description = "CloudWatch Logs group created for the function."
  value       = aws_cloudwatch_log_group.function.name
}
