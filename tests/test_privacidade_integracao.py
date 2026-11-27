"""P13 Perfil e privacidade com MySQL REAL (migrações 000–017) — ADR-0025 e ADR-0026.

Rodar com TESTE_DB_* (usuário da aplicação, `apm_area`): prova que os grants por
coluna da `sql/017` bastam e que consentimento e pedido do titular são imutáveis
para a aplicação. Cada teste usa contatos novos.

O ensaio de `scripts/anonimizar_titular.sql` precisa da credencial administrativa
do banco descartável (`TESTE_ADMIN_PASS`, usuário `TESTE_ADMIN_USER` ou root); sem
ela, é pulado — nunca aponta para produção.
"""

from __future__ import annotations

import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.mysql

RAIZ = Path(__file__).resolve().parents[1]


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _db():
    from app.database import session_scope

    return session_scope()


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    from app import flags, prontidao
    from app.dominio import ajuda
    from app.dominio.solicitacoes import esquema, parametros

    for modulo in (prontidao, flags, parametros, ajuda):
        modulo.limpar_cache()
    esquema.redefinir()
    monkeypatch.setattr(flags, "_ler_tabela", lambda: {"perfil_preferencias": True, "lgpd_consentimentos": True})
    yield
    flags.limpar_cache()
    prontidao.limpar_cache()


def _cid() -> str:
    """Contato novo, com a linha de `associado` (serializa escritas do associado)."""
    cid = str(uuid.uuid4())
    with _db() as db:
        db.execute(text(
            "INSERT INTO associado (contact_id, sub_hash, primeiro_acesso_em, ultimo_acesso_em) "
            "VALUES (:c, :h, :agora, :agora)"), {"c": cid, "h": secrets.token_hex(32), "agora": _agora()})
    return cid


def _um(sql: str, **parametros):
    with _db() as db:
        return db.execute(text(sql), parametros).first()


def _contar(tabela: str, cid: str) -> int:
    assert re.fullmatch(r"[a-z_]+", tabela)
    return int(_um(f"SELECT COUNT(*) AS n FROM {tabela} WHERE contact_id = :c", c=cid).n)


# ----------------------------------------------------------------- grants
def test_prontidao_ve_as_tabelas_da_017():
    from app import prontidao

    assert prontidao.disponivel("privacidade")


def test_trilhas_e_pedidos_sao_imutaveis_para_a_aplicacao():
    from app.dominio import consentimento, preferencias, titular

    cid = _cid()
    preferencias.salvar(cid, preferencias.validar({"fonte": "grande"}))
    consentimento.registrar(contact_id=cid, sub_hash=None, finalidade="ofertas_parceiros", canal="email",
                            valor="concedido", versao="v0")
    titular.exportar(contact_id=cid, sub_hash=secrets.token_hex(32))
    recusados = [
        "UPDATE consentimento SET valor = 'retirado' WHERE contact_id = :c",
        "UPDATE consentimento_texto SET texto = 'outro texto qualquer, bem diferente' WHERE finalidade = 'ofertas_parceiros'",
        "UPDATE titular_pedido SET status = 'cancelado', concluido_em = UTC_TIMESTAMP(6) WHERE contact_id = :c",
        "UPDATE perfil_declarado SET contact_id = UUID() WHERE contact_id = :c",
        "UPDATE perfil_declarado SET criado_em = UTC_TIMESTAMP(6) WHERE contact_id = :c",
        "DELETE FROM perfil_declarado WHERE contact_id = :c",
        "DELETE FROM consentimento WHERE contact_id = :c",
        "DELETE FROM titular_pedido WHERE contact_id = :c",
        "DELETE FROM pergunta_perfil WHERE contact_id = :c",
    ]
    for sql in recusados:
        with pytest.raises(DBAPIError) as erro:
            with _db() as db:
                db.execute(text(sql), {"c": cid})
        assert "denied" in str(erro.value).lower(), sql


