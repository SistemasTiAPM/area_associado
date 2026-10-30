"""Ajuda e atendimento (P14; REQUISITOS §3.15 RF-AJ-01/02; TI-20).

- **FAQ** (`faq`, sql/013): só as publicadas, cache por processo de 60 s
  (despublicar some sem deploy em até 1 min). Busca normalizada sem acento e
  sem caixa, todos os termos significativos precisam aparecer (pergunta,
  resposta ou rótulo da categoria); pergunta pesa mais. Sem resultado ⇒
  sugere categorias. O termo buscado nunca é gravado (RF-SH-14).
- **Contato da Central**: WhatsApp de `Settings.WHATSAPP_CENTRAL` (sem dado
  pessoal na URL), telefone e horário de `parametro` (vazio = o bloco some).

Bloqueante (SQL): chamar de rota async via `run_in_threadpool`.
"""

from __future__ import annotations

import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..config import get_settings
from .solicitacoes import parametros
from .solicitacoes.schemas import texto_livre

logger = logging.getLogger("area_associado.ajuda")

TTL_FAQ_S = 60.0
Q_MAX = 80
SUGESTOES_MAX = 3

# Ordem e rótulos das categorias conhecidas; código novo no banco aparece com
# rótulo derivado do próprio código, depois das conhecidas.
CATEGORIAS: dict[str, str] = {
    "acesso": "Acesso e senha",
    "beneficios": "Benefícios",
    "solicitacoes": "Solicitações",
    "carteirinha": "Carteirinha",
    "cadastro": "Cadastro",
    "financeiro": "Financeiro",
    "eventos": "Eventos",
    "privacidade": "Privacidade",
    "cancelamento": "Cancelamento",
    "outros": "Outros assuntos",
}

_STOPWORDS = frozenset(
    "a o as os e de da das do dos em no na nos nas um uma uns umas para pra por com sem que como qual quais "
    "eu meu minha meus minhas me se ao aos ou ser ter sobre onde quando posso pode preciso".split()
)
_RE_NAO_ALFANUM = re.compile(r"[^0-9a-z]+")
_RE_CATEGORIA = re.compile(r"^[a-z][a-z0-9_]{1,31}$")

MENSAGEM_WHATSAPP = "Olá. Vim pela Minha APM e quero falar com a Central de Relacionamento."


class FaqIndisponivel(Exception):
    """Banco fora ao carregar a FAQ (sem cache válido)."""


def normalizar(texto_bruto: str) -> str:
    """Minúsculas, sem acento, só letras/dígitos separados por um espaço."""
    decomposto = unicodedata.normalize("NFKD", texto_bruto.casefold())
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(_RE_NAO_ALFANUM.sub(" ", sem_acento).split())


def termos(q: str) -> list[str]:
    """Termos significativos da busca: sem stopwords, plural simples aparado."""
    saida: list[str] = []
    for t in normalizar(q).split():
        if t in _STOPWORDS or len(t) < 2:
            continue
        if len(t) > 4 and t.endswith("s"):
            t = t[:-1]
        if t not in saida:
            saida.append(t)
    return saida[:12]


def rotulo_categoria(codigo: str) -> str:
    return CATEGORIAS.get(codigo) or codigo.replace("_", " ").capitalize()


def _ordem_categoria(codigo: str) -> tuple[int, str]:
    chaves = list(CATEGORIAS)
    return (chaves.index(codigo), "") if codigo in CATEGORIAS else (len(chaves), codigo)


@dataclass(frozen=True)
class Pergunta:
    id: int
    categoria: str
    pergunta: str
    resposta: str
    ordem: int
    busca_pergunta: str
    busca_resto: str


_lock = threading.Lock()
_cache: tuple[float, tuple[Pergunta, ...]] | None = None


def _ler_faq() -> list[Any]:
    from ..database import session_scope  # import tardio: testes substituem esta função

    with session_scope() as db:
        return list(db.execute(text(
            "SELECT id, categoria, pergunta, resposta, ordem FROM faq WHERE publicada = 1 ORDER BY ordem, id"
        )).all())


def carregar() -> tuple[Pergunta, ...]:
    global _cache
    agora = time.monotonic()
    with _lock:
        if _cache is not None and agora - _cache[0] < TTL_FAQ_S:
            return _cache[1]
    try:
        linhas = _ler_faq()
    except SQLAlchemyError as exc:
        logger.error("ajuda: leitura da FAQ falhou (%s)", type(exc).__name__)
        raise FaqIndisponivel() from exc
    itens = []
    for r in linhas:
        categoria = str(r.categoria)
        if not _RE_CATEGORIA.match(categoria):
            continue
        pergunta, resposta = str(r.pergunta).strip(), str(r.resposta).strip()
        itens.append(Pergunta(int(r.id), categoria, pergunta, resposta, int(r.ordem), normalizar(pergunta),
                              normalizar(f"{resposta} {rotulo_categoria(categoria)}")))
    resultado = tuple(itens)
    with _lock:
        _cache = (agora, resultado)
    return resultado


