"""Ajuda (P14, Onda 2) — unidades puras e API com banco substituído. Sem banco, sem rede.

Cobre: normalização e busca da FAQ (sem acento, stopwords, plural, ranking,
sugestões), contato da Central (WhatsApp sem PII, telefone, horário, vazio =
bloco some), parâmetros com padrão seguro, formulário (= `outro`) e pedido de
cancelamento (flag → 404, step-up → 403, ordem das dependências, nunca o hub).
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from app.dominio import ajuda
from app.dominio.solicitacoes import parametros, servico
from tests.test_solicitacoes_unidades import SID, detalhe_falso, varrer_chaves


def _p(i, categoria, pergunta, resposta, ordem=10):
    return ajuda.Pergunta(i, categoria, pergunta, resposta, ordem, ajuda.normalizar(pergunta),
                          ajuda.normalizar(f"{resposta} {ajuda.rotulo_categoria(categoria)}"))


FAQ = (
    _p(1, "carteirinha", "Como baixo minha carteirinha digital?", "Abra Carteirinha e toque em Baixar.", 1),
    _p(2, "acesso", "Esqueci minha senha. O que faço?", "Use Esqueci a senha no Login APM.", 1),
    _p(3, "beneficios", "Quais benefícios tenho como associado?", "Veja a página Benefícios.", 1),
    _p(4, "financeiro", "Como pago a anuidade?", "Por boleto; a carteirinha continua válida.", 2),
    _p(5, "nova_categoria", "Pergunta de categoria nova?", "Resposta.", 1),
)


def test_normalizar_e_termos():
    assert ajuda.normalizar("  Ação, CARTEIRINHA!  çÇ ") == "acao carteirinha cc"
    assert ajuda.termos("Como eu baixo a minha Carteirinhas?") == ["baixo", "carteirinha"]
    assert ajuda.termos("de a o") == []
    assert ajuda.termos("x" * 3 + " " + "y") == ["xxx"]


def test_busca_sem_acento_ranking_e_categorias():
    r = ajuda.buscar("ANUIDADE", perguntas=FAQ)
    assert [i["id"] for i in r["itens"]] == [4] and r["sugestoes"] == []
    r = ajuda.buscar("carteirinha", perguntas=FAQ)
    assert [i["id"] for i in r["itens"]] == [1, 4]  # na pergunta pesa mais que na resposta
    r = ajuda.buscar("senha esquecí", perguntas=FAQ)
    assert [i["id"] for i in r["itens"]] == [2]
    assert [c["codigo"] for c in r["categorias"]] == ["acesso", "beneficios", "carteirinha", "financeiro",
                                                      "nova_categoria"]
    assert r["categorias"][-1]["rotulo"] == "Nova categoria"
    r = ajuda.buscar(None, "acesso", perguntas=FAQ)
    assert [i["id"] for i in r["itens"]] == [2]
    assert ajuda.buscar(None, "inexistente", perguntas=FAQ)["itens"] == []
    assert set(r["itens"][0]) == {"id", "pergunta", "resposta", "categoria"}


def test_sem_resultado_sugere_categorias():
    r = ajuda.buscar("financeira boleto atrasado", perguntas=FAQ)
    assert r["itens"] == [] and r["sugestoes"] == ["financeiro"]
    r = ajuda.buscar("zzzz", perguntas=FAQ)
    assert r["itens"] == [] and 1 <= len(r["sugestoes"]) <= ajuda.SUGESTOES_MAX
    assert ajuda.buscar("zzzz", perguntas=())["sugestoes"] == []


def test_faq_cache_e_falha(monkeypatch):
    from sqlalchemy.exc import OperationalError

    linhas = [SimpleNamespace(id=1, categoria="acesso", pergunta="P?", resposta="R.", ordem=1),
              SimpleNamespace(id=2, categoria="Inválida!", pergunta="X?", resposta="Y.", ordem=1)]
    chamadas = []
    monkeypatch.setattr(ajuda, "_ler_faq", lambda: chamadas.append(1) or linhas)
    ajuda.limpar_cache()
    assert [p.id for p in ajuda.carregar()] == [1]  # categoria fora do padrão não sai
    ajuda.carregar()
    assert len(chamadas) == 1

    def fora():
        raise OperationalError("x", {}, Exception("down"))

    monkeypatch.setattr(ajuda, "_ler_faq", fora)
    ajuda.limpar_cache()
    with pytest.raises(ajuda.FaqIndisponivel):
        ajuda.carregar()
    ajuda.limpar_cache()


def test_contato_whatsapp_telefone_horario(monkeypatch, settings):
    w = ajuda.whatsapp()
    assert w["exibicao"] == "(11) 3188-6200"
    assert w["url"].startswith("https://wa.me/551131886200?text=") and "%20" in w["url"]
    monkeypatch.setattr(settings, "show_whatsapp", False)
    assert ajuda.whatsapp() is None
    assert ajuda.telefone("(11) 3188-6200") == {"exibicao": "(11) 3188-6200", "uri": "tel:+551131886200"}
    assert ajuda.telefone("+55 11 98888-7777") == {"exibicao": "(11) 98888-7777", "uri": "tel:+5511988887777"}
    assert ajuda.telefone("0800 123 4567") == {"exibicao": "0800 123 4567", "uri": "tel:08001234567"}
    assert ajuda.telefone("123") is None and ajuda.telefone("") is None and ajuda.telefone(None) is None
    assert ajuda.horario("Segunda a sexta,  8h às 18h") == "Segunda a sexta, 8h às 18h"
    assert ajuda.horario("<b>8h</b>") is None and ajuda.horario("") is None


def test_parametros_padrao_seguro():
    assert parametros.interpretar_inteiro("avaliacao_prazo_dias", "45") == 45
    assert parametros.interpretar_inteiro("avaliacao_prazo_dias", None) == 30
    assert parametros.interpretar_inteiro("avaliacao_prazo_dias", "abc") == 30
    assert parametros.interpretar_inteiro("avaliacao_prazo_dias", "0") == 30  # fora da faixa
    assert parametros.interpretar_inteiro("cancelamento_janela_horas", "0") == 0
    assert parametros.interpretar_inteiro("prazo_retorno_padrao_dias", "9999") == 10
    with pytest.raises(KeyError):
        parametros.texto_cacheado("inventado")


# ------------------------------------------------------------------ API
@pytest.fixture
def api_ajuda(monkeypatch):

    from fastapi.testclient import TestClient

    from app import audit, flags, main, prontidao, uso
    from app.api.v1 import ajuda as rota_ajuda
    from app.api.v1 import solicitacoes as rota
    from app.dominio import associado as dom
    from app.integracoes import hub
    from app.limites import LimiteJanela
    from tests.test_api import TOKEN_STUB

    monkeypatch.setattr(main.settings, "auth_mode", "stub")
    monkeypatch.setattr(main.settings, "dev_stub_token", TOKEN_STUB)
    monkeypatch.setattr(dom, "_executar", lambda p: None)
    gravados: list[dict] = []
    monkeypatch.setattr(uso, "_gravar", lambda linhas: gravados.extend(linhas))
    auditados: list[dict] = []
    monkeypatch.setattr(audit, "registrar_isolado", lambda request, **kw: auditados.append(kw))
    estado = {"tabelas": frozenset(set().union(*prontidao.RECURSOS.values())), "flags": {}}
    monkeypatch.setattr(prontidao, "_ler_tabelas", lambda: estado["tabelas"])
    prontidao.limpar_cache()
    monkeypatch.setattr(flags, "_ler_tabela", lambda: estado["flags"])
    flags.limpar_cache()
    monkeypatch.setattr(parametros, "_ler_texto", lambda chave: {"central_telefone": "(11) 3188-6200",
                                                                 "central_horario": "8h às 18h"}.get(chave))
    parametros.limpar_cache()
    monkeypatch.setattr(ajuda, "_ler_faq", lambda: [SimpleNamespace(id=p.id, categoria=p.categoria,
                                                                    pergunta=p.pergunta, resposta=p.resposta,
                                                                    ordem=p.ordem) for p in FAQ])
    ajuda.limpar_cache()
    monkeypatch.setattr(rota, "limite_escrita", LimiteJanela(100, 60))
    monkeypatch.setattr(rota_ajuda, "limite_faq", LimiteJanela(100, 60))
    monkeypatch.setattr(servico, "contar_aguardando", lambda cid: 0)

    def hub_proibido():
        raise AssertionError("o pedido de cancelamento nunca chama o hub")

    monkeypatch.setattr(hub, "obter_hub", hub_proibido)
    criadas: list[dict] = []

    def criar(**kw):
        criadas.append(kw)
        tipo = kw["tipo_servico"]
        return servico.Criacao(detalhe_falso(tipo={"codigo": tipo, "rotulo": "x"}), True, SID)

    monkeypatch.setattr(servico, "criar", criar)
    c = TestClient(main.app, base_url="https://minha.apm.org.br")
    yield SimpleNamespace(c=c, gravados=gravados, auditados=auditados, estado=estado, criadas=criadas)
    prontidao.limpar_cache()
    flags.limpar_cache()
    parametros.limpar_cache()
    ajuda.limpar_cache()


def _entrar(c):
    from tests.test_api import _cabecalhos, entrar

    entrar(c)
    return _cabecalhos(c.get("/api/v1/sessao").json()["csrf"])


def test_faq_e_contato_pela_api(api_ajuda):
    from app import prontidao

    c = api_ajuda.c
    assert c.get("/api/v1/ajuda/faq").status_code == 401
    _entrar(c)
    r = c.get("/api/v1/ajuda/faq", params={"q": "senha"})
    assert r.status_code == 200 and [i["id"] for i in r.json()["itens"]] == [2]
    assert c.get("/api/v1/ajuda/faq", params={"q": "x" * 81}).status_code == 400
    assert c.get("/api/v1/ajuda/faq", params={"categoria": "Não'Pode"}).status_code == 400
    r = c.get("/api/v1/ajuda/contato").json()
    assert r == {"whatsapp": {"exibicao": "(11) 3188-6200", "url": r["whatsapp"]["url"]},
                 "telefone": {"exibicao": "(11) 3188-6200", "uri": "tel:+551131886200"}, "horario": "8h às 18h"}
    api_ajuda.estado["tabelas"] = frozenset()
    prontidao.limpar_cache()
    r = c.get("/api/v1/ajuda/faq")
    assert r.status_code == 503 and r.json()["erro"] == "recurso_indisponivel"
    assert c.get("/api/v1/ajuda/contato").status_code == 200  # contato não depende de migração


def test_formulario_vira_solicitacao_outro(api_ajuda):
    c = api_ajuda.c
    h = _entrar(c)
    r = c.post("/api/v1/ajuda/formulario", json={"assunto": "financeiro", "mensagem": " Boleto  não chegou ",
                                                 "chave_idempotencia": SID}, headers=h)
    assert r.status_code == 201, r.text
    kw = api_ajuda.criadas[0]
    assert kw["tipo_servico"] == "outro"
    assert kw["campos"] == {"assunto": "Financeiro", "mensagem": "Boleto não chegou", "categoria": "financeiro"}
    for ruim in ({"assunto": "x", "mensagem": "m", "chave_idempotencia": SID},
                 {"assunto": "outro", "mensagem": "", "chave_idempotencia": SID},
                 {"assunto": "outro", "mensagem": "cpf 123.456.789-09", "chave_idempotencia": SID},
                 {"assunto": "outro", "mensagem": "m"}):
        assert c.post("/api/v1/ajuda/formulario", json=ruim, headers=h).status_code == 400, ruim


def test_cancelamento_flag_step_up_e_sem_hub(api_ajuda, monkeypatch):
    from app import flags

    c = api_ajuda.c
    h = _entrar(c)
    corpo = {"motivo": "preco", "quer_conversa": True, "comentario": "Vou pensar", "chave_idempotencia": SID}
    r = c.post("/api/v1/ajuda/cancelamento", json=corpo, headers=h)
    assert r.status_code == 404 and r.json()["erro"] == "recurso_desligado"  # flag nasce desligada
    api_ajuda.estado["flags"] = {"cancelamento_online": True}
    flags.limpar_cache()
    r = c.post("/api/v1/ajuda/cancelamento", json=corpo, headers=h)
    assert r.status_code == 201, r.text  # login stub acabou de acontecer: step-up satisfeito
    kw = api_ajuda.criadas[-1]
    assert kw["tipo_servico"] == "cancelamento_associacao"
    assert kw["campos"] == {"motivo": "preco", "quer_conversa": True, "comentario": "Vou pensar"}
    acoes = [g["acao"] for g in api_ajuda.gravados]
    assert acoes == ["solicitacao_criar", "cancelamento_pedir"]
    assert '"motivo": "preco"' in api_ajuda.gravados[1]["detalhes"]
    assert any(a["tipo"] == "cancelamento_pedido" for a in api_ajuda.auditados)

    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 1000)  # senha digitada há ~17 min
    r = c.post("/api/v1/ajuda/cancelamento", json=corpo, headers=h)
    assert r.status_code == 403 and r.json()["erro"] == "reautenticacao_necessaria"
    assert "cancelamento" in r.json()["mensagem"]
    # Sem a flag, 404 vem ANTES do step-up (não revela recurso desligado a quem não reautenticou).
    api_ajuda.estado["flags"] = {}
    flags.limpar_cache()
    assert c.post("/api/v1/ajuda/cancelamento", json=corpo, headers=h).status_code == 404


def test_cancelamento_valida_motivo_e_booleano(api_ajuda):
    from app import flags

    api_ajuda.estado["flags"] = {"cancelamento_online": True}
    flags.limpar_cache()
    c = api_ajuda.c
    h = _entrar(c)
    for ruim in ({"motivo": "caro", "quer_conversa": False, "chave_idempotencia": SID},
                 {"quer_conversa": False, "chave_idempotencia": SID},
                 {"motivo": "preco", "quer_conversa": "sim", "chave_idempotencia": SID},
                 {"motivo": "preco", "quer_conversa": False, "comentario": "x" * 501, "chave_idempotencia": SID}):
        r = c.post("/api/v1/ajuda/cancelamento", json=ruim, headers=h)
        assert r.status_code == 400, ruim
    assert api_ajuda.criadas == []


def test_respostas_da_ajuda_sem_chaves_proibidas(api_ajuda):
    c = api_ajuda.c
    _entrar(c)
    proibidas = {"contact_id", "sub", "cpf", "email", "crm_id", "crm_sync"}
    for corpo in (c.get("/api/v1/ajuda/faq").json(), c.get("/api/v1/ajuda/contato").json()):
        assert not ({k for k, _ in varrer_chaves(corpo)} & proibidas)