def test_checks_do_banco_sao_a_rede_de_protecao():
    cid = _cid()
    invalidos = [
        ("INSERT INTO perfil_declarado (contact_id, tratamento) VALUES (:c, '123.456.789-09')", {}),
        ("INSERT INTO perfil_declarado (contact_id, tratamento) VALUES (:c, '<b>Ana</b>')", {}),
        ("INSERT INTO perfil_declarado (contact_id, atuacao) VALUES (:c, '{\"a\": 1}')", {}),
        ("INSERT INTO consentimento (contact_id, finalidade, canal, valor, versao) "
         "VALUES (:c, 'ofertas_parceiros', 'email', 'concedido', 'v999')", {}),          # FK: versão inexistente
        ("INSERT INTO titular_pedido (id, protocolo, contact_id, sub_hash, tipo, status) "
         "VALUES (:id, 'LGPD-20261119-ABC234', :c, :h, 'exclusao', 'registrado')", {}),  # exclusão sem solicitação
        ("INSERT INTO titular_pedido (id, protocolo, contact_id, sub_hash, tipo, status) "
         "VALUES (:id, 'PROTOCOLO-ERRADO-0000', :c, :h, 'exportacao', 'registrado')", {}),
        ("INSERT INTO titular_pedido (id, protocolo, contact_id, sub_hash, tipo, status) "
         "VALUES (:id, 'LGPD-20261119-ABC235', :c, :h, 'exportacao', 'concluido')", {}),  # concluído sem data
    ]
    for sql, extra in invalidos:
        with pytest.raises(DBAPIError):
            with _db() as db:
                db.execute(text(sql), {"c": cid, "id": str(uuid.uuid4()), "h": secrets.token_hex(32), **extra})


# ------------------------------------------------------------ preferências
def test_preferencias_gravam_so_o_enviado_e_dizem_o_que_mudou():
    from app.dominio import preferencias

    cid = _cid()
    assert preferencias.ler(cid) == preferencias.Preferencias()
    atual, mudou = preferencias.salvar(cid, preferencias.validar(
        {"tratamento": " Dra.  Ana ", "atuacao": ["plantao", "consultorio_proprio"], "fonte": "grande"}))
    assert mudou == ["tratamento", "atuacao", "fonte"]
    assert atual.tratamento == "Dra. Ana" and atual.atuacao == ("consultorio_proprio", "plantao") and atual.fonte == "grande"
    assert atual.temas == () and atual.frequencia is None and atual.faltam() == ["temas", "frequencia"]
    assert atual.canal_preferido is None
    criado = _um("SELECT criado_em, atualizado_em FROM perfil_declarado WHERE contact_id = :c", c=cid)

    time.sleep(0.01)
    atual, mudou = preferencias.salvar(cid, preferencias.validar({"temas": ["comunidade"], "fonte": "grande"}))
    assert mudou == ["temas"] and atual.tratamento == "Dra. Ana" and atual.atuacao == ("consultorio_proprio", "plantao")
    depois = _um("SELECT criado_em, atualizado_em FROM perfil_declarado WHERE contact_id = :c", c=cid)
    assert depois.criado_em == criado.criado_em and depois.atualizado_em > criado.atualizado_em

    # Nada mudou → nada gravado.
    atual, mudou = preferencias.salvar(cid, preferencias.validar({"fonte": "grande"}))
    assert mudou == [] and _um("SELECT atualizado_em FROM perfil_declarado WHERE contact_id = :c",
                               c=cid).atualizado_em == depois.atualizado_em
    # Vazio apaga a resposta (volta a faltar) e o tratamento volta ao neutro.
    atual, mudou = preferencias.salvar(cid, preferencias.validar({"tratamento": "", "temas": []}))
    assert atual.tratamento is None and atual.temas == () and set(mudou) == {"tratamento", "temas"}
    assert preferencias.resumo_sessao(cid) == {"fonte": "grande", "tratamento": None}


def test_perfil_progressivo_uma_pergunta_por_vez_com_pulo():
    from app.dominio import preferencias

    cid = _cid()
    assert preferencias.proxima_pergunta(cid).chave == "tratamento"
    preferencias.pular(cid, "tratamento")
    assert preferencias.proxima_pergunta(cid).chave == "atuacao"
    atual, mudou = preferencias.responder(cid, "atuacao", ["hospital"])
    assert atual.atuacao == ("hospital",) and mudou == ["atuacao"]
    assert preferencias.proxima_pergunta(cid).chave == "temas"
    preferencias.pular(cid, "temas")
    preferencias.pular(cid, "temas")
    assert _um("SELECT vezes FROM pergunta_perfil WHERE contact_id = :c AND chave = 'temas'", c=cid).vezes == 2
    preferencias.responder(cid, "frequencia", "minima")
    assert preferencias.proxima_pergunta(cid) is None  # o resto foi pulado há pouco
    with pytest.raises(preferencias.PreferenciaInvalida):
        preferencias.responder(cid, "temas", [])
    with pytest.raises(preferencias.PerguntaDesconhecida):
        preferencias.pular(cid, "especialidade")


