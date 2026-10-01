"""Ambiente fictício para os testes: nada aqui toca o RDS nem o IdP."""

import os

import pytest

_ENV = {
    "DB_HOST": "localhost",
    "DB_USER": "apm_area",
    "DB_PASS": "x",
    "DB_NAME": "area_associado",
    "DB_SSL_VERIFY": "0",
    "APP_ENV": "test",
    "SECRET_KEY": "s" * 48,
    "LOG_HASH_KEY": "l" * 48,
    "AUTH_MODE": "oidc",
    "OIDC_CLIENT_SECRET": "c" * 48,
    "OIDC_ISSUER": "https://login.apm.org.br",
    "OIDC_BACKCHANNEL_BASE_URL": "http://login_associado:8000",
    "PUBLIC_BASE_URL": "https://associado.apm.org.br",
}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings():
    from app.config import get_settings

    return get_settings()
