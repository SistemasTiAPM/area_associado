"""mcp_hub simulado (`HUB_MODE=stub`), para construir e testar sem o hub real.

Mesmo contrato de `ClienteHubReal` (docs/CONTRATO-HUB.md). Dados
determinísticos por `contact_id` e escritas em memória do processo. Com 2
workers, a memória não é compartilhada — por isso a área sempre relê do cache
`associado_perfil` depois de uma escrita confirmada, nunca do stub.

`falhar = True` simula hub fora do ar (testes de degradação, RNF-18).
`situacoes[contact_id] = "cancelado"` (ou `suspenso`/`outro`) simula o CRM com o associado
fora de "ativo"; `registros_inativos` simula contato desativado (`statecode=1`).
`endereco_disponivel = False` simula o hub sem a flag/Metadata do endereço:
perfil sem endereço e gravação de endereço com 409.
Solicitações (contrato "Solicitações", ADR-0023): `registros` guarda o que o
"CRM" tem, por `registro_id` (criação idempotente: repetir devolve `criada=False`
com o mesmo protocolo; o mesmo id com outro contato é 409 `conflito`, como no
hub); `criar_chamadas` registra cada pedido; `definir_estado(id, statecode,
statuscode)` simula a Central mexendo no CRM; `registros_central(contact_id, n)`
cria linhas abertas pela Central (sem canal); `falhar_solicitacoes[id] =
HubError(...)` simula erro por pedido. Toda ocorrência nasce 0/1 ("Em andamento"),
como no tenant.
Paridade com o App (ADR-0024): `registro_app(contact_id, tipo, ...)` cria um registro
aberto pelo App APM (canal 100000000); `produtos_inativos` desliga um produto (o
`criar` responde 422 `produto_inativo` e `solicitacao_produtos` diz `ativo=False`);
`produto_indisponivel = True` simula o 503 que pede reenvio sem `produto_id`;
`central_responder(id, texto)` publica uma mensagem da Central (statuscode 100000002);
`bloqueados` simula "Bloquear mensagens do associado"; `limite_titular = n` faz a
n+1-ésima mensagem do contato responder 429 `limite_titular`; `falhar_produtos` e
`falhar_interacoes[id]` simulam erro do hub.
Escrita obedece a `HUB_ESCRITA_HABILITADA` como no cliente real.
Proibido em produção (validador de `Settings`).
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from typing import Any

from .hub import (
    CANAL_APP,
    CANAL_MINHA_APM,
    INTERACOES_LIMITE_MAX,
    LISTAR_LIMITE_MAX,
    SITUACOES_NORMALIZADAS,
    CriacaoCrm,
    Endereco,
    EnvioInteracao,
    HubError,
    InteracaoCrm,
    PedidoCrm,
    PedidoInteracao,
    PerfilCrm,
    RegistroCrm,
    SituacaoCrm,
    exigir_escrita_habilitada,
    validar_produto_ids,
)

_NS_CENTRAL = uuid.UUID("6f1c2a9e-3b7d-4c55-9a1e-0d2f6b8c4e71")
_NS_APP = uuid.UUID("0b7e5d1c-9a42-4f6e-8c33-5d1a7e9b2f04")
_CANAL_MINHA_APM = CANAL_MINHA_APM
_STATUS_RESPONDIDO_ASSOCIADO = 100000001
_STATUS_RESPONDIDO_CENTRAL = 100000002


class ClienteHubStub:
    def __init__(self) -> None:
        self.falhar = False
        self.endereco_disponivel = True
        self._lock = threading.Lock()
        self._contatos: dict[str, dict[str, Any]] = {}
        self._fotos: dict[str, bytes] = {}
        self.situacoes: dict[str, str] = {}
        self.registros_inativos: set[str] = set()
        self.registros: dict[str, dict[str, Any]] = {}
        self.criar_chamadas: list[dict[str, Any]] = []
        self.listar_chamadas: list[tuple[str, int]] = []
        self.falhar_solicitacoes: dict[str, HubError] = {}
        self.produtos_inativos: set[str] = set()
        self.produto_indisponivel = False
        self.falhar_produtos: HubError | None = None
        self.produtos_chamadas: list[list[str]] = []
        self.interacoes: dict[str, list[dict[str, Any]]] = {}
        self.interagir_chamadas: list[dict[str, Any]] = []
        self.interacoes_chamadas: list[tuple[str, str]] = []
        self.falhar_interacoes: dict[str, HubError] = {}
        self.bloqueados: set[str] = set()
        self.sem_coluna_envio = False  # True = hub anterior ao adendo (lista sem `pode_enviar_mensagem`)
        self.limite_titular: int | None = None
        self._sequencia = 0

    def _verificar(self) -> None:
        if self.falhar:
            raise HubError("fonte_indisponivel")

    def _base(self, contact_id: str) -> dict[str, Any]:
        digitos = int(hashlib.sha256(contact_id.encode()).hexdigest()[:8], 16)
        return {
            "celular": f"(11) 9{digitos % 10000:04d}-{(digitos // 10000) % 10000:04d}",
            "telefone": None,
            "telefone2": None,
            "endereco": Endereco(logradouro="Rua de Exemplo", numero=str(100 + digitos % 900),
                                 bairro="Centro", cidade="São Paulo", uf="SP", cep="01000-000"),
        }

    def perfil_consultar(self, contact_id: str) -> PerfilCrm | None:
        self._verificar()
        with self._lock:
            dados = self._contatos.setdefault(contact_id, self._base(contact_id))
            # Nome, e-mail e dados da carteirinha ficam com o que veio do IdP
            # (None aqui = "não sobrescrever o cache").
            return PerfilCrm(tem_foto=contact_id in self._fotos, **{k: dados.get(k) for k in
                             ("celular", "telefone", "telefone2")},
                             endereco=dados.get("endereco") if self.endereco_disponivel else None,
                             endereco_disponivel=self.endereco_disponivel, email=dados.get("email"))

    # Rótulo e código por situação; só o código 2 (Ativo) e 3 (Pendente) são confirmados no
    # tenant (tabela versionada no hub) — os demais ficam sem código, como o hub faria.
    _SITUACOES = {
        "ativo": ("Ativo", 2),
        "suspenso": ("Suspenso", None),
        "cancelado": ("Cancelado", None),
        "outro": ("Pendente", 3),
    }

    def situacao_consultar(self, contact_id: str) -> SituacaoCrm | None:
        self._verificar()
        with self._lock:
            normalizada = self.situacoes.get(contact_id, "ativo")
            inativo = contact_id in self.registros_inativos
        if normalizada not in SITUACOES_NORMALIZADAS:
            normalizada = "outro"
        rotulo, codigo = self._SITUACOES[normalizada]
        ativa = normalizada == "ativo"
        return SituacaoCrm(
            contact_id=contact_id.lower(),
            status_associativo=rotulo,
            status_associativo_codigo=codigo,
            situacao_normalizada=normalizada,
            tipo_associado=None,  # tipo e filiação ficam com o que veio do IdP (como no perfil)
            data_filiacao=None,
            statecode=1 if inativo else 0,
            associacao_status="Ativa" if ativa else rotulo,
            associacao_status_codigo=100000001 if ativa else None,
            associacao_data=None,
        )

    def contato_atualizar(self, contact_id: str, campos: dict[str, Any]) -> list[str]:
        exigir_escrita_habilitada()
        self._verificar()
        if "endereco" in campos and not self.endereco_disponivel:
            raise HubError("endereco_indisponivel", 409)
        with self._lock:
            dados = self._contatos.setdefault(contact_id, self._base(contact_id))
            for chave, valor in campos.items():
                dados[chave] = Endereco(**valor) if chave == "endereco" and isinstance(valor, dict) else valor
        return list(campos)

    def foto_obter(self, contact_id: str) -> bytes | None:
        self._verificar()
        with self._lock:
            return self._fotos.get(contact_id)

    def foto_atualizar(self, contact_id: str, jpeg: bytes | None) -> None:
        exigir_escrita_habilitada()
        self._verificar()
        with self._lock:
            if jpeg:
                self._fotos[contact_id] = jpeg
            else:
                self._fotos.pop(contact_id, None)

    # ------------------------------------------------ solicitações (ADR-0023)
    def _relogio(self) -> str:
        self._sequencia += 1
        return f"2026-11-04T{(self._sequencia // 3600) % 24:02d}:{(self._sequencia // 60) % 60:02d}:" \
               f"{self._sequencia % 60:02d}Z"

    def solicitacao_criar(self, pedido: PedidoCrm) -> CriacaoCrm:
        exigir_escrita_habilitada()
        self._verificar()
        argumentos = pedido.argumentos()  # mesma validação de contrato do cliente real
        with self._lock:
            erro = self.falhar_solicitacoes.get(pedido.registro_id)
        if erro is not None:
            raise erro
        with self._lock:
            self.criar_chamadas.append(argumentos)
            existente = self.registros.get(pedido.registro_id)
            if existente is None and pedido.produto_id is not None:
                if self.produto_indisponivel:
                    raise HubError("produto_indisponivel", 503)
                if pedido.produto_id in self.produtos_inativos:
                    raise HubError("produto_inativo", 422)
            if existente is not None:
                if existente["contact_id"] != pedido.contact_id:
                    raise HubError("conflito", 409)
                criada = False
            else:
                digitos = int(hashlib.sha256(pedido.registro_id.encode()).hexdigest()[:10], 16)
                protocolo = (f"CAS-{digitos % 1000000:06d}-{format(digitos, 'X')[-6:].rjust(6, 'A')}"
                             if pedido.entidade == "ocorrencia" else None)
                quando = self._relogio()
                existente = self.registros[pedido.registro_id] = {
                    "contact_id": pedido.contact_id, "registro_id": pedido.registro_id,
                    "entidade": pedido.entidade, "protocolo": protocolo, "statecode": 0, "statuscode": 1,
                    "canal": _CANAL_MINHA_APM, "criado_em": quando, "atualizado_em": quando,
                    "tipo": pedido.tipo, "titulo": pedido.titulo, "descricao": pedido.descricao,
                    "assunto_id": pedido.assunto_id, "produto_id": pedido.produto_id,
                }
                criada = True
            return CriacaoCrm(pedido.registro_id, pedido.entidade, criada, existente["protocolo"],
                              existente["statecode"], existente["statuscode"])

    def definir_estado(self, registro_id: str, statecode: int, statuscode: int) -> None:
        """Simula a Central mudando o registro no CRM."""
        with self._lock:
            registro = self.registros[registro_id]
            registro.update(statecode=statecode, statuscode=statuscode, atualizado_em=self._relogio())

    def registros_central(self, contact_id: str, quantidade: int) -> None:
        """Simula ocorrências abertas pela Central (sem canal) — gastam linha no `listar`."""
        with self._lock:
            for _ in range(quantidade):
                rid = str(uuid.uuid5(_NS_CENTRAL, f"{contact_id}:{self._sequencia}"))
                quando = self._relogio()
                self.registros[rid] = {"contact_id": contact_id, "registro_id": rid, "entidade": "ocorrencia",
                                       "protocolo": "CAS-000001-CENTRA", "statecode": 0, "statuscode": 1,
                                       "canal": None, "criado_em": quando, "atualizado_em": quando}

    def solicitacao_listar(self, contact_id: str, limite: int) -> list[RegistroCrm]:
        self._verificar()
        limite = max(1, min(int(limite), LISTAR_LIMITE_MAX))
        with self._lock:
            erro = self.falhar_solicitacoes.get(contact_id)
            if erro is not None:
                raise erro
            self.listar_chamadas.append((contact_id, limite))
            do_contato = sorted((r for r in self.registros.values() if r["contact_id"] == contact_id),
                                key=lambda r: r["criado_em"], reverse=True)[:limite]
            return [RegistroCrm(r["registro_id"], r["entidade"], r["protocolo"], r["statecode"], r["statuscode"],
                                r["canal"], r["criado_em"], r["atualizado_em"], tipo=r.get("tipo"),
                                assunto_id=r.get("assunto_id"),
                                ultima_interacao_em=r.get("ultima_interacao_em"),
                                ultima_interacao_autor=r.get("ultima_interacao_autor"),
                                descricao=r.get("descricao"),
                                pode_enviar_mensagem=None if self.sem_coluna_envio else (
                                    r["canal"] is not None and r["statecode"] == 0
                                    and r["registro_id"] not in self.bloqueados)) for r in do_contato]

    # ------------------------------------- catálogo e conversa (ADR-0024)
    def registro_app(self, contact_id: str, tipo: str, entidade: str = "ocorrencia",
                     titulo: str = "Dúvidas e perguntas", descricao: str = "Pedido aberto pelo App APM.") -> str:
        """Simula um registro que o associado abriu pelo App APM. Devolve o `registro_id`."""
        with self._lock:
            rid = str(uuid.uuid5(_NS_APP, f"{contact_id}:{tipo}:{self._sequencia}"))
            quando = self._relogio()
            self.registros[rid] = {
                "contact_id": contact_id, "registro_id": rid, "entidade": entidade,
                "protocolo": "CAS-000002-APPAPM" if entidade == "ocorrencia" else None,
                "statecode": 0, "statuscode": 1, "canal": CANAL_APP, "criado_em": quando,
                "atualizado_em": quando, "tipo": tipo, "titulo": titulo, "descricao": descricao,
                "assunto_id": None, "produto_id": None}
            return rid

    def solicitacao_produtos(self, produto_ids: list[str]) -> dict[str, bool]:
        self._verificar()
        ids = validar_produto_ids(produto_ids)
        with self._lock:
            self.produtos_chamadas.append(ids)
            if self.falhar_produtos is not None:
                raise self.falhar_produtos
            return {pid: pid not in self.produtos_inativos for pid in ids}

    def _pai(self, contact_id: str, registro_id: str, entidade: str) -> dict[str, Any] | None:
        pai = self.registros.get(registro_id)
        if (pai is None or pai["contact_id"] != contact_id or pai["entidade"] != entidade
                or pai["canal"] is None):
            return None
        return pai

    def solicitacao_interacoes_listar(self, contact_id: str, registro_id: str, entidade: str,
                                      limite: int) -> list[InteracaoCrm]:
        self._verificar()
        limite = max(1, min(int(limite), INTERACOES_LIMITE_MAX))
        with self._lock:
            erro = self.falhar_interacoes.get(registro_id)
            if erro is not None:
                raise erro
            self.interacoes_chamadas.append((contact_id, registro_id))
            if self._pai(contact_id, registro_id, entidade) is None:
                return []
            mensagens = sorted(self.interacoes.get(registro_id, []), key=lambda m: m["criado_em"])[-limite:]
            return [InteracaoCrm(m["interacao_id"], m["autor"], m["canal"], m["criado_em"], m["texto"])
                    for m in mensagens]

    def solicitacao_interagir(self, pedido: PedidoInteracao) -> EnvioInteracao:
        exigir_escrita_habilitada()
        self._verificar()
        argumentos = pedido.argumentos()
        with self._lock:
            erro = self.falhar_interacoes.get(pedido.interacao_id)
            if erro is not None:
                raise erro
            self.interagir_chamadas.append({k: v for k, v in argumentos.items() if k != "texto"})
            pai = self.registros.get(pedido.registro_id)
            if pai is None or pai["contact_id"] != pedido.contact_id or pai["entidade"] != pedido.entidade:
                raise HubError("nao_encontrado", 404)
            for rid, mensagens in self.interacoes.items():
                for m in mensagens:
                    if m["interacao_id"] == pedido.interacao_id:
                        if rid != pedido.registro_id:
                            raise HubError("conflito", 409)
                        return EnvioInteracao(pedido.interacao_id, False, m["criado_em"])
            if pai["canal"] is None or pedido.registro_id in self.bloqueados:
                raise HubError("interacao_nao_permitida", 403)
            if pai["statecode"] != 0:
                raise HubError("registro_fechado", 409)
            if self.limite_titular is not None:
                enviadas = sum(1 for rid, ms in self.interacoes.items() for m in ms
                               if m["autor"] == "associado"
                               and self.registros[rid]["contact_id"] == pedido.contact_id)
                if enviadas >= self.limite_titular:
                    raise HubError("limite_titular", 429, retry_after=1800)
            quando = self._relogio()
            self.interacoes.setdefault(pedido.registro_id, []).append({
                "interacao_id": pedido.interacao_id, "autor": "associado", "canal": _CANAL_MINHA_APM,
                "texto": pedido.texto, "criado_em": quando})
            pai.update(statuscode=_STATUS_RESPONDIDO_ASSOCIADO, atualizado_em=quando,
                       ultima_interacao_em=quando, ultima_interacao_autor="associado")
            return EnvioInteracao(pedido.interacao_id, True, quando)

    def central_responder(self, registro_id: str, texto: str) -> str:
        """Simula a Central publicando uma mensagem ao associado. Devolve o `interacao_id`."""
        with self._lock:
            pai = self.registros[registro_id]
            quando = self._relogio()
            iid = str(uuid.uuid5(_NS_CENTRAL, f"{registro_id}:{self._sequencia}"))
            self.interacoes.setdefault(registro_id, []).append({
                "interacao_id": iid, "autor": "central", "canal": None, "texto": texto, "criado_em": quando})
            pai.update(atualizado_em=quando, ultima_interacao_em=quando, ultima_interacao_autor="central")
            if pai["statecode"] == 0:
                pai["statuscode"] = _STATUS_RESPONDIDO_CENTRAL
            return iid