# ---------------------------------------------------------- consentimentos
def test_consentimento_e_trilha_com_versao_e_estado_pela_ultima_linha():
    from app.dominio import consentimento

    cid = _cid()
    [item] = consentimento.listar(cid)
    assert item["finalidade"] == "ofertas_parceiros" and item["canal"] == "email" and item["versao"] == "v0"
    assert item["concedido"] is False and item["historico"] == [] and item["texto_mudou"] is False
    assert consentimento.concedido(cid, "ofertas_parceiros", "email") is False

    comum = dict(contact_id=cid, sub_hash=secrets.token_hex(32), finalidade="ofertas_parceiros", canal="email")
    # Retirar o que nunca foi concedido não gera linha.
    _, gravou = consentimento.registrar(**comum, valor="retirado", versao="v0")
    assert gravou is False and _contar("consentimento", cid) == 0
    item, gravou = consentimento.registrar(**comum, valor="concedido", versao="v0", request_id="a" * 16)
    assert gravou and item["concedido"] and item["versao_registrada"] == "v0" and len(item["historico"]) == 1
    assert consentimento.concedido(cid, "ofertas_parceiros", "email") is True
    # Repetição do clique: mesma decisão, mesma versão → nada novo.
    _, gravou = consentimento.registrar(**comum, valor="concedido", versao="v0")
    assert gravou is False and _contar("consentimento", cid) == 1
    item, gravou = consentimento.registrar(**comum, valor="retirado", versao="v0")
    assert gravou and item["concedido"] is False
    assert [h["valor"] for h in item["historico"]] == ["retirado", "concedido"]
    assert consentimento.concedido(cid, "ofertas_parceiros", "email") is False
    atual = _um("SELECT valor, versao FROM vw_consentimento_atual WHERE contact_id = :c", c=cid)
    assert (atual.valor, atual.versao) == ("retirado", "v0")

    with pytest.raises(consentimento.VersaoDesatualizada) as erro:
        consentimento.registrar(**comum, valor="concedido", versao="v1")
    assert erro.value.vigente == "v0" and _contar("consentimento", cid) == 2
    # WhatsApp: canal ainda não existe (regra 19) — nem lista nem aceita.
    with pytest.raises(consentimento.ConsentimentoDesconhecido):
        consentimento.registrar(contact_id=cid, sub_hash=None, finalidade="whatsapp_relacionamento",
                                canal="whatsapp", valor="concedido", versao="v0")
    assert consentimento.concedido(cid, "whatsapp_relacionamento", "whatsapp") is False


def test_texto_novo_exige_confirmacao_na_versao_nova(monkeypatch):
    from app.dominio import consentimento

    finalidade = "teste_" + secrets.token_hex(4)
    monkeypatch.setitem(consentimento.FINALIDADES, finalidade, ("email",))
    texto = "Texto de teste da finalidade, com tamanho suficiente para o CHECK."
    with _db() as db:
        db.execute(text("INSERT INTO consentimento_texto (finalidade, versao, titulo, texto, vigente_desde) "
                        "VALUES (:f, 'v1', 'Teste', :t, :d)"),
                   {"f": finalidade, "t": texto, "d": _agora() - timedelta(days=2)})
        # Versão futura ainda não vale.
        db.execute(text("INSERT INTO consentimento_texto (finalidade, versao, titulo, texto, vigente_desde) "
                        "VALUES (:f, 'v3', 'Teste futuro', :t, :d)"),
                   {"f": finalidade, "t": texto, "d": _agora() + timedelta(days=30)})
    cid = _cid()
    comum = dict(contact_id=cid, sub_hash=None, finalidade=finalidade, canal="email")
    consentimento.registrar(**comum, valor="concedido", versao="v1")
    with _db() as db:
        db.execute(text("INSERT INTO consentimento_texto (finalidade, versao, titulo, texto, vigente_desde) "
                        "VALUES (:f, 'v2', 'Teste novo', :t, :d)"),
                   {"f": finalidade, "t": texto + " Mudou.", "d": _agora() - timedelta(seconds=5)})
    item = next(i for i in consentimento.listar(cid) if i["finalidade"] == finalidade)
    assert item["versao"] == "v2" and item["titulo"] == "Teste novo"
    assert item["concedido"] is True and item["versao_registrada"] == "v1" and item["texto_mudou"] is True
    with pytest.raises(consentimento.VersaoDesatualizada):
        consentimento.registrar(**comum, valor="concedido", versao="v1")
    item, gravou = consentimento.registrar(**comum, valor="concedido", versao="v2")
    assert gravou and item["texto_mudou"] is False and [h["versao"] for h in item["historico"]] == ["v2", "v1"]


