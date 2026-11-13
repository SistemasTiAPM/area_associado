"""Texto que a área manda ao CRM em `solicitacao.criar` (ADR-0023; contrato do hub D-10).

O hub não recebe `campos`: a área formata o que o associado preencheu em texto puro,
uma linha "rótulo: valor" por campo (texto longo em bloco próprio), e respeita os
limites do Dataverse medidos em **unidades UTF-16** (emoji vale 2): título ≤ 200,
descrição 10–2000. O limite é garantido na ORIGEM (o texto longo de cada tipo cabe
com folga: teste de pior caso em `tests/test_solicitacoes_crm.py`); o corte aqui é
só defesa, marcado, nunca no meio de um caractere.

Nunca CPF (o banco e a validação já recusam; conferido de novo no texto final),
nunca e-mail, telefone, `contact_id` ou dado de sessão: só o que o associado escreveu
no formulário do tipo (allowlist de `schemas.SCHEMAS`). Funções puras.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from . import catalogo_crm, rotulos, schemas

TITULO_MAX = 200
DESCRICAO_MIN = 10
DESCRICAO_MAX = 2000
MARCA_CORTE = "\n[texto cortado pela Minha APM]"
CABECALHO = "Pedido aberto pelo associado na Minha APM."

ROTULO_CAMPO: dict[str, str] = {
    "assunto": "Assunto",
    "categoria": "Categoria",
    "mensagem": "Mensagem",
    "finalidade": "Finalidade",
    "observacao": "Observação",
    "alteracoes": "Alterações pedidas",
    "justificativa": "Justificativa",
    "motivo": "Motivo",
    "quer_conversa": "Quer conversar com a APM antes",
    "comentario": "Comentário",
    "titulo": "Título",
    "area_interesse": "Área de interesse",
}
OPCOES_CAMPO: dict[str, Mapping[str, str]] = {
    "categoria": rotulos.ASSUNTO_FORMULARIO,
    "finalidade": rotulos.FINALIDADE_DECLARACAO,
    "motivo": rotulos.MOTIVO_CANCELAMENTO,
}
# Texto livre multilinha: vai em bloco ("Rótulo:" e o texto embaixo) e é o único
# que a defesa corta.
CAMPOS_BLOCO: frozenset[str] = frozenset({"mensagem", "justificativa", "comentario"})


class ConteudoRecusado(Exception):
    """O texto final não pode ir ao CRM (CPF ou tamanho impossível). Permanente."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


@dataclass(frozen=True)
class TextoCrm:
    titulo: str
    descricao: str
    cortado: bool


def unidades_utf16(texto: str) -> int:
    """Tamanho como o Dataverse conta (code units UTF-16)."""
    return len(texto.encode("utf-16-le")) // 2


def _data_br(valor: str) -> str:
    ano, mes, dia = valor.split("-")
    return f"{dia}/{mes}/{ano}"


def _valor_cadastro(campo: str, valor: Any) -> str:
    if campo == "data_nascimento" and isinstance(valor, str) and len(valor) == 10:
        return _data_br(valor)
    if campo == "sexo":
        return rotulos.SEXO.get(str(valor), str(valor))
    return str(valor)


def _linhas_campo(campo: str, valor: Any) -> list[str]:
    rotulo = ROTULO_CAMPO[campo]
    if campo in CAMPOS_BLOCO:
        return [f"{rotulo}:", str(valor)]
    if campo in OPCOES_CAMPO:
        return [f"{rotulo}: {OPCOES_CAMPO[campo].get(str(valor), str(valor))}"]
    if isinstance(valor, bool):
        return [f"{rotulo}: {'Sim' if valor else 'Não'}"]
    if campo == "alteracoes" and isinstance(valor, Mapping):
        itens = [f"- {rotulos.CAMPO_CADASTRO.get(c, c)}: {_valor_cadastro(c, v)}"
                 for c, v in sorted(valor.items()) if c in rotulos.CAMPO_CADASTRO]
        return [f"{rotulo}:", *itens]
    return [f"{rotulo}: {valor}"]


def _normalizar(texto: str) -> str:
    """NFC e só `\\n` como controle (o hub normaliza igual; aqui para medir certo)."""
    texto = unicodedata.normalize("NFC", texto).replace("\r\n", "\n").replace("\r", "\n")
    return "".join(c for c in texto if c in "\n\t" or unicodedata.category(c)[0] != "C").strip()


