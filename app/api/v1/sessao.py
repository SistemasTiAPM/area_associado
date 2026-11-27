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

from ... import prontidao
from ...config import get_settings
from ...csrf import csrf_token
from ...dominio import perfil, preferencias
from ...dominio.associado import contact_id_valido
from ...dominio.solicitacoes import servico as solicitacoes
from ...flags import flags_efetivas
from ...session_guard import Associado, require_associado
from .modelos import SessaoResposta

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
                  foto_versao: str | None = None, recursos: dict[str, bool] | None = None,
                  aguardando: int = 0, preferencias_sessao: dict[str, Any] | None = None) -> dict[str, Any]:
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
        # Hub do CRM ou e-mail simulados: contato, endereço e foto são de demonstração.
        "dados_demonstracao": s.hub_mode == "stub" or s.smtp_mode == "stub",
        # Prontidão das migrações da Onda 2: sem as tabelas, a SPA mostra "em construção".
        "recursos": {"solicitacoes": bool((recursos or {}).get("solicitacoes")),
                     "ajuda": bool((recursos or {}).get("ajuda")),
                     "privacidade": bool((recursos or {}).get("privacidade"))},
        "solicitacoes_aguardando": aguardando,
        # Tamanho de fonte e tratamento (ADR-0026): o shell aplica antes de qualquer tela.
        "preferencias": preferencias_sessao or {"fonte": preferencias.FONTE_PADRAO, "tratamento": None},
        "expira_em": expira.isoformat().replace("+00:00", "Z"),
    }


@router.get("/sessao", response_model=SessaoResposta)
async def obter_sessao(request: Request, associado: Associado = Depends(require_associado)) -> dict[str, Any]:
    flags = await run_in_threadpool(flags_efetivas)
    cid = contact_id_valido(associado.contact_id)
    versao = await run_in_threadpool(perfil.foto_etag, cid)
    recursos = await run_in_threadpool(prontidao.recursos)
    # Contador real (RF-SO-07); sem o recurso ou com falha de banco, 0 — o menu nunca depende disto.
    aguardando = await run_in_threadpool(solicitacoes.contar_aguardando, cid) if recursos["solicitacoes"] else 0
    # Preferências só com a flag ligada e a sql/017 aplicada; senão, o padrão (sem tocar o banco).
    prefs = None
    if flags.get("perfil_preferencias") and recursos.get("privacidade"):
        prefs = await run_in_threadpool(preferencias.resumo_sessao, cid)
    return montar_sessao(request, associado, flags, versao, recursos, aguardando, prefs)
