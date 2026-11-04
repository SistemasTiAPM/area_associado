"""Ensaio do espelho de solicitações no CRM (ADR-0023), SÓ com o contato sintético.

Uso (dentro do container de jobs, em janela combinada; docs/JOBS.md §5):

    python -m scripts.ensaio_espelho criar     # pedido local de ensaio (tipo `outro`), sem e-mail/notificação
    python -m scripts.ensaio_espelho estado    # pedidos do contato sintético: status, crm_sync, protocolo, par do CRM
    python -m scripts.ensaio_espelho repetir <id>   # chama solicitacao.criar de novo: prova `criada: false`

O envio e a sincronização em si são os jobs, em execução avulsa restrita ao contato:

    docker compose exec -e JOBS_APLICAR=1 -e HUB_ESCRITA_HABILITADA=true \
      -e JOBS_ENSAIO_CONTATOS=8eb5da36-3847-ee11-be6f-00224837e097 \
      area-associado-jobs python -m app.jobs --uma-vez espelhar_solicitacoes

Nada aqui toca outro contato: o `contact_id` é fixo. O pedido de ensaio nasce sem
comunicação (nenhum e-mail ao contato sintético) e com texto que manda a Central
não atender. Registros criados no CRM são cancelados à mão pela Central, nunca apagados.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

CONTATO_SINTETICO = "8eb5da36-3847-ee11-be6f-00224837e097"
CAMPOS_ENSAIO = {
    "assunto": "Ensaio Minha APM - não atender",
    "mensagem": "Registro de ensaio da integração Minha APM com o CRM. Não atender: a Central cancela este pedido.",
    "categoria": "outro",
}


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def criar() -> int:
    from app.database import session_scope
    from app.dominio.solicitacoes import maquina, parametros, schemas

    campos = schemas.validar("outro", CAMPOS_ENSAIO)
    agora = _agora()
    sid = str(uuid.uuid4())
    with session_scope() as db:
        prazo = parametros.inteiro(db, "prazo_retorno_padrao_dias")
        db.execute(text(
            "INSERT INTO solicitacao (id, contact_id, sub_hash, tipo_servico, tipo_ativacao, canal_envio, "
            " prazo_retorno_dias, status, dados, crm_sync, crm_proxima_em, criada_em, atualizada_em) "
            "VALUES (:id, :c, :h, 'outro', 3, 'crm', :prazo, 'criada', :dados, 'pendente', :agora, :agora, :agora)"
        ), {"id": sid, "c": CONTATO_SINTETICO, "h": hashlib.sha256(f"ensaio:{CONTATO_SINTETICO}".encode()).hexdigest(),
            "prazo": prazo, "dados": schemas.serializar(campos), "agora": agora})
        maquina.registrar_evento(
            db, solicitacao_id=sid, evento="criacao", de=None, para="criada", ator="sistema", origem="job",
            agora=agora,
            conteudo_enviado={"campos": sorted(campos), "sha256": schemas.sha256_conteudo(campos),
                              "destino": "ensaio", "canal": "crm"})
    print(f"criado: {sid} (contato sintético, tipo outro, crm_sync=pendente)")
    return 0


def estado() -> int:
    from app.database import session_scope

    with session_scope() as db:
        linhas = db.execute(text(
            "SELECT id, status, crm_sync, crm_tentativas, crm_entidade, crm_protocolo, crm_estado, crm_status, "
            " crm_consultado_em, criada_em FROM solicitacao WHERE contact_id = :c ORDER BY criada_em"
        ), {"c": CONTATO_SINTETICO}).all()
    if not linhas:
        print("nenhum pedido do contato sintético")
    for r in linhas:
        par = f"{r.crm_estado}/{r.crm_status}" if r.crm_estado is not None else "-"
        print(f"{r.id}  status={r.status:<20} sync={r.crm_sync:<8} tent={r.crm_tentativas} "
              f"ent={r.crm_entidade or '-'} prot={r.crm_protocolo or '-'} crm={par} "
              f"consultado={r.crm_consultado_em or '-'}")
    return 0


def repetir(sid: str) -> int:
    from app.database import session_scope
    from app.integracoes.hub import HubError, obter_hub
    from app.jobs.solicitacoes import pedido_crm

    with session_scope() as db:
        r = db.execute(text(
            "SELECT id, contact_id, tipo_servico, beneficio_id, status, crm_id, crm_protocolo, crm_tentativas, "
            " dados, atualizada_em FROM solicitacao WHERE id = :id AND contact_id = :c"
        ), {"id": sid, "c": CONTATO_SINTETICO}).first()
    if r is None or r.crm_id is None:
        print("pedido do contato sintético já enviado não encontrado", file=sys.stderr)
        return 2
    pedido = pedido_crm(r)
    if pedido is None:
        print("tipo sem destino no catálogo", file=sys.stderr)
        return 2
    try:
        c = obter_hub().solicitacao_criar(pedido)
    except HubError as exc:
        print(f"hub: {exc.codigo}", file=sys.stderr)
        return 1
    print(f"repetição: criada={c.criada} protocolo={c.protocolo} crm={c.statecode}/{c.statuscode}"
          f"  (esperado: criada=False e o mesmo protocolo)")
    return 0 if c.criada is False and c.protocolo == r.crm_protocolo else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ensaio do espelho no CRM (contato sintético).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("criar")
    sub.add_parser("estado")
    rep = sub.add_parser("repetir")
    rep.add_argument("id")
    args = parser.parse_args(argv)
    if args.cmd == "criar":
        return criar()
    if args.cmd == "estado":
        return estado()
    try:
        uuid.UUID(args.id, version=4)
    except ValueError:
        print("id inválido", file=sys.stderr)
        return 2
    return repetir(args.id.lower())


if __name__ == "__main__":
    raise SystemExit(main())
