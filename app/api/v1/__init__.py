"""Roteador `/api/v1` — um módulo por recurso."""

from fastapi import APIRouter

from . import carteirinha, perfil, sessao, uso

router = APIRouter(prefix="/api/v1")
router.include_router(sessao.router)
router.include_router(uso.router)
router.include_router(perfil.router)
router.include_router(carteirinha.router)
