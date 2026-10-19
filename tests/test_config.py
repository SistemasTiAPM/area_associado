import pytest
from pydantic import ValidationError


def _build(monkeypatch, **over):
    for k, v in over.items():
        monkeypatch.setenv(k, v)
    from app.config import Settings

    return Settings()


def test_stub_em_producao_e_recusado(monkeypatch):
    with pytest.raises(ValidationError, match="stub"):
        _build(monkeypatch, APP_ENV="production", AUTH_MODE="stub", DEV_STUB_TOKEN="t" * 40, DB_SSL_VERIFY="1")


def test_stub_exige_token_longo(monkeypatch):
    with pytest.raises(ValidationError, match="DEV_STUB_TOKEN"):
        _build(monkeypatch, APP_ENV="staging", AUTH_MODE="stub", DEV_STUB_TOKEN="curto")


def test_stub_em_staging_ok(monkeypatch):
    s = _build(monkeypatch, APP_ENV="staging", AUTH_MODE="stub", DEV_STUB_TOKEN="t" * 40)
    assert s.auth_mode == "stub" and s.session_https_only and not s.expose_openapi


def test_tls_sem_verificacao_em_producao_e_recusado(monkeypatch):
    with pytest.raises(ValidationError, match="DB_SSL_VERIFY"):
        _build(monkeypatch, APP_ENV="production", DB_SSL_VERIFY="0")


def test_oidc_exige_client_secret(monkeypatch):
    monkeypatch.delenv("OIDC_CLIENT_SECRET")
    with pytest.raises(ValidationError, match="OIDC_CLIENT_SECRET"):
        _build(monkeypatch)


def test_derivados(settings):
    assert settings.redirect_uri == "https://minha.apm.org.br/auth/callback"
    assert settings.post_logout_redirect_uri == "https://minha.apm.org.br/"
    assert settings.backchannel_host_header == "login.apm.org.br"
    assert "password" not in settings.sqlalchemy_dsn and "x@" not in settings.sqlalchemy_dsn


def test_backchannel_igual_ao_issuer_nao_forca_host(monkeypatch):
    s = _build(monkeypatch, OIDC_BACKCHANNEL_BASE_URL="https://login.apm.org.br/")
    assert s.backchannel_host_header is None
