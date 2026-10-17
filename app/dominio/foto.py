"""Foto de perfil (ADR-0005): validação e normalização antes de ir ao CRM.

Defesas (RNF-09):
- tipo pelos BYTES MÁGICOS (JPEG, PNG, WebP), nunca pela extensão ou pelo
  Content-Type do navegador; o decodificador do Pillow tem de concordar;
- teto de bytes (FOTO_MAX_BYTES) e de pixels (25 MP); aviso de bomba de
  descompressão vira erro;
- recodificação do zero: só os pixels sobrevivem (EXIF, GPS, ICC, carga
  embutida e poliglotas somem);
- `exif_transpose` antes de descartar o EXIF (foto de celular "deitada");
- recorte central quadrado → 512×512 (CRM) e 128×128 (cache local);
- um processamento por vez por worker (semáforo): contêiner de 400 MB.

Bloqueante (CPU): chamar via `run_in_threadpool`.
"""

from __future__ import annotations

import hashlib
import io
import logging
import threading
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger("area_associado.foto")

MAX_PIXELS = 25_000_000
LADO_CRM = 512
LADO_MINIATURA = 128
_FORMATOS = {"JPEG", "PNG", "WEBP"}

Image.MAX_IMAGE_PIXELS = MAX_PIXELS
_semaforo = threading.BoundedSemaphore(1)


class FotoInvalida(Exception):
    def __init__(self, codigo: str, mensagem: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo
        self.mensagem = mensagem


class FotoOcupada(Exception):
    """Outro processamento em curso neste worker além do tempo de espera."""


def tipo_por_assinatura(dados: bytes) -> str | None:
    if dados[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "WEBP"
    return None


def _quadrado(img: Image.Image, lado: int) -> Image.Image:
    return ImageOps.fit(img, (lado, lado), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def _jpeg(img: Image.Image, qualidade: int) -> bytes:
    saida = io.BytesIO()
    # Imagem nova (sem `info`): nada de EXIF/ICC/comentário é copiado.
    img.save(saida, format="JPEG", quality=qualidade, optimize=True, progressive=True)
    return saida.getvalue()


def processar(dados: bytes, max_bytes: int) -> tuple[bytes, bytes]:
    """Devolve (jpeg 512×512, jpeg 128×128). Levanta `FotoInvalida`/`FotoOcupada`."""
    if not dados:
        raise FotoInvalida("arquivo_vazio", "Envie uma foto.")
    if len(dados) > max_bytes:
        raise FotoInvalida("arquivo_grande", f"A foto deve ter até {max_bytes // (1024 * 1024)} MB.")
    esperado = tipo_por_assinatura(dados)
    if esperado is None:
        raise FotoInvalida("tipo_nao_suportado", "Use uma foto JPG, PNG ou WebP.")
    if not _semaforo.acquire(timeout=10):
        raise FotoOcupada()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            try:
                with Image.open(io.BytesIO(dados)) as img:
                    if img.format != esperado or img.format not in _FORMATOS:
                        raise FotoInvalida("tipo_nao_suportado", "Use uma foto JPG, PNG ou WebP.")
                    if img.width < 64 or img.height < 64:
                        raise FotoInvalida("foto_pequena", "A foto precisa ter ao menos 64×64 pixels.")
                    img.load()  # decodifica de fato: arquivo truncado/corrompido falha aqui
                    img = ImageOps.exif_transpose(img)
                    if img.mode in ("RGBA", "LA", "P"):
                        fundo = Image.new("RGB", img.size, (255, 255, 255))
                        rgba = img.convert("RGBA")
                        fundo.paste(rgba, mask=rgba.getchannel("A"))
                        img = fundo
                    else:
                        img = img.convert("RGB")
                    grande = _jpeg(_quadrado(img, LADO_CRM), 85)
                    pequena = _jpeg(_quadrado(img, LADO_MINIATURA), 80)
            except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
                raise FotoInvalida("foto_grande_demais", "A foto tem resolução grande demais.") from exc
            except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
                raise FotoInvalida("foto_corrompida", "Não conseguimos ler esta foto. Tente outro arquivo.") from exc
    finally:
        _semaforo.release()
    return grande, pequena


def etag(miniatura: bytes) -> str:
    return hashlib.sha256(miniatura).hexdigest()[:16]