# -------------------------------------------------------------- exportação
def _semear_dados(cid: str) -> str:
    """Perfil em cache, preferência, consentimento, solicitação e uso do contato. Devolve o id da solicitação."""
    from app import uso
    from app.dominio import consentimento, preferencias
    from app.dominio.solicitacoes import schemas, servico

    with _db() as db:
        db.execute(text(
            "INSERT INTO associado_perfil (contact_id, nome, email, celular, endereco, num_contato, crm, crm_uf, "
            " tipo_associado, status_associativo, data_filiacao, origem, atualizado_em) "
            "VALUES (:c, 'CONTATO DE TESTE', 'teste@example.org', '(11) 90000-0000', "
            " '{\"cidade\": \"São Paulo\", \"uf\": \"SP\"}', '000123', '000000', 'SP', 'Efetivo', 'Ativo', "
            " '2026-01-01', 'stub', :agora)"), {"c": cid, "agora": _agora()})
    preferencias.salvar(cid, preferencias.validar({"tratamento": "Dra. Teste", "temas": ["comunidade"]}))
    consentimento.registrar(contact_id=cid, sub_hash=None, finalidade="ofertas_parceiros", canal="email",
                            valor="concedido", versao="v0")
    campos = schemas.validar("outro", {"assunto": "Assunto de teste", "mensagem": "Mensagem de teste."})
    criacao = servico.criar(contact_id=cid, sub_hash=secrets.token_hex(32), tipo_servico="outro", campos=campos,
                            chave_idempotencia=str(uuid.uuid4()))
    assert uso.registrar("perfil_declarado_atualizar", "perfil_declarado", contact_id=cid, sub="sub-" + cid[:8],
                         detalhes={"campos": ["temas"]})
    return criacao.id


def test_exportacao_traz_o_que_a_area_guarda_e_vale_uma_por_semana():
    from app.dominio import titular

    cid = _cid()
    sid = _semear_dados(cid)
    exportacao = titular.exportar(contact_id=cid, sub_hash=secrets.token_hex(32), request_id="b" * 16,
                                  demonstracao=True)
    dados = exportacao.dados
    assert dados["formato"] == "minha-apm-dados/1" and dados["protocolo"] == exportacao.protocolo
    assert set(titular.GRUPOS_EXPORTADOS) <= set(dados)
    assert dados["cadastro"]["nome"] == "CONTATO DE TESTE" and dados["cadastro"]["endereco"]["uf"] == "SP"
    assert dados["cadastro"]["data_filiacao"] == "2026-01-01" and dados["cadastro"]["tem_foto"] is False
    assert dados["preferencias"]["tratamento"] == "Dra. Teste" and dados["preferencias"]["temas"] == ["comunidade"]
    assert [c["valor"] for c in dados["consentimentos"]] == ["concedido"]
    [sol] = dados["solicitacoes"]
    assert sol["id"] == sid and sol["tipo"] == "outro" and sol["campos"]["mensagem"] == "Mensagem de teste."
    assert sol["linha_do_tempo"][0]["evento"] == "criacao"
    assert dados["notificacoes"] and dados["uso"]["truncado"] is False
    assert any(u["acao"] == "perfil_declarado_atualizar" for u in dados["uso"]["itens"])
    # O próprio pedido aparece, já concluído; nada de CPF, sub ou contact_id no arquivo.
    assert dados["pedidos_titular"] == [{"protocolo": exportacao.protocolo, "tipo": "exportacao",
                                         "status": "concluido", "criado_em": dados["gerado_em"],
                                         "concluido_em": dados["gerado_em"]}]
    bruto = str(dados).lower()
    assert cid not in bruto and "'cpf'" not in bruto and "sub_hash" not in bruto
    assert any("demonstração" in o for o in dados["observacoes"])

    with pytest.raises(titular.LimiteExportacao) as erro:
        titular.exportar(contact_id=cid, sub_hash=secrets.token_hex(32))
    assert timedelta(days=6, hours=23) < erro.value.libera_em - _agora() <= timedelta(days=7)
    assert _contar("titular_pedido", cid) == 1
    pedidos = titular.listar_pedidos(cid)
    assert pedidos["exportacao_disponivel_em"] is not None and pedidos["exclusao_aberta"] is None

    # Outro associado não é afetado pelo limite deste.
    outro = _cid()
    assert titular.exportar(contact_id=outro, sub_hash=secrets.token_hex(32)).dados["cadastro"] is None


