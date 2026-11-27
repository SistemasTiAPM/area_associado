"""Consentimentos por finalidade, com versão e histórico (P13, spec v2 §11.6; ADR-0026).

- `consentimento_texto` guarda o texto de cada finalidade POR VERSÃO; a vigente
  é a de maior `vigente_desde` já alcançado. Texto novo = versão nova.
- `consentimento` é trilha append-only: conceder e retirar são linhas novas. O
  estado atual é a última linha de (associado, finalidade, canal).
- Decidir exige a versão que a pessoa VIU: se o texto mudou entre a leitura e
  o clique, a gravação é recusada (`VersaoDesatualizada`) e a tela recarrega.
- Finalidade só aparece se o canal dela existe (regra 19): WhatsApp fica
  oculto até haver canal contratado (P-64).
- Sem consentimento registrado = não concedido. Mensagem transacional
  (pedido, pagamento, código) não depende disto: é execução do contrato.

Bloqueante (SQL): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import limites_negocio

logger = logging.getLogger("area_associado.consentimento")

# Finalidade → canais em que ela é pedida (spec v2 §11.6).
FINALIDADES: dict[str, tuple[str, ...]] = {
    "ofertas_parceiros": ("email",),
    "whatsapp_relacionamento": ("whatsapp",),
}
# Canais que a APM de fato opera hoje (regra 19; P-64 para WhatsApp e SMS).
CANAIS_DISPONIVEIS: frozenset[str] = frozenset({"email"})
VALORES: tuple[str, ...] = ("concedido", "retirado")
HISTORICO_MAX = 20


class ConsentimentoDesconhecido(LookupError):
    """404: finalidade/canal fora do catálogo, canal indisponível ou sem texto vigente."""


class VersaoDesatualizada(Exception):
    """409 `versao_desatualizada`: o texto mudou depois que a tela foi carregada."""

    def __init__(self, vigente: str) -> None:
        super().__init__("versao_desatualizada")
        self.vigente = vigente


def _sessao():
    from ..database import session_scope  # import tardio: testes substituem funções deste módulo

    return session_scope()


def _iso(valor: datetime | None) -> str | None:
    return valor.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z") if valor else None


def pares_visiveis() -> list[tuple[str, str]]:
    return [(finalidade, canal) for finalidade, canais in FINALIDADES.items() for canal in canais
            if canal in CANAIS_DISPONIVEIS]


_SQL_TEXTO_VIGENTE = text(
    "SELECT versao, titulo, texto, vigente_desde FROM consentimento_texto "
    "WHERE finalidade = :f AND vigente_desde <= UTC_TIMESTAMP(6) "
    "ORDER BY vigente_desde DESC, versao DESC LIMIT 1"
)
_SQL_HISTORICO = text(
    "SELECT valor, versao, origem, registrado_em FROM consentimento "
    "WHERE contact_id = :c AND finalidade = :f AND canal = :canal ORDER BY id DESC LIMIT :n"
)
_SQL_INSERIR = text(
    "INSERT INTO consentimento (contact_id, sub_hash, finalidade, canal, valor, versao, origem, request_id, "
    " registrado_em) VALUES (:c, :sub_hash, :f, :canal, :valor, :versao, 'perfil', :request_id, UTC_TIMESTAMP(6))"
)


def _item(db: Session, contact_id: str, finalidade: str, canal: str) -> dict[str, Any] | None:
    vigente = db.execute(_SQL_TEXTO_VIGENTE, {"f": finalidade}).first()
    if vigente is None:
        return None
    linhas = db.execute(_SQL_HISTORICO, {"c": contact_id, "f": finalidade, "canal": canal,
                                         "n": HISTORICO_MAX}).all()
    atual = linhas[0] if linhas else None
    return {
        "finalidade": finalidade,
        "canal": canal,
        "titulo": vigente.titulo,
        "texto": vigente.texto,
        "versao": vigente.versao,
        "concedido": atual is not None and atual.valor == "concedido",
        "versao_registrada": atual.versao if atual is not None else None,
        "registrado_em": _iso(atual.registrado_em) if atual is not None else None,
        # Concedido sobre um texto que já não é o vigente: a tela pede a confirmação de novo.
        "texto_mudou": atual is not None and atual.valor == "concedido" and atual.versao != vigente.versao,
        "historico": [{"valor": r.valor, "versao": r.versao, "origem": r.origem,
                       "registrado_em": _iso(r.registrado_em)} for r in linhas],
    }


def listar(contact_id: str) -> list[dict[str, Any]]:
    """Finalidades visíveis com texto vigente, estado atual e histórico recente."""
    itens: list[dict[str, Any]] = []
    with _sessao() as db:
        for finalidade, canal in pares_visiveis():
            item = _item(db, contact_id, finalidade, canal)
            if item is None:
                logger.warning("consentimento: finalidade %s sem texto vigente; oculta", finalidade)
                continue
            itens.append(item)
    return itens


def registrar(*, contact_id: str, sub_hash: str | None, finalidade: str, canal: str, valor: str, versao: str,
              request_id: str | None = None) -> tuple[dict[str, Any], bool]:
    """Registra a decisão. Devolve (item atualizado, gravou). A mesma decisão
    sobre a mesma versão não gera linha nova (repetição de clique)."""
    if (finalidade, canal) not in pares_visiveis() or valor not in VALORES:
        raise ConsentimentoDesconhecido(finalidade)
    with _sessao() as db:
        # Serializa as decisões do associado: duas abas não gravam em ordem trocada.
        limites_negocio.bloquear_associado(db, contact_id)
        vigente = db.execute(_SQL_TEXTO_VIGENTE, {"f": finalidade}).first()
        if vigente is None:
            raise ConsentimentoDesconhecido(finalidade)
        if versao != vigente.versao:
            raise VersaoDesatualizada(vigente.versao)
        atual = db.execute(_SQL_HISTORICO, {"c": contact_id, "f": finalidade, "canal": canal, "n": 1}).first()
        # Retirar o que nunca foi concedido, ou repetir a decisão vigente: nada a gravar.
        sem_mudanca = (atual is None and valor == "retirado") or (
            atual is not None and atual.valor == valor and atual.versao == versao)
        if not sem_mudanca:
            db.execute(_SQL_INSERIR, {"c": contact_id, "sub_hash": sub_hash, "f": finalidade, "canal": canal,
                                      "valor": valor, "versao": versao, "request_id": request_id})
        item = _item(db, contact_id, finalidade, canal)
        if item is None:  # o texto vigente acabou de ser lido nesta transação
            raise ConsentimentoDesconhecido(finalidade)
    return item, not sem_mudanca


def concedido(contact_id: str, finalidade: str, canal: str) -> bool:
    """Consulta para quem ENVIA (outbox de comunicação): só `concedido` na
    última linha autoriza. Sem linha, canal indisponível ou finalidade
    desconhecida = não autorizado (fail-closed)."""
    if (finalidade, canal) not in pares_visiveis():
        return False
    with _sessao() as db:
        atual = db.execute(_SQL_HISTORICO, {"c": contact_id, "f": finalidade, "canal": canal, "n": 1}).first()
    return atual is not None and atual.valor == "concedido"
