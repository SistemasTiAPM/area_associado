"""Perfil declarado e perfil progressivo (P13, ADR-0026; `sql/017`).

`perfil_declarado` guarda o que o associado DIZ de si — não é cadastro (o
cadastro é do CRM). Catálogos fechados aqui; valor fora deles é recusado:

- tratamento: "como prefere ser chamado" (DEC-26). Vazio = saudação neutra.
- atuação: as seis áreas da spec v2 (P13).
- temas: lista PROVISÓRIA, igual às oito categorias de benefícios (a spec não
  enumera os temas — pendência com a agência).
- canal preferido: só os que existem (regra 19). Hoje, e-mail; WhatsApp e SMS
  entram quando houver canal contratado (P-64).
- frequência (`normal` ou `minima`, REQUISITOS §9.1) e tamanho de fonte (DEC-27:
  no servidor, nunca em `localStorage`).

Especialidade e regional NÃO são declaradas aqui: vêm do CRM (P-56).

Perfil progressivo: "uma pergunta por visita". A próxima pergunta é o primeiro
campo sem resposta que não foi pulado há pouco; pulada `PULAR_MAX` vezes, para
de aparecer (continua editável no perfil).

Bloqueante (SQL): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("area_associado.preferencias")

ATUACAO: dict[str, str] = {
    "consultorio_proprio": "Consultório próprio",
    "hospital": "Hospital",
    "plantao": "Plantão",
    "pesquisa": "Pesquisa",
    "gestao": "Gestão",
    "docencia": "Docência",
}
TEMAS: dict[str, str] = {
    "tecnologia_ia": "Tecnologia e IA",
    "consultorio_pratica": "Consultório e prática",
    "saude_bem_estar": "Saúde mental e bem-estar",
    "financas_protecao": "Finanças e proteção",
    "educacao_carreira": "Educação e carreira",
    "defesa_juridico": "Defesa e jurídico",
    "comunidade": "Comunidade",
    "vida_lazer": "Vida e lazer",
}
CANAL_PREFERIDO: dict[str, str] = {"email": "E-mail"}
FREQUENCIA: dict[str, str] = {"normal": "Todas as novidades", "minima": "Só o essencial"}
FONTE: dict[str, str] = {"padrao": "Padrão", "grande": "Grande", "maior": "Maior"}
FONTE_PADRAO = "padrao"

TRATAMENTO_MAX = 40
PULAR_MAX = 3
PULAR_INTERVALO = timedelta(days=30)

# Campo → catálogo (lista) ou None (valor único / texto). Ordem = ordem de gravação.
_LISTAS: dict[str, dict[str, str]] = {"atuacao": ATUACAO, "temas": TEMAS}
_COLUNAS: tuple[str, ...] = ("tratamento", "atuacao", "temas", "canal_preferido", "frequencia", "fonte")
# Campos que contam para "complete seu perfil" (fonte tem padrão; não é pergunta).
CAMPOS_PERFIL: tuple[str, ...] = ("tratamento", "atuacao", "temas", "frequencia")

# Letras (com acento), espaço, ponto, apóstrofo e hífen. Sem dígito (barra CPF e
# telefone), sem marcação e sem controle — mesmo critério do CHECK da sql/017.
_RE_TRATAMENTO = re.compile(r"^[^\W\d_](?:[^\W\d_]|[ .'’-])*$")


class PreferenciaInvalida(ValueError):
    """400 `entrada_invalida` com `detalhes [{campo, mensagem}]`."""

    def __init__(self, campo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.detalhes = [{"campo": campo, "mensagem": mensagem}]


class PerguntaDesconhecida(LookupError):
    """404 `nao_encontrado`."""


@dataclass(frozen=True)
class Preferencias:
    tratamento: str | None = None
    atuacao: tuple[str, ...] = ()
    temas: tuple[str, ...] = ()
    canal_preferido: str | None = None
    frequencia: str | None = None
    fonte: str = FONTE_PADRAO
    atualizado_em: datetime | None = None

    def faltam(self) -> list[str]:
        return [campo for campo in CAMPOS_PERFIL if not getattr(self, campo)]


@dataclass(frozen=True)
class Pergunta:
    chave: str
    titulo: str
    ajuda: str
    tipo: str                      # texto | multipla | unica
    opcoes: dict[str, str] = field(default_factory=dict)
    maximo: int | None = None


PERGUNTAS: tuple[Pergunta, ...] = (
    Pergunta("tratamento", "Como prefere ser chamado?",
             "Usamos na saudação e nas mensagens. Por exemplo: Dra. Ana.", "texto", maximo=TRATAMENTO_MAX),
    Pergunta("atuacao", "Onde você atua?",
             "Com isso, mostramos primeiro os benefícios que fazem sentido para a sua rotina.", "multipla", ATUACAO),
    Pergunta("temas", "Quais temas interessam a você?",
             "Com isso, as recomendações e as notícias ficam mais próximas do que você procura.", "multipla", TEMAS),
    Pergunta("frequencia", "Quanto quer receber de novidades?",
             "Avisos sobre seus pedidos e pagamentos chegam sempre, qualquer que seja a escolha.", "unica",
             FREQUENCIA),
)
_PERGUNTA_POR_CHAVE: dict[str, Pergunta] = {p.chave: p for p in PERGUNTAS}


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sessao():
    from ..database import session_scope  # import tardio: testes substituem funções deste módulo

    return session_scope()


# ---------------------------------------------------------------- validação
def validar_tratamento(valor: Any) -> str | None:
    """Texto normalizado ou None (vazio = saudação neutra)."""
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise PreferenciaInvalida("tratamento", "informe um texto")
    limpo = " ".join(unicodedata.normalize("NFC", valor).split())
    if not limpo:
        return None
    if len(limpo) < 2 or len(limpo) > TRATAMENTO_MAX:
        raise PreferenciaInvalida("tratamento", f"use de 2 a {TRATAMENTO_MAX} caracteres")
    if not _RE_TRATAMENTO.match(limpo):
        raise PreferenciaInvalida("tratamento", "use só letras, espaço, ponto e hífen")
    return limpo


def _validar_lista(campo: str, valor: Any) -> tuple[str, ...]:
    catalogo = _LISTAS[campo]
    if valor is None:
        return ()
    if not isinstance(valor, (list, tuple)) or len(valor) > len(catalogo):
        raise PreferenciaInvalida(campo, "lista inválida")
    vistos: list[str] = []
    for item in valor:
        if not isinstance(item, str) or item not in catalogo:
            raise PreferenciaInvalida(campo, "opção inválida")
        if item not in vistos:
            vistos.append(item)
    # Ordem do catálogo: a mesma escolha grava sempre o mesmo JSON.
    return tuple(chave for chave in catalogo if chave in vistos)


def _validar_enum(campo: str, valor: Any, catalogo: dict[str, str], *, obrigatorio: bool) -> str | None:
    if valor is None:
        if obrigatorio:
            raise PreferenciaInvalida(campo, "obrigatório")
        return None
    if not isinstance(valor, str) or valor not in catalogo:
        raise PreferenciaInvalida(campo, "opção inválida")
    return valor


def validar(campos: dict[str, Any]) -> dict[str, Any]:
    """Normaliza os campos enviados (só os de `_COLUNAS`). Ausente = não muda."""
    if not isinstance(campos, dict) or not campos:
        raise PreferenciaInvalida("preferencias", "nada para alterar")
    saida: dict[str, Any] = {}
    for campo, valor in campos.items():
        if campo == "tratamento":
            saida[campo] = validar_tratamento(valor)
        elif campo in _LISTAS:
            saida[campo] = _validar_lista(campo, valor)
        elif campo == "frequencia":
            saida[campo] = _validar_enum(campo, valor, FREQUENCIA, obrigatorio=False)
        elif campo == "canal_preferido":
            saida[campo] = _validar_enum(campo, valor, CANAL_PREFERIDO, obrigatorio=False)
        elif campo == "fonte":
            saida[campo] = _validar_enum(campo, valor, FONTE, obrigatorio=True)
        else:
            raise PreferenciaInvalida(str(campo)[:32], "campo não permitido")
    return saida


# ------------------------------------------------------------------ leitura
_SQL_LER = text(
    "SELECT tratamento, atuacao, temas, canal_preferido, frequencia, fonte, atualizado_em "
    "FROM perfil_declarado WHERE contact_id = :c"
)


def _lista_do_banco(campo: str, valor: Any) -> tuple[str, ...]:
    if valor is None:
        return ()
    if isinstance(valor, (str, bytes)):
        try:
            valor = json.loads(valor)
        except ValueError:
            return ()
    if not isinstance(valor, list):
        return ()
    catalogo = _LISTAS[campo]
    # Opção retirada do catálogo deixa de aparecer, sem erro.
    return tuple(chave for chave in catalogo if chave in valor)


def _da_linha(linha: Any) -> Preferencias:
    if linha is None:
        return Preferencias()
    return Preferencias(
        tratamento=linha.tratamento or None,
        atuacao=_lista_do_banco("atuacao", linha.atuacao),
        temas=_lista_do_banco("temas", linha.temas),
        canal_preferido=linha.canal_preferido if linha.canal_preferido in CANAL_PREFERIDO else None,
        frequencia=linha.frequencia if linha.frequencia in FREQUENCIA else None,
        fonte=linha.fonte if linha.fonte in FONTE else FONTE_PADRAO,
        atualizado_em=linha.atualizado_em,
    )


def ler(contact_id: str) -> Preferencias:
    with _sessao() as db:
        return _da_linha(db.execute(_SQL_LER, {"c": contact_id}).first())


def resumo_sessao(contact_id: str | None) -> dict[str, Any]:
    """Tamanho de fonte e tratamento para `GET /sessao`. Nunca lança: com banco
    fora ou sem a `sql/017`, vale o padrão (a área não depende disto)."""
    padrao = {"fonte": FONTE_PADRAO, "tratamento": None}
    if not contact_id:
        return padrao
    try:
        p = ler(contact_id)
    except SQLAlchemyError as exc:
        logger.error("preferencias: leitura para a sessão falhou (%s)", type(exc).__name__)
        return padrao
    return {"fonte": p.fonte, "tratamento": p.tratamento}


# ------------------------------------------------------------------ escrita
def _para_banco(campo: str, valor: Any) -> Any:
    if campo in _LISTAS:
        return json.dumps(list(valor), ensure_ascii=False, separators=(",", ":")) if valor else None
    return valor


def _sql_gravar(campos: tuple[str, ...]):
    """INSERT ... ON DUPLICATE KEY UPDATE só das colunas enviadas. Os nomes vêm
    de `_COLUNAS` (constante), nunca do chamador (regra 2)."""
    for campo in campos:
        if campo not in _COLUNAS:  # defesa: `validar` já recusou
            raise ValueError(f"coluna fora da allowlist: {campo!r}")
    colunas = ", ".join(campos)
    valores = ", ".join(f":{c}" for c in campos)
    atualiza = ", ".join(f"{c} = novo.{c}" for c in campos)
    return text(
        f"INSERT INTO perfil_declarado (contact_id, {colunas}, criado_em, atualizado_em) "
        f"VALUES (:contact_id, {valores}, :agora, :agora) AS novo "
        f"ON DUPLICATE KEY UPDATE {atualiza}, atualizado_em = novo.atualizado_em"
    )


def salvar(contact_id: str, campos: dict[str, Any]) -> tuple[Preferencias, list[str]]:
    """Grava os campos JÁ validados por `validar`. Devolve o estado e os nomes
    dos campos que mudaram de fato (base do `evento_uso`)."""
    ordenados = tuple(c for c in _COLUNAS if c in campos)
    if not ordenados:
        raise PreferenciaInvalida("preferencias", "nada para alterar")
    with _sessao() as db:
        antes = _da_linha(db.execute(_SQL_LER, {"c": contact_id}).first())
        mudou = [c for c in ordenados if getattr(antes, c) != campos[c]]
        if mudou:
            parametros = {c: _para_banco(c, campos[c]) for c in ordenados}
            parametros.update({"contact_id": contact_id, "agora": _agora()})
            db.execute(_sql_gravar(ordenados), parametros)
        depois = _da_linha(db.execute(_SQL_LER, {"c": contact_id}).first())
    return depois, mudou


# ------------------------------------------------------- perfil progressivo
_SQL_PULADAS = text("SELECT chave, pulada_em, vezes FROM pergunta_perfil WHERE contact_id = :c")
_SQL_PULAR = text(
    "INSERT INTO pergunta_perfil (contact_id, chave, pulada_em, vezes) VALUES (:c, :chave, :agora, 1) AS novo "
    "ON DUPLICATE KEY UPDATE pulada_em = novo.pulada_em, vezes = LEAST(pergunta_perfil.vezes + 1, 50)"
)


def pergunta(chave: str) -> Pergunta:
    achada = _PERGUNTA_POR_CHAVE.get(chave)
    if achada is None:
        raise PerguntaDesconhecida(chave)
    return achada


def _escolher(prefs: Preferencias, puladas: dict[str, tuple[datetime, int]], agora: datetime) -> Pergunta | None:
    for p in PERGUNTAS:
        if getattr(prefs, p.chave):
            continue
        pulo = puladas.get(p.chave)
        if pulo is not None and (pulo[1] >= PULAR_MAX or agora - pulo[0] < PULAR_INTERVALO):
            continue
        return p
    return None


def proxima_pergunta(contact_id: str) -> Pergunta | None:
    """Primeira pergunta sem resposta que não foi pulada há pouco (ou vezes demais)."""
    with _sessao() as db:
        prefs = _da_linha(db.execute(_SQL_LER, {"c": contact_id}).first())
        puladas = {str(r.chave): (r.pulada_em, int(r.vezes)) for r in db.execute(_SQL_PULADAS, {"c": contact_id})}
    return _escolher(prefs, puladas, _agora())


def pular(contact_id: str, chave: str) -> None:
    pergunta(chave)
    with _sessao() as db:
        db.execute(_SQL_PULAR, {"c": contact_id, "chave": chave, "agora": _agora()})


def responder(contact_id: str, chave: str, resposta: Any) -> tuple[Preferencias, list[str]]:
    """Resposta de uma pergunta = gravação do campo correspondente. Resposta
    vazia não vale como resposta: para não responder, existe `pular`."""
    p = pergunta(chave)
    campos = validar({p.chave: resposta})
    if not campos[p.chave]:
        raise PreferenciaInvalida(p.chave, "escolha uma opção ou pule a pergunta")
    return salvar(contact_id, campos)


def opcoes() -> dict[str, list[dict[str, str]]]:
    def lista(catalogo: dict[str, str]) -> list[dict[str, str]]:
        return [{"valor": valor, "rotulo": rotulo} for valor, rotulo in catalogo.items()]

    return {"atuacao": lista(ATUACAO), "temas": lista(TEMAS), "canal_preferido": lista(CANAL_PREFERIDO),
            "frequencia": lista(FREQUENCIA), "fonte": lista(FONTE)}