# ---------------------------------------------------------------- exclusão
def test_pedido_de_exclusao_e_idempotente_unico_e_segue_o_cancelamento():
    from app.dominio import limites_negocio, titular
    from app.dominio.solicitacoes import servico

    cid = _cid()
    sub_hash = secrets.token_hex(32)
    chave = str(uuid.uuid4())
    pedido = titular.pedir_exclusao(contact_id=cid, sub_hash=sub_hash, chave_idempotencia=chave)
    assert pedido.criado and re.fullmatch(r"LGPD-20\d{6}-[A-Z2-7]{6}", pedido.protocolo)
    sol = _um("SELECT tipo_servico, status FROM solicitacao WHERE id = :s AND contact_id = :c",
              s=pedido.solicitacao_id, c=cid)
    assert (sol.tipo_servico, sol.status) == ("exclusao_dados", "criada")
    # Pedir não exclui nada.
    assert _contar("associado", cid) == 1 and _um(
        "SELECT anonimizado_em FROM associado WHERE contact_id = :c", c=cid).anonimizado_em is None

    repetido = titular.pedir_exclusao(contact_id=cid, sub_hash=sub_hash, chave_idempotencia=chave.upper())
    assert not repetido.criado and repetido.protocolo == pedido.protocolo
    assert repetido.solicitacao_id == pedido.solicitacao_id and _contar("titular_pedido", cid) == 1
    with pytest.raises(limites_negocio.PedidoAbertoExistente):
        titular.pedir_exclusao(contact_id=cid, sub_hash=sub_hash, chave_idempotencia=str(uuid.uuid4()))

    pedidos = titular.listar_pedidos(cid)
    assert pedidos["exclusao_aberta"]["protocolo"] == pedido.protocolo
    assert pedidos["exclusao_aberta"]["status"] == "registrado"

    # O associado desiste: a solicitação é cancelada e o pedido passa a valer como cancelado.
    servico.cancelar(cid, pedido.solicitacao_id, motivo=None)
    pedidos = titular.listar_pedidos(cid)
    assert pedidos["exclusao_aberta"] is None and pedidos["itens"][0]["status"] == "cancelado"
    novo = titular.pedir_exclusao(contact_id=cid, sub_hash=sub_hash, chave_idempotencia=str(uuid.uuid4()))
    assert novo.criado and novo.protocolo != pedido.protocolo and _contar("titular_pedido", cid) == 2


# --------------------------------------------------------------------- API
@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.v1 import deps, privacidade as rota, solicitacoes
    from app.csrf import exigir_csrf
    from app.limites import LimiteJanela
    from app.main import app
    from app.session_guard import Associado, require_associado

    cid = _cid()
    associado = Associado(sub="sub-" + cid[:8], contact_id=cid, nome="Contato de Teste", email=None, cpf_mask=None,
                          auth_at=int(time.time()), amr=("pwd",), idp_auth_time=int(time.time()))
    app.dependency_overrides[require_associado] = lambda: associado
    app.dependency_overrides[deps.contexto] = lambda: deps.Contexto(associado, cid)
    app.dependency_overrides[exigir_csrf] = lambda: None
    for nome in ("_limite_preferencias", "_limite_consentimento", "_limite_dados"):
        monkeypatch.setattr(rota, nome, LimiteJanela(1000, 60))
    monkeypatch.setattr(solicitacoes, "limite_escrita", LimiteJanela(1000, 60))
    try:
        yield TestClient(app, base_url="https://minha.apm.org.br"), cid
    finally:
        app.dependency_overrides.clear()


def test_api_preferencias_pergunta_e_sessao(api):
    c, cid = api
    r = c.get("/api/v1/perfil/preferencias")
    assert r.status_code == 200 and r.json()["faltam"] == ["tratamento", "atuacao", "temas", "frequencia"]
    assert [o["valor"] for o in r.json()["opcoes"]["canal_preferido"]] == ["email"]
    assert [o["valor"] for o in r.json()["opcoes"]["frequencia"]] == ["normal", "minima"]
    r = c.put("/api/v1/perfil/preferencias", json={"tratamento": "Dra. Teste", "fonte": "maior"})
    assert r.status_code == 200 and r.json()["tratamento"] == "Dra. Teste" and r.json()["fonte"] == "maior"
    r = c.get("/api/v1/perfil/pergunta")
    assert r.json()["pergunta"]["chave"] == "atuacao" and r.json()["pergunta"]["tipo"] == "multipla"
    r = c.post("/api/v1/perfil/pergunta/atuacao", json={"resposta": ["gestao", "docencia"]})
    assert r.status_code == 200 and r.json()["atuacao"] == ["gestao", "docencia"]
    assert c.post("/api/v1/perfil/pergunta/temas", json={"pular": True}).status_code == 200
    assert c.get("/api/v1/perfil/pergunta").json()["pergunta"]["chave"] == "frequencia"
    assert c.post("/api/v1/perfil/pergunta/frequencia", json={"resposta": "diaria"}).status_code == 400
    assert c.post("/api/v1/perfil/pergunta/inexistente", json={"pular": True}).status_code == 404

    usos = [r.detalhes for r in _linhas_uso(cid, "perfil_declarado_atualizar")]
    assert len(usos) == 2 and "Dra. Teste" not in str(usos)  # nomes de campos, nunca valores
    logs = _logs(cid, "perfil_declarado_atualizado")
    assert len(logs) == 2 and "Dra. Teste" not in str(logs)


