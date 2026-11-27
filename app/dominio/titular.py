"""Direitos do titular (LGPD) pelo perfil: baixar os dados e pedir exclusão
(P13, spec v2 §11.6; ADR-0025; `sql/017`).

EXPORTAÇÃO — síncrona, só do que a ÁREA guarda sobre o próprio associado. O
cadastro oficial é do CRM (o que aparece aqui é o cache), e o CPF não entra
porque a área não o tem (ADR-0014). Uma exportação a cada `EXPORTACAO_INTERVALO`,
contada no banco (`titular_pedido`), com a linha do associado travada: dois
workers não liberam duas (ADR-0020). Nada do arquivo é guardado — só o fato.

EXCLUSÃO — é PEDIDO, não efeito. A aplicação registra o pedido com protocolo
(`titular_pedido`) e abre a solicitação `exclusao_dados` que o associado
acompanha. Quem executa é o operador, depois da análise do encarregado, por
`scripts/anonimizar_titular.sql`, com a credencial administrativa: a aplicação
não tem (e não ganha) privilégio para apagar ou sobrescrever dado pessoal em
massa. Exclusão é ANONIMIZAÇÃO (DEC-06): sem DELETE.

Bloqueante (SQL): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import json
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import limites_negocio
from .solicitacoes import schemas, servico

logger = logging.getLogger("area_associado.titular")

EXPORTACAO_INTERVALO = timedelta(days=7)
FORMATO_EXPORTACAO = "minha-apm-dados/1"
_ER_DUPLICADO = 1062
_ALFABETO_PROTOCOLO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
_TENTATIVAS_PROTOCOLO = 4

# Tetos da exportação: o arquivo é montado em memória numa resposta síncrona.
_MAX_LINHAS = 500
_MAX_EVENTOS_SOLICITACAO = 2000
_MAX_USO = 2000

# Grupos de dados entregues (nomes, nunca valores): vão para o registro de
# acesso a dado pessoal (`audit.registrar_acesso_dado_pessoal`).
GRUPOS_EXPORTADOS: tuple[str, ...] = (
    "acessos", "cadastro", "preferencias", "consentimentos", "solicitacoes", "mensagens_em_envio",
    "notificacoes", "comunicacoes", "trocas_de_email", "pedidos_titular", "uso",
)

OBSERVACOES_EXPORTACAO: tuple[str, ...] = (
    "Este arquivo reúne o que a Minha APM guarda sobre você.",
    "O cadastro oficial fica no sistema de relacionamento da APM; o bloco cadastro é a cópia usada pela área. "
    "Para o cadastro completo, fale com a Central de Relacionamento.",
    "O CPF não aparece porque a Minha APM não o guarda.",
    "Registros de segurança são guardados com identificador pseudonimizado e não fazem parte deste arquivo.",
    "Mensagens trocadas com a Central ficam no sistema de relacionamento da APM; aqui só aparecem as que "
    "ainda não foram enviadas.",
)


class LimiteExportacao(Exception):
    """429 `limite_negocio`: já houve exportação dentro do intervalo."""

    def __init__(self, libera_em: datetime) -> None:
        super().__init__("limite_negocio")
        self.libera_em = libera_em


@dataclass(frozen=True)
class Exportacao:
    protocolo: str
    dados: dict[str, Any]


@dataclass(frozen=True)
class PedidoExclusao:
    protocolo: str
    solicitacao_id: str
    registrado_em: datetime
    criado: bool


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sessao():
    from ..database import session_scope  # import tardio: testes substituem funções deste módulo

    return session_scope()


def _iso(valor: Any) -> Any:
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(valor, date):
        return valor.isoformat()
    return valor


def _json(valor: Any) -> Any:
    if isinstance(valor, (str, bytes)):
        try:
            return json.loads(valor)
        except ValueError:
            return None
    return valor


def gerar_protocolo(agora: datetime) -> str:
    """`LGPD-AAAAMMDD-XXXXXX` (base32 sem 0/1/8/9: ditável por telefone)."""
    sufixo = "".join(secrets.choice(_ALFABETO_PROTOCOLO) for _ in range(6))
    return f"LGPD-{agora:%Y%m%d}-{sufixo}"


_SQL_INSERIR_PEDIDO = text(
    "INSERT INTO titular_pedido (id, protocolo, contact_id, sub_hash, tipo, status, solicitacao_id, "
    " chave_idempotencia, criado_em, concluido_em, request_id) "
    "VALUES (:id, :protocolo, :c, :sub_hash, :tipo, :status, :solicitacao_id, :chave, :agora, :concluido_em, "
    " :request_id)"
)


def _inserir_pedido(db: Session, *, contact_id: str, sub_hash: str, tipo: str, status: str, agora: datetime,
                    solicitacao_id: str | None = None, chave: str | None = None,
                    request_id: str | None = None) -> str:
    """Insere com protocolo único; colisão de protocolo (1 em 2^30 por dia) tenta outro.
    Violação de outra chave única (idempotência, solicitação) propaga."""
    for _ in range(_TENTATIVAS_PROTOCOLO):
        protocolo = gerar_protocolo(agora)
        try:
            with db.begin_nested():
                db.execute(_SQL_INSERIR_PEDIDO, {
                    "id": str(uuid.uuid4()), "protocolo": protocolo, "c": contact_id, "sub_hash": sub_hash,
                    "tipo": tipo, "status": status, "solicitacao_id": solicitacao_id, "chave": chave,
                    "agora": agora, "concluido_em": agora if status == "concluido" else None,
                    "request_id": request_id,
                })
            return protocolo
        except IntegrityError as exc:
            args = getattr(getattr(exc, "orig", None), "args", ())
            if not (args and args[0] == _ER_DUPLICADO and "uq_titular_pedido_protocolo" in str(args[-1])):
                raise
    raise RuntimeError("titular: protocolo único não gerado")


# -------------------------------------------------------------- exportação
def _linhas(db: Session, sql: str, parametros: dict[str, Any]) -> list[Any]:
    return list(db.execute(text(sql), parametros).all())


def _coletar(db: Session, contact_id: str) -> dict[str, Any]:
    c = {"c": contact_id}
    acesso = db.execute(text(
        "SELECT primeiro_acesso_em, ultimo_acesso_em FROM associado WHERE contact_id = :c"), c).first()
    cadastro = db.execute(text(
        "SELECT nome, email, celular, telefone, telefone2, endereco, num_contato, crm, crm_uf, tipo_associado, "
        " status_associativo, data_filiacao, foto_miniatura IS NOT NULL AS tem_foto, atualizado_em "
        "FROM associado_perfil WHERE contact_id = :c"), c).first()
    prefs = db.execute(text(
        "SELECT tratamento, atuacao, temas, canal_preferido, frequencia, fonte, atualizado_em "
        "FROM perfil_declarado WHERE contact_id = :c"), c).first()
    consentimentos = _linhas(db,
        "SELECT finalidade, canal, valor, versao, origem, registrado_em FROM consentimento "
        "WHERE contact_id = :c ORDER BY id DESC LIMIT :n", {**c, "n": _MAX_LINHAS})
    solicitacoes = _linhas(db,
        "SELECT id, tipo_servico, status, dados, criada_em, atualizada_em, concluida_em, avaliacao_nota, "
        " avaliacao_comentario, cancel_motivo FROM solicitacao "
        "WHERE contact_id = :c ORDER BY criada_em DESC, id DESC LIMIT :n", {**c, "n": _MAX_LINHAS})
    eventos: dict[str, list[dict[str, Any]]] = {}
    if solicitacoes:
        sql_eventos = text(
            "SELECT solicitacao_id, ocorrido_em, evento, de_status, para_status, mensagem_publica "
            "FROM solicitacao_evento WHERE solicitacao_id IN :ids ORDER BY ocorrido_em, id LIMIT :n"
        ).bindparams(bindparam("ids", expanding=True))
        for r in db.execute(sql_eventos, {"ids": [s.id for s in solicitacoes], "n": _MAX_EVENTOS_SOLICITACAO}):
            eventos.setdefault(str(r.solicitacao_id), []).append({
                "ocorrido_em": _iso(r.ocorrido_em), "evento": r.evento, "de": r.de_status, "para": r.para_status,
                "mensagem": r.mensagem_publica,
            })
    mensagens = _linhas(db,
        "SELECT registro_id, status, texto, criada_em, enviada_em FROM solicitacao_mensagem "
        "WHERE contact_id = :c AND texto IS NOT NULL ORDER BY criada_em DESC LIMIT :n", {**c, "n": _MAX_LINHAS})
    notificacoes = _linhas(db,
        "SELECT tipo, titulo, corpo, criada_em, lida_em FROM notificacao "
        "WHERE contact_id = :c ORDER BY criada_em DESC, id DESC LIMIT :n", {**c, "n": _MAX_LINHAS})
    comunicacoes = _linhas(db,
        "SELECT gatilho, canal, status, criado_em FROM comunicacao_evento "
        "WHERE contact_id = :c AND destinatario = 'associado' ORDER BY criado_em DESC, id DESC LIMIT :n",
        {**c, "n": _MAX_LINHAS})
    trocas = _linhas(db,
        "SELECT criado_em, usado_em FROM email_verificacao WHERE contact_id = :c ORDER BY id DESC LIMIT :n",
        {**c, "n": 100})
    pedidos = _linhas(db,
        "SELECT protocolo, tipo, status, criado_em, concluido_em FROM titular_pedido "
        "WHERE contact_id = :c ORDER BY criado_em DESC LIMIT :n", {**c, "n": _MAX_LINHAS})
    uso = _linhas(db,
        "SELECT acao, entidade, entidade_id, origem, ocorrido_em FROM evento_uso "
        "WHERE contact_id = :c ORDER BY ocorrido_em DESC, id DESC LIMIT :n", {**c, "n": _MAX_USO + 1})

    return {
        "acessos": None if acesso is None else {
            "primeiro_acesso_em": _iso(acesso.primeiro_acesso_em), "ultimo_acesso_em": _iso(acesso.ultimo_acesso_em)},
        "cadastro": None if cadastro is None else {
            "nome": cadastro.nome, "email": cadastro.email, "celular": cadastro.celular,
            "telefone": cadastro.telefone, "telefone2": cadastro.telefone2, "endereco": _json(cadastro.endereco),
            "matricula": cadastro.num_contato, "crm": cadastro.crm, "crm_uf": cadastro.crm_uf,
            "tipo_associado": cadastro.tipo_associado, "status_associativo": cadastro.status_associativo,
            "data_filiacao": _iso(cadastro.data_filiacao), "tem_foto": bool(cadastro.tem_foto),
            "atualizado_em": _iso(cadastro.atualizado_em)},
        "preferencias": None if prefs is None else {
            "tratamento": prefs.tratamento, "atuacao": _json(prefs.atuacao) or [], "temas": _json(prefs.temas) or [],
            "canal_preferido": prefs.canal_preferido, "frequencia": prefs.frequencia, "fonte": prefs.fonte,
            "atualizado_em": _iso(prefs.atualizado_em)},
        "consentimentos": [{
            "finalidade": r.finalidade, "canal": r.canal, "valor": r.valor, "versao": r.versao, "origem": r.origem,
            "registrado_em": _iso(r.registrado_em)} for r in consentimentos],
        "solicitacoes": [{
            "id": s.id, "tipo": s.tipo_servico, "status": s.status,
            "campos": schemas.campos_publicos(s.tipo_servico, _json(s.dados)),
            "criada_em": _iso(s.criada_em), "atualizada_em": _iso(s.atualizada_em),
            "concluida_em": _iso(s.concluida_em),
            "avaliacao": None if s.avaliacao_nota is None else {
                "nota": int(s.avaliacao_nota), "comentario": s.avaliacao_comentario},
            "motivo_cancelamento": s.cancel_motivo,
            "linha_do_tempo": eventos.get(str(s.id), [])} for s in solicitacoes],
        "mensagens_em_envio": [{
            "solicitacao_id": m.registro_id, "status": m.status, "texto": m.texto, "criada_em": _iso(m.criada_em),
            "enviada_em": _iso(m.enviada_em)} for m in mensagens],
        "notificacoes": [{
            "tipo": n.tipo, "titulo": n.titulo, "corpo": n.corpo, "criada_em": _iso(n.criada_em),
            "lida_em": _iso(n.lida_em)} for n in notificacoes],
        "comunicacoes": [{
            "gatilho": r.gatilho, "canal": r.canal, "status": r.status, "criado_em": _iso(r.criado_em)}
            for r in comunicacoes],
        "trocas_de_email": [{"pedida_em": _iso(r.criado_em), "confirmada_em": _iso(r.usado_em)} for r in trocas],
        "pedidos_titular": [{
            "protocolo": p.protocolo, "tipo": p.tipo, "status": p.status, "criado_em": _iso(p.criado_em),
            "concluido_em": _iso(p.concluido_em)} for p in pedidos],
        "uso": {
            "itens": [{"acao": u.acao, "entidade": u.entidade, "entidade_id": u.entidade_id, "origem": u.origem,
                       "ocorrido_em": _iso(u.ocorrido_em)} for u in uso[:_MAX_USO]],
            "truncado": len(uso) > _MAX_USO,
        },
    }


_SQL_ULTIMA_EXPORTACAO = text(
    "SELECT MAX(criado_em) FROM titular_pedido WHERE contact_id = :c AND tipo = 'exportacao' AND criado_em > :desde"
)


def exportar(*, contact_id: str, sub_hash: str, request_id: str | None = None,
             demonstracao: bool = False) -> Exportacao:
    """Monta o arquivo e registra o pedido (já concluído) na MESMA transação: se
    a montagem falhar, nada é contado contra o limite."""
    agora = _agora()
    with _sessao() as db:
        limites_negocio.bloquear_associado(db, contact_id)
        ultima = db.execute(_SQL_ULTIMA_EXPORTACAO, {"c": contact_id, "desde": agora - EXPORTACAO_INTERVALO}).scalar()
        if ultima is not None:
            raise LimiteExportacao(ultima + EXPORTACAO_INTERVALO)
        protocolo = _inserir_pedido(db, contact_id=contact_id, sub_hash=sub_hash, tipo="exportacao",
                                    status="concluido", agora=agora, request_id=request_id)
        dados = _coletar(db, contact_id)
    observacoes = list(OBSERVACOES_EXPORTACAO)
    if demonstracao:
        observacoes.append("A área está em fase de construção: contato, endereço e foto podem ser de demonstração.")
    return Exportacao(protocolo, {"formato": FORMATO_EXPORTACAO, "gerado_em": _iso(agora), "protocolo": protocolo,
                                  "observacoes": observacoes, **dados})


# ---------------------------------------------------------------- exclusão
_SQL_PEDIDO_DA_SOLICITACAO = text(
    "SELECT protocolo, criado_em FROM titular_pedido WHERE solicitacao_id = :s AND contact_id = :c"
)


def pedir_exclusao(*, contact_id: str, sub_hash: str, chave_idempotencia: str,
                   request_id: str | None = None) -> PedidoExclusao:
    """Abre a solicitação `exclusao_dados` (idempotente pela chave; uma aberta por
    associado) e registra o pedido do titular com protocolo.

    Duas transações, nesta ordem, ambas idempotentes: a solicitação nasce pelo
    caminho único de criação (`servico.criar`, com notificação e trilha); o
    pedido do titular é único por solicitação. Se a segunda falhar, repetir a
    chamada com a mesma chave devolve a mesma solicitação e completa o pedido.
    Levanta as exceções de `servico.criar` (`PedidoAbertoExistente`, ...)."""
    criacao = servico.criar(contact_id=contact_id, sub_hash=sub_hash, tipo_servico="exclusao_dados",
                            campos=schemas.validar("exclusao_dados", {}), chave_idempotencia=chave_idempotencia,
                            request_id=request_id)
    agora = _agora()
    with _sessao() as db:
        limites_negocio.bloquear_associado(db, contact_id)
        existente = db.execute(_SQL_PEDIDO_DA_SOLICITACAO, {"s": criacao.id, "c": contact_id}).first()
        if existente is not None:
            return PedidoExclusao(existente.protocolo, criacao.id, existente.criado_em, False)
        try:
            protocolo = _inserir_pedido(db, contact_id=contact_id, sub_hash=sub_hash, tipo="exclusao",
                                        status="registrado", agora=agora, solicitacao_id=criacao.id,
                                        chave=chave_idempotencia.lower(), request_id=request_id)
        except IntegrityError:
            # Corrida sem a linha de `associado` (sem o bloqueio): o outro pedido venceu.
            existente = db.execute(_SQL_PEDIDO_DA_SOLICITACAO, {"s": criacao.id, "c": contact_id}).first()
            if existente is None:
                raise
            return PedidoExclusao(existente.protocolo, criacao.id, existente.criado_em, False)
    return PedidoExclusao(protocolo, criacao.id, agora, True)


# ----------------------------------------------------------------- leitura
_SQL_PEDIDOS = text(
    "SELECT p.protocolo, p.tipo, p.status, p.criado_em, p.concluido_em, p.solicitacao_id, s.status AS sol_status "
    "FROM titular_pedido p LEFT JOIN solicitacao s ON s.id = p.solicitacao_id "
    "WHERE p.contact_id = :c ORDER BY p.criado_em DESC LIMIT 20"
)
_ABERTOS = ("registrado", "em_analise")


def _status_efetivo(status: str, sol_status: str | None) -> str:
    """O associado pode cancelar a solicitação antes da análise; o pedido do
    titular não é alterado pela aplicação (sem UPDATE), então o cancelamento é
    lido da solicitação. O script do operador confere a mesma coisa."""
    if status in _ABERTOS and sol_status == "cancelada":
        return "cancelado"
    return status


def listar_pedidos(contact_id: str) -> dict[str, Any]:
    agora = _agora()
    with _sessao() as db:
        linhas = db.execute(_SQL_PEDIDOS, {"c": contact_id}).all()
    itens = [{
        "protocolo": r.protocolo, "tipo": r.tipo, "status": _status_efetivo(r.status, r.sol_status),
        "criado_em": _iso(r.criado_em), "concluido_em": _iso(r.concluido_em), "solicitacao_id": r.solicitacao_id,
    } for r in linhas]
    ultima = max((r.criado_em for r in linhas if r.tipo == "exportacao"), default=None)
    libera = ultima + EXPORTACAO_INTERVALO if ultima is not None and ultima + EXPORTACAO_INTERVALO > agora else None
    aberta = next((i for i in itens if i["tipo"] == "exclusao" and i["status"] in _ABERTOS), None)
    return {"itens": itens, "exportacao_disponivel_em": _iso(libera), "exclusao_aberta": aberta}
