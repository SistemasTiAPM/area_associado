"""Carteirinha para baixar: PNG e PDF gerados no servidor, em memória (TI-46, RF-CA-07).

Conteúdo FECHADO (spec P07): marca textual "APM"/"Minha APM", selo
"ASSOCIADO", nome, categoria, número de associado, "Associado desde AAAA",
situação na data de emissão e o QR da URL pública de verificação — que
consulta a situação na leitura (TI-45), então o arquivo salvo continua
honesto. Nunca CPF, CRM, e-mail, telefone, foto ou imagem de terceiro.

Sem metadados: o PNG sai sem chunks de texto/EXIF; o PDF (Pillow) leva só a
data de criação e o título fixo "Carteirinha APM" — nada do associado.

Fonte: Sora (OFL, `app/static/fonts/OFL-sora.txt`), a mesma da SPA. O
FreeType do Pillow lê os `.woff2` self-hosted (brotli embutido), então não
há TTF nem pacote de sistema novo na imagem. Os subconjuntos `latin` e
`latin-ext` são combinados por trecho; caractere fora dos dois cai na letra
base (NFKD) ou é omitido — nunca um quadrado de glifo ausente.

Bloqueante (CPU, ~0,1 s): chamar via `run_in_threadpool`. Um processamento por
worker por vez (faces FreeType compartilhadas; contêiner de 512 MB).
"""

from __future__ import annotations

import io
import logging
import threading
import unicodedata
from itertools import pairwise
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import segno
from PIL import Image, ImageChops, ImageDraw, ImageFont

logger = logging.getLogger("area_associado.carteirinha_arquivo")

# Proporção ISO/IEC 7810 ID-1 (85,6 × 54 mm) a 300 dpi.
LARGURA, ALTURA = 1012, 638
DPI = 300.0
_MARGEM = 56
_LADO_QR = 250

_FONTES = Path(__file__).resolve().parents[1] / "static" / "fonts"
_FUSO = ZoneInfo("America/Sao_Paulo")

# Paleta da carteirinha na SPA (tokens.css: --grad-carteirinha, --navy-muted).
_GRADIENTE = ((0.0, (0x00, 0x17, 0x2D)), (0.45, (0x00, 0x41, 0x65)), (1.0, (0x00, 0x67, 0x5A)))
_BRANCO = (255, 255, 255)
_SUAVE = (0xB3, 0xD9, 0xE6)
_QR_ESCURO = (0x00, 0x17, 0x2D)

# Um por worker: as faces FreeType em cache (`_fonte`) não são para uso concorrente.
_semaforo = threading.BoundedSemaphore(1)
_ESPERA_S = 5.0


class CarteirinhaOcupada(Exception):
    """Processamentos demais em curso neste worker além do tempo de espera."""


@dataclass(frozen=True)
class DadosCartao:
    nome: str
    categoria: str | None
    numero: str | None
    desde: str | None  # AAAA
    situacao: str | None
    url_verificacao: str
    emitida_em: datetime | None = None  # UTC; None = agora


# --------------------------------------------------------------------------- #
# Texto                                                                        #
# --------------------------------------------------------------------------- #
def _no_latin(cp: int) -> bool:
    return (cp <= 0xFF or cp in (0x131, 0x152, 0x153, 0x2C6, 0x2DA, 0x2DC, 0x20AC, 0x2122, 0x2212)
            or 0x2000 <= cp <= 0x206F)


def _no_latin_ext(cp: int) -> bool:
    return 0x100 <= cp <= 0x24F or 0x1E00 <= cp <= 0x1EFF


