"""Configuração segura lida do ambiente de execução."""

import os
from dataclasses import dataclass, field

_ALLOWED_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True, slots=True)
class Settings:
    log_level: str
    database_url: str = field(default="", repr=False)
    database_secret_arn: str = field(default="", repr=False)
    jwt_issuer: str = ""
    jwt_audience: str = ""
    jwt_ttl_seconds: int = 900
    jwt_kid: str = ""
    kms_key_id: str = field(default="", repr=False)
    aws_region: str = ""

    @property
    def auth_configured(self) -> bool:
        return all(
            (
                self.database_url or self.database_secret_arn,
                self.jwt_issuer,
                self.jwt_audience,
                1 <= self.jwt_ttl_seconds <= 900,
                self.jwt_kid,
                self.kms_key_id,
                self.aws_region,
            )
        )

    @classmethod
    def from_environment(cls) -> "Settings":
        log_level = os.environ.get("LOG_LEVEL", "WARNING").strip().upper()
        if log_level not in _ALLOWED_LOG_LEVELS:
            allowed = ", ".join(sorted(_ALLOWED_LOG_LEVELS))
            raise ValueError(f"LOG_LEVEL deve ser um destes valores: {allowed}")

        try:
            jwt_ttl_seconds = int(os.environ.get("JWT_TTL_SECONDS", "900"))
        except ValueError:
            raise ValueError("JWT_TTL_SECONDS deve ser um inteiro") from None
        if not 1 <= jwt_ttl_seconds <= 900:
            raise ValueError("JWT_TTL_SECONDS deve estar entre 1 e 900")

        return cls(
            log_level=log_level,
            database_url=os.environ.get("DATABASE_URL", "").strip(),
            database_secret_arn=os.environ.get("DATABASE_SECRET_ARN", "").strip(),
            jwt_issuer=os.environ.get("JWT_ISSUER", "").strip(),
            jwt_audience=os.environ.get("JWT_AUDIENCE", "").strip(),
            jwt_ttl_seconds=jwt_ttl_seconds,
            jwt_kid=os.environ.get("JWT_KID", "").strip(),
            kms_key_id=os.environ.get("JWT_KMS_KEY_ID", "").strip(),
            aws_region=os.environ.get(
                "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "")
            ).strip(),
        )
