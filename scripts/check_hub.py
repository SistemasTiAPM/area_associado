"""Smoke da integração com o mcp_hub — só LEITURA, nunca escreve no CRM.

Uso (dentro do container, com HUB_MODE=real):
    docker compose exec area-associado python -m scripts.check_hub [contact_id]

1. Emite o token com `ferramentas:ler ferramentas:escrever` (prova que a conta
   `area-associado` tem os dois escopos — P-05).
2. Com um `contact_id` de teste, chama `associado.perfil_consultar` e imprime
   só QUAIS campos vieram (nunca valores), se o endereço está disponível e se
   a resposta veio sem CPF (ADR-0014).
Sai com 1 em qualquer falha. Não imprime token, segredo nem dado pessoal.
"""

from __future__ import annotations

import sys
from typing import Any

import httpx

from app.config import get_settings
from app.dominio.associado import contact_id_valido
from app.integracoes.hub import ClienteHubReal, HubError, perfil_de_linha

_ESPERADOS = ("nome", "email", "celular", "telefone", "telefone2", "endereco", "endereco_disponivel", "num_contato",
              "crm", "crm_uf", "tipo_associado", "status_associativo", "data_filiacao", "tem_foto")


class _Sonda(ClienteHubReal):
    """Olha a resposta CRUA antes de o cliente descartar a chave `cpf`."""

    cpf_visto = False

    def _interpretar(self, ferramenta: str, r: httpx.Response) -> list[dict[str, Any]]:
        try:
            corpo = r.json()
            linhas = corpo.get("linhas") if isinstance(corpo, dict) else None
            self.cpf_visto = isinstance(linhas, list) and any(isinstance(x, dict) and "cpf" in x for x in linhas)
        except ValueError:
            pass
        return super()._interpretar(ferramenta, r)


def main(argv: list[str]) -> int:
    s = get_settings()
    if s.hub_mode != "real":
        print(f"HUB_MODE={s.hub_mode}: nada a verificar (hub simulado).")
        return 0
    print(f"hub       : {s.effective_hub_base_url} (Host={s.hub_public_host})")
    print(f"client_id : {s.hub_client_id}")
    cliente = _Sonda()
    try:
        cliente._obter_token(renovar=True)
    except HubError as exc:
        print(f"FALHA: token recusado ({exc.codigo}) — conta sem os dois escopos ou segredo errado", file=sys.stderr)
        return 1
    print("token     : ok (ferramentas:ler ferramentas:escrever)")
    if len(argv) < 2:
        print("perfil    : -- (informe um contact_id de teste para consultar)")
        return 0
    cid = contact_id_valido(argv[1])
    if cid is None:
        print("FALHA: contact_id inválido", file=sys.stderr)
        return 1
    try:
        linhas = cliente.chamar("associado.perfil_consultar", {"contact_id": cid})
    except HubError as exc:
        print(f"FALHA: perfil_consultar → {exc.codigo} (HTTP {exc.status})", file=sys.stderr)
        return 1
    if not linhas:
        print("FALHA: contato não encontrado no CRM", file=sys.stderr)
        return 1
    linha = linhas[0]
    print(f"sem cpf   : {'FALHA — o hub devolveu cpf' if cliente.cpf_visto else 'ok'}")
    faltando = [c for c in _ESPERADOS if c not in linha]
    print(f"campos    : {len(_ESPERADOS) - len(faltando)}/{len(_ESPERADOS)}"
          + (f" (faltando: {', '.join(faltando)})" if faltando else ""))
    perfil = perfil_de_linha(linha)
    print(f"endereço  : {'disponível' if perfil.endereco_disponivel else 'indisponível (flag/Metadata no hub)'}")
    print(f"UF do CRM : {'sigla ok' if perfil.crm_uf else 'vazia ou fora do padrão'}")
    return 1 if faltando or cliente.cpf_visto else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