def _linhas_uso(cid: str, acao: str):
    with _db() as db:
        return db.execute(text("SELECT detalhes FROM evento_uso WHERE contact_id = :c AND acao = :a ORDER BY id"),
                          {"c": cid, "a": acao}).all()


def _logs(cid: str, tipo: str):
    with _db() as db:
        return db.execute(text("SELECT categoria, detalhes FROM evento_log WHERE contact_id = :c AND tipo = :t "
                               "ORDER BY id"), {"c": cid, "t": tipo}).all()


def test_api_consentimento_com_versao_e_trilha(api):
    c, cid = api
    [item] = c.get("/api/v1/perfil/consentimentos").json()["itens"]
    corpo = {"finalidade": item["finalidade"], "canal": item["canal"], "concedido": True, "versao": item["versao"]}
    r = c.put("/api/v1/perfil/consentimentos", json=corpo)
    assert r.status_code == 200 and r.json()["concedido"] is True and len(r.json()["historico"]) == 1
    r = c.put("/api/v1/perfil/consentimentos", json={**corpo, "versao": "v9"})
    assert r.status_code == 409 and r.json()["erro"] == "versao_desatualizada"
    assert r.json()["detalhes"] == [{"campo": "versao", "mensagem": "v0"}]
    r = c.put("/api/v1/perfil/consentimentos", json={**corpo, "finalidade": "whatsapp_relacionamento",
                                                     "canal": "whatsapp"})
    assert r.status_code == 404
    assert c.put("/api/v1/perfil/consentimentos", json={**corpo, "concedido": False}).json()["concedido"] is False
    assert len(_linhas_uso(cid, "consentimento_alterar")) == 2 and len(_logs(cid, "consentimento_alterado")) == 2


def test_api_exportar_e_pedir_exclusao(api):
    c, cid = api
    _semear_dados(cid)
    r = c.post("/api/v1/perfil/dados/exportar")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert r.json()["cadastro"]["nome"] == "CONTATO DE TESTE"
    [acesso] = _logs(cid, "acesso_dado_pessoal")
    assert acesso.categoria == "seguranca" and "CONTATO DE TESTE" not in str(acesso.detalhes)
    assert len(_linhas_uso(cid, "dados_exportar")) == 1
    r = c.post("/api/v1/perfil/dados/exportar")
    assert r.status_code == 429 and r.json()["erro"] == "limite_negocio"
    assert len(_logs(cid, "acesso_dado_pessoal")) == 1

    chave = str(uuid.uuid4())
    r = c.post("/api/v1/perfil/dados/exclusao", json={"confirmacao": "excluir", "chave_idempotencia": chave})
    assert r.status_code == 201 and set(r.json()) == {"protocolo", "solicitacao_id", "registrado_em"}
    protocolo = r.json()["protocolo"]
    r = c.post("/api/v1/perfil/dados/exclusao", json={"confirmacao": "EXCLUIR", "chave_idempotencia": chave})
    assert r.status_code == 200 and r.json()["protocolo"] == protocolo
    r = c.post("/api/v1/perfil/dados/exclusao", json={"confirmacao": "EXCLUIR",
                                                      "chave_idempotencia": str(uuid.uuid4())})
    assert r.status_code == 409 and r.json()["erro"] == "estado_invalido"
    assert "exclusão de dados" in r.json()["mensagem"]
    r = c.get("/api/v1/perfil/dados/pedidos").json()
    assert r["exclusao_aberta"]["protocolo"] == protocolo and r["exige_reautenticacao"] is False
    assert {i["tipo"] for i in r["itens"]} == {"exportacao", "exclusao"}
    assert len(_linhas_uso(cid, "exclusao_pedir")) == 1 and len(_logs(cid, "exclusao_pedida")) == 1
    # A solicitação aparece para o associado acompanhar.
    r = c.get(f"/api/v1/solicitacoes/{r['exclusao_aberta']['solicitacao_id']}")
    assert r.status_code == 200 and r.json()["tipo"] == {"codigo": "exclusao_dados", "rotulo": "Exclusão de dados"}


