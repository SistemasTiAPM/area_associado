"""Agregação com recorte mínimo (spec v2 §11.6, TI-90).

"Parceiros e patrocinadores recebem só agregados, com no mínimo 20 pessoas por
recorte, para impedir identificação." Esta é a ÚNICA função por onde um número
por grupo pode sair para painel de terceiro ou exportação a parceiro.

Regras:
- grupo com menos de `min_n` pessoas não é publicado;
- os grupos suprimidos viram um único grupo `outros` **só se** a soma deles
  alcançar `min_n`; senão somem;
- o total publicado é a soma do que foi publicado. O total real nunca sai
  junto: com um grupo suprimido, `total − publicados` devolveria exatamente o
  número escondido (ataque por diferença).

Função pura (sem banco): quem chama conta PESSOAS distintas por grupo.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

MIN_N_PADRAO = 20
ROTULO_OUTROS = "outros"


@dataclass(frozen=True)
class Agregado:
    grupos: dict[str, int]   # só grupos com n ≥ min_n (e `outros`, quando alcança o mínimo)
    total: int               # soma do que foi publicado — nunca o total real
    suprimidos: int          # QUANTOS grupos ficaram de fora (não quantas pessoas)


def agregar(contagens: Mapping[str, int] | Iterable[tuple[str, int]], *, min_n: int = MIN_N_PADRAO) -> Agregado:
    """Aplica o recorte mínimo a `grupo → pessoas distintas`."""
    if isinstance(min_n, bool) or not isinstance(min_n, int) or min_n < 2:
        raise ValueError("min_n deve ser um inteiro ≥ 2")
    pares = contagens.items() if isinstance(contagens, Mapping) else contagens
    somados: dict[str, int] = {}
    for grupo, n in pares:
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError("contagem inválida")
        chave = str(grupo)
        if chave == ROTULO_OUTROS:
            raise ValueError(f"grupo reservado: {ROTULO_OUTROS!r}")
        somados[chave] = somados.get(chave, 0) + n
    publicados = {g: n for g, n in somados.items() if n >= min_n}
    pequenos = [n for n in somados.values() if 0 < n < min_n]
    resto = sum(pequenos)
    suprimidos = len(pequenos)
    # Um único grupo pequeno nunca vira `outros` (seria o próprio grupo com outro nome).
    if len(pequenos) >= 2 and resto >= min_n:
        publicados[ROTULO_OUTROS] = resto
        suprimidos = 0
    ordenados = dict(sorted(publicados.items(), key=lambda par: (par[0] == ROTULO_OUTROS, -par[1], par[0])))
    return Agregado(ordenados, sum(ordenados.values()), suprimidos)
