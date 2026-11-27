"""Onda 2 ponta a ponta com MySQL REAL (migrações 000–013) — solicitações, ajuda, outbox.

Rodar com TESTE_DB_HOST/TESTE_DB_USER/TESTE_DB_PASS/TESTE_DB_NAME (usuário da
aplicação, `apm_area`, com `sql/000`…`sql/013` aplicadas) — sem eles, pulados
(ver conftest). O "atendente" é simulado pela própria máquina de estados
(`maquina.transitar` com ator `apm`), que roda com os grants do `apm_area`:
o teste prova também que o UPDATE por coluna basta para o fluxo inteiro.
"""

from __future__ import annotations

import re
import secrets
import threading
import time
import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.mysql

BASE = "https://minha.apm.org.br"
TOKEN_STUB = "t" * 40
_PROIBIDAS = {"contact_id", "sub", "sub_hash", "cpf", "email", "crm_id", "crm_sync", "crm_tentativas",
              "crm_proxima_em", "justificativa", "usuario_interno", "conteudo_enviado", "chave_idempotencia",
              "dados", "responsavel"}


class _HubEspiao:
    """Registra qualquer chamada: o pedido de cancelamento não pode chamar nenhuma."""

    def __init__(self):
        self.chamadas: list[str] = []

    def __getattr__(self, nome):
        if nome.startswith("_"):
            raise AttributeError(nome)

        def chamar(*a, **k):
            self.chamadas.append(nome)
            raise AssertionError(f"hub chamado: {nome}")

        return chamar


@pytest.fixture
def ambiente(monkeypatch):
    from app import flags, main, prontidao
    from app.api.v1 import ajuda as rota_ajuda
    from app.api.v1 import solicitacoes as rota
    from app.config import get_settings
    from app.dominio import ajuda
    from app.dominio.solicitacoes import parametros
    from app.integracoes.hub import redefinir_hub
    from app.limites import LimiteJanela

    monkeypatch.setattr(main.settings, "auth_mode", "stub")
    monkeypatch.setattr(main.settings, "dev_stub_token", TOKEN_STUB)
    monkeypatch.setattr(rota, "limite_escrita", LimiteJanela(1000, 60))
    monkeypatch.setattr(rota_ajuda, "limite_faq", LimiteJanela(1000, 60))
    for modulo in (prontidao, flags, parametros, ajuda):
        modulo.limpar_cache()
    redefinir_hub(None)
    yield SimpleNs(settings=get_settings())
    for modulo in (prontidao, flags, parametros, ajuda):
        modulo.limpar_cache()
    redefinir_hub(None)


class SimpleNs:
    def __init__(self, **k):
        self.__dict__.update(k)


def _cpf() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(11))


def novo_cliente() -> tuple[TestClient, dict, str]:
    """Associado novo (CPF aleatório ⇒ contact_id próprio). Devolve (cliente, cabeçalhos, contact_id)."""
    from app import main
    from app.dominio.associado import contact_id_stub

    c = TestClient(main.app, base_url=BASE)
    r = c.get("/auth/login", params={"next": "/area"})
    csrf = re.search(r'name="csrf" value="([^"]+)"', r.text).group(1)
    cpf = _cpf()
    r = c.post("/auth/login", data={"csrf": csrf, "token": TOKEN_STUB, "nome": "TELMA NOGUEIRA",
                                    "email": "telma@exemplo.org", "cpf": cpf, "tipo": "Efetivo"},
               follow_redirects=False)
    assert r.status_code == 303
    s = c.get("/api/v1/sessao").json()
    return c, {"X-CSRF-Token": s["csrf"], "Sec-Fetch-Site": "same-origin"}, contact_id_stub(cpf)


def _chave() -> str:
    return str(uuid.uuid4())


def _outro(c, h, assunto="Dúvida", mensagem="Quero saber sobre o seguro.", chave=None):
    return c.post("/api/v1/solicitacoes", json={"tipo_servico": "outro", "campos": {"assunto": assunto,
                                                                                    "mensagem": mensagem},
                                                "chave_idempotencia": chave or _chave()}, headers=h)


def _db():
    from app.database import session_scope

    return session_scope()


