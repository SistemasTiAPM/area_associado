"""Unidades da Fase 1: analytics, nomes, limites, grants (db_check) e configuração."""

import pytest
from pydantic import ValidationError

from app import uso
from app.api.v1.sessao import formatar_nome, iniciais
from app.limites import LimiteJanela
from scripts.db_check import avaliar_grants


# --------------------------------------------------------------- analytics
def test_ui_so_aceita_detalhes_tipados():
    _, det = uso._validar(uso.Evento("busca_global", "rota", "/area", {"resultados": 3, "tamanho": 5, "termo": "x"}), "ui")
    assert det == '{"resultados": 3, "tamanho": 5}'
    _, det = uso._validar(uso.Evento("busca_global", "rota", "/area", {"resultados": True}), "ui")
    assert det is None  # bool não é inteiro aqui


def test_origem_e_entidade_conferidas():
    with pytest.raises(ValueError, match="origem"):
        uso._validar(uso.Evento("beneficio_ativar", "beneficio"), "ui")
    with pytest.raises(ValueError, match="entidade"):
        uso._validar(uso.Evento("pagina_ver", "beneficio"), "ui")
    with pytest.raises(ValueError, match="desconhecida"):
        uso._validar(uso.Evento("drop_table", "rota"), "servidor")
    with pytest.raises(ValueError, match="entidade_id"):
        uso._validar(uso.Evento("pagina_ver", "rota", "<script>"), "ui")


def test_cpf_em_detalhes_e_recusado_mas_hex_nao():
    with pytest.raises(ValueError, match="cpf"):
        uso._validar(uso.Evento("solicitacao_criar", "solicitacao", None, {"nota": "123.456.789-01"}), "servidor")
    with pytest.raises(ValueError, match="cpf"):
        uso._validar(uso.Evento("solicitacao_criar", "solicitacao", None, {"nota": "12345678901"}), "servidor")
    _, det = uso._validar(
        uso.Evento("erro_exibido", "rota", "/area", {"codigo": "x", "request_id": "12345678901abcde"}), "ui"
    )
    assert "12345678901abcde" in det


def test_chaves_proibidas_somem_dos_detalhes_do_servidor():
    _, det = uso._validar(uso.Evento("solicitacao_criar", "solicitacao", None, {"tipo": "outro", "token": "x"}), "servidor")
    assert det == '{"tipo": "outro"}'


def test_catalogo_cobre_as_36_acoes_dos_requisitos():
    assert len(uso.CATALOGO) == 36
    assert uso.ACOES_UI >= {"pagina_ver", "erro_exibido", "central_whatsapp_abrir"}
    assert "beneficio_ativar" not in uso.ACOES_UI


def test_falha_de_banco_conta_e_nao_lanca(monkeypatch):
    from sqlalchemy.exc import OperationalError

    def falhar(_linhas):
        raise OperationalError("INSERT", {}, Exception("down"))

    monkeypatch.setattr(uso, "_gravar", falhar)
    antes = uso.falhas()
    assert uso.registrar("pagina_ver", "rota", origem="ui", contact_id=None, sub="s") is False
    assert uso.falhas() == antes + 1


# ------------------------------------------------------------------- nomes
@pytest.mark.parametrize("bruto,formatado,ini", [
    ("TELMA NOGUEIRA", "Telma Nogueira", "TN"),
    ("MARIA DA SILVA", "Maria da Silva", "MS"),
    ("João dos Santos", "João dos Santos", "JS"),
    ("Ana", "Ana", "A"),
    ("", "", "?"),
])
def test_nome_e_iniciais(bruto, formatado, ini):
    assert formatar_nome(bruto) == formatado
    assert iniciais(formatado) == ini


# ------------------------------------------------------------------ limites
def test_limite_janela():
    limite = LimiteJanela(maximo=2, janela_s=60)
    assert [limite.permitir("a") for _ in range(3)] == [True, True, False]
    assert limite.permitir("b") is True


