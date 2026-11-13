"""Espelho das solicitações no CRM por incident/opportunity (ADR-0023) — sem rede e sem banco.

Catálogo, texto para o CRM (unidades UTF-16, pior caso por tipo, defesa de corte, CPF),
cliente real do hub (`solicitacao.criar`/`listar`, Retry-After, erros novos), simulado,
mapeamento statecode/statuscode, e os dois jobs com o banco substituído.
"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import httpx
import pytest

from app.dominio.solicitacoes import catalogo_crm, crm, rotulos, schemas
from app.integracoes.hub import CriacaoCrm, HubError, PedidoCrm, RegistroCrm

SID = "0b9c3c6e-5d0f-4a5e-8b1a-2f3c4d5e6f70"
CID = "11111111-2222-3333-4444-555555555555"
RE_GUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
EMOJI = "\U0001F600"  # 2 unidades UTF-16


# ================================================================= catálogo
def test_catalogo_cobre_todos_os_tipos_e_so_aponta_para_a_central():
    import re

    # Todo tipo da área tem destino decidido (ou None explícito); nada fora do catálogo comum.
    for tipo in schemas.SCHEMAS:
        destino = catalogo_crm.destino(tipo)
        if destino is None:
            assert tipo == "exclusao_dados"
            continue
        assert destino.tipo in catalogo_crm.TIPOS_CRM, tipo
        assert re.match(RE_GUID, destino.time_id)
        if destino.entidade == "ocorrencia":
            assert re.match(RE_GUID, destino.assunto_id) and destino.produto_id is None, tipo
        else:
            assert destino.assunto_id is None and re.match(RE_GUID, destino.produto_id), tipo
    # Tipos antigos da área: traduzidos para o slug do App, todos ocorrência da Central.
    for tipo in ("outro", "declaracao_associado", "cancelamento_associacao", "cartao_apm", "mentoria_pedir"):
        destino = catalogo_crm.destino(tipo)
        assert (destino.tipo, destino.entidade, destino.time_id) == ("outros", "ocorrencia",
                                                                     catalogo_crm.TIME_CENTRAL), tipo
        assert destino.assunto_id == catalogo_crm.ASSUNTO_ATENDIMENTO_APM and catalogo_crm.traduzido(tipo)
    cadastro = catalogo_crm.destino("alteracao_cadastro")
    assert (cadastro.tipo, cadastro.assunto_id) == ("alteracao_cadastral", catalogo_crm.ASSUNTO_ATUALIZACAO_CADASTRAL)
    # Sem destino: LGPD (DEC-06), benefício (Fase 4), tipo desconhecido (fail-closed).
    assert catalogo_crm.destino("exclusao_dados") is None
    assert catalogo_crm.destino(None, "beneficio-x") is None and catalogo_crm.destino("outro", "b1") is None
    assert catalogo_crm.destino("tipo_que_nao_existe") is None


# ==================================================================== texto
def test_unidades_utf16_e_limite_na_origem():
    assert crm.unidades_utf16("aé") == 2 and crm.unidades_utf16(EMOJI) == 2
    assert schemas.unidades_utf16(EMOJI * 3) == 6
    ok = schemas.validar("outro", {"assunto": "A" * 120, "mensagem": EMOJI * 850})
    assert schemas.unidades_utf16(ok["mensagem"]) == 1700
    for campo, valor in (("mensagem", EMOJI * 851), ("mensagem", "a" * 1701), ("assunto", EMOJI * 61)):
        dados = {"assunto": "A", "mensagem": "B", campo: valor}
        with pytest.raises(schemas.EntradaInvalida) as e:
            schemas.validar("outro", dados)
        assert e.value.detalhes[0]["campo"] == f"campos.{campo}"


def test_titulo_e_descricao_legiveis_sem_dado_de_contato():
    dados = schemas.validar("outro", {"assunto": "Dúvida sobre o seguro", "mensagem": "Linha 1\n\nLinha 2",
                                      "categoria": "beneficio"})
    texto = crm.texto_para_crm("outro", dados)
    assert texto.titulo == "Minha APM: Dúvida sobre o seguro" and not texto.cortado
    assert texto.descricao == ("Pedido aberto pelo associado na Minha APM.\nTipo: Outro assunto\n\n"
                               "Assunto: Dúvida sobre o seguro\nMensagem:\nLinha 1\n\nLinha 2\n"
                               "Categoria: Dúvida sobre benefício")
    cad = schemas.validar("alteracao_cadastro", {"alteracoes": {"data_nascimento": "1980-05-02", "sexo": "feminino"},
                                                 "justificativa": "Erro no cadastro"})
    t = crm.texto_para_crm("alteracao_cadastro", cad)
    assert t.titulo == "Minha APM: Alteração de cadastro"
    assert "Alterações pedidas:\n- Data de nascimento: 02/05/1980\n- Sexo: Feminino" in t.descricao
    canc = schemas.validar("cancelamento_associacao", {"motivo": "preco", "quer_conversa": True})
    assert "Motivo: Preço\nQuer conversar com a APM antes: Sim" in crm.texto_para_crm(
        "cancelamento_associacao", canc).descricao
    # Tipo sem formulário ainda vira texto válido (≥ 10 unidades).
    assert crm.texto_para_crm("cartao_apm", {}).descricao.endswith("Tipo: Cartão APM")
    for tipo in schemas.SCHEMAS:
        assert all(campo.nome in crm.ROTULO_CAMPO for campo in schemas.SCHEMAS[tipo]), tipo


def _maior_aceito(validar, caractere: str) -> str | None:
    """Maior texto de `caractere` que o validador aceita (busca binária até 5000)."""
    baixo, alto, melhor = 1, 5000, None
    while baixo <= alto:
        meio = (baixo + alto) // 2
        try:
            melhor = validar(caractere * meio)
            baixo = meio + 1
        except ValueError:
            alto = meio - 1
    return melhor


def _pior_caso(tipo: str) -> dict:
    dados: dict = {}
    for campo in schemas.SCHEMAS[tipo]:
        if campo.nome in crm.OPCOES_CAMPO:
            opcoes = crm.OPCOES_CAMPO[campo.nome]
            dados[campo.nome] = max(opcoes, key=lambda k: crm.unidades_utf16(opcoes[k]))
        elif campo.nome == "quer_conversa":
            dados[campo.nome] = False
        elif campo.nome == "alteracoes":
            dados[campo.nome] = {"nome": "A" * 80, "sobrenome": "B" * 80, "data_nascimento": "1980-01-01",
                                 "sexo": "prefiro_nao_informar"}
        else:
            candidatos = [v for v in (_maior_aceito(campo.validar, EMOJI), _maior_aceito(campo.validar, "a"))
                          if v is not None]
            dados[campo.nome] = max(candidatos, key=crm.unidades_utf16)
    return schemas.validar(tipo, dados) if dados else {}


@pytest.mark.parametrize("tipo", sorted(schemas.SCHEMAS))
def test_pior_caso_de_cada_tipo_cabe_no_crm_sem_corte(tipo):
    texto = crm.texto_para_crm(tipo, _pior_caso(tipo))
    assert not texto.cortado
    assert crm.unidades_utf16(texto.descricao) <= crm.DESCRICAO_MAX
    assert crm.unidades_utf16(texto.titulo) <= crm.TITULO_MAX


def test_defesa_corta_marcado_sem_partir_emoji_e_recusa_cpf():
    dados = {"assunto": "Assunto", "mensagem": "x" + EMOJI * 1500}  # acima do limite: só por bug a montante
    texto = crm.texto_para_crm("outro", dados)
    assert texto.cortado and texto.descricao.endswith(crm.MARCA_CORTE.strip())
    assert crm.unidades_utf16(texto.descricao) <= 2000
    texto.descricao.encode("utf-16-le")  # nenhum substituto solto
    with pytest.raises(crm.ConteudoRecusado) as e:
        crm.texto_para_crm("outro", {"assunto": "x", "mensagem": "cpf 123.456.789-09"})
    assert e.value.motivo == "cpf"
    longo = crm.titulo("outro", {"assunto": EMOJI * 150})
    assert crm.unidades_utf16(longo) <= 200


# ======================================================= cliente real do hub
def _cliente(monkeypatch, rotas):
    monkeypatch.setenv("HUB_MODE", "real")
    monkeypatch.setenv("HUB_CLIENT_SECRET", "s" * 32)
    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    from app.config import get_settings
    from app.integracoes.hub import ClienteHubReal

    get_settings.cache_clear()
    pedidos: list[httpx.Request] = []

    def tratar(req):
        pedidos.append(req)
        if req.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 600})
        return rotas(req, json.loads(req.content)["argumentos"])

    return ClienteHubReal(transporte=httpx.MockTransport(tratar)), pedidos


def _pedido(**kw) -> PedidoCrm:
    base = dict(contact_id=CID, registro_id=SID, entidade="ocorrencia", tipo="outro", titulo="Minha APM: X",
                descricao="Pedido aberto pelo associado na Minha APM.", assunto_id=catalogo_crm.ASSUNTO_ATENDIMENTO_APM,
                time_id=catalogo_crm.TIME_CENTRAL)
    base.update(kw)
    return PedidoCrm(**base)


def test_pedido_valida_o_contrato_antes_de_sair():
    assert set(_pedido().argumentos()) == {"contact_id", "registro_id", "entidade", "tipo", "titulo", "descricao",
                                           "assunto_id", "time_id"}
    for ruim in (dict(registro_id=CID), dict(entidade="task"), dict(tipo="Outro!"), dict(assunto_id=None),
                 dict(entidade="oportunidade"), dict(contact_id="x"), dict(time_id="x")):
        with pytest.raises(ValueError):
            _pedido(**ruim).argumentos()
    _pedido(entidade="oportunidade", assunto_id=None).argumentos()


def test_criar_envia_o_contrato_e_valida_a_resposta(monkeypatch):
    resposta = {"registro_id": SID.upper(), "entidade": "ocorrencia", "criada": True,
                "protocolo": "CAS-285497-M7P9T5", "statecode": 0, "statuscode": 1, "contact_id": CID}
    estado = {"linha": resposta}

    def rotas(req, args):
        assert req.url.path.endswith("/solicitacao.criar")
        return httpx.Response(200, json={"colunas": [], "linhas": [estado["linha"]]})

    hub, pedidos = _cliente(monkeypatch, rotas)
    c = hub.solicitacao_criar(_pedido())
    assert c == CriacaoCrm(SID, "ocorrencia", True, "CAS-285497-M7P9T5", 0, 1)
    assert json.loads(pedidos[-1].content)["argumentos"]["registro_id"] == SID
    assert "ferramentas%3Aescrever" in pedidos[0].content.decode()
    # Resposta fora do contrato = resultado incerto (repetir é seguro): outro id, sem protocolo, sem códigos.
    for ruim in ({"registro_id": CID}, {"protocolo": None}, {"statecode": "x"}, {"criada": "sim"}):
        estado["linha"] = {**resposta, **ruim}
        with pytest.raises(HubError) as e:
            hub.solicitacao_criar(_pedido())
        assert e.value.codigo == "escrita_indeterminada"


def test_listar_descarta_texto_e_linha_invalida(monkeypatch):
    linhas = [
        {"registro_id": SID, "entidade": "ocorrencia", "protocolo": "CAS-285497-M7P9T5", "statecode": 0,
         "statuscode": 3, "canal": 100000001, "titulo": "texto do associado", "descricao": "não guardar",
         "criado_em": "2026-11-04T10:00:00-03:00", "atualizado_em": "2026-11-04T11:00:00-03:00", "contact_id": CID},
        {"registro_id": "nao-guid", "entidade": "ocorrencia", "statecode": 0, "statuscode": 1},
        {"registro_id": CID, "entidade": "ocorrencia", "protocolo": None, "statecode": 0, "statuscode": 1,
         "canal": None, "titulo": None, "descricao": None},
    ]
    vistos = []

    def rotas(req, args):
        vistos.append(args)
        return httpx.Response(200, json={"colunas": [], "linhas": linhas})

    hub, _ = _cliente(monkeypatch, rotas)
    regs = hub.solicitacao_listar(CID, 500)
    assert vistos == [{"contact_id": CID, "limite": 50}]  # teto do hub
    assert [r.registro_id for r in regs] == [SID, CID]
    assert regs[0] == RegistroCrm(SID, "ocorrencia", "CAS-285497-M7P9T5", 0, 3, 100000001,
                                  "2026-11-04T10:00:00-03:00", "2026-11-04T11:00:00-03:00",
                                  descricao="não guardar")
    # O título do CRM é descartado; a descrição fica só em trânsito e fora do repr (ADR-0024).
    assert regs[1].canal is None and not hasattr(regs[0], "titulo")
    assert "não guardar" not in repr(regs[0])
    with pytest.raises(ValueError):
        hub.solicitacao_listar("x", 10)


def test_429_pausa_o_processo_pelo_retry_after(monkeypatch):
    estado = {"retry": "7"}

    def rotas(req, args):
        return httpx.Response(429, json={"erro": "fonte_limitada"}, headers={"Retry-After": estado["retry"]})

    hub, pedidos = _cliente(monkeypatch, rotas)
    with pytest.raises(HubError) as e:
        hub.solicitacao_listar(CID, 10)
    assert (e.value.codigo, e.value.status, e.value.retry_after) == ("limite_taxa", 429, 7)
    antes = len(pedidos)
    with pytest.raises(HubError) as e:  # dentro do prazo: nem sai para a rede
        hub.solicitacao_listar(CID, 10)
    assert e.value.codigo == "limite_taxa" and 1 <= e.value.retry_after <= 7 and len(pedidos) == antes
    from app.integracoes.hub import _retry_after

    assert (_retry_after("abc"), _retry_after(None), _retry_after("0"), _retry_after("900")) == (60, 60, 1, 60)


@pytest.mark.parametrize("status,corpo,codigo", [
    (404, {"erro": "nao_encontrado", "detalhes": [{"campo": "time_id"}]}, "catalogo_crm_invalido"),
    (404, {"erro": "nao_encontrado", "mensagem": "Time não encontrado no CRM."}, "catalogo_crm_invalido"),
    (404, {"erro": "nao_encontrado", "mensagem": "Contato não encontrado no CRM."}, "nao_encontrado"),
    (409, {"erro": "conflito"}, "conflito"),
    (403, {"erro": "canal_nao_configurado"}, "canal_nao_configurado"),
    (504, {"erro": "escrita_indeterminada"}, "escrita_indeterminada"),
    (400, {"erro": "entrada_invalida"}, "entrada_invalida"),
])
def test_erros_do_criar(monkeypatch, status, corpo, codigo):
    hub, _ = _cliente(monkeypatch, lambda req, args: httpx.Response(status, json=corpo))
    with pytest.raises(HubError) as e:
        hub.solicitacao_criar(_pedido())
    assert e.value.codigo == codigo


def test_criar_com_escrita_desligada_nao_sai(monkeypatch):
    hub, pedidos = _cliente(monkeypatch, lambda req, args: pytest.fail("saiu"))
    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(HubError) as e:
        hub.solicitacao_criar(_pedido())
    assert e.value.codigo == "edicao_desligada" and pedidos == []


# ================================================================ simulado
def test_stub_idempotente_conflito_listar_e_estado(monkeypatch):
    from app.config import get_settings
    from app.integracoes.hub_stub import ClienteHubStub

    stub = ClienteHubStub()
    with pytest.raises(HubError):
        stub.solicitacao_criar(_pedido())  # escrita desligada
    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    get_settings.cache_clear()
    c1 = stub.solicitacao_criar(_pedido())
    c2 = stub.solicitacao_criar(_pedido())
    assert c1.criada and not c2.criada and c1.protocolo == c2.protocolo and (c1.statecode, c1.statuscode) == (0, 1)
    import re

    assert re.match(r"^CAS-\d{6}-[A-Z0-9]{6}$", c1.protocolo)
    with pytest.raises(HubError) as e:
        stub.solicitacao_criar(_pedido(contact_id="99999999-2222-3333-4444-555555555555"))
    assert e.value.codigo == "conflito"
    stub.registros_central(CID, 3)
    regs = stub.solicitacao_listar(CID, 2)
    assert len(regs) == 2 and all(r.canal is None for r in regs)  # Central, mais recentes primeiro
    stub.definir_estado(SID, 1, 5)
    alvo = [r for r in stub.solicitacao_listar(CID, 50) if r.registro_id == SID][0]
    assert (alvo.statecode, alvo.statuscode, alvo.canal) == (1, 5, 100000001)
    assert stub.listar_chamadas == [(CID, 2), (CID, 50)]


# ============================================================== mapeamento
def test_mapeamento_do_crm_e_caminho_pela_maquina():
    from app.jobs.solicitacoes import _caminho, mapear_crm, mensagem_pendente_crm

    assert mapear_crm("ocorrencia", 0, 1) == (None, True)  # status de criação: nada muda
    assert mapear_crm("ocorrencia", 0, 2) == ("em_atendimento", True)
    assert mapear_crm("ocorrencia", 0, 3) == ("pendente_associado", True)
    assert mapear_crm("ocorrencia", 1, 5) == ("concluida_positiva", True)
    assert mapear_crm("ocorrencia", 2, 6) == ("concluida_negativa", True)
    assert mapear_crm("ocorrencia", 2, 2000) == (None, False)  # mesclada: segue em outra
    assert mapear_crm("ocorrencia", 1, 100000007) == ("concluida_positiva", False)  # final customizado
    assert mapear_crm("ocorrencia", 0, 100000007) == (None, False)  # ativo desconhecido: não muda
    assert mapear_crm("oportunidade", 1, 3)[0] == "concluida_positiva"
    assert mapear_crm("oportunidade", 2, 4)[0] == "concluida_negativa"
    assert _caminho("enviada", "pendente_associado") == ["em_atendimento", "pendente_associado"]
    # P-66: a Central conclui um pedido que aguardava o associado.
    assert _caminho("pendente_associado", "concluida_positiva") == ["em_atendimento", "concluida_positiva"]
    assert _caminho("pendente_associado", "em_atendimento") == ["em_atendimento"]
    assert _caminho("cancelada", "concluida_negativa") == []
    assert mensagem_pendente_crm("CAS-1-ABC").endswith("Protocolo: CAS-1-ABC.")
    assert mensagem_pendente_crm(None) == rotulos.MENSAGEM_PENDENTE_CRM


# =================================================================== espelho
def _ctx(aplicar=True, **kw):
    from app.jobs.base import Contexto

    return Contexto(job="teste_job", aplicar=aplicar, agora=datetime(2026, 11, 4, 12, 0), **kw)


def _linha(**kw):
    base = dict(id=SID, contact_id=CID, tipo_servico="outro", beneficio_id=None, status="criada", crm_id=None,
                crm_protocolo=None, crm_tentativas=0, dados='{"assunto":"Dúvida","mensagem":"Quero saber."}',
                atualizada_em=datetime(2026, 11, 4, 11, 0))
    base.update(kw)
    return SimpleNamespace(**base)


class _Hub:
    def __init__(self, erro=None):
        self.erro, self.pedidos = erro, []

    def solicitacao_criar(self, pedido):
        self.pedidos.append(pedido)
        if self.erro:
            raise self.erro
        return CriacaoCrm(pedido.registro_id, pedido.entidade, True, "CAS-285497-M7P9T5", 0, 1)


def _espelho(monkeypatch, linhas, hub):
    from app.config import get_settings
    from app.jobs import solicitacoes

    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    get_settings.cache_clear()
    registro = {"falhas": [], "retidos": [], "confirmados": []}
    monkeypatch.setattr(solicitacoes, "pendentes_do_espelho", lambda *a, **k: linhas)
    monkeypatch.setattr(solicitacoes, "_registrar_falha",
                        lambda r, classe, codigo, agora: registro["falhas"].append((r.id, classe, codigo)))
    monkeypatch.setattr(solicitacoes, "_reter", lambda r, motivo, agora: registro["retidos"].append(
        (r.id, motivo)) or True)
    monkeypatch.setattr(solicitacoes, "_confirmar", lambda r, c, agora: registro["confirmados"].append(
        (r.id, c)) or [])
    ctx = _ctx()
    solicitacoes.espelhar_solicitacoes(ctx, hub=hub)
    return ctx, registro


def test_espelho_cria_ocorrencia_com_o_catalogo(monkeypatch):
    hub = _Hub()
    ctx, reg = _espelho(monkeypatch, [_linha(), _linha(id="22222222-2222-4222-8222-222222222222", tipo_servico="alteracao_cadastro",
                                                       dados='{"alteracoes":{"sexo":"feminino"}}')], hub)
    assert [p.entidade for p in hub.pedidos] == ["ocorrencia", "ocorrencia"]
    assert hub.pedidos[0].assunto_id == catalogo_crm.ASSUNTO_ATENDIMENTO_APM
    assert hub.pedidos[1].assunto_id == catalogo_crm.ASSUNTO_ATUALIZACAO_CADASTRAL
    assert hub.pedidos[0].registro_id == SID and hub.pedidos[0].titulo == "Minha APM: Dúvida"
    assert len(reg["confirmados"]) == 2 and ctx.gravados == 2 and reg["falhas"] == []


def test_espelho_retem_o_que_o_crm_nao_recebe(monkeypatch):
    hub = _Hub()
    linhas = [_linha(crm_id=SID, status="cancelada"),                       # mudança depois do envio
              _linha(id=CID, tipo_servico="exclusao_dados", dados="{}"),     # sem destino (LGPD)
              _linha(id="22222222-2222-4222-8222-222222222222", tipo_servico=None, beneficio_id="b-1")]
    ctx, reg = _espelho(monkeypatch, linhas, hub)
    assert hub.pedidos == [] and reg["falhas"] == []
    assert [m for _, m in reg["retidos"]] == ["sem_ferramenta_status", "sem_destino_no_catalogo",
                                              "sem_destino_no_catalogo"]
    assert ctx.gravados == 3


@pytest.mark.parametrize("erro,classe,sistemico", [
    (HubError("fonte_indisponivel"), "transitorio", None),
    (HubError("escrita_indeterminada", 504), "transitorio", None),
    (HubError("conflito", 409), "permanente", None),
    (HubError("nao_encontrado", 404), "permanente", None),
    (HubError("limite_taxa", 429, retry_after=30), None, "disjuntor: limite_taxa"),
    (HubError("catalogo_crm_invalido"), None, "disjuntor: catalogo_crm_invalido"),
    (HubError("canal_nao_configurado"), None, "disjuntor: canal_nao_configurado"),
])
def test_espelho_classifica_os_erros_do_hub(monkeypatch, erro, classe, sistemico):
    hub = _Hub(erro)
    ctx, reg = _espelho(monkeypatch, [_linha()], hub)
    assert ctx.erro_sistemico == sistemico
    assert [f[1] for f in reg["falhas"]] == ([classe] if classe else [])  # sistêmico não gasta tentativa
    assert reg["confirmados"] == []


def test_espelho_texto_recusado_vira_falha_permanente(monkeypatch):
    from app.jobs import solicitacoes

    def recusa(*a, **k):
        raise crm.ConteudoRecusado("cpf")

    monkeypatch.setattr(solicitacoes.crm, "texto_para_crm", recusa)
    hub = _Hub()
    ctx, reg = _espelho(monkeypatch, [_linha()], hub)
    assert hub.pedidos == [] and reg["falhas"] == [(SID, "permanente", "conteudo_cpf")]


def test_espelho_dry_run_nao_toca_hub_nem_estado(monkeypatch):
    from app.jobs import solicitacoes

    monkeypatch.setattr(solicitacoes, "pendentes_do_espelho", lambda *a, **k: [_linha(), _linha(crm_id=SID)])
    for nome in ("_confirmar", "_registrar_falha", "_nada_a_espelhar", "_reter"):
        monkeypatch.setattr(solicitacoes, nome, lambda *a, **k: pytest.fail("mudou estado em dry-run"))
    ctx = _ctx(aplicar=False)
    solicitacoes.espelhar_solicitacoes(ctx, hub=SimpleNamespace())
    assert ctx.lidos == 2 and ctx.gravados == 0


# ============================================================ sincronização
def _reg(rid, estado=0, status=1):
    return RegistroCrm(rid, "ocorrencia", "CAS-285497-M7P9T5", estado, status, 100000001, None, None)


def _sync(monkeypatch, contatos, abertos, hub, lidas_hoje=0, **env):
    from app.config import get_settings
    from app.jobs import solicitacoes

    for chave, valor in env.items():
        monkeypatch.setenv(chave, str(valor))
    get_settings.cache_clear()
    aplicados, marcados = [], []
    monkeypatch.setattr(solicitacoes, "contatos_a_consultar", lambda agora, cad, lote: contatos)
    monkeypatch.setattr(solicitacoes, "_abertos_do_contato", lambda cid: abertos.get(cid, []))
    monkeypatch.setattr(solicitacoes, "linhas_lidas_hoje", lambda agora: lidas_hoje)
    monkeypatch.setattr(solicitacoes, "aplicar_registro", lambda sid, reg, agora: aplicados.append(
        (sid, reg.statecode, reg.statuscode)) or (False, []))
    monkeypatch.setattr(solicitacoes, "_marcar_consultado", lambda ids, agora: marcados.extend(ids))
    monkeypatch.setattr(solicitacoes, "PAUSA_SYNC_S", 0)
    monkeypatch.setattr(solicitacoes.audit, "registrar_sistema", lambda **kw: None)
    ctx = _ctx()
    solicitacoes.sincronizar_solicitacoes(ctx, hub=hub)
    return ctx, aplicados, marcados


class _HubLista:
    def __init__(self, paginas):
        self.paginas, self.chamadas = paginas, []

    def solicitacao_listar(self, cid, limite):
        self.chamadas.append((cid, limite))
        resposta = self.paginas.get((cid, limite), [])
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def test_sync_casa_por_registro_e_amplia_quando_nao_acha(monkeypatch):
    outro = "33333333-3333-4333-8333-333333333333"
    central = [_reg(f"44444444-4444-4444-8444-44444444444{i}") for i in range(10)]
    hub = _HubLista({(CID, 10): central, (CID, 50): [*central, _reg(SID, 0, 3)],
                     (outro, 10): [_reg(outro, 1, 5)]})
    abertos = {CID: [SimpleNamespace(id=SID, status="enviada")], outro: [SimpleNamespace(id=outro, status="enviada")]}
    ctx, aplicados, marcados = _sync(monkeypatch, [CID, outro], abertos, hub)
    assert hub.chamadas == [(CID, 10), (CID, 50), (outro, 10)]
    assert aplicados == [(SID, 0, 3), (outro, 1, 5)] and marcados == []
    assert ctx.lidos == 10 + 11 + 1 and ctx.erro_sistemico is None


def test_sync_registro_sumido_vira_divergencia_e_conta_consulta(monkeypatch):
    hub = _HubLista({(CID, 10): [_reg("44444444-4444-4444-8444-444444444440")]})
    ctx, aplicados, marcados = _sync(monkeypatch, [CID], {CID: [SimpleNamespace(id=SID, status="enviada")]}, hub)
    assert hub.chamadas == [(CID, 10)]  # página incompleta: não amplia
    assert aplicados == [] and marcados == [SID]


def test_sync_respeita_o_teto_diario_de_linhas(monkeypatch):
    hub = _HubLista({})
    ctx, aplicados, _ = _sync(monkeypatch, [CID], {CID: [SimpleNamespace(id=SID, status="enviada")]}, hub,
                              lidas_hoje=4995, JOBS_SYNC_LINHAS_DIA=5000)
    assert hub.chamadas == [] and "teto diário" in ctx.erro_sistemico


def test_sync_hub_fora_para_a_rodada(monkeypatch):
    hub = _HubLista({(CID, 10): HubError("limite_taxa", 429, retry_after=60)})
    ctx, aplicados, _ = _sync(monkeypatch, [CID, "33333333-3333-4333-8333-333333333333"],
                              {CID: [SimpleNamespace(id=SID, status="enviada")]}, hub)
    assert ctx.erro_sistemico == "hub: limite_taxa" and len(hub.chamadas) == 1 and aplicados == []


def test_sync_dry_run_so_conta(monkeypatch):
    from app.jobs import solicitacoes

    monkeypatch.setattr(solicitacoes, "contatos_a_consultar", lambda *a: [CID])
    ctx = _ctx(aplicar=False)
    solicitacoes.sincronizar_solicitacoes(ctx, hub=SimpleNamespace())
    assert ctx.lidos == 0 and ctx.erro_sistemico is None
