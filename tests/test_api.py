"""API /api/v1, SPA e fluxo stub — sem banco e sem rede (dependências substituídas)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

BASE = "https://associado.apm.org.br"
TOKEN_STUB = "t" * 40
_PROIBIDAS_NA_SESSAO = ("cpf", "cpf_mask", "email", "sub", "contact_id", "cid", "idt")


class _DbFalso:
    def __init__(self):
        self.execucoes = []

    def execute(self, sql, params=None):
        self.execucoes.append((str(sql), params))

    def commit(self):
        pass

    def rollback(self):
        pass


@pytest.fixture
def ctx(monkeypatch, tmp_path):
    from app import audit, flags, main, spa, uso
    from app.api.v1 import uso as rota_uso
    from app.database import get_session
    from app.dominio import associado as dom
    from app.limites import LimiteJanela

    monkeypatch.setattr(main.settings, "auth_mode", "stub")
    monkeypatch.setattr(main.settings, "dev_stub_token", TOKEN_STUB)

    gravados: list[dict] = []
    monkeypatch.setattr(uso, "_gravar", lambda linhas: gravados.extend(linhas))
    acessos: list[dict] = []
    monkeypatch.setattr(dom, "_executar", lambda p: acessos.append(p))
    isolados: list[dict] = []
    monkeypatch.setattr(audit, "registrar_isolado", lambda request, **kw: isolados.append(kw))
    monkeypatch.setattr(flags, "_ler_tabela", lambda: {"fatura_valor": True, "totalpass": True, "inventada": True})
    flags.limpar_cache()
    monkeypatch.setattr(rota_uso, "_limite_lotes", LimiteJanela(maximo=3, janela_s=60))

    index = tmp_path / "index.html"
    index.write_text('<!doctype html><div id="raiz"></div><script type="module" src="/static/spa/assets/a.js"></script>')
    monkeypatch.setattr(spa, "INDEX", index)
    monkeypatch.setattr(spa, "_cache", None)

    db = _DbFalso()
    main.app.dependency_overrides[get_session] = lambda: db
    cliente = TestClient(main.app, base_url=BASE)
    yield {"c": cliente, "gravados": gravados, "acessos": acessos, "isolados": isolados, "db": db, "spa": spa}
    main.app.dependency_overrides.clear()
    flags.limpar_cache()


def entrar(c: TestClient, cpf: str = "12345678901", tipo: str = "Efetivo", nome: str = "TELMA NOGUEIRA DA SILVA"):
    r = c.get("/auth/login", params={"next": "/area/perfil"})
    assert r.status_code == 200
    csrf = re.search(r'name="csrf" value="([^"]+)"', r.text).group(1)
    r = c.post("/auth/login", data={"csrf": csrf, "token": TOKEN_STUB, "nome": nome, "email": "t@x.org",
                                    "cpf": cpf, "tipo": tipo, "next": "/area/perfil"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/area/perfil"
    return csrf


def _cabecalhos(csrf: str, **extra: str) -> dict[str, str]:
    return {"X-CSRF-Token": csrf, "Sec-Fetch-Site": "same-origin", **extra}


# ------------------------------------------------------------------ sem sessão
def test_api_sem_sessao_responde_401_json_sem_redirecionar(ctx):
    r = ctx["c"].get("/api/v1/sessao", follow_redirects=False)
    assert r.status_code == 401
    assert r.json()["erro"] == "nao_autenticado" and r.json()["request_id"] == r.headers["X-Request-Id"]


def test_post_api_sem_sessao_e_401_nao_403(ctx):
    r = ctx["c"].post("/api/v1/uso", json={"eventos": [{"acao": "pagina_ver", "entidade": "rota"}]},
                      headers={"Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 401


def test_area_sem_sessao_redireciona_para_login_com_next_seguro(ctx):
    r = ctx["c"].get("/area/beneficios", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/auth/login?next=/area/beneficios"


def test_rota_api_inexistente_e_404_json_e_html_fora_da_api(ctx):
    assert ctx["c"].get("/api/v1/nada").json()["erro"] == "nao_encontrado"
    r = ctx["c"].get("/nada")
    assert r.status_code == 404 and r.headers["content-type"].startswith("text/html")


# ------------------------------------------------------------ sessão / contrato
def test_sessao_entrega_contrato_sem_dado_pessoal(ctx):
    entrar(ctx["c"])
    r = ctx["c"].get("/api/v1/sessao")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    corpo = r.json()
    assert corpo["associado"] == {"nome": "Telma Nogueira da Silva", "nome_exibicao": "Telma", "iniciais": "TS",
                                  "tipo": "Efetivo", "status": "Ativo", "tem_foto": False}
    assert corpo["stub"] is True and corpo["rota_inicial"] == "/area" and corpo["csrf"]
    assert corpo["config"] == {"whatsapp": "551131886200", "show_whatsapp": True, "animations": True}
    texto = r.text
    for chave in _PROIBIDAS_NA_SESSAO:
        assert f'"{chave}"' not in texto, chave
    assert "12345678901" not in texto and "456.789" not in texto and "t@x.org" not in texto


def test_flags_forcadas_vencem_a_tabela_e_desconhecidas_somem(ctx):
    entrar(ctx["c"])
    flags = ctx["c"].get("/api/v1/sessao").json()["flags"]
    assert flags["fatura_valor"] is False  # forçada desligada por padrão
    assert flags["totalpass"] is True
    assert "inventada" not in flags and len(flags) == 8


def test_flags_com_banco_fora_ficam_todas_desligadas(ctx, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from app import flags

    def falhar():
        raise OperationalError("SELECT", {}, Exception("down"))

    monkeypatch.setattr(flags, "_ler_tabela", falhar)
    flags.limpar_cache()
    assert not any(flags.flags_efetivas().values())


def test_login_registra_acesso_com_contact_id_e_regenera_sessao(ctx):
    c = ctx["c"]
    csrf_antes = entrar(c)
    assert len(ctx["acessos"]) == 1 and re.fullmatch(r"[0-9a-f-]{36}", ctx["acessos"][0]["contact_id"])
    assert ctx["acessos"][0]["sub_hash"] and "12345678901" not in str(ctx["acessos"])
    assert c.get("/api/v1/sessao").json()["csrf"] != csrf_antes  # fixation: sessão nova após o login


def test_cookie_de_sessao_e_host_prefixado_secure_httponly(ctx):
    r = ctx["c"].get("/auth/login")
    cookie = r.headers["set-cookie"]
    assert cookie.startswith("__Host-area=gAAAA")  # token Fernet
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie and "path=/" in cookie


def test_stub_rejeita_tipo_fora_da_lista(ctx):
    c = ctx["c"]
    r = c.get("/auth/login")
    csrf = re.search(r'name="csrf" value="([^"]+)"', r.text).group(1)
    r = c.post("/auth/login", data={"csrf": csrf, "token": TOKEN_STUB, "cpf": "12345678901", "tipo": "Admin"})
    assert r.status_code == 400


# ---------------------------------------------------------------------- CSRF
@pytest.mark.parametrize("cabecalhos,esperado", [
    ({}, "token"),
    ({"X-CSRF-Token": "errado", "Sec-Fetch-Site": "same-origin"}, "token"),
    ({"Sec-Fetch-Site": "cross-site"}, "sec_fetch_site"),
    ({"Sec-Fetch-Site": "same-site"}, "sec_fetch_site"),
    ({"Origin": "https://evil.example"}, "origin"),
    ({}, "origin_ausente"),
])
def test_csrf_recusa_e_registra(ctx, cabecalhos, esperado):
    c = ctx["c"]
    entrar(c)
    csrf = c.get("/api/v1/sessao").json()["csrf"]
    if esperado in ("sec_fetch_site", "origin"):
        cabecalhos = {"X-CSRF-Token": csrf, **cabecalhos}
    if esperado == "origin_ausente":
        cabecalhos = {"X-CSRF-Token": csrf}  # sem Sec-Fetch-Site e sem Origin
    r = c.post("/api/v1/uso", json={"eventos": [{"acao": "pagina_ver", "entidade": "rota"}]}, headers=cabecalhos)
    assert r.status_code == 403 and r.json()["erro"] == "csrf_invalido"
    assert ctx["isolados"][-1]["tipo"] == "csrf_recusado"
    assert ctx["gravados"] == []


def test_csrf_aceita_origin_publico_sem_sec_fetch(ctx):
    c = ctx["c"]
    entrar(c)
    csrf = c.get("/api/v1/sessao").json()["csrf"]
    r = c.post("/api/v1/uso", json={"eventos": [{"acao": "pagina_ver", "entidade": "rota"}]},
               headers={"X-CSRF-Token": csrf, "Origin": BASE})
    assert r.status_code == 202


def test_content_type_de_formulario_e_recusado(ctx):
    c = ctx["c"]
    entrar(c)
    csrf = c.get("/api/v1/sessao").json()["csrf"]
    r = c.post("/api/v1/uso", content='{"eventos":[]}', headers={**_cabecalhos(csrf), "Content-Type": "text/plain"})
    assert r.status_code == 415 and r.json()["erro"] == "tipo_nao_suportado"


# ---------------------------------------------------------------- analytics
def test_uso_grava_com_identidade_da_sessao_e_sem_texto_livre(ctx):
    c = ctx["c"]
    entrar(c)
    csrf = c.get("/api/v1/sessao").json()["csrf"]
    eventos = [
        {"acao": "pagina_ver", "entidade": "rota", "entidade_id": "/area/perfil"},
        {"acao": "busca_global", "entidade": "rota", "entidade_id": "/area", "detalhes": {"resultados": 3, "termo": "dado"}},
        {"acao": "beneficio_ativar", "entidade": "beneficio"},  # ação de servidor: cliente não pode forjar
        {"acao": "nao_existe", "entidade": "rota"},
    ]
    r = c.post("/api/v1/uso", json={"eventos": eventos}, headers=_cabecalhos(csrf))
    assert r.status_code == 202 and r.json() == {"gravados": 2, "descartados": 2}
    linhas = ctx["gravados"]
    assert {linha["acao"] for linha in linhas} == {"pagina_ver", "busca_global"}
    assert all(linha["origem"] == "ui" and linha["contact_id"] == ctx["acessos"][0]["contact_id"] for linha in linhas)
    assert "termo" not in (linhas[1]["detalhes"] or "")


def test_uso_valida_corpo_sem_ecoar_valores(ctx):
    c = ctx["c"]
    entrar(c)
    csrf = c.get("/api/v1/sessao").json()["csrf"]
    r = c.post("/api/v1/uso", json={"eventos": [{"acao": "x" * 99, "entidade": "rota", "extra": "123.456.789-01"}]},
               headers=_cabecalhos(csrf))
    assert r.status_code == 400 and r.json()["erro"] == "entrada_invalida"
    assert "123.456.789-01" not in r.text and {d["campo"] for d in r.json()["detalhes"]} >= {"eventos.0.acao"}


def test_uso_limite_por_associado(ctx):
    c = ctx["c"]
    entrar(c)
    csrf = c.get("/api/v1/sessao").json()["csrf"]
    corpo = {"eventos": [{"acao": "pagina_ver", "entidade": "rota"}]}
    estados = [c.post("/api/v1/uso", json=corpo, headers=_cabecalhos(csrf)).status_code for _ in range(4)]
    assert estados == [202, 202, 202, 429]


# ----------------------------------------------------------------------- SPA
def test_spa_servida_em_qualquer_rota_da_area_sem_cache(ctx):
    c = ctx["c"]
    entrar(c)
    for caminho in ("/area", "/area/beneficios", "/area/qualquer/coisa"):
        r = c.get(caminho)
        assert r.status_code == 200 and 'id="raiz"' in r.text and r.headers["cache-control"] == "no-store", caminho


def test_spa_ausente_responde_503(ctx, tmp_path, monkeypatch):
    c = ctx["c"]
    entrar(c)
    monkeypatch.setattr(ctx["spa"], "INDEX", tmp_path / "nao-existe.html")
    monkeypatch.setattr(ctx["spa"], "_cache", None)
    r = c.get("/area")
    assert r.status_code == 503 and r.headers["X-Request-Id"] in r.text


def test_csp_sem_inline_e_com_hosts_de_imagem(ctx):
    csp = ctx["c"].get("/").headers["content-security-policy"]
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert "style-src 'self';" in csp and "img-src 'self' data: https://www.apm.org.br;" in csp
    assert "frame-ancestors 'none'" in csp and "form-action 'self' https://login.apm.org.br" in csp


def test_asset_404_nao_fica_imutavel(ctx):
    r = ctx["c"].get("/static/spa/assets/inexistente-abc123.js")
    assert r.status_code == 404 and r.headers["cache-control"] == "no-store"


# -------------------------------------------------------------------- logout
def test_logout_limpa_cookie_e_volta_para_o_inicio(ctx):
    c = ctx["c"]
    csrf_form = None
    entrar(c)
    csrf_form = c.get("/api/v1/sessao").json()["csrf"]
    r = c.post("/auth/logout", data={"csrf": csrf_form}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert "Max-Age=0" in r.headers["set-cookie"]
    assert c.get("/api/v1/sessao").status_code == 401
