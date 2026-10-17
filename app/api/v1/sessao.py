"""`GET /api/v1/sessao` — primeira chamada da SPA (RF-AU-03).

Entrega identidade de exibição, persona, token CSRF, flags efetivas e
configuração da interface. **Nunca** devolve CPF, CPF mascarado, e-mail, `sub`
ou `contact_id`: a SPA não precisa deles e tudo que sai daqui pode parar em
extensão de navegador, ferramenta de suporte ou log de cliente.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from ...config import get_settings
from ...csrf import csrf_token
from ...dominio import perfil
from ...dominio.associado import contact_id_valido
from ...flags import flags_efetivas
from ...session_guard import Associado, require_associado

router = APIRouter(tags=["sessao"])

# Partículas que não viram inicial nem ganham maiúscula ("Maria da Silva" → "MS").
_PARTICULAS = frozenset({"da", "das", "de", "di", "do", "dos", "du", "e", "d'"})


def formatar_nome(nome: str | None) -> str:
    """Normaliza nome vindo do CRM, que costuma chegar em CAIXA ALTA."""
    if not nome:
        return ""
    palavras = nome.split()
    if nome.isupper() or nome.islower():
        palavras = [p.lower() if p.lower() in _PARTICULAS else p.capitalize() for p in palavras]
    return " ".join(palavras)


def iniciais(nome: str) -> str:
    significativas = [p for p in nome.split() if p.lower() not in _PARTICULAS and p[:1].isalpha()]
    if not significativas:
        return "?"
    if len(significativas) == 1:
        return significativas[0][:1].upper()
    return (significativas[0][:1] + significativas[-1][:1]).upper()


def montar_sessao(request: Request, associado: Associado, flags: dict[str, bool],
                  foto_versao: str | None = None) -> dict[str, Any]:
    s = get_settings()
    nome = formatar_nome(associado.nome)
    expira = datetime.fromtimestamp(associado.auth_at + s.session_absolute_max, tz=timezone.utc)
    return {
        "associado": {
            "nome": nome,
            "nome_exibicao": nome.split()[0] if nome else "",
            "iniciais": iniciais(nome),
            "tipo": associado.tipo,
            "status": associado.status,
            "tem_foto": foto_versao is not None,
            "foto_versao": foto_versao,
        },
        "csrf": csrf_token(request),
        "rota_inicial": "/area",  # regra por persona na Fase 6 (RF-AU-04)
        "flags": flags,
        "config": {
            "whatsapp": s.whatsapp_central,
            "show_whatsapp": s.show_whatsapp,
            "animations": s.animations,
        },
        "stub": associado.is_stub,
        "solicitacoes_aguardando": 0,  # Fase 3 (solicitações)
        "expira_em": expira.isoformat().replace("+00:00", "Z"),
    }


@router.get("/sessao")
async def obter_sessao(request: Request, associado: Associado = Depends(require_associado)) -> dict[str, Any]:
    flags = await run_in_threadpool(flags_efetivas)
    versao = await run_in_threadpool(perfil.foto_etag, contact_id_valido(associado.contact_id))
    return montar_sessao(request, associado, flags, versao)
