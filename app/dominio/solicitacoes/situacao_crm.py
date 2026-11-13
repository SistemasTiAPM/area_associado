"""Situação e rótulo de um registro do CRM — IGUAIS aos do App APM (ADR-0024).

O hub devolve `statecode`/`statuscode` crus. A regra de leitura é a do BFF do App
(`appapm/src/includes/solicitacoes_service.php`), para o associado ver o mesmo texto nos
dois canais; mudar aqui só junto com o App, combinado pelo William.

| par                                   | situação               |
|---------------------------------------|------------------------|
| 1/*                                   | `concluida`            |
| 2/*                                   | `cancelada`            |
| 0/1                                   | `aberta`               |
| 0/3 em ocorrência ("Aguardando detalhes") | `aguardando_associado` |
| 0/100000002 ("Respondido pela Central")   | `aguardando_associado` |
| 0/qualquer outro (inclui 100000001)   | `em_andamento`         |
| statecode fora de 0/1/2               | `em_andamento`         |

Ordem e regra confirmadas pelo hub em 2026-11-13 (retorno à resposta da área). O texto
depende da ENTIDADE — "a Central" em ocorrência, "a APM" em oportunidade e em entidade
desconhecida — e, em `em_andamento`, de quem falou por último. (Quem assina a conversa é
outra regra, por tipo: `catalogo_crm.responde`.) Os textos de `aberta`, `em_andamento`,
`concluida` e `cancelada` estão no app Flutter; os daqui valem até o William trazê-los (P-80).
Situações ABERTAS (unicidade e caixa de envio): `aberta`, `em_andamento`, `aguardando_associado`.

Funções puras.
"""

from __future__ import annotations

SITUACOES: tuple[str, ...] = ("aberta", "em_andamento", "aguardando_associado", "concluida", "cancelada")
ENCERRADAS: frozenset[str] = frozenset({"concluida", "cancelada"})

STATUS_AGUARDANDO_DETALHES = 3
STATUS_RESPONDIDO_ASSOCIADO = 100000001
STATUS_RESPONDIDO_CENTRAL = 100000002

# Status da área mais próximo de cada situação (campo `status` do contrato da API, que
# a SPA usa só como reserva de tom quando não há `situacao`).
_STATUS_EQUIVALENTE: dict[str, str] = {
    "aberta": "enviada",
    "em_andamento": "em_atendimento",
    "aguardando_associado": "pendente_associado",
    "concluida": "concluida_positiva",
    "cancelada": "cancelada",
}
_CENTRAL, _APM = ("A Central", "a Central"), ("A APM", "a APM")  # (sujeito, "Aguardando ...")


def aberta(sit: str | None) -> bool:
    return sit is not None and sit not in ENCERRADAS


def situacao(entidade: str | None, statecode: int | None, statuscode: int | None) -> str:
    if statecode == 1:
        return "concluida"
    if statecode == 2:
        return "cancelada"
    if statecode != 0:
        return "em_andamento"
    if statuscode == 1:
        return "aberta"
    if statuscode == STATUS_RESPONDIDO_CENTRAL or (
            entidade == "ocorrencia" and statuscode == STATUS_AGUARDANDO_DETALHES):
        return "aguardando_associado"
    return "em_andamento"


def rotulo(sit: str, entidade: str | None, ultimo_autor: str | None = None) -> str:
    sujeito, objeto = _CENTRAL if entidade == "ocorrencia" else _APM
    if sit == "aguardando_associado":
        return f"{sujeito} aguarda seu retorno"
    if sit == "em_andamento":
        return f"Aguardando {objeto}" if ultimo_autor == "associado" else "Em andamento"
    if sit == "aberta":
        return "Aberta"
    if sit == "concluida":
        return "Concluída"
    return "Cancelada"


def status_equivalente(sit: str) -> str:
    return _STATUS_EQUIVALENTE[sit]
