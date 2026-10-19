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
    "PUBLIC_BASE_URL": "https://minha.apm.org.br",
}


# Integração com MySQL real (opcional): com TESTE_DB_HOST definido, os testes
# usam esse banco (migrações 000–007 aplicadas) e os marcados `mysql` rodam.
_INTEGRACAO = {k[len("TESTE_"):]: v for k, v in os.environ.items() if k.startswith("TESTE_DB_")}
if _INTEGRACAO:
    _ENV.update(_INTEGRACAO)


def pytest_collection_modifyitems(config, items):
    if _INTEGRACAO:
        return
    pular = pytest.mark.skip(reason="defina TESTE_DB_HOST/USER/PASS para a integração com MySQL")
    for item in items:
        if "mysql" in item.keywords:
            item.add_marker(pular)


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