# ---------------------------------------------- anonimização pelo operador
def _admin():
    import pymysql

    senha = os.environ.get("TESTE_ADMIN_PASS")
    if not senha:
        pytest.skip("defina TESTE_ADMIN_PASS (banco descartável) para ensaiar scripts/anonimizar_titular.sql")
    return pymysql.connect(host=os.environ["TESTE_DB_HOST"], user=os.environ.get("TESTE_ADMIN_USER", "root"),
                           password=senha, database=os.environ.get("TESTE_DB_NAME", "area_associado"),
                           charset="utf8mb4", autocommit=True)


def _comandos(arquivo: Path) -> list[str]:
    linhas = [linha for linha in arquivo.read_text(encoding="utf-8").splitlines()
              if not linha.lstrip().startswith("--")]
    return [c.strip() for c in "\n".join(linhas).split(";") if c.strip()]


def _anonimizar(protocolo: str) -> tuple[str, str]:
    """Roda o script como o operador. Devolve (situação inicial, resultado final)."""
    con = _admin()
    try:
        with con.cursor() as cur:
            cur.execute("SET @protocolo = %s", (protocolo,))
            cur.execute("SET @operador = 'operador.teste'")
            saidas: list[tuple] = []
            for comando in _comandos(RAIZ / "scripts" / "anonimizar_titular.sql"):
                cur.execute(comando)
                if cur.description:
                    saidas.append(cur.fetchone())
        return str(saidas[0][0]), str(saidas[-1][0])
    finally:
        con.close()


_TABELAS_COM_CONTATO = ("associado", "associado_perfil", "perfil_declarado", "pergunta_perfil", "consentimento",
                        "email_verificacao", "solicitacao", "solicitacao_mensagem", "solicitacao_leitura",
                        "notificacao", "comunicacao_evento", "comunicacao_envio", "comunicacao_supressao",
                        "fila_ligacao", "evento_uso", "evento_log", "titular_pedido")


