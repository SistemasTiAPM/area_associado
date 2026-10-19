"""mcp_hub simulado (`HUB_MODE=stub`), para construir e testar sem o hub real.

Mesmo contrato de `ClienteHubReal` (docs/CONTRATO-HUB.md). Dados
determinísticos por `contact_id` e escritas em memória do processo. Com 2
workers, a memória não é compartilhada — por isso a área sempre relê do cache
`associado_perfil` depois de uma escrita confirmada, nunca do stub.

`falhar = True` simula hub fora do ar (testes de degradação, RNF-18).
`endereco_disponivel = False` simula o hub sem a flag/Metadata do endereço:
perfil sem endereço e gravação de endereço com 409.
Proibido em produção (validador de `Settings`).
"""

from __future__ import annotations

import hashlib
import threading
from typing import Any

from .hub import Endereco, HubError, PerfilCrm


class ClienteHubStub:
    def __init__(self) -> None:
        self.falhar = False
        self.endereco_disponivel = True
        self._lock = threading.Lock()
        self._contatos: dict[str, dict[str, Any]] = {}
        self._fotos: dict[str, bytes] = {}

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

    def contato_atualizar(self, contact_id: str, campos: dict[str, Any]) -> list[str]:
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
        self._verificar()
        with self._lock:
            if jpeg:
                self._fotos[contact_id] = jpeg
            else:
                self._fotos.pop(contact_id, None)
