"""Paridade com o App APM (ADR-0024; contrato do hub de 2026-11-13) — unidades sem rede e sem banco.

Cliente do hub (produto na oportunidade, produtos, conversa, erros novos), catálogo comum
(slugs e GUIDs do §2 do contrato), situação e rótulos iguais aos do App, catálogo visível
com cache, texto enviado ao CRM, política dos jobs e o simulado.
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest

from app.dominio.solicitacoes import catalogo, catalogo_crm, crm, rotulos, schemas, situacao_crm
from app.integracoes.hub import (
    CANAL_APP,
    EnvioInteracao,
    HubError,
    InteracaoCrm,
    PedidoCrm,
    PedidoInteracao,
    redefinir_hub,
)
from app.integracoes.hub_stub import ClienteHubStub
from app.jobs import politica

from .test_solicitacoes_crm import CID, SID, _cliente

IID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
PRODUTO_AUTO = "c0fce926-6e88-e911-a968-000d3ac1b6c7"

# §2 do contrato do hub (2026-11-13), copiado à mão: slug → (entidade, grupo, assunto, time, produto).
CONTRATO = {
    "alteracao_cadastral": ("ocorrencia", None, "e2d19f07-29e1-e811-a974-000d3ac1b8d2", "312dcfcf-0714-e911-a952-000d3ac1be86", None),
    "duvida": ("ocorrencia", None, "64fb455c-c4e1-e811-a974-000d3ac1b8d2", "312dcfcf-0714-e911-a952-000d3ac1be86", None),
    "segunda_via_boleto": ("ocorrencia", None, "710f6a32-29e1-e811-a974-000d3ac1b8d2", "312dcfcf-0714-e911-a952-000d3ac1be86", None),
    "outros": ("ocorrencia", None, "64fb455c-c4e1-e811-a974-000d3ac1b8d2", "312dcfcf-0714-e911-a952-000d3ac1be86", None),
    "defesa_profissional": ("ocorrencia", None, "774db512-2bfb-ed11-8f6e-000d3ac16b52", "810c580c-c8cc-ed11-a7c6-000d3ac16b52", None),
    "planos_de_saude": ("oportunidade", None, None, "7bb27bfb-0714-e911-a952-000d3ac1be86", "217ad212-6d88-e911-a968-000d3ac1b6c7"),
    "seguro_vida": ("oportunidade", "seguros", None, "7bb27bfb-0714-e911-a952-000d3ac1be86", "51fff108-6e88-e911-a968-000d3ac1b6c7"),
    "seguro_vida_dit": ("oportunidade", "seguros", None, "7bb27bfb-0714-e911-a952-000d3ac1be86", "6e87d9fe-87e9-eb11-bacb-0022483785cc"),
    "seguro_carro": ("oportunidade", "seguros", None, "7bb27bfb-0714-e911-a952-000d3ac1be86", PRODUTO_AUTO),
    "seguro_residencial": ("oportunidade", "seguros", None, "7bb27bfb-0714-e911-a952-000d3ac1be86", "d26d429c-5ef5-eb11-94ef-002248370ae9"),
    "seguro_viagem": ("oportunidade", "seguros", None, "7bb27bfb-0714-e911-a952-000d3ac1be86", "b8cfc64a-6e88-e911-a968-000d3ac1b6c7"),
    "seguro_pet": ("oportunidade", "seguros", None, "7bb27bfb-0714-e911-a952-000d3ac1be86", "f200d262-6e88-e911-a968-000d3ac1b6c7"),
    "seguro_responsabilidade_civil": ("oportunidade", "seguros", None, "7bb27bfb-0714-e911-a952-000d3ac1be86", "3edf4a52-6a14-ef11-9f89-6045bd3ae7ae"),
    "assessoria_aposentadoria": ("oportunidade", None, None, "9b92ec59-c106-ed11-82e5-000d3ac16b52", "11bcef28-8625-e911-a963-000d3ac1b38b"),
    "contabilidade": ("oportunidade", None, None, "66665b46-d8e5-e811-a979-000d3ac1b2cd", "cb0f0d4d-8625-e911-a963-000d3ac1b38b"),
    "despachante": ("oportunidade", None, None, "4d111e0f-7e1e-ed11-b83d-000d3ac16b52", "f6fdd73e-8525-e911-a963-000d3ac1b38b"),
    "apm_facilities": ("oportunidade", None, None, "3afbea3a-7d1e-ed11-b83d-000d3ac16b52", "27ad3e28-53f5-eb11-94ef-002248370ae9"),
    "seguros": ("oportunidade", None, None, "7bb27bfb-0714-e911-a952-000d3ac1be86", None),
}


# ================================================================= catálogo
def test_catalogo_e_o_do_contrato_do_hub():
    assert set(catalogo_crm.TIPOS_CRM) == set(CONTRATO)
    for slug, (entidade, grupo, assunto, time, produto) in CONTRATO.items():
        t = catalogo_crm.TIPOS_CRM[slug]
        assert (t.entidade, t.grupo, t.assunto_id, t.time_id, t.produto_id) == (entidade, grupo, assunto, time,
                                                                               produto), slug
    assert not catalogo_crm.TIPOS_CRM["seguros"].ofertavel  # legado: só reconhecido
    assert "seguros" not in catalogo_crm.TIPOS_NOVOS and "outros" not in catalogo_crm.TIPOS_NOVOS
    assert len(catalogo_crm.TIPOS_NOVOS) == 15 and catalogo_crm.TIPOS_NOVOS <= set(schemas.SCHEMAS)
    assert catalogo_crm.aceita_mensagem("seguros") and not catalogo_crm.aceita_mensagem("outro")
    assert not catalogo_crm.aceita_mensagem(None)
    # Ordem e grupo como o App: Planos, Seguros (7), ..., ocorrências gerais no fim.
    ordenados = [t.slug for t in catalogo_crm.ofertaveis()]
    assert ordenados[0] == "planos_de_saude" and ordenados[1:8] == [
        "seguro_vida", "seguro_vida_dit", "seguro_carro", "seguro_residencial", "seguro_viagem", "seguro_pet",
        "seguro_responsabilidade_civil"]
    assert ordenados[-2:] == ["duvida", "segunda_via_boleto"]
    assert catalogo_crm.TIPOS_CRM["seguro_carro"].rotulo == "Seguro Auto"
    assert {s: catalogo_crm.TIPOS_CRM[s].carencia_meses for s in catalogo_crm.TIPOS_NOVOS
            if catalogo_crm.TIPOS_CRM[s].carencia_meses} == {
        "defesa_profissional": 3, "assessoria_aposentadoria": 3, "contabilidade": 2, "despachante": 2}


def test_destino_usa_o_slug_do_app_e_o_produto():
    auto = catalogo_crm.destino("seguro_carro")
    assert (auto.tipo, auto.entidade, auto.assunto_id, auto.produto_id) == ("seguro_carro", "oportunidade", None,
                                                                           PRODUTO_AUTO)
    duvida = catalogo_crm.destino("duvida")
    assert (duvida.tipo, duvida.entidade, duvida.produto_id) == ("duvida", "ocorrencia", None)
    assert catalogo_crm.slug_crm("outro") == "outros" and catalogo_crm.slug_crm("alteracao_cadastro") == \
        "alteracao_cadastral"
    # `outros`/`seguros` não são `tipo_servico` da área: nada sai para o CRM por eles.
    assert catalogo_crm.destino("outros") is None and catalogo_crm.destino("seguros") is None
    assert catalogo_crm.destino("seguro_carro", "beneficio-1") is None
    assert not catalogo_crm.traduzido("seguro_carro")


@pytest.mark.parametrize("slug,entidade,esperado", [
    ("duvida", "ocorrencia", "central"), ("outros", "ocorrencia", "central"),
    ("alteracao_cadastral", "ocorrencia", "central"), ("segunda_via_boleto", "ocorrencia", "central"),
    ("defesa_profissional", "ocorrencia", "apm"), ("seguro_carro", "oportunidade", "apm"),
    ("seguros", "oportunidade", "apm"), (None, "ocorrencia", "central"), ("inventado", "ocorrencia", "central"),
    (None, "oportunidade", "apm"), (None, None, "apm"),
])
def test_quem_responde_igual_ao_app(slug, entidade, esperado):
    assert catalogo_crm.responde(slug, entidade) == esperado


def test_rotulos_e_schemas_dos_tipos_novos():
    assert rotulos.rotulo_tipo("seguro_carro") == "Seguro Auto"
    assert rotulos.rotulo_tipo("outro") == "Outro assunto"  # tipos antigos não mudam
    assert schemas.TIPOS_CRIAVEIS_PARIDADE == schemas.TIPOS_CRIAVEIS_API | catalogo_crm.TIPOS_NOVOS
    ok = schemas.validar("seguro_carro", {"mensagem": "  Quero uma cotação\r\npara o meu carro.  "})
    assert ok == {"mensagem": "Quero uma cotação\npara o meu carro."}
    for ruim in ({"mensagem": "curta"}, {}, {"mensagem": "x" * 2001}, {"mensagem": "meu cpf 123.456.789-09 aqui"},
                 {"mensagem": "texto válido aqui", "assunto": "não existe neste tipo"},
                 {"mensagem": "<b>negrito</b> não pode"}):
        with pytest.raises(schemas.EntradaInvalida):
            schemas.validar("seguro_carro", ruim)
    assert schemas.campos_publicos("duvida", {"mensagem": "Como faço?", "interno": 1}) == {"mensagem": "Como faço?"}


def test_texto_para_o_crm_igual_ao_app_nos_tipos_novos():
    t = crm.texto_para_crm("seguro_carro", {"mensagem": "Quero uma cotação para o meu carro."})
    assert (t.titulo, t.descricao, t.cortado) == ("Seguro Auto", "Quero uma cotação para o meu carro.", False)
    # Pior caso: 2000 unidades UTF-16 cabem inteiras, sem cabeçalho.
    cheio = crm.texto_para_crm("duvida", {"mensagem": "😀" * 1000})
    assert crm.unidades_utf16(cheio.descricao) == 2000 and not cheio.cortado
    # Tipo antigo da área (traduzido para `outros`): mantém o rótulo real no título.
    antigo = crm.texto_para_crm("declaracao_associado", {"finalidade": "geral"})
    assert antigo.titulo == "Minha APM: Declaração de associado" and antigo.descricao.startswith(crm.CABECALHO)
    with pytest.raises(crm.ConteudoRecusado):
        crm.texto_para_crm("duvida", {"mensagem": "curto"})


# ================================================================= situação
@pytest.mark.parametrize("entidade,estado,status,esperada", [
    ("ocorrencia", 0, 1, "aberta"), ("oportunidade", 0, 1, "aberta"),
    ("ocorrencia", 0, 3, "aguardando_associado"), ("oportunidade", 0, 3, "em_andamento"),
    ("ocorrencia", 0, 100000002, "aguardando_associado"), ("oportunidade", 0, 100000002, "aguardando_associado"),
    ("ocorrencia", 0, 100000001, "em_andamento"), ("ocorrencia", 0, 2, "em_andamento"),
    ("ocorrencia", 0, 921140000, "em_andamento"), ("ocorrencia", 1, 5, "concluida"),
    ("oportunidade", 1, 3, "concluida"), ("ocorrencia", 2, 6, "cancelada"), ("oportunidade", 2, 4, "cancelada"),
    ("ocorrencia", None, None, "em_andamento"), ("ocorrencia", 7, 1, "em_andamento"),
])
def test_situacao_igual_a_do_bff_do_app(entidade, estado, status, esperada):
    assert situacao_crm.situacao(entidade, estado, status) == esperada
    assert situacao_crm.status_equivalente(esperada) in rotulos.STATUS


def test_rotulos_de_situacao_iguais_aos_do_app():
    """O texto segue a ENTIDADE (retorno do hub de 2026-11-13): ocorrência → Central; oportunidade
    e entidade desconhecida → APM. Defesa Profissional é ocorrência: "a Central", embora quem
    assine a conversa seja a Equipe APM (`catalogo_crm.responde`)."""
    r = situacao_crm.rotulo
    assert r("aguardando_associado", "ocorrencia") == "A Central aguarda seu retorno"
    assert r("aguardando_associado", "oportunidade") == r("aguardando_associado", None) == "A APM aguarda seu retorno"
    assert r("em_andamento", "ocorrencia", "associado") == "Aguardando a Central"
    assert r("em_andamento", "oportunidade", "associado") == "Aguardando a APM"
    assert r("em_andamento", "ocorrencia", "central") == r("em_andamento", "oportunidade", None) == "Em andamento"
    assert [r(s, "ocorrencia") for s in ("aberta", "concluida", "cancelada")] == ["Aberta", "Concluída", "Cancelada"]
    assert situacao_crm.ENCERRADAS == {"concluida", "cancelada"}
    assert [s for s in situacao_crm.SITUACOES if situacao_crm.aberta(s)] == ["aberta", "em_andamento",
                                                                            "aguardando_associado"]
    assert not situacao_crm.aberta(None)
    assert catalogo_crm.responde("defesa_profissional", "ocorrencia") == "apm"


# ============================================================ cliente do hub
def _pedido(**kw) -> PedidoCrm:
    base = dict(contact_id=CID, registro_id=SID, entidade="oportunidade", tipo="seguro_carro", titulo="Seguro Auto",
                descricao="Quero uma cotação para o meu carro.", assunto_id=None,
                time_id=catalogo_crm.TIME_SEGUROS, produto_id=PRODUTO_AUTO)
    base.update(kw)
    return PedidoCrm(**base)


def test_pedido_leva_produto_so_em_oportunidade():
    assert _pedido().argumentos()["produto_id"] == PRODUTO_AUTO
    assert "produto_id" not in _pedido(produto_id=None).argumentos()  # vazio = chave omitida
    assert _pedido().sem_produto().argumentos() == _pedido(produto_id=None).argumentos()
    for ruim in (dict(entidade="ocorrencia", assunto_id=catalogo_crm.ASSUNTO_ATENDIMENTO_APM),
                 dict(produto_id="nao-guid")):
        with pytest.raises(ValueError):
            _pedido(**ruim).argumentos()


def test_produtos_valida_entrada_e_resposta(monkeypatch):
    outro = "217ad212-6d88-e911-a968-000d3ac1b6c7"
    estado = {"linhas": [{"produto_id": PRODUTO_AUTO.upper(), "numero": "P-1", "nome": "PREV - SEGURO CARRO",
                          "ativo": True},
                         {"produto_id": outro, "numero": None, "nome": None, "ativo": False}]}
    vistos = []

    def rotas(req, args):
        assert req.url.path.endswith("/solicitacao.produtos")
        vistos.append(args)
        return httpx.Response(200, json={"colunas": [], "linhas": estado["linhas"]})

    hub, _ = _cliente(monkeypatch, rotas)
    assert hub.solicitacao_produtos([PRODUTO_AUTO, outro]) == {PRODUTO_AUTO: True, outro: False}
    assert vistos == [{"produto_ids": [PRODUTO_AUTO, outro]}]
    # Resposta que não cobre os ids pedidos, ou `ativo` que não é booleano = fora do contrato.
    for ruim in ([estado["linhas"][0]], [{**estado["linhas"][0], "ativo": "sim"}, estado["linhas"][1]]):
        estado["linhas"] = ruim
        with pytest.raises(HubError) as e:
            hub.solicitacao_produtos([PRODUTO_AUTO, outro])
        assert e.value.codigo == "fonte_indisponivel"
    for entrada in ([], [PRODUTO_AUTO, PRODUTO_AUTO], ["x"], [str(uuid.uuid4()) for _ in range(51)]):
        with pytest.raises(ValueError):
            hub.solicitacao_produtos(entrada)


def test_interacoes_listar_descarta_linha_fora_do_contrato(monkeypatch):
    linhas = [
        {"contact_id": CID, "registro_id": SID, "entidade": "ocorrencia", "interacao_id": IID, "autor": "associado",
         "canal": 100000000, "texto": "Olá,\r\nbom dia\x00.", "criado_em": "2026-11-13T12:00:00Z"},
        {"registro_id": SID, "interacao_id": str(uuid.uuid4()), "autor": "central", "canal": None,
         "texto": "Resposta da Central", "criado_em": "2026-11-13T13:00:00Z"},
        {"registro_id": SID, "interacao_id": str(uuid.uuid4()), "autor": "robo", "texto": "autor inválido"},
        {"registro_id": CID, "interacao_id": str(uuid.uuid4()), "autor": "central", "texto": "de outro pai"},
        {"registro_id": SID, "interacao_id": "x", "autor": "central", "texto": "id inválido"},
        {"registro_id": SID, "interacao_id": str(uuid.uuid4()), "autor": "central", "texto": "   "},
    ]
    vistos = []

    def rotas(req, args):
        assert req.url.path.endswith("/solicitacao.interacoes_listar")
        vistos.append(args)
        return httpx.Response(200, json={"colunas": [], "linhas": linhas})

    hub, _ = _cliente(monkeypatch, rotas)
    msgs = hub.solicitacao_interacoes_listar(CID, SID, "ocorrencia", 500)
    assert vistos == [{"contact_id": CID, "registro_id": SID, "entidade": "ocorrencia", "limite": 50}]
    assert [(m.autor, m.canal, m.texto) for m in msgs] == [("associado", 100000000, "Olá,\nbom dia."),
                                                          ("central", None, "Resposta da Central")]
    assert "bom dia" not in repr(msgs[0])  # texto fora do repr: não vaza em log
    for ruim in (("x", SID, "ocorrencia"), (CID, "x", "ocorrencia"), (CID, SID, "task")):
        with pytest.raises(ValueError):
            hub.solicitacao_interacoes_listar(*ruim, 10)


def test_interagir_envia_o_contrato_e_valida_a_resposta(monkeypatch):
    estado = {"linha": {"contact_id": CID, "registro_id": SID, "entidade": "ocorrencia", "interacao_id": IID,
                        "criada": True, "criado_em": "2026-11-13T12:00:00Z"}}

    def rotas(req, args):
        assert req.url.path.endswith("/solicitacao.interagir")
        assert args == {"contact_id": CID, "registro_id": SID, "entidade": "ocorrencia", "interacao_id": IID,
                        "texto": "Segue o documento."}
        return httpx.Response(200, json={"colunas": [], "linhas": [estado["linha"]]})

    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    hub, pedidos = _cliente(monkeypatch, rotas)
    pedido = PedidoInteracao(CID, SID, "ocorrencia", IID, "Segue o documento.")
    assert hub.solicitacao_interagir(pedido) == EnvioInteracao(IID, True, "2026-11-13T12:00:00Z")
    assert "ferramentas%3Aescrever" in pedidos[0].content.decode()
    assert "Segue o documento" not in repr(pedido)
    for ruim in ({"interacao_id": str(uuid.uuid4())}, {"registro_id": CID}, {"criada": 1}):
        estado["linha"] = {**estado["linha"], **ruim}
        with pytest.raises(HubError) as e:
            hub.solicitacao_interagir(pedido)
        assert e.value.codigo == "escrita_indeterminada"
    for invalido in (dict(texto="x"), dict(texto="😀" * 1001), dict(interacao_id=CID), dict(entidade="task"),
                     dict(registro_id="x")):
        campos = dict(contact_id=CID, registro_id=SID, entidade="ocorrencia", interacao_id=IID, texto="ok, obrigado")
        campos.update(invalido)
        with pytest.raises(ValueError):
            PedidoInteracao(**campos).argumentos()


def test_interagir_nao_sai_com_a_escrita_desligada(monkeypatch):
    """Conta web (só `ferramentas:ler`): lê a conversa, mas nenhuma escrita sai — nem o token."""
    from app.config import get_settings
    from app.integracoes.hub import ClienteHubReal

    pedidos: list[httpx.Request] = []

    def tratar(req):
        pedidos.append(req)
        if req.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 600})
        return httpx.Response(200, json={"colunas": [], "linhas": []})

    monkeypatch.setenv("HUB_MODE", "real")
    monkeypatch.setenv("HUB_CLIENT_SECRET", "s" * 32)
    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "false")
    get_settings.cache_clear()
    hub = ClienteHubReal(transporte=httpx.MockTransport(tratar))
    with pytest.raises(HubError) as e:
        hub.solicitacao_interagir(PedidoInteracao(CID, SID, "ocorrencia", IID, "Segue o documento."))
    assert e.value.codigo == "edicao_desligada" and pedidos == []
    assert hub.solicitacao_interacoes_listar(CID, SID, "ocorrencia", 50) == []
    assert "ferramentas%3Aescrever" not in pedidos[0].content.decode()  # token só com `ler`
    get_settings.cache_clear()


@pytest.mark.parametrize("status,corpo,codigo,http", [
    (403, {"erro": "interacao_nao_permitida"}, "interacao_nao_permitida", 403),
    (409, {"erro": "registro_fechado"}, "registro_fechado", 409),
    (409, {"erro": "conflito"}, "conflito", 409),
    (422, {"erro": "produto_inativo"}, "produto_inativo", 422),
    (503, {"erro": "produto_indisponivel"}, "produto_indisponivel", 503),
    (503, {"erro": "interacao_desabilitada"}, "interacao_desabilitada", 503),
    (503, {"erro": "fonte_limitada"}, "fonte_indisponivel", 503),
    (404, {"erro": "nao_encontrado", "mensagem": "Produto não encontrado no CRM."}, "catalogo_crm_invalido", 503),
    (404, {"erro": "nao_encontrado", "detalhes": [{"campo": "produto_id"}]}, "catalogo_crm_invalido", 503),
    (404, {"erro": "nao_encontrado", "mensagem": "Registro não encontrado."}, "nao_encontrado", 404),
])
def test_erros_novos_do_contrato(monkeypatch, status, corpo, codigo, http):
    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    hub, _ = _cliente(monkeypatch, lambda req, args: httpx.Response(status, json=corpo))
    with pytest.raises(HubError) as e:
        hub.solicitacao_criar(_pedido())
    assert (e.value.codigo, e.value.status) == (codigo, http)


def test_limite_do_titular_nao_pausa_o_processo(monkeypatch):
    estado = {"resposta": httpx.Response(429, json={"erro": "limite_titular"}, headers={"Retry-After": "1800"})}
    chamadas = []

    def rotas(req, args):
        chamadas.append(req.url.path)
        return estado["resposta"]

    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    hub, _ = _cliente(monkeypatch, rotas)
    pedido = PedidoInteracao(CID, SID, "ocorrencia", IID, "Segue o documento.")
    with pytest.raises(HubError) as e:
        hub.solicitacao_interagir(pedido)
    assert (e.value.codigo, e.value.status, e.value.retry_after) == ("limite_titular", 429, 1800)
    # Outro associado continua sendo atendido: o processo não ficou em pausa.
    estado["resposta"] = httpx.Response(200, json={"colunas": [], "linhas": []})
    assert hub.solicitacao_listar(CID, 10) == [] and len(chamadas) == 2
    # Teto de 1 h e padrão de 60 s sem cabeçalho.
    estado["resposta"] = httpx.Response(429, json={"erro": "limite_titular"}, headers={"Retry-After": "99999"})
    with pytest.raises(HubError) as e:
        hub.solicitacao_interagir(pedido)
    assert e.value.retry_after == 3600
    estado["resposta"] = httpx.Response(429, json={"erro": "limite_titular"})
    with pytest.raises(HubError) as e:
        hub.solicitacao_interagir(pedido)
    assert e.value.retry_after == 60


def test_cota_esgotada_suspende_so_as_leituras_pessoais_por_15_min(monkeypatch):
    """429 `cota_pii_esgotada` não traz Retry-After e só zera às 00:00 de Brasília; cada negação é
    auditada no hub. As leituras pessoais da conta param por 15 min; o que não gasta cota segue."""
    chamadas = []

    def rotas(req, args):
        ferramenta = req.url.path.rsplit("/", 1)[-1]
        chamadas.append(ferramenta)
        if ferramenta == "solicitacao.listar":
            return httpx.Response(429, json={"erro": "cota_pii_esgotada"})
        if ferramenta == "solicitacao.produtos":
            return httpx.Response(200, json={"colunas": [], "linhas": [{"produto_id": PRODUTO_AUTO, "ativo": True}]})
        if ferramenta == "solicitacao.interagir":
            return httpx.Response(200, json={"colunas": [], "linhas": [
                {"registro_id": SID, "interacao_id": IID, "criada": True, "criado_em": "2026-11-13T12:00:00Z"}]})
        return httpx.Response(200, json={"colunas": [], "linhas": []})

    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    hub, _ = _cliente(monkeypatch, rotas)
    with pytest.raises(HubError) as e:
        hub.solicitacao_listar(CID, 10)
    assert (e.value.codigo, e.value.status, e.value.retry_after) == ("cota_esgotada", 429, 900)
    # Enquanto durar a suspensão, nenhuma leitura pessoal chega ao hub (nem de outra ferramenta).
    for leitura in (lambda: hub.solicitacao_listar(CID, 10),
                    lambda: hub.solicitacao_interacoes_listar(CID, SID, "ocorrencia", 20),
                    lambda: hub.situacao_consultar(CID)):
        with pytest.raises(HubError) as e:
            leitura()
        assert e.value.codigo == "cota_esgotada" and 1 <= e.value.retry_after <= 900
    assert chamadas == ["solicitacao.listar"]
    # Sem dado pessoal e escritas não gastam cota: seguem.
    assert hub.solicitacao_produtos([PRODUTO_AUTO]) == {PRODUTO_AUTO: True}
    assert hub.solicitacao_interagir(PedidoInteracao(CID, SID, "ocorrencia", IID, "Segue o documento.")).criada
    assert chamadas == ["solicitacao.listar", "solicitacao.produtos", "solicitacao.interagir"]
    # Passados os 15 min, uma nova tentativa.
    hub._pausa_cota_ate = 0.0
    with pytest.raises(HubError):
        hub.solicitacao_listar(CID, 10)
    assert chamadas.count("solicitacao.listar") == 2


def test_limite_de_taxa_e_fonte_limitada_seguem_o_retry_after(monkeypatch):
    for codigo, retry in (("limite_taxa", "60"), ("fonte_limitada", "7")):
        hub, _ = _cliente(monkeypatch, lambda req, args, c=codigo, r=retry: httpx.Response(
            429, json={"erro": c}, headers={"Retry-After": r}))
        with pytest.raises(HubError) as e:
            hub.solicitacao_listar(CID, 10)
        assert (e.value.codigo, e.value.retry_after) == ("limite_taxa", int(retry))


def test_politica_dos_jobs_para_os_erros_novos():
    c = politica.classificar_hub
    for codigo in ("registro_fechado", "interacao_nao_permitida", "produto_inativo", "conflito", "nao_encontrado"):
        assert c(HubError(codigo)).classe == politica.PERMANENTE, codigo
    assert c(HubError("interacao_desabilitada")).classe == politica.SISTEMICO
    assert c(HubError("cota_esgotada", 429)).classe == politica.SISTEMICO  # para a rodada, sem gastar tentativa
    for codigo in ("escrita_indeterminada", "fonte_indisponivel", "produto_indisponivel", "limite_titular"):
        assert c(HubError(codigo)).classe == politica.TRANSITORIO, codigo


# ================================================================ simulado
@pytest.fixture
def stub(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("HUB_ESCRITA_HABILITADA", "true")
    get_settings.cache_clear()
    hub = ClienteHubStub()
    redefinir_hub(hub)
    catalogo.redefinir()
    yield hub
    redefinir_hub(None)
    catalogo.redefinir()
    get_settings.cache_clear()


def test_stub_produto_inativo_e_indisponivel(stub):
    stub.produtos_inativos.add(PRODUTO_AUTO)
    with pytest.raises(HubError) as e:
        stub.solicitacao_criar(_pedido())
    assert e.value.codigo == "produto_inativo"
    stub.produtos_inativos.clear()
    stub.produto_indisponivel = True
    with pytest.raises(HubError) as e:
        stub.solicitacao_criar(_pedido())
    assert e.value.codigo == "produto_indisponivel"
    criacao = stub.solicitacao_criar(_pedido().sem_produto())  # mesmo registro_id, sem produto
    assert criacao.criada and criacao.protocolo is None
    assert stub.registros[SID]["tipo"] == "seguro_carro" and stub.registros[SID]["produto_id"] is None
    assert not stub.solicitacao_criar(_pedido()).criada  # repetição: idempotente, nem olha o produto


def test_stub_conversa_cruza_canais_e_respeita_bloqueios(stub):
    rid = stub.registro_app(CID, "duvida")
    reg = stub.solicitacao_listar(CID, 10)[0]
    assert (reg.registro_id, reg.canal, reg.tipo, reg.descricao) == (rid, CANAL_APP, "duvida",
                                                                    "Pedido aberto pelo App APM.")
    assert stub.solicitacao_interacoes_listar(CID, rid, "ocorrencia", 50) == []
    envio = stub.solicitacao_interagir(PedidoInteracao(CID, rid, "ocorrencia", IID, "Olá, tudo bem?"))
    assert envio.criada and not stub.solicitacao_interagir(
        PedidoInteracao(CID, rid, "ocorrencia", IID, "Olá, tudo bem?")).criada
    assert "texto" not in stub.interagir_chamadas[0]  # o registro de chamadas não guarda o texto
    reg = stub.solicitacao_listar(CID, 10)[0]
    assert (reg.statuscode, reg.ultima_interacao_autor) == (100000001, "associado")
    stub.central_responder(rid, "Bom dia! Pode enviar o documento.")
    reg = stub.solicitacao_listar(CID, 10)[0]
    assert (reg.statuscode, reg.ultima_interacao_autor) == (100000002, "central")
    conversa = stub.solicitacao_interacoes_listar(CID, rid, "ocorrencia", 50)
    assert [(m.autor, type(m)) for m in conversa] == [("associado", InteracaoCrm), ("central", InteracaoCrm)]
    # Outro contato não lê nem escreve; id reaproveitado em outro pai é conflito.
    outro = str(uuid.uuid4())
    assert stub.solicitacao_interacoes_listar(outro, rid, "ocorrencia", 50) == []
    with pytest.raises(HubError) as e:
        stub.solicitacao_interagir(PedidoInteracao(outro, rid, "ocorrencia", str(uuid.uuid4()), "Não é meu."))
    assert e.value.codigo == "nao_encontrado"
    rid2 = stub.registro_app(CID, "outros")
    with pytest.raises(HubError) as e:
        stub.solicitacao_interagir(PedidoInteracao(CID, rid2, "ocorrencia", IID, "Mesmo id, outro pai."))
    assert e.value.codigo == "conflito"
    # Bloqueado pela Central, fechado e limite do titular.
    stub.bloqueados.add(rid2)
    with pytest.raises(HubError) as e:
        stub.solicitacao_interagir(PedidoInteracao(CID, rid2, "ocorrencia", str(uuid.uuid4()), "Bloqueado."))
    assert e.value.codigo == "interacao_nao_permitida"
    stub.definir_estado(rid, 1, 5)
    with pytest.raises(HubError) as e:
        stub.solicitacao_interagir(PedidoInteracao(CID, rid, "ocorrencia", str(uuid.uuid4()), "Já fechou."))
    assert e.value.codigo == "registro_fechado"
    rid3 = stub.registro_app(CID, "duvida")
    stub.limite_titular = 1
    with pytest.raises(HubError) as e:
        stub.solicitacao_interagir(PedidoInteracao(CID, rid3, "ocorrencia", str(uuid.uuid4()), "Passou do limite."))
    assert (e.value.codigo, e.value.retry_after) == ("limite_titular", 1800)


# ========================================================= catálogo visível
def test_catalogo_visivel_some_com_produto_inativo_e_sobrevive_ao_hub(stub, monkeypatch):
    assert [t["codigo"] for t in catalogo.publico()] == [t.slug for t in catalogo_crm.ofertaveis()]
    assert len(stub.produtos_chamadas) == 1 and len(stub.produtos_chamadas[0]) == 12
    catalogo.publico()
    assert len(stub.produtos_chamadas) == 1  # dentro do TTL: sem nova chamada
    item = next(t for t in catalogo.publico() if t["codigo"] == "seguro_carro")
    assert item == {"codigo": "seguro_carro", "rotulo": "Seguro Auto", "grupo": "seguros", "grupo_rotulo": "Seguros",
                    "ordem": 22, "responde": "apm", "carencia_meses": 0}
    assert "PREV" not in json.dumps(catalogo.publico())  # nunca o nome do produto no CRM

    # A APM desliga o Seguro Auto no CRM: some da tela na próxima renovação.
    stub.produtos_inativos.add(PRODUTO_AUTO)
    assert catalogo.disponivel("seguro_carro")  # ainda no cache
    catalogo.invalidar()
    assert not catalogo.disponivel("seguro_carro") and catalogo.disponivel("seguro_vida")
    assert catalogo.disponivel("duvida") and catalogo.disponivel("outro")  # sem produto / tipo antigo

    # Hub fora: vale o último resultado bom, e só tenta de novo depois de 120 s.
    stub.falhar_produtos = HubError("fonte_indisponivel")
    stub.produtos_inativos.clear()
    catalogo.invalidar()
    antes = len(stub.produtos_chamadas)
    assert not catalogo.disponivel("seguro_carro")
    assert not catalogo.disponivel("seguro_carro")
    assert len(stub.produtos_chamadas) == antes + 1


def test_catalogo_sem_nenhum_resultado_usa_o_local(stub):
    stub.falhar_produtos = HubError("limite_taxa", 429, retry_after=60)
    assert [t.slug for t in catalogo.visiveis()] == [t.slug for t in catalogo_crm.ofertaveis()]
    assert catalogo.produtos_ativos() is None


@pytest.mark.parametrize("valor,esperado", [(True, True), (False, False), ("AUSENTE", None), (None, None),
                                            ("false", None), (0, None)])
def test_listar_le_pode_enviar_mensagem_so_como_booleano(monkeypatch, valor, esperado):
    """Adendo do hub de 2026-11-13: coluna ausente ou fora do contrato = comportamento anterior."""
    linha = {"contact_id": CID, "registro_id": SID, "entidade": "ocorrencia", "protocolo": "CAS-286597-X6Y5C2",
             "statecode": 0, "statuscode": 1, "canal": 100000000, "criado_em": "2026-11-13T12:00:00Z",
             "atualizado_em": "2026-11-13T12:00:00Z", "tipo": "duvida"}
    if valor != "AUSENTE":
        linha["pode_enviar_mensagem"] = valor
    hub, _ = _cliente(monkeypatch, lambda req, args: httpx.Response(200, json={"colunas": [], "linhas": [linha]}))
    (reg,) = hub.solicitacao_listar(CID, 10)
    assert reg.pode_enviar_mensagem is esperado