# ------------------------------------------------------------------- grants
_BASE = [
    "GRANT USAGE ON *.* TO `apm_area`@`%`",
    "GRANT SELECT, INSERT, EXECUTE ON `area_associado`.* TO `apm_area`@`%`",
    "GRANT UPDATE ON `area_associado`.`associado` TO `apm_area`@`%`",
]


def test_grants_conformes():
    assert avaliar_grants(_BASE, "area_associado") == []


@pytest.mark.parametrize("extra,trecho", [
    ("GRANT UPDATE ON `area_associado`.* TO `apm_area`@`%`", "nível do schema"),
    ("GRANT DELETE ON `area_associado`.`associado` TO `apm_area`@`%`", "DELETE"),
    ("GRANT UPDATE ON `area_associado`.`evento_log` TO `apm_area`@`%`", "fora da allowlist"),
    ("GRANT ALL PRIVILEGES ON `area_associado`.* TO `apm_area`@`%`", "ALL"),
    ("GRANT SELECT ON `login_associado`.* TO `apm_area`@`%`", "outro schema"),
    ("GRANT CREATE ON *.* TO `apm_area`@`%`", "global"),
    ("GRANT UPDATE (`ultimo_acesso_em`), INSERT ON `area_associado`.`associado` TO `apm_area`@`%`", "além de UPDATE"),
])
def test_grants_violacoes(extra, trecho):
    violacoes = avaliar_grants([*_BASE, extra], "area_associado")
    assert violacoes and trecho in violacoes[0]


# ------------------------------------------------------------- configuração
def _build(monkeypatch, **over):
    for k, v in over.items():
        monkeypatch.setenv(k, v)
    from app.config import Settings

    return Settings()


def test_producao_exige_chave_de_sessao(monkeypatch):
    with pytest.raises(ValidationError, match="SESSION_ENC_KEYS"):
        _build(monkeypatch, APP_ENV="production", DB_SSL_VERIFY="1")


def test_chave_de_sessao_invalida_e_recusada(monkeypatch):
    with pytest.raises(ValidationError, match="SESSION_ENC_KEYS"):
        _build(monkeypatch, SESSION_ENC_KEYS="curta-demais")


@pytest.mark.parametrize("host", ["http://www.apm.org.br", "https://*.apm.org.br", "https://www.apm.org.br/img",
                                  "https://a@b.com", "https://x.com;script-src *"])
def test_csp_img_hosts_so_origens_https(monkeypatch, host):
    with pytest.raises(ValidationError, match="CSP_IMG_HOSTS"):
        _build(monkeypatch, CSP_IMG_HOSTS=host)


def test_whatsapp_validado(monkeypatch):
    with pytest.raises(ValidationError, match="WHATSAPP_CENTRAL"):
        _build(monkeypatch, WHATSAPP_CENTRAL="(11) 3188-6200")


def test_flags_forcadas_validadas(monkeypatch):
    with pytest.raises(ValidationError, match="FLAGS_FORCAR_DESLIGADAS"):
        _build(monkeypatch, FLAGS_FORCAR_DESLIGADAS="ok,Flag Ruim")


def test_cookie_sem_prefixo_host_so_em_development(monkeypatch):
    assert _build(monkeypatch).session_cookie_name == "__Host-area"
    dev = _build(monkeypatch, APP_ENV="development", PUBLIC_BASE_URL="http://localhost:8000")
    assert dev.session_cookie_name == "area_sessao" and not dev.session_https_only


# --------------------------------------------------------------- csp_check
def test_csp_check_aceita_a_csp_da_aplicacao():
    from app.main import _csp
    from scripts.csp_check import avaliar_csp

    assert avaliar_csp(_csp("abc123")) == []


def test_csp_check_acusa_inline_e_curinga():
    from scripts.csp_check import avaliar_csp

    ruim = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src *; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'")
    problemas = avaliar_csp(ruim)
    assert any("unsafe-inline" in p for p in problemas) and any("img-src" in p for p in problemas)