def test_script_do_operador_anonimiza_sem_delete_e_so_com_pedido_aberto():
    from app.dominio import preferencias, titular
    from app.dominio.solicitacoes import servico

    _admin().close()  # pula cedo sem a credencial administrativa
    cid = _cid()
    sid = _semear_dados(cid)
    preferencias.pular(cid, "atuacao")
    with _db() as db:
        db.execute(text("INSERT INTO solicitacao_mensagem (id, contact_id, registro_id, entidade, texto, status, "
                        " proxima_em, criada_em) VALUES (:id, :c, :r, 'ocorrencia', 'Texto pendente.', 'pendente', "
                        " :agora, :agora)"), {"id": str(uuid.uuid4()), "c": cid, "r": sid, "agora": _agora()})
        db.execute(text("INSERT INTO solicitacao_leitura (contact_id, registro_id, visto_em) VALUES (:c, :r, :agora)"),
                   {"c": cid, "r": sid, "agora": _agora()})
        db.execute(text("INSERT INTO evento_log (categoria, tipo, sub_hash, contact_id) "
                        "VALUES ('negocio', 'teste_anonimizacao', :h, :c)"), {"h": "a" * 64, "c": cid})
    antes = {t: _contar(t, cid) for t in _TABELAS_COM_CONTATO}
    assert all(antes[t] >= 1 for t in ("associado", "associado_perfil", "perfil_declarado", "pergunta_perfil",
                                       "consentimento", "solicitacao", "solicitacao_mensagem", "notificacao",
                                       "comunicacao_evento", "evento_uso", "evento_log"))

    # Protocolo inexistente e pedido cancelado pelo associado: nada acontece.
    assert _anonimizar("LGPD-20200101-AAAAAA")[1] == "nada alterado"
    desistido = titular.pedir_exclusao(contact_id=cid, sub_hash=secrets.token_hex(32),
                                       chave_idempotencia=str(uuid.uuid4()))
    servico.cancelar(cid, desistido.solicitacao_id, motivo=None)
    situacao, resultado = _anonimizar(desistido.protocolo)
    assert situacao.startswith("NADA A FAZER") and resultado == "nada alterado"
    assert _contar("associado", cid) == 1 and _contar("associado_perfil", cid) == 1

    pedido = titular.pedir_exclusao(contact_id=cid, sub_hash=secrets.token_hex(32),
                                    chave_idempotencia=str(uuid.uuid4()))
    antes = {t: _contar(t, cid) for t in _TABELAS_COM_CONTATO}
    totais = {t: int(_um(f"SELECT COUNT(*) AS n FROM {t}").n) for t in _TABELAS_COM_CONTATO}
    situacao, resultado = _anonimizar(pedido.protocolo)
    assert situacao.startswith("anonimizando") and resultado == "anonimização concluída"

    # Nenhuma linha com o contato; nenhuma linha apagada (sem DELETE).
    for tabela in _TABELAS_COM_CONTATO:
        assert _contar(tabela, cid) == 0, tabela
        assert int(_um(f"SELECT COUNT(*) AS n FROM {tabela}").n) >= totais[tabela], tabela
    fechado = _um("SELECT contact_id, status, concluido_em, observacao, sub_hash FROM titular_pedido "
                  "WHERE protocolo = :p", p=pedido.protocolo)
    anon = fechado.contact_id
    assert anon != cid and fechado.status == "concluido" and fechado.concluido_em is not None
    assert fechado.observacao == "anonimizado por operador.teste" and fechado.sub_hash == "0" * 64
    for tabela in _TABELAS_COM_CONTATO:
        assert _contar(tabela, anon) == antes[tabela], tabela

    perfil = _um("SELECT nome, email, celular, endereco, crm, num_contato, data_filiacao, tipo_associado "
                 "FROM associado_perfil WHERE contact_id = :c", c=anon)
    assert tuple(perfil)[:7] == (None,) * 7 and perfil.tipo_associado == "Efetivo"
    assoc = _um("SELECT sub_hash, carteirinha_token, anonimizado_em FROM associado WHERE contact_id = :c", c=anon)
    assert assoc.sub_hash == "0" * 64 and assoc.carteirinha_token is None and assoc.anonimizado_em is not None
    declarado = _um("SELECT tratamento, temas FROM perfil_declarado WHERE contact_id = :c", c=anon)
    assert declarado.tratamento is None and "comunidade" in str(declarado.temas)
    sol = _um("SELECT dados, sub_hash, status, crm_sync FROM solicitacao WHERE id = :s", s=sid)
    assert str(sol.dados) == "{}" and sol.sub_hash == "0" * 64 and sol.crm_sync in ("retido", "ok", "falhou")
    excl = _um("SELECT status, concluida_em FROM solicitacao WHERE id = :s", s=pedido.solicitacao_id)
    assert excl.status == "concluida_positiva" and excl.concluida_em is not None
    evento = _um("SELECT ator, origem, usuario_interno, justificativa FROM solicitacao_evento "
                 "WHERE solicitacao_id = :s AND para_status = 'concluida_positiva'", s=pedido.solicitacao_id)
    assert (evento.ator, evento.origem, evento.usuario_interno) == ("apm", "backoffice", "operador.teste")
    assert pedido.protocolo in evento.justificativa
    mensagem = _um("SELECT texto, status, erro_codigo FROM solicitacao_mensagem WHERE contact_id = :c", c=anon)
    assert (mensagem.texto, mensagem.status, mensagem.erro_codigo) == (None, "falhou", "titular_anonimizado")
    notificacoes = {r.titulo for r in _db_todas("SELECT titulo, corpo FROM notificacao WHERE contact_id = :c", anon)}
    assert notificacoes == {"Notificação removida"}
    pendentes = _um("SELECT COUNT(*) AS n FROM comunicacao_evento WHERE contact_id = :c "
                    "AND status IN ('pendente', 'enviando', 'erro')", c=anon)
    assert pendentes.n == 0
    usos = _um("SELECT COUNT(*) AS n, SUM(sub_hash IS NOT NULL) AS com_hash FROM evento_uso WHERE contact_id = :c",
               c=anon)
    assert usos.n >= 1 and int(usos.com_hash) == 0
    # `evento_log` fica: a identidade só como HMAC.
    log = _um("SELECT sub_hash FROM evento_log WHERE contact_id = :c AND tipo = 'teste_anonimizacao'", c=anon)
    assert log.sub_hash == "a" * 64

    # Segunda execução: nada a fazer. O associado que volta nasce de novo, sem herdar nada.
    assert _anonimizar(pedido.protocolo)[1] == "nada alterado"
    assert _contar("associado", anon) == 1
    from app.dominio import associado as dominio_associado

    assert dominio_associado.registrar_acesso(cid, "sub-novo") is True
    assert _contar("associado", cid) == 1 and _contar("solicitacao", cid) == 0
    assert titular.listar_pedidos(cid) == {"itens": [], "exportacao_disponivel_em": None, "exclusao_aberta": None}


def _db_todas(sql: str, cid: str):
    with _db() as db:
        return db.execute(text(sql), {"c": cid}).all()