def titulo(tipo_servico: str | None, dados: Mapping[str, Any]) -> str:
    """`Minha APM: <rótulo do tipo>`; no formulário livre, o assunto que o associado deu."""
    base = rotulos.rotulo_tipo(tipo_servico)
    assunto = dados.get("assunto") if tipo_servico == "outro" else None
    texto = _normalizar(f"Minha APM: {assunto or base}")
    return _cortar_unidades(texto, TITULO_MAX)


def _cortar_unidades(texto: str, maximo: int) -> str:
    """Prefixo com no máximo `maximo` unidades UTF-16, sem partir um par substituto."""
    if unidades_utf16(texto) <= maximo:
        return texto
    saida, total = [], 0
    for c in texto:
        tamanho = 2 if ord(c) > 0xFFFF else 1
        if total + tamanho > maximo:
            break
        saida.append(c)
        total += tamanho
    return "".join(saida).rstrip()


def descricao(tipo_servico: str | None, dados: Mapping[str, Any]) -> tuple[str, bool]:
    """(texto, cortado). Ordem dos campos = ordem do schema do tipo."""
    campos = schemas.SCHEMAS.get(tipo_servico or "", ())
    blocos: list[tuple[str | None, list[str]]] = []
    for campo in campos:
        valor = dados.get(campo.nome)
        if valor is None or valor == "" or valor == {}:
            continue
        blocos.append((campo.nome if campo.nome in CAMPOS_BLOCO else None, _linhas_campo(campo.nome, valor)))
    cabecalho = [CABECALHO, f"Tipo: {rotulos.rotulo_tipo(tipo_servico)}"]

    def montar(partes: list[tuple[str | None, list[str]]]) -> str:
        corpo = "\n".join(linha for _, linhas in partes for linha in linhas)
        return _normalizar("\n".join(cabecalho) + ("\n\n" + corpo if corpo else ""))

    texto = montar(blocos)
    excesso = unidades_utf16(texto) - DESCRICAO_MAX
    if excesso <= 0:
        return texto, False
    # Defesa (não deveria acontecer: limites na origem): corta o maior bloco livre.
    indices = [i for i, (nome, _) in enumerate(blocos) if nome is not None]
    if not indices:
        raise ConteudoRecusado("tamanho")
    maior = max(indices, key=lambda i: unidades_utf16(blocos[i][1][1]))
    nome, (rotulo_linha, livre) = blocos[maior]
    alvo = unidades_utf16(livre) - excesso - unidades_utf16(MARCA_CORTE)
    if alvo < 1:
        raise ConteudoRecusado("tamanho")
    blocos[maior] = (nome, [rotulo_linha, _cortar_unidades(livre, alvo) + MARCA_CORTE])
    texto = montar(blocos)
    if unidades_utf16(texto) > DESCRICAO_MAX:
        raise ConteudoRecusado("tamanho")
    return texto, True


def texto_para_crm(tipo_servico: str | None, dados: Mapping[str, Any]) -> TextoCrm:
    """Título e descrição prontos para `solicitacao.criar`. `ConteudoRecusado` se o
    texto final tiver padrão de CPF ou não couber.

    Tipo do catálogo comum com o App (ADR-0024): igual ao App — título = nome do tipo,
    descrição = o texto do associado, sem cabeçalho (o canal já vai no campo Canal do CRM).
    Tipo antigo da área (traduzido para outro slug): mantém `Minha APM: <rótulo>` e os
    campos do formulário, para a Central ver o que foi pedido."""
    if tipo_servico in catalogo_crm.TIPOS_NOVOS:
        t = _cortar_unidades(_normalizar(rotulos.rotulo_tipo(tipo_servico)), TITULO_MAX)
        mensagem = dados.get("mensagem")
        d, cortado = _normalizar(mensagem) if isinstance(mensagem, str) else "", False
        if unidades_utf16(d) > DESCRICAO_MAX:
            raise ConteudoRecusado("tamanho")
    else:
        t = titulo(tipo_servico, dados)
        d, cortado = descricao(tipo_servico, dados)
    if schemas.RE_CPF.search(t) or schemas.RE_CPF.search(d):
        raise ConteudoRecusado("cpf")
    if unidades_utf16(d) < DESCRICAO_MIN or not t:
        raise ConteudoRecusado("tamanho")
    return TextoCrm(t, d, cortado)
