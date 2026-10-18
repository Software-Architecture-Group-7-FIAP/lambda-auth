"""Entrypoint AWS Lambda, sem inicializar serviços externos."""

import logging

from lambda_auth.adapters.api_gateway import ApiGatewayAdapter
from lambda_auth.application.health import HealthApplication
from lambda_auth.settings import Settings

_adapter = ApiGatewayAdapter(HealthApplication())


def lambda_handler(event: object, context: object) -> dict[str, object]:
    settings = Settings.from_environment()
    logging.getLogger().setLevel(settings.log_level)
    return _adapter.handle(event)
