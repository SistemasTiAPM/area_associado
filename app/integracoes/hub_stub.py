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
Escrita obedece a `HUB_ESCRITA_HABILITADA` como no cliente real.
Proibido em produção (validador de `Settings`).
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from typing import Any

from .hub import (
    LISTAR_LIMITE_MAX,
    SITUACOES_NORMALIZADAS,
    CriacaoCrm,
    Endereco,
    HubError,
    PedidoCrm,
    PerfilCrm,
    RegistroCrm,
    SituacaoCrm,
    exigir_escrita_habilitada,
)

_NS_CENTRAL = uuid.UUID("6f1c2a9e-3b7d-4c55-9a1e-0d2f6b8c4e71")
_CANAL_MINHA_APM = 100000001


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
                                r["canal"], r["criado_em"], r["atualizado_em"]) for r in do_contato]