def limpar_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def _pontuar(p: Pergunta, ts: list[str]) -> int | None:
    pontos = 0
    for t in ts:
        if t in p.busca_pergunta:
            pontos += 3
        elif t in p.busca_resto:
            pontos += 1
        else:
            return None
    return pontos


def _sugestoes(ts: list[str], perguntas: tuple[Pergunta, ...]) -> list[str]:
    contagem: dict[str, int] = {}
    for p in perguntas:
        contagem[p.categoria] = contagem.get(p.categoria, 0) + 1
    if not contagem:
        return []
    proximas = [c for c in contagem
                if any(t[:3] in normalizar(f"{c} {rotulo_categoria(c)}") for t in ts if len(t) >= 3)]
    if proximas:
        return sorted(proximas, key=_ordem_categoria)[:SUGESTOES_MAX]
    return sorted(contagem, key=lambda c: (-contagem[c], _ordem_categoria(c)))[:SUGESTOES_MAX]


def buscar(q: str | None = None, categoria: str | None = None,
           perguntas: tuple[Pergunta, ...] | None = None) -> dict[str, Any]:
    """`{categorias, itens, sugestoes}` no contrato de `GET /ajuda/faq`."""
    todas = carregar() if perguntas is None else perguntas
    categorias = sorted({p.categoria for p in todas}, key=_ordem_categoria)
    candidatas = [p for p in todas if categoria is None or p.categoria == categoria]
    ts = termos(q or "")
    if ts:
        pontuadas = [(s, p) for p in candidatas if (s := _pontuar(p, ts)) is not None]
        pontuadas.sort(key=lambda sp: (-sp[0], _ordem_categoria(sp[1].categoria), sp[1].ordem, sp[1].id))
        escolhidas = [p for _, p in pontuadas]
    else:
        escolhidas = sorted(candidatas, key=lambda p: (_ordem_categoria(p.categoria), p.ordem, p.id))
    return {
        "categorias": [{"codigo": c, "rotulo": rotulo_categoria(c)} for c in categorias],
        "itens": [{"id": p.id, "pergunta": p.pergunta, "resposta": p.resposta, "categoria": p.categoria}
                  for p in escolhidas],
        "sugestoes": _sugestoes(ts, todas) if ts and not escolhidas else [],
    }


# ------------------------------------------------------------------ contato
def _formatar_nacional(digitos: str) -> str | None:
    """DDD + número (10 ou 11 dígitos) → '(11) 3188-6200' / '(11) 98888-7777'."""
    if len(digitos) not in (10, 11) or digitos[0] == "0":
        return None
    ddd, numero = digitos[:2], digitos[2:]
    meio = 5 if len(numero) == 9 else 4
    return f"({ddd}) {numero[:meio]}-{numero[meio:]}"


def whatsapp() -> dict[str, str] | None:
    s = get_settings()
    numero = s.whatsapp_central
    if not s.show_whatsapp or not numero:
        return None
    exibicao = _formatar_nacional(numero[2:]) if numero.startswith("55") else None
    return {
        "exibicao": exibicao or f"+{numero}",
        "url": f"https://wa.me/{numero}?text={quote(MENSAGEM_WHATSAPP, safe='')}",
    }


def telefone(bruto: str | None) -> dict[str, str] | None:
    if not bruto:
        return None
    digitos = "".join(c for c in bruto if c.isdigit())
    if digitos.startswith("0800") and len(digitos) == 11:
        return {"exibicao": f"0800 {digitos[4:7]} {digitos[7:]}", "uri": f"tel:{digitos}"}
    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    exibicao = _formatar_nacional(digitos)
    if exibicao is None:
        logger.error("ajuda: parametro central_telefone em formato inválido; bloco omitido")
        return None
    return {"exibicao": exibicao, "uri": f"tel:+55{digitos}"}


def horario(bruto: str | None) -> str | None:
    if not bruto:
        return None
    try:
        return texto_livre(bruto, maximo=120)
    except ValueError:
        logger.error("ajuda: parametro central_horario inválido; bloco omitido")
        return None


def contato() -> dict[str, Any]:
    """`GET /ajuda/contato`. Nunca lança: parâmetro ausente = bloco omitido."""
    return {
        "whatsapp": whatsapp(),
        "telefone": telefone(parametros.texto_cacheado("central_telefone")),
        "horario": horario(parametros.texto_cacheado("central_horario")),
    }


def contato_resumo() -> dict[str, str] | None:
    """`contato` da solicitação (RF-SO-15): canal da Central, como texto."""
    w = whatsapp()
    if w is not None:
        return {"canal": "whatsapp", "texto": f"Central de Relacionamento · WhatsApp {w['exibicao']}"}
    t = telefone(parametros.texto_cacheado("central_telefone"))
    if t is not None:
        return {"canal": "telefone", "texto": f"Central de Relacionamento · {t['exibicao']}"}
    return None