def _transitar(sid, para, ator="apm", origem="backoffice", **kw):
    from app.dominio.solicitacoes import maquina

    if origem == "backoffice":
        kw.setdefault("justificativa", "Atendimento registrado pela Central (teste).")
    with _db() as db:
        return maquina.transitar(db, solicitacao_id=sid, para=para, ator=ator, origem=origem, **kw)


def _sem_chaves_proibidas(corpo):
    def chaves(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from chaves(v)
        elif isinstance(o, list):
            for v in o:
                yield from chaves(v)
    vazou = set(chaves(corpo)) & _PROIBIDAS
    assert not vazou, vazou
    assert not re.search(r"\b\d{11}\b", str(corpo))


# ===================================================================== fluxo
def test_criar_listar_detalhe_e_idempotencia(ambiente):
    c, h, cid = novo_cliente()
    s = c.get("/api/v1/sessao").json()
    assert s["recursos"] == {"solicitacoes": True, "ajuda": True, "privacidade": True} and s["solicitacoes_aguardando"] == 0
    chave = _chave()
    r = _outro(c, h, assunto="  Seguro ", chave=chave)
    assert r.status_code == 201, r.text
    d = r.json()
    _sem_chaves_proibidas(d)
    assert d["status"] == "criada" and d["rotulo_status"] == "Recebida pela APM" and d["prazo_em"] is None
    assert d["tipo"] == {"codigo": "outro", "rotulo": "Outro assunto"} and d["campos"]["assunto"] == "Seguro"
    assert d["pode_cancelar"] and not d["pode_responder"] and not d["pode_avaliar"]
    assert [e["status"] for e in d["linha_do_tempo"]] == ["criada"] and d["linha_do_tempo"][0]["ator"] == "voce"
    assert d["contato"]["canal"] == "whatsapp"
    # Repetição da chave: 200, mesma solicitação, nenhuma linha nova.
    r2 = _outro(c, h, assunto="Outro texto", chave=chave)
    assert r2.status_code == 200 and r2.json()["id"] == d["id"]
    with _db() as db:
        n = db.execute(text("SELECT COUNT(*) FROM solicitacao WHERE contact_id = :c"), {"c": cid}).scalar_one()
        ev = db.execute(text("SELECT evento, conteudo_enviado, request_id FROM solicitacao_evento "
                             "WHERE solicitacao_id = :s"), {"s": d["id"]}).all()
        linha = db.execute(text("SELECT tipo_ativacao, canal_envio, prazo_retorno_dias, crm_sync, sub_hash "
                                "FROM solicitacao WHERE id = :s"), {"s": d["id"]}).one()
    assert n == 1 and len(ev) == 1 and ev[0].evento == "criacao" and re.fullmatch(r"[0-9a-f]{16}", ev[0].request_id)
    assert '"sha256"' in ev[0].conteudo_enviado and "Seguro" not in ev[0].conteudo_enviado  # nunca o payload
    assert (linha.tipo_ativacao, linha.canal_envio, linha.prazo_retorno_dias, linha.crm_sync) == (3, "crm", 10,
                                                                                                    "pendente")
    # Chave reaproveitada em OUTRO tipo: 409, sem linha nova.
    r3 = c.post("/api/v1/solicitacoes", json={"tipo_servico": "declaracao_associado",
                                              "campos": {"finalidade": "geral"}, "chave_idempotencia": chave},
                headers=h)
    assert r3.status_code == 409 and r3.json()["erro"] == "estado_invalido"
    lista = c.get("/api/v1/solicitacoes").json()
    assert [i["id"] for i in lista["itens"]] == [d["id"]] and lista["proximo_cursor"] is None
    _sem_chaves_proibidas(lista)
    assert c.get("/api/v1/solicitacoes", params={"situacao": "encerradas"}).json()["itens"] == []


def test_paginacao_por_cursor(ambiente):
    c, h, _ = novo_cliente()
    ids = [_outro(c, h, assunto=f"Assunto {i}").json()["id"] for i in range(3)]
    p1 = c.get("/api/v1/solicitacoes", params={"limite": 2}).json()
    assert len(p1["itens"]) == 2 and p1["proximo_cursor"]
    p2 = c.get("/api/v1/solicitacoes", params={"limite": 2, "cursor": p1["proximo_cursor"]}).json()
    assert len(p2["itens"]) == 1 and p2["proximo_cursor"] is None
    assert {i["id"] for i in p1["itens"] + p2["itens"]} == set(ids)
    r = c.get("/api/v1/solicitacoes", params={"cursor": "lixo"})
    assert r.status_code == 400 and r.json()["detalhes"][0]["campo"] == "cursor"


def test_outbox_e_notificacao_na_mesma_transacao(ambiente, monkeypatch):
    from app.dominio import comunicacao
    from app.dominio.solicitacoes import servico

    c, h, cid = novo_cliente()
    sid = _outro(c, h).json()["id"]
    with _db() as db:
        outbox = db.execute(text("SELECT gatilho, canal, destinatario, status FROM comunicacao_evento "
                                 "WHERE referencia_id = :s ORDER BY canal"), {"s": sid}).all()
        notif = db.execute(text("SELECT tipo, chave, link FROM notificacao WHERE contact_id = :c"), {"c": cid}).all()
    assert sorted(tuple(o) for o in outbox) == [("A04", "email", "associado", "pendente"),
                                                ("A04", "rd", "associado", "pendente")]
    assert [tuple(n) for n in notif] == [("solicitacao_criada", f"A04:{sid}", f"/area/solicitacoes/{sid}")]

    # Falha na produção da outbox ⇒ a solicitação também não existe (rollback inteiro).
    def quebrar(*a, **k):
        raise RuntimeError("outbox fora")

    monkeypatch.setattr(comunicacao, "enfileirar", quebrar)
    chave = _chave()
    with pytest.raises(RuntimeError):
        servico.criar(contact_id=cid, sub_hash="a" * 64, tipo_servico="outro",
                      campos={"assunto": "x", "mensagem": "y"}, chave_idempotencia=chave)
    with _db() as db:
        assert db.execute(text("SELECT COUNT(*) FROM solicitacao WHERE contact_id = :c AND chave_idempotencia = :k"),
                          {"c": cid, "k": chave}).scalar_one() == 0
    # Dedupe: enfileirar de novo a mesma causa não duplica.
    monkeypatch.undo()
    with _db() as db:
        n = comunicacao.enfileirar(db, gatilho="A04", contact_id=cid, referencia_tipo="solicitacao",
                                   referencia_id=sid, destinos=[("email", "associado"), ("rd", "associado")])
    assert n == 0


def test_atendimento_pendente_responder_contador_e_linha_do_tempo(ambiente):
    c, h, cid = novo_cliente()
    sid = _outro(c, h).json()["id"]
    _transitar(sid, "enviada", ator="sistema", origem="job")
    d = c.get(f"/api/v1/solicitacoes/{sid}").json()
    assert d["rotulo_status"] == "Encaminhada à equipe" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["prazo_em"])
    _transitar(sid, "em_atendimento", ator="apm", origem="crm")
    r = c.post(f"/api/v1/solicitacoes/{sid}/cancelar", json={}, headers=h)
    assert r.status_code == 409 and r.json()["erro"] == "estado_invalido"  # nunca em atendimento
    r = c.post(f"/api/v1/solicitacoes/{sid}/responder", json={"texto": "Segue."}, headers=h)
    assert r.status_code == 409  # só em pendente_associado
    _transitar(sid, "pendente_associado", mensagem="Envie o número da apólice, por favor.")
    s = c.get("/api/v1/sessao").json()
    assert s["solicitacoes_aguardando"] == 1
    d = c.get(f"/api/v1/solicitacoes/{sid}").json()
    assert d["pode_responder"] and d["pode_cancelar"]
    assert d["linha_do_tempo"][-1]["mensagem"] == "Envie o número da apólice, por favor."
    assert d["linha_do_tempo"][-1]["ator"] == "equipe_apm"
    r = c.post(f"/api/v1/solicitacoes/{sid}/responder", json={"texto": "  Apólice ABC-77.  "}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "em_atendimento"
    assert c.get("/api/v1/sessao").json()["solicitacoes_aguardando"] == 0
    tl = r.json()["linha_do_tempo"]
    assert [e["status"] for e in tl] == ["criada", "enviada", "em_atendimento", "pendente_associado",
                                         "em_atendimento"]
    assert tl[-1] == {**tl[-1], "ator": "voce", "mensagem": "Apólice ABC-77."}
    _sem_chaves_proibidas(r.json())
    with _db() as db:
        notifs = db.execute(text("SELECT tipo FROM notificacao WHERE contact_id = :c ORDER BY id"),
                            {"c": cid}).scalars().all()
        just = db.execute(text("SELECT COUNT(*) FROM solicitacao_evento WHERE solicitacao_id = :s "
                               "AND origem = 'backoffice' AND justificativa IS NOT NULL"), {"s": sid}).scalar_one()
    assert notifs == ["solicitacao_criada", "solicitacao_pendente"] and just == 1


def test_cancelar_suprime_outbox_pendente(ambiente):
    c, h, cid = novo_cliente()
    sid = _outro(c, h).json()["id"]
    r = c.post(f"/api/v1/solicitacoes/{sid}/cancelar", json={"motivo": "Resolvi por telefone."}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "cancelada" and not r.json()["pode_cancelar"]
    with _db() as db:
        st = db.execute(text("SELECT status, supressao_motivo FROM comunicacao_evento WHERE referencia_id = :s"),
                        {"s": sid}).all()
        sup = db.execute(text("SELECT COUNT(*) FROM comunicacao_supressao WHERE contact_id = :c"),
                         {"c": cid}).scalar_one()
        motivo = db.execute(text("SELECT cancel_motivo FROM solicitacao WHERE id = :s"), {"s": sid}).scalar_one()
    assert {tuple(x) for x in st} == {("suprimido", "fato_mudou")} and sup == 2
    assert motivo == "Resolvi por telefone."
    r = c.post(f"/api/v1/solicitacoes/{sid}/cancelar", json={}, headers=h)
    assert r.status_code == 409  # terminal


def test_cancelamento_concorrente_tem_um_vencedor(ambiente):
    from app.dominio.solicitacoes import maquina, servico

    c, h, cid = novo_cliente()
    sid = _outro(c, h).json()["id"]
    barreira = threading.Barrier(2)
    resultados: list[str] = []

    def tentar(acao):
        barreira.wait()
        try:
            if acao == "cancelar":
                servico.cancelar(cid, sid, motivo=None)
            else:
                _transitar(sid, "em_atendimento", ator="apm", origem="crm")
            resultados.append(f"{acao}:ok")
        except maquina.TransicaoInvalida:
            resultados.append(f"{acao}:409")

    threads = [threading.Thread(target=tentar, args=(a,)) for a in ("cancelar", "atender")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert len(resultados) == 2 and sum(r.endswith(":ok") for r in resultados) == 1, resultados
    with _db() as db:
        n = db.execute(text("SELECT COUNT(*) FROM solicitacao_evento WHERE solicitacao_id = :s AND evento = "
                            "'transicao'"), {"s": sid}).scalar_one()
    assert n == 1


def test_isolamento_por_contact_id(ambiente):
    a, ha, _ = novo_cliente()
    b, hb, _ = novo_cliente()
    sid = _outro(a, ha).json()["id"]
    assert b.get(f"/api/v1/solicitacoes/{sid}").status_code == 404
    assert b.get("/api/v1/solicitacoes").json()["itens"] == []
    for rota, corpo in (("cancelar", {}), ("responder", {"texto": "x"}), ("avaliar", {"nota": 5})):
        r = b.post(f"/api/v1/solicitacoes/{sid}/{rota}", json=corpo, headers=hb)
        assert r.status_code == 404 and r.json()["erro"] == "nao_encontrado", rota
    assert a.get(f"/api/v1/solicitacoes/{sid}").json()["status"] == "criada"
    assert a.get("/api/v1/solicitacoes/nao-e-uuid").status_code == 404


def test_avaliacao_uma_vez_no_prazo(ambiente):
    c, h, _ = novo_cliente()
    sid = _outro(c, h).json()["id"]
    r = c.post(f"/api/v1/solicitacoes/{sid}/avaliar", json={"nota": 9}, headers=h)
    assert r.status_code == 409 and r.json()["erro"] == "estado_invalido"
    _transitar(sid, "em_atendimento")
    _transitar(sid, "concluida_positiva")
    d = c.get(f"/api/v1/solicitacoes/{sid}").json()
    assert d["pode_avaliar"] and d["rotulo_status"] == "Concluída" and d["prazo_em"] is None
    r = c.post(f"/api/v1/solicitacoes/{sid}/avaliar", json={"nota": 9, "comentario": "Rápido e  claro."},
               headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["avaliacao"]["nota"] == 9 and r.json()["avaliacao"]["comentario"] == "Rápido e claro."
    assert not r.json()["pode_avaliar"]
    assert "Avaliação registrada" not in {e["rotulo"] for e in r.json()["linha_do_tempo"]}
    r = c.post(f"/api/v1/solicitacoes/{sid}/avaliar", json={"nota": 3}, headers=h)
    assert r.status_code == 409 and r.json()["erro"] == "ja_avaliada"
    # Fora do prazo (parametro.avaliacao_prazo_dias = 30).
    sid2 = _outro(c, h).json()["id"]
    _transitar(sid2, "em_atendimento")
    _transitar(sid2, "concluida_negativa")
    with _db() as db:
        db.execute(text("UPDATE solicitacao SET concluida_em = concluida_em - INTERVAL 31 DAY WHERE id = :s"),
                   {"s": sid2})
    assert c.get(f"/api/v1/solicitacoes/{sid2}").json()["pode_avaliar"] is False
    r = c.post(f"/api/v1/solicitacoes/{sid2}/avaliar", json={"nota": 7}, headers=h)
    assert r.status_code == 409 and r.json()["erro"] == "prazo_expirado"
    with _db() as db:
        notif = db.execute(text("SELECT COUNT(*) FROM notificacao WHERE chave = :k"), {"k": f"A06:{sid}"}).scalar_one()
        a06 = db.execute(text("SELECT COUNT(*) FROM comunicacao_evento WHERE gatilho = 'A06' AND referencia_id = :s"),
                         {"s": sid}).scalar_one()
    assert notif == 1 and a06 == 2


def test_limite_outro_5_por_dia(ambiente):
    c, h, _ = novo_cliente()
    for i in range(5):
        assert _outro(c, h, assunto=f"A{i}").status_code == 201
    r = _outro(c, h, assunto="sexta")
    assert r.status_code == 429 and r.json()["erro"] == "limite_negocio"


def test_declaracao_amb_carencia_e_unicidade_por_finalidade(ambiente):
    from app.dominio.solicitacoes.schemas import hoje_sp

    c, h, cid = novo_cliente()
    filiacao = hoje_sp() - timedelta(days=10)
    with _db() as db:
        db.execute(text("UPDATE associado_perfil SET data_filiacao = :d WHERE contact_id = :c"),
                   {"d": filiacao, "c": cid})

    def pedir(finalidade):
        return c.post("/api/v1/solicitacoes", json={"tipo_servico": "declaracao_associado",
                                                    "campos": {"finalidade": finalidade},
                                                    "chave_idempotencia": _chave()}, headers=h)

    r = pedir("amb_prova_titulo")
    assert r.status_code == 409 and r.json()["erro"] == "nao_elegivel"
    libera = r.json()["detalhes"][0]
    assert libera["campo"] == "libera_em" and date.fromisoformat(libera["mensagem"]) > hoje_sp()
    assert pedir("geral").status_code == 201  # sem carência
    assert pedir("geral").json()["erro"] == "estado_invalido"  # uma aberta por finalidade
    with _db() as db:
        db.execute(text("UPDATE associado_perfil SET data_filiacao = :d WHERE contact_id = :c"),
                   {"d": hoje_sp() - timedelta(days=40), "c": cid})
    r = pedir("amb_prova_titulo")
    assert r.status_code == 201 and r.json()["campos"] == {"finalidade": "amb_prova_titulo"}


def test_alteracao_cadastro_um_aberto_por_campo(ambiente):
    c, h, _ = novo_cliente()

    def pedir(alteracoes):
        return c.post("/api/v1/solicitacoes", json={"tipo_servico": "alteracao_cadastro",
                                                    "campos": {"alteracoes": alteracoes},
                                                    "chave_idempotencia": _chave()}, headers=h)

    assert pedir({"nome": "Telma"}).status_code == 201
    assert pedir({"nome": "Telmah", "sobrenome": "Silva"}).json()["erro"] == "estado_invalido"
    assert pedir({"sobrenome": "Silva"}).status_code == 201
    assert pedir({"email": "x@y.z"}).status_code == 400


def test_criacao_concorrente_da_mesma_declaracao(ambiente):
    from app.dominio.limites_negocio import PedidoAbertoExistente
    from app.dominio.solicitacoes import servico

    c, h, cid = novo_cliente()
    barreira = threading.Barrier(2)
    resultados: list[str] = []

    def tentar():
        barreira.wait()
        try:
            servico.criar(contact_id=cid, sub_hash="b" * 64, tipo_servico="declaracao_associado",
                          campos={"finalidade": "geral"}, chave_idempotencia=_chave())
            resultados.append("ok")
        except PedidoAbertoExistente:
            resultados.append("409")

    threads = [threading.Thread(target=tentar) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(resultados) == ["409", "ok"]


def test_cancelamento_da_associacao_flag_step_up_janela_e_sem_hub(ambiente, monkeypatch):
    from app import flags
    from app.integracoes.hub import redefinir_hub

    c, h, cid = novo_cliente()
    corpo = {"motivo": "mudanca", "quer_conversa": True, "comentario": "Vou morar fora.",
             "chave_idempotencia": _chave()}
    r = c.post("/api/v1/ajuda/cancelamento", json=corpo, headers=h)
    assert r.status_code == 404 and r.json()["erro"] == "recurso_desligado"
    monkeypatch.setattr(flags, "_ler_tabela", lambda: {"cancelamento_online": True})
    flags.limpar_cache()
    espiao = _HubEspiao()
    redefinir_hub(espiao)
    r = c.post("/api/v1/ajuda/cancelamento", json=corpo, headers=h)
    assert r.status_code == 201, r.text
    assert espiao.chamadas == []  # nunca escreve (nem lê) no CRM
    d = r.json()
    assert d["tipo"]["codigo"] == "cancelamento_associacao" and d["pode_cancelar"]
    with _db() as db:
        linha = db.execute(text("SELECT TIMESTAMPDIFF(MINUTE, criada_em, crm_proxima_em) AS m, crm_sync "
                                "FROM solicitacao WHERE id = :s"), {"s": d["id"]}).one()
        outbox = db.execute(text("SELECT gatilho, canal, destinatario FROM comunicacao_evento "
                                 "WHERE referencia_id = :s ORDER BY canal"), {"s": d["id"]}).all()
        ligacao = db.execute(text("SELECT motivo, status FROM fila_ligacao WHERE referencia_id = :s"),
                             {"s": d["id"]}).all()
    assert linha.m == 24 * 60 and linha.crm_sync == "pendente"  # janela de arrependimento
    assert sorted(tuple(o) for o in outbox) == [("A16", "email", "associado"), ("A16", "interno", "central"),
                                                ("A16", "rd", "associado")]
    assert [tuple(x) for x in ligacao] == [("cancelamento_conversa", "pendente")]
    # Um aberto por associado.
    r = c.post("/api/v1/ajuda/cancelamento", json={**corpo, "chave_idempotencia": _chave()}, headers=h)
    assert r.status_code == 409 and r.json()["erro"] == "estado_invalido"
    # Com pedido de cancelamento aberto, gatilho de oferta para o RD nasce suprimido.
    from app.dominio import comunicacao

    with _db() as db:
        comunicacao.enfileirar(db, gatilho="A15", contact_id=cid, referencia_tipo="beneficio",
                               referencia_id="BEN042", destinos=[("rd", "associado")])
        st = db.execute(text("SELECT status, supressao_motivo FROM comunicacao_evento WHERE gatilho = 'A15' "
                             "AND contact_id = :c"), {"c": cid}).one()
    assert tuple(st) == ("suprimido", "cancelamento")
    # Desistir dentro da janela: cancela a solicitação, suprime o que não saiu.
    r = c.post(f"/api/v1/solicitacoes/{d['id']}/cancelar", json={}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "cancelada"
    assert espiao.chamadas == []
    with _db() as db:
        st = db.execute(text("SELECT DISTINCT status FROM comunicacao_evento WHERE referencia_id = :s"),
                        {"s": d["id"]}).scalars().all()
    assert st == ["suprimido"]
    # Step-up vencido (senha há ~17 min): 403 antes de criar qualquer coisa.
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 1000)
    r = c.post("/api/v1/ajuda/cancelamento", json={**corpo, "chave_idempotencia": _chave()}, headers=h)
    assert r.status_code == 403 and r.json()["erro"] == "reautenticacao_necessaria"


def test_formulario_e_faq_da_ajuda(ambiente):
    c, h, _ = novo_cliente()
    r = c.post("/api/v1/ajuda/formulario", json={"assunto": "eventos", "mensagem": "Quando abre o congresso?",
                                                 "chave_idempotencia": _chave()}, headers=h)
    assert r.status_code == 201 and r.json()["campos"]["assunto"] == "Eventos"
    faq = c.get("/api/v1/ajuda/faq").json()
    assert set(faq) == {"categorias", "itens", "sugestoes"}  # FAQ sem seed: listas podem estar vazias
    contato = c.get("/api/v1/ajuda/contato").json()
    assert contato["whatsapp"]["url"].startswith("https://wa.me/") and contato["telefone"] is None  # parametro vazio
    assert contato["horario"] is None


def test_marcador_sem_retorno_e_fila_de_ligacao(ambiente):
    from app.dominio.solicitacoes import maquina

    c, h, cid = novo_cliente()
    sid = _outro(c, h).json()["id"]
    with _db() as db:
        assert maquina.marcar_sem_retorno(db, solicitacao_id=sid) is False  # criada: prazo nem começou
    _transitar(sid, "enviada", ator="sistema", origem="job")
    with _db() as db:
        assert maquina.marcar_sem_retorno(db, solicitacao_id=sid) is False  # dentro do prazo
        db.execute(text("UPDATE solicitacao SET enviada_em = enviada_em - INTERVAL 11 DAY WHERE id = :s"), {"s": sid})
    with _db() as db:
        assert maquina.marcar_sem_retorno(db, solicitacao_id=sid) is True
        assert maquina.marcar_sem_retorno(db, solicitacao_id=sid) is False  # idempotente
        assert maquina.marcar_sem_retorno(db, solicitacao_id=sid, segundo=True) is False  # 2× ainda não venceu
    d = c.get(f"/api/v1/solicitacoes/{sid}").json()
    assert d["aguardando_parceiro"] is True
    assert d["linha_do_tempo"][-1]["rotulo"] == "Aguardando o parceiro, a APM já está cobrando"
    with _db() as db:
        db.execute(text("UPDATE solicitacao SET enviada_em = enviada_em - INTERVAL 10 DAY WHERE id = :s"), {"s": sid})
    with _db() as db:
        assert maquina.marcar_sem_retorno(db, solicitacao_id=sid, segundo=True) is True
        a05 = db.execute(text("SELECT COUNT(*) FROM comunicacao_evento WHERE gatilho='A05' AND referencia_id=:s"),
                         {"s": sid}).scalar_one()
        lig = db.execute(text("SELECT motivo FROM fila_ligacao WHERE referencia_id = :s"), {"s": sid}).scalars().all()
    assert a05 == 3 and lig == ["sem_retorno_2"]
    _transitar(sid, "em_atendimento", ator="apm", origem="crm")  # qualquer transição limpa o marcador
    assert c.get(f"/api/v1/solicitacoes/{sid}").json()["aguardando_parceiro"] is False


# ====================================================== privilégios e CHECKs
def _recusado(sql, params=None, *, codigo=None):
    with pytest.raises(DBAPIError) as e:
        with _db() as db:
            db.execute(text(sql), params or {})
    if codigo is not None:
        assert e.value.orig.args[0] == codigo, e.value.orig.args
    return e.value


def test_grants_do_apm_area_e_trilhas_append_only(ambiente):
    c, h, cid = novo_cliente()
    sid = _outro(c, h).json()["id"]
    # 1142 = comando negado na tabela; 1143 = negado na coluna.
    _recusado("UPDATE solicitacao_evento SET mensagem_publica = 'x' WHERE solicitacao_id = :s", {"s": sid},
              codigo=1142)
    _recusado("DELETE FROM solicitacao WHERE id = :s", {"s": sid}, codigo=1142)
    _recusado("DELETE FROM solicitacao_evento WHERE solicitacao_id = :s", {"s": sid}, codigo=1142)
    _recusado("UPDATE solicitacao SET dados = JSON_OBJECT() WHERE id = :s", {"s": sid}, codigo=1143)
    _recusado("UPDATE solicitacao SET contact_id = contact_id WHERE id = :s", {"s": sid}, codigo=1143)
    _recusado("UPDATE notificacao SET titulo = 'x' WHERE contact_id = :c", {"c": cid}, codigo=1143)
    _recusado("UPDATE parametro SET valor = '1' WHERE chave = 'avaliacao_prazo_dias'", codigo=1142)
    _recusado("UPDATE faq SET publicada = 1", codigo=1142)
    _recusado("UPDATE fila_ligacao SET status = 'concluida'", codigo=1142)
    _recusado("UPDATE comunicacao_envio SET situacao = 'aberto'", codigo=1142)
    _recusado("UPDATE comunicacao_evento SET gatilho = 'A01' WHERE referencia_id = :s", {"s": sid}, codigo=1143)
    with _db() as db:  # o que É concedido funciona
        assert db.execute(text("UPDATE notificacao SET lida_em = UTC_TIMESTAMP(6) WHERE contact_id = :c "
                               "AND lida_em IS NULL"), {"c": cid}).rowcount == 1
        assert db.execute(text("UPDATE comunicacao_evento SET tentativas = tentativas + 1, "
                               "atualizado_em = UTC_TIMESTAMP(6) WHERE referencia_id = :s"), {"s": sid}).rowcount == 2


def test_checks_do_banco_recusam_cpf_marcador_e_backoffice_sem_justificativa(ambiente):
    """3819 = ER_CHECK_CONSTRAINT_VIOLATED (o PyMySQL entrega como OperationalError)."""
    c, h, cid = novo_cliente()
    sid = _outro(c, h).json()["id"]
    _recusado("INSERT INTO solicitacao_evento (solicitacao_id, evento, de_status, para_status, ator, origem) "
              "VALUES (:s, 'transicao', 'criada', 'cancelada', 'apm', 'backoffice')", {"s": sid}, codigo=3819)
    _recusado("UPDATE solicitacao SET sem_retorno_desde = UTC_TIMESTAMP(6) WHERE id = :s", {"s": sid}, codigo=3819)
    _recusado("INSERT INTO solicitacao_evento (solicitacao_id, evento, de_status, para_status, ator, origem) "
              "VALUES (:s, 'transicao', 'em_atendimento', 'pendente_associado', 'apm', 'crm')", {"s": sid},
              codigo=3819)  # pendente sem mensagem pública
    _recusado("INSERT INTO solicitacao (id, contact_id, sub_hash, tipo_servico, prazo_retorno_dias, dados, "
              "crm_proxima_em) VALUES (:id, :c, REPEAT('a', 64), 'outro', 10, :d, UTC_TIMESTAMP(6))",
              {"id": str(uuid.uuid4()), "c": cid, "d": '{"mensagem": "cpf 123.456.789-09"}'}, codigo=3819)
    _recusado("UPDATE solicitacao SET avaliacao_nota = 11, avaliada_em = UTC_TIMESTAMP(6) WHERE id = :s",
              {"s": sid}, codigo=3819)
    _recusado("INSERT INTO notificacao (contact_id, tipo, chave, titulo, link) VALUES "
              "(:c, 'novidade', 'x1', 'Oi', 'https://evil.example/area')", {"c": cid}, codigo=3819)
    _recusado("INSERT INTO solicitacao_evento (solicitacao_id, evento, para_status, ator, origem, mensagem_publica) "
              "VALUES (:s, 'sem_retorno', 'criada', 'sistema', 'job', 'meu cpf 12345678909')", {"s": sid},
              codigo=3819)
