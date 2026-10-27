"""Entrypoint AWS Lambda, sem inicializar serviços externos."""

import logging

from lambda_auth.adapters.api_gateway import ApiGatewayAdapter
from lambda_auth.adapters.kms_token_signer import KmsTokenSigner
from lambda_auth.adapters.postgres_customer_repository import PostgresCustomerRepository
from lambda_auth.adapters.secrets_manager_database_url import SecretsManagerDatabaseUrl
from lambda_auth.application.authentication import AuthenticateCustomer
from lambda_auth.application.http_application import HttpApplication
from lambda_auth.settings import Settings

_settings = Settings.from_environment()
_token_signer = KmsTokenSigner(
    _settings.kms_key_id,
    _settings.jwt_kid,
    _settings.aws_region,
    additional_public_keys=tuple(
        (key.kid, key.kms_key_id) for key in _settings.additional_public_keys
    ),
)
_database_url_provider = (
    SecretsManagerDatabaseUrl(_settings.database_secret_arn, _settings.aws_region)
    if _settings.database_secret_arn
    else None
)
_customer_repository = PostgresCustomerRepository(
    _settings.database_url,
    database_url_provider=_database_url_provider,
)
_application = HttpApplication(
    AuthenticateCustomer(_customer_repository, _token_signer, _settings),
    _token_signer,
)
_adapter = ApiGatewayAdapter(_application)


def lambda_handler(event: object, context: object) -> dict[str, object]:
    logging.getLogger().setLevel(_settings.log_level)
    return _adapter.handle(event)