def limpar(texto: str | None, limite: int = 160) -> str:
    """NFC, sem caracteres de controle/formatação, espaços normalizados."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFC", str(texto))
    texto = "".join(" " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c for c in texto)
    return " ".join(texto.split())[:limite]


def _trechos(texto: str) -> list[tuple[str, str]]:
    """Divide o texto em trechos (`latin`|`latin-ext`) com glifo garantido."""
    trechos: list[tuple[str, str]] = []
    for c in texto:
        cp = ord(c)
        if _no_latin(cp):
            sub = "latin"
        elif _no_latin_ext(cp):
            sub = "latin-ext"
        else:
            base = "".join(b for b in unicodedata.normalize("NFKD", c) if _no_latin(ord(b)) and not unicodedata.combining(b))
            if not base:
                continue
            c, sub = base, "latin"
        if trechos and trechos[-1][1] == sub:
            trechos[-1] = (trechos[-1][0] + c, sub)
        else:
            trechos.append((c, sub))
    return trechos


@lru_cache(maxsize=64)
def _fonte(subconjunto: str, peso: int, tamanho: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    caminho = _FONTES / f"sora-{subconjunto}-{peso}-normal.woff2"
    try:
        return ImageFont.truetype(str(caminho), tamanho)
    except OSError as exc:  # fonte ausente/ilegível: degrada, não derruba o download
        logger.error("carteirinha: fonte %s indisponível (%s) — usando a padrão", caminho.name, type(exc).__name__)
        return ImageFont.load_default(size=tamanho)


def _largura(texto: str, peso: int, tamanho: int) -> float:
    return sum(_fonte(sub, peso, tamanho).getlength(t) for t, sub in _trechos(texto))


def _escrever(desenho: ImageDraw.ImageDraw, x: float, y: float, texto: str, peso: int, tamanho: int,
              cor: tuple[int, int, int], *, alinhar: str = "esquerda") -> None:
    """Texto na linha de base `y` (âncora `ls`): trechos de fontes diferentes alinham."""
    if alinhar == "direita":
        x -= _largura(texto, peso, tamanho)
    elif alinhar == "centro":
        x -= _largura(texto, peso, tamanho) / 2
    for trecho, sub in _trechos(texto):
        fonte = _fonte(sub, peso, tamanho)
        desenho.text((x, y), trecho, font=fonte, fill=cor, anchor="ls")
        x += fonte.getlength(trecho)


def _caber(texto: str, peso: int, maximo: int, minimo: int, largura: float) -> tuple[str, int]:
    """Maior tamanho entre `maximo` e `minimo` em que o texto cabe; senão corta com reticências."""
    for tamanho in range(maximo, minimo - 1, -2):
        if _largura(texto, peso, tamanho) <= largura:
            return texto, tamanho
    while texto and _largura(texto + "…", peso, minimo) > largura:
        texto = texto[:-1].rstrip()
    return (texto + "…" if texto else ""), minimo


def _linhas_do_nome(nome: str, largura: float) -> tuple[list[str], int]:
    texto, tamanho = _caber(nome, 700, 46, 34, largura)
    if texto == nome:
        return [nome], tamanho
    palavras = nome.split()
    melhor: tuple[list[str], int] | None = None
    for corte in range(len(palavras) - 1, 0, -1):
        primeira, segunda = " ".join(palavras[:corte]), " ".join(palavras[corte:])
        for tamanho in range(40, 29, -2):
            if _largura(primeira, 700, tamanho) <= largura and _largura(segunda, 700, tamanho) <= largura:
                if melhor is None or tamanho > melhor[1]:
                    melhor = ([primeira, segunda], tamanho)
                break
    if melhor:
        return melhor
    primeira, _ = _caber(nome, 700, 30, 30, largura)
    return [primeira], 30


# --------------------------------------------------------------------------- #
# Desenho                                                                      #
# --------------------------------------------------------------------------- #
def _fundo() -> Image.Image:
    """Gradiente diagonal de 3 paradas (135°), sem laço por pixel."""
    horizontal = Image.linear_gradient("L").rotate(90).resize((LARGURA, ALTURA))
    vertical = Image.linear_gradient("L").resize((LARGURA, ALTURA))
    t = ImageChops.add(horizontal, vertical, scale=2.0)  # 0 no canto superior esquerdo, 255 no oposto

    def tabela(canal: int) -> list[int]:
        saida = []
        for i in range(256):
            p = i / 255
            for (p0, c0), (p1, c1) in pairwise(_GRADIENTE):
                if p <= p1:
                    f = (p - p0) / (p1 - p0)
                    saida.append(round(c0[canal] + (c1[canal] - c0[canal]) * f))
                    break
        return saida

    return Image.merge("RGB", [t.point(tabela(c)) for c in range(3)])


def _qr(desenho: ImageDraw.ImageDraw, url: str, x0: int, y0: int, lado: int) -> None:
    matriz = segno.make(url, error="m", micro=False).matrix
    n = len(matriz)
    modulo = max(1, (lado - 32) // n)  # ≥ 16 px de margem branca em volta (zona de silêncio)
    inicio_x = x0 + (lado - modulo * n) // 2
    inicio_y = y0 + (lado - modulo * n) // 2
    desenho.rounded_rectangle((x0, y0, x0 + lado - 1, y0 + lado - 1), radius=18, fill=_BRANCO)
    for linha, valores in enumerate(matriz):
        for coluna, escuro in enumerate(valores):
            if escuro & 1:
                px, py = inicio_x + coluna * modulo, inicio_y + linha * modulo
                desenho.rectangle((px, py, px + modulo - 1, py + modulo - 1), fill=_QR_ESCURO)


def desenhar(dados: DadosCartao) -> Image.Image:
    img = _fundo()
    d = ImageDraw.Draw(img)
    m = _MARGEM
    qr_x = LARGURA - m - _LADO_QR
    coluna = qr_x - 40 - m  # largura útil à esquerda do QR

    # Marca textual (sem logotipo de terceiro) e selo.
    _escrever(d, m, m + 44, "APM", 700, 52, _BRANCO)
    _escrever(d, m, m + 76, "Associação Paulista de Medicina", 500, 19, _SUAVE)
    selo, tam_selo = "ASSOCIADO", 17
    largura_selo = _largura(selo, 600, tam_selo) + 36
    d.rounded_rectangle((LARGURA - m - largura_selo, m + 8, LARGURA - m, m + 46), radius=19, outline=_BRANCO, width=2)
    _escrever(d, LARGURA - m - largura_selo / 2, m + 33, selo, 600, tam_selo, _BRANCO, alinhar="centro")

    # Nome (até 2 linhas), categoria e "desde".
    linhas, tam_nome = _linhas_do_nome(limpar(dados.nome) or "Associado APM", coluna)
    y = 236
    for linha in linhas:
        _escrever(d, m, y, linha, 700, tam_nome, _BRANCO)
        y += tam_nome + 10
    y += 4
    categoria = limpar(dados.categoria, 40)
    if categoria:
        texto, tam = _caber(categoria, 600, 24, 18, coluna)
        _escrever(d, m, y, texto, 600, tam, _SUAVE)
        y += 36
    desde = limpar(dados.desde, 4)
    if desde.isdigit() and len(desde) == 4:
        _escrever(d, m, y, f"Associado desde {desde}", 400, 21, _BRANCO)

    # Número e situação (rodapé esquerdo).
    rot_y, val_y = 506, 542
    meia = (coluna - 24) / 2
    for i, (rotulo, valor) in enumerate((("Nº DE ASSOCIADO", limpar(dados.numero, 20) or "—"),
                                         ("SITUAÇÃO", limpar(dados.situacao, 40) or "não confirmada"))):
        x = m + i * (meia + 24)
        _escrever(d, x, rot_y, rotulo, 500, 14, _SUAVE)
        texto, tam = _caber(valor, 600, 26, 16, meia)
        _escrever(d, x, val_y, texto, 600, tam, _BRANCO)

    emitida = (dados.emitida_em or datetime.now(timezone.utc)).replace(tzinfo=timezone.utc).astimezone(_FUSO)
    _escrever(d, m, ALTURA - m + 14, f"Minha APM · emitida em {emitida:%d/%m/%Y}", 400, 15, _SUAVE)

    # QR (direita) + legenda: a situação atual vale na leitura.
    qr_y = 196
    _qr(d, dados.url_verificacao, qr_x, qr_y, _LADO_QR)
    _escrever(d, qr_x + _LADO_QR / 2, qr_y + _LADO_QR + 30, "Confira a situação atual", 500, 15, _SUAVE,
              alinhar="centro")
    _escrever(d, qr_x + _LADO_QR / 2, qr_y + _LADO_QR + 52, "pelo QR code", 500, 15, _SUAVE, alinhar="centro")
    return img


# --------------------------------------------------------------------------- #
# Formatos                                                                     #
# --------------------------------------------------------------------------- #
def _com_limite(gerar):
    if not _semaforo.acquire(timeout=_ESPERA_S):
        raise CarteirinhaOcupada()
    try:
        return gerar()
    finally:
        _semaforo.release()


def png(dados: DadosCartao) -> bytes:
    """PNG 1012×638 (300 dpi), sem chunks de texto, EXIF ou ICC."""
    def gerar() -> bytes:
        buf = io.BytesIO()
        desenhar(dados).save(buf, "PNG", optimize=True, dpi=(DPI, DPI))
        return buf.getvalue()

    return _com_limite(gerar)


def pdf(dados: DadosCartao) -> bytes:
    """PDF de uma página no tamanho do cartão (85,6 × 54 mm). Metadados só genéricos."""
    def gerar() -> bytes:
        buf = io.BytesIO()
        desenhar(dados).save(buf, "PDF", resolution=DPI, quality=95, title="Carteirinha APM",
                             author="APM", subject="", keywords="", creator="Minha APM", producer="Minha APM")
        return buf.getvalue()

    return _com_limite(gerar)
