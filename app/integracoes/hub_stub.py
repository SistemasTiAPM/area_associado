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
Escrita obedece a `HUB_ESCRITA_HABILITADA` como no cliente real.
Proibido em produção (validador de `Settings`).
"""

from __future__ import annotations

import hashlib
import threading
from typing import Any

from .hub import SITUACOES_NORMALIZADAS, Endereco, HubError, PerfilCrm, SituacaoCrm, exigir_escrita_habilitada


class ClienteHubStub:
    def __init__(self) -> None:
        self.falhar = False
        self.endereco_disponivel = True
        self._lock = threading.Lock()
        self._contatos: dict[str, dict[str, Any]] = {}
        self._fotos: dict[str, bytes] = {}
        self.situacoes: dict[str, str] = {}
        self.registros_inativos: set[str] = set()

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
