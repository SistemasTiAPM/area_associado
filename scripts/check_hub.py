"""Smoke da integração com o mcp_hub — só LEITURA, nunca escreve no CRM.

Uso (dentro do container, com HUB_MODE=real):
    docker compose exec area-associado python -m scripts.check_hub [contact_id]

1. Emite o token com o escopo que a área vai pedir em produção: `ferramentas:ler`,
   mais `ferramentas:escrever` só com `HUB_ESCRITA_HABILITADA=true` (prova que a
   conta `area-associado` tem esses escopos — P-02; `escrever` só depois da P-29).
2. Com um `contact_id` de teste, chama `associado.perfil_consultar` e imprime
   só QUAIS campos vieram (nunca valores), se o endereço está disponível e se
   a resposta veio sem CPF (ADR-0014).
3. Chama `associado.situacao` com o mesmo `contact_id` (TI-47) e imprime só os
   nomes dos campos e a `situacao_normalizada` (enum fechado, não é dado pessoal).
   Falha se vier qualquer chave `cpf`.
Sai com 1 em qualquer falha. Não imprime token, segredo nem dado pessoal.
"""

from __future__ import annotations

import sys
from typing import Any

import httpx

from app.config import get_settings
from app.dominio.associado import contact_id_valido
from app.integracoes.hub import ClienteHubReal, HubError, escopos_do_token, perfil_de_linha, situacao_de_linha

_ESPERADOS = ("nome", "email", "celular", "telefone", "telefone2", "endereco", "endereco_disponivel", "num_contato",
              "crm", "crm_uf", "tipo_associado", "status_associativo", "data_filiacao", "tem_foto")
_ESPERADOS_SITUACAO = ("contact_id", "status_associativo", "status_associativo_codigo", "situacao_normalizada",
                       "tipo_associado", "data_filiacao", "statecode", "situacao_registro", "associacao_status",
                       "associacao_status_codigo", "associacao_data", "associacao_criada_em")


class _Sonda(ClienteHubReal):
    """Olha a resposta CRUA antes de o cliente descartar a chave `cpf` (acumula entre chamadas)."""

    cpf_visto = False

    def _interpretar(self, ferramenta: str, r: httpx.Response) -> list[dict[str, Any]]:
        try:
            corpo = r.json()
            linhas = corpo.get("linhas") if isinstance(corpo, dict) else None
            if isinstance(linhas, list) and any(isinstance(x, dict) and "cpf" in x for x in linhas):
                self.cpf_visto = True
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
    escopos = escopos_do_token()
    cliente = _Sonda()
    try:
        cliente._obter_token(renovar=True)
    except HubError as exc:
        print(f"FALHA: token recusado ({exc.codigo}) — conta sem '{escopos}' (invalid_scope) ou segredo errado",
              file=sys.stderr)
        return 1
    print(f"token     : ok ({escopos})")
    print(f"edição    : {'habilitada' if s.hub_escrita_habilitada else 'desligada (HUB_ESCRITA_HABILITADA=false)'}")
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
    falhas = bool(faltando) or cliente.cpf_visto

    # 3. associado.situacao (TI-47): só nomes de campos + enum fechado; nunca valores pessoais.
    try:
        linhas_sit = cliente.chamar("associado.situacao", {"contact_id": cid})
    except HubError as exc:
        motivo = "sem grant exato na conta (404 do hub)" if exc.codigo == "fonte_indisponivel" else exc.codigo
        print(f"situacao  : FALHA — {motivo} (HTTP {exc.status})", file=sys.stderr)
        return 1
    if not linhas_sit:
        print("situacao  : FALHA — contato não encontrado", file=sys.stderr)
        return 1
    sit = linhas_sit[0]
    faltando_sit = [c for c in _ESPERADOS_SITUACAO if c not in sit]
    situacao = situacao_de_linha(sit)
    print(f"situacao  : {'FALHA — o hub devolveu cpf' if cliente.cpf_visto else 'ok'} "
          f"({situacao.situacao_normalizada}; registro {'ativo' if situacao.statecode == 0 else 'inativo/desconhecido'})")
    print(f"campos    : {len(_ESPERADOS_SITUACAO) - len(faltando_sit)}/{len(_ESPERADOS_SITUACAO)}"
          + (f" (faltando: {', '.join(faltando_sit)})" if faltando_sit else ""))
    return 1 if falhas or faltando_sit or cliente.cpf_visto else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
