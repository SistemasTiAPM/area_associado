"""Allowlist de campos por `tipo_servico`, validação e normalização (REQUISITOS §7.4, §9.0).

Regras para todo texto livre (regra 13, ADR-0014, REQUISITOS §7.6):
- normalizado (NFC, espaços colapsados; quebra de linha só onde é multilinha);
- sem caracteres de controle nem de formatação invisível/bidirecional;
- sem HTML (tag, comentário ou entidade) — a SPA renderiza texto puro, mas o
  CRM e o e-mail transacional não precisam receber marcação;
- sem CPF (mesmo padrão do CHECK do banco): a aplicação recusa com 400 antes
  de o banco recusar com erro de integridade.

Mensagens de erro listam o campo e o motivo, **nunca o valor recebido**.
Funções puras (sem banco): testáveis isoladamente.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from . import catalogo_crm, rotulos

DADOS_MAX_BYTES = 16 * 1024

# Mesmo padrão dos CHECKs (sql/004, sql/010): CPF com ou sem pontuação,
# delimitado por não-hex para não pegar dentro de UUID/sha256.
RE_CPF = re.compile(r"(^|[^0-9a-fA-F])[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}([^0-9a-fA-F]|$)")
_RE_HTML = re.compile(r"<\s*[A-Za-z!/?]|&#?[A-Za-z0-9]{1,10};")
_RE_INVISIVEL = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁠-⁤⁦-⁩﻿]"
)
_RE_NOME_PROPRIO = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ '\-][A-Za-zÀ-ÖØ-öø-ÿ]+)*$")
_RE_CHAVE_CAMPO = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class EntradaInvalida(Exception):
    """400 `entrada_invalida` com `detalhes [{campo, mensagem}]` (sem valores)."""

    def __init__(self, detalhes: list[dict[str, str]], mensagem: str | None = None) -> None:
        super().__init__("entrada_invalida")
        self.detalhes = detalhes[:20]
        self.mensagem = mensagem


# Texto livre que vai ao CRM (ADR-0023): medido em unidades UTF-16, como o Dataverse
# (e o `maxLength` do navegador) contam — emoji vale 2. Com o cabeçalho e os rótulos
# de `crm.descricao`, assunto + mensagem do tipo `outro` cabem nas 2000 da descrição.
ASSUNTO_OUTRO_MAX = 120
MENSAGEM_OUTRO_MAX = 1700
# Tipos do catálogo comum com o App (ADR-0024): formulário único, o texto do associado É
# a descrição no CRM (10–2000 unidades UTF-16, limites do hub). Mensagem da conversa: 2–2000.
MENSAGEM_CATALOGO_MIN, MENSAGEM_CATALOGO_MAX = 10, 2000
MENSAGEM_CONVERSA_MIN, MENSAGEM_CONVERSA_MAX = 2, 2000


def unidades_utf16(texto: str) -> int:
    return len(texto.encode("utf-16-le")) // 2


# ---------------------------------------------------------------- texto
def texto_livre(valor: Any, *, minimo: int = 1, maximo: int, multilinha: bool = False,
                utf16: bool = False) -> str:
    """Normaliza e valida um texto do associado. `ValueError` com motivo fixo.
    `utf16=True`: o máximo conta unidades UTF-16 (texto que vai ao CRM)."""
    if not isinstance(valor, str):
        raise ValueError("deve ser texto")
    v = unicodedata.normalize("NFC", valor).replace("\r\n", "\n").replace("\r", "\n")
    if _RE_INVISIVEL.search(v.replace("\n", "").replace("\t", "")):
        raise ValueError("contém caracteres inválidos")
    if multilinha:
        linhas = [" ".join(linha.split()) for linha in v.split("\n")]
        v = re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()
    else:
        v = " ".join(v.split())
    if len(v) < minimo:
        raise ValueError("obrigatório" if minimo == 1 else f"mínimo de {minimo} caracteres")
    if (unidades_utf16(v) if utf16 else len(v)) > maximo:
        raise ValueError(f"máximo de {maximo} caracteres")
    if _RE_HTML.search(v):
        raise ValueError("não use marcação HTML")
    if RE_CPF.search(v):
        raise ValueError("não informe CPF nem números de documento")
    return v


def _texto(maximo: int, minimo: int = 1, multilinha: bool = False, utf16: bool = False) -> Callable[[Any], str]:
    return lambda v: texto_livre(v, minimo=minimo, maximo=maximo, multilinha=multilinha, utf16=utf16)


def _enum(opcoes: Mapping[str, str]) -> Callable[[Any], str]:
    def validar(v: Any) -> str:
        if not isinstance(v, str) or v not in opcoes:
            raise ValueError("opção inválida")
        return v

    return validar


def _booleano(v: Any) -> bool:
    if not isinstance(v, bool):
        raise ValueError("deve ser verdadeiro ou falso")
    return v


def _nome_proprio(v: Any) -> str:
    s = texto_livre(v, minimo=2, maximo=80)
    if not _RE_NOME_PROPRIO.match(s):
        raise ValueError("use só letras, espaço, apóstrofo e hífen")
    return s


FUSO = ZoneInfo("America/Sao_Paulo")


def hoje_sp() -> date:
    return datetime.now(FUSO).date()


def _data_nascimento(v: Any, hoje: date | None = None) -> str:
    if not isinstance(v, str) or not _RE_DATA.match(v):
        raise ValueError("data inválida: use AAAA-MM-DD")
    try:
        d = date.fromisoformat(v)
    except ValueError as exc:
        raise ValueError("data inválida") from exc
    hoje = hoje or hoje_sp()
    idade = hoje.year - d.year - ((hoje.month, hoje.day) < (d.month, d.day))
    if not 16 <= idade <= 110:
        raise ValueError("data fora do intervalo aceito")
    return d.isoformat()


_CAMPOS_CADASTRO: dict[str, Callable[[Any], str]] = {
    "nome": _nome_proprio,
    "sobrenome": _nome_proprio,
    "data_nascimento": _data_nascimento,
    "sexo": _enum(rotulos.SEXO),
}


def _alteracoes(v: Any) -> dict[str, str]:
    """`{campo: novo_valor}`, campos do regime "com aprovação" (REQUISITOS §9.0)."""
    if not isinstance(v, dict) or not v:
        raise ValueError("informe ao menos um campo para alterar")
    saida: dict[str, str] = {}
    for campo, novo in v.items():
        if campo not in _CAMPOS_CADASTRO:
            raise ValueError("campo do cadastro não alterável por aqui")
        try:
            saida[campo] = _CAMPOS_CADASTRO[campo](novo)
        except ValueError as exc:
            raise ValueError(f"{rotulos.CAMPO_CADASTRO[campo].lower()}: {exc}") from exc
    return dict(sorted(saida.items()))


# --------------------------------------------------------------- schemas
@dataclass(frozen=True)
class Campo:
    nome: str
    obrigatorio: bool
    validar: Callable[[Any], Any]


SCHEMAS: dict[str, tuple[Campo, ...]] = {
    "outro": (
        Campo("assunto", True, _texto(ASSUNTO_OUTRO_MAX, utf16=True)),
        Campo("mensagem", True, _texto(MENSAGEM_OUTRO_MAX, multilinha=True, utf16=True)),
        Campo("categoria", False, _enum(rotulos.ASSUNTO_FORMULARIO)),
    ),
    "declaracao_associado": (
        Campo("finalidade", True, _enum(rotulos.FINALIDADE_DECLARACAO)),
        Campo("observacao", False, _texto(200)),
    ),
    "alteracao_cadastro": (
        Campo("alteracoes", True, _alteracoes),
        Campo("justificativa", False, _texto(500, multilinha=True)),
    ),
    "cancelamento_associacao": (
        Campo("motivo", True, _enum(rotulos.MOTIVO_CANCELAMENTO)),
        Campo("quer_conversa", True, _booleano),
        Campo("comentario", False, _texto(500, multilinha=True)),
    ),
    # Tipos sem formulário nesta onda (criados por outras telas/fases); a
    # allowlist já fica fechada para quando a rota existir.
    "diagnostico_marketing": (),
    "submeter_trabalho": (Campo("titulo", False, _texto(200)),),
    "mentoria_pedir": (Campo("area_interesse", False, _texto(120)),),
    "mentoria_oferecer": (Campo("area_interesse", False, _texto(120)),),
    "cartao_apm": (),
    "exclusao_dados": (),
    **{slug: (Campo("mensagem", True, _texto(MENSAGEM_CATALOGO_MAX, minimo=MENSAGEM_CATALOGO_MIN,
                                             multilinha=True, utf16=True)),)
       for slug in sorted(catalogo_crm.TIPOS_NOVOS)},
}

# Contrato da Onda 2: só estes nascem por `POST /solicitacoes`. Cancelamento
# só por `POST /ajuda/cancelamento` (flag + step-up); os demais, pelas telas
# das fases seguintes.
TIPOS_CRIAVEIS_API: frozenset[str] = frozenset({"outro", "declaracao_associado", "alteracao_cadastro"})
# Com a flag `solicitacoes_crm` (ADR-0024), também os tipos do catálogo comum com o App.
TIPOS_CRIAVEIS_PARIDADE: frozenset[str] = TIPOS_CRIAVEIS_API | catalogo_crm.TIPOS_NOVOS


def _nome_detalhe(chave: object) -> str:
    return f"campos.{chave}" if isinstance(chave, str) and _RE_CHAVE_CAMPO.match(chave) else "campos"


def validar(tipo_servico: str, campos: Any) -> dict[str, Any]:
    """Devolve os campos normalizados (só os da allowlist, com `None` omitido)
    ou levanta `EntradaInvalida` com todos os problemas de uma vez."""
    schema = SCHEMAS.get(tipo_servico)
    if schema is None:
        raise EntradaInvalida([{"campo": "tipo_servico", "mensagem": "tipo de solicitação inválido"}])
    if campos is None:
        campos = {}
    if not isinstance(campos, dict):
        raise EntradaInvalida([{"campo": "campos", "mensagem": "deve ser um objeto"}])
    detalhes: list[dict[str, str]] = []
    permitidos = {c.nome for c in schema}
    for chave in campos:
        if chave not in permitidos:
            detalhes.append({"campo": _nome_detalhe(chave), "mensagem": "campo não permitido para este tipo"})
    saida: dict[str, Any] = {}
    for c in schema:
        bruto = campos.get(c.nome)
        if bruto is None or (isinstance(bruto, str) and not bruto.strip()):
            if c.obrigatorio:
                detalhes.append({"campo": f"campos.{c.nome}", "mensagem": "obrigatório"})
            continue
        try:
            saida[c.nome] = c.validar(bruto)
        except ValueError as exc:
            detalhes.append({"campo": f"campos.{c.nome}", "mensagem": str(exc)[:120]})
    if detalhes:
        raise EntradaInvalida(detalhes)
    if len(serializar(saida).encode("utf-8")) > DADOS_MAX_BYTES:
        raise EntradaInvalida([{"campo": "campos", "mensagem": "conteúdo grande demais"}])
    return saida


def campos_publicos(tipo_servico: str | None, dados: Any) -> dict[str, Any]:
    """O que volta ao associado: só os campos permitidos do tipo (nada interno)."""
    if not isinstance(dados, dict) or tipo_servico not in SCHEMAS:
        return {}
    return {c.nome: dados[c.nome] for c in SCHEMAS[tipo_servico] if c.nome in dados}


def serializar(dados: Mapping[str, Any]) -> str:
    """JSON canônico (chaves ordenadas, sem espaços): base do sha256 do conteúdo enviado."""
    return json.dumps(dados, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_conteudo(dados: Mapping[str, Any]) -> str:
    return hashlib.sha256(serializar(dados).encode("utf-8")).hexdigest()
