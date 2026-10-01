"""Configurações da aplicação (pydantic-settings).

Única fonte de leitura de ambiente. Nada de `os.getenv` espalhado: campo novo
entra aqui, tipado, com alias igual ao nome da variável.

Os validadores no fim são a lei do projeto: combinações inseguras (modo stub em
produção, TLS do banco sem verificação em produção) impedem o container de subir.
"""

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENVS = ("production", "staging", "development", "test")
_AUTH_MODES = ("oidc", "stub")
_MIN_SECRET_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Banco de dados (RDS MySQL) — schema EXCLUSIVO `area_associado`.     #
    # ------------------------------------------------------------------ #
    db_host: str = Field(..., alias="DB_HOST")
    db_port: int = Field(3306, alias="DB_PORT")
    db_user: str = Field(..., alias="DB_USER")
    db_pass: str = Field(..., alias="DB_PASS")
    db_name: str = Field(..., alias="DB_NAME")
    db_ssl_ca: str = Field("/etc/ssl/rds/global-bundle.pem", alias="DB_SSL_CA")
    db_ssl_verify: bool = Field(True, alias="DB_SSL_VERIFY")
    db_pool_size: int = Field(5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(10, alias="DB_MAX_OVERFLOW")
    db_pool_recycle: int = Field(1800, alias="DB_POOL_RECYCLE")

    # ------------------------------------------------------------------ #
    # Aplicação                                                          #
    # ------------------------------------------------------------------ #
    app_env: str = Field("production", alias="APP_ENV")
    secret_key: str = Field(..., alias="SECRET_KEY")
    session_max_age: int = Field(28800, alias="SESSION_MAX_AGE")          # 8 h deslizante
    session_absolute_max: int = Field(43200, alias="SESSION_ABSOLUTE_MAX")  # 12 h desde o login
    public_base_url: str = Field("https://associado.apm.org.br", alias="PUBLIC_BASE_URL")

    # ------------------------------------------------------------------ #
    # Autenticação: `oidc` (login_associado) ou `stub` (construção).      #
    # ------------------------------------------------------------------ #
    auth_mode: str = Field("oidc", alias="AUTH_MODE")
    dev_stub_token: str | None = Field(None, alias="DEV_STUB_TOKEN")

    # ------------------------------------------------------------------ #
    # OIDC — esta app como Relying Party do login.apm.org.br.             #
    # ------------------------------------------------------------------ #
    oidc_issuer: str = Field("https://login.apm.org.br", alias="OIDC_ISSUER")
    oidc_backchannel_base_url: str = Field(
        "http://login_associado:8000", alias="OIDC_BACKCHANNEL_BASE_URL"
    )
    oidc_client_id: str = Field("area-associado", alias="OIDC_CLIENT_ID")
    oidc_client_secret: str | None = Field(None, alias="OIDC_CLIENT_SECRET")
    oidc_scopes: str = Field("openid profile email cpf", alias="OIDC_SCOPES")
    oidc_pending_ttl: int = Field(600, alias="OIDC_PENDING_TTL")
    oidc_jwks_ttl: int = Field(300, alias="OIDC_JWKS_TTL")
    oidc_http_timeout: float = Field(10.0, alias="OIDC_HTTP_TIMEOUT")
    oidc_leeway: int = Field(60, alias="OIDC_LEEWAY")

    # ------------------------------------------------------------------ #
    # Auditoria                                                          #
    # ------------------------------------------------------------------ #
    log_hash_key: str | None = Field(None, alias="LOG_HASH_KEY")
    evento_log_table: str = Field("evento_log", alias="EVENTO_LOG_TABLE")

    # ------------------------------------------------------------------ #
    # Propriedades derivadas                                             #
    # ------------------------------------------------------------------ #
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def session_https_only(self) -> bool:
        """Cookie Secure em tudo que não seja desenvolvimento local."""
        return self.app_env != "development"

    @property
    def expose_openapi(self) -> bool:
        return self.app_env == "development"

    @property
    def effective_issuer(self) -> str:
        """Issuer sem barra final — comparado byte a byte com o claim `iss`."""
        return self.oidc_issuer.rstrip("/")

    @property
    def effective_backchannel(self) -> str:
        return self.oidc_backchannel_base_url.rstrip("/")

    @property
    def backchannel_host_header(self) -> str | None:
        """Host do issuer quando o back-channel usa outro endereço (rede Docker)."""
        issuer_host = urlsplit(self.effective_issuer).netloc
        back_host = urlsplit(self.effective_backchannel).netloc
        return issuer_host if issuer_host != back_host else None

    @property
    def effective_public_base_url(self) -> str:
        return self.public_base_url.rstrip("/")

    @property
    def redirect_uri(self) -> str:
        return f"{self.effective_public_base_url}/auth/callback"

    @property
    def post_logout_redirect_uri(self) -> str:
        return f"{self.effective_public_base_url}/"

    @property
    def scope_list(self) -> list[str]:
        return [s for s in self.oidc_scopes.split() if s]

    @property
    def effective_log_hash_key(self) -> str:
        return self.log_hash_key or self.secret_key

    @property
    def sqlalchemy_dsn(self) -> str:
        # Senha vai por connect_args (database.py), nunca na URL.
        return (
            f"mysql+pymysql://{self.db_user}@{self.db_host}:{self.db_port}/{self.db_name}"
            "?charset=utf8mb4"
        )

    # ------------------------------------------------------------------ #
    # Coerência — combinações inseguras derrubam o boot de propósito.     #
    # ------------------------------------------------------------------ #
    @model_validator(mode="after")
    def _coerencia(self) -> "Settings":
        self.app_env = self.app_env.lower().strip()
        self.auth_mode = self.auth_mode.lower().strip()
        if self.app_env not in _ENVS:
            raise ValueError(f"APP_ENV inválido: {self.app_env!r} (use {', '.join(_ENVS)})")
        if self.auth_mode not in _AUTH_MODES:
            raise ValueError(f"AUTH_MODE inválido: {self.auth_mode!r} (use oidc|stub)")
        if len(self.secret_key) < _MIN_SECRET_LEN:
            raise ValueError(f"SECRET_KEY precisa de ao menos {_MIN_SECRET_LEN} caracteres")
        if self.auth_mode == "stub":
            if self.is_production:
                raise ValueError("AUTH_MODE=stub é proibido com APP_ENV=production")
            if not self.dev_stub_token or len(self.dev_stub_token) < _MIN_SECRET_LEN:
                raise ValueError("AUTH_MODE=stub exige DEV_STUB_TOKEN com ao menos 32 caracteres")
        if self.auth_mode == "oidc" and not self.oidc_client_secret:
            raise ValueError("AUTH_MODE=oidc exige OIDC_CLIENT_SECRET")
        if self.is_production and not self.db_ssl_verify:
            raise ValueError("DB_SSL_VERIFY=0 é proibido com APP_ENV=production")
        if not self.effective_issuer.startswith("https://"):
            raise ValueError("OIDC_ISSUER precisa ser https://")
        if not self.effective_public_base_url.startswith("https://") and self.app_env != "development":
            raise ValueError("PUBLIC_BASE_URL precisa ser https:// fora de development")
        if self.session_absolute_max < self.session_max_age:
            raise ValueError("SESSION_ABSOLUTE_MAX deve ser >= SESSION_MAX_AGE")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
