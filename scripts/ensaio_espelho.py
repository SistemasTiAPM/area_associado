"""Ensaio do espelho de solicitações no CRM (ADR-0023, ADR-0024), SÓ com o contato sintético.

Uso (dentro do container de jobs, em janela combinada; docs/JOBS.md §5):

    python -m scripts.ensaio_espelho criar [--tipo seguro_carro]   # pedido local de ensaio, sem e-mail/notificação
                                               # (padrão `outro`; `--tipo` aceita os tipos do catálogo comum com o App)
    python -m scripts.ensaio_espelho estado    # pedidos do contato sintético: status, crm_sync, protocolo, par do CRM
                                               # e a fila de mensagens (sem texto)
    python -m scripts.ensaio_espelho repetir <id>   # chama solicitacao.criar de novo: prova `criada: false`
    python -m scripts.ensaio_espelho listar    # o que o hub devolve para o contato (dois canais): sem texto
    python -m scripts.ensaio_espelho encerrar-antigo  # cancela na área o que ficou aberto do contato sintético
                                               # antigo (excluído do CRM em 13/11); não chama o hub
    python -m scripts.ensaio_espelho mensagem <id>  # põe uma mensagem de ensaio na fila do registro <id>
                                               # (da área ou aberto pelo App); quem envia é o job enviar_mensagens

O envio e a sincronização em si são os jobs, em execução avulsa restrita ao contato:

    docker compose exec -e JOBS_APLICAR=1 -e HUB_ESCRITA_HABILITADA=true \
      -e JOBS_ENSAIO_CONTATOS=1538029d-dbde-f111-84e8-7ced8db12239 \
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

from sqlalchemy import bindparam, text

CONTATO_SINTETICO = "1538029d-dbde-f111-84e8-7ced8db12239"
# Excluído do CRM em 2026-11-13, com todos os registros dele. Só `encerrar-antigo` o usa.
CONTATO_SINTETICO_ANTIGO = "8eb5da36-3847-ee11-be6f-00224837e097"
MENSAGEM_ENCERRAR_ANTIGO = "Registro de ensaio encerrado: o contato de teste foi excluído do CRM."
CAMPOS_ENSAIO = {
    "assunto": "Ensaio Minha APM - não atender",
    "mensagem": "Registro de ensaio da integração Minha APM com o CRM. Não atender: a Central cancela este pedido.",
    "categoria": "outro",
}


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


MENSAGEM_ENSAIO = "Mensagem de ensaio da integração Minha APM com o CRM. Não responder."
TEXTO_ENSAIO = "Registro de ensaio da integração Minha APM com o CRM. Não atender: a equipe cancela este pedido."


def criar(tipo: str = "outro") -> int:
    from app.database import session_scope
    from app.dominio.solicitacoes import catalogo_crm, maquina, parametros, schemas

    if tipo != "outro" and tipo not in catalogo_crm.TIPOS_NOVOS:
        print(f"tipo inválido: use `outro` ou um de {', '.join(sorted(catalogo_crm.TIPOS_NOVOS))}", file=sys.stderr)
        return 2
    campos = schemas.validar(tipo, CAMPOS_ENSAIO if tipo == "outro" else {"mensagem": TEXTO_ENSAIO})
    agora = _agora()
    sid = str(uuid.uuid4())
    with session_scope() as db:
        prazo = parametros.inteiro(db, "prazo_retorno_padrao_dias")
        db.execute(text(
            "INSERT INTO solicitacao (id, contact_id, sub_hash, tipo_servico, tipo_ativacao, canal_envio, "
            " prazo_retorno_dias, status, dados, crm_sync, crm_proxima_em, criada_em, atualizada_em) "
            "VALUES (:id, :c, :h, :tipo, 3, 'crm', :prazo, 'criada', :dados, 'pendente', :agora, :agora, :agora)"
        ), {"id": sid, "c": CONTATO_SINTETICO, "h": hashlib.sha256(f"ensaio:{CONTATO_SINTETICO}".encode()).hexdigest(),
            "tipo": tipo, "prazo": prazo, "dados": schemas.serializar(campos), "agora": agora})
        maquina.registrar_evento(
            db, solicitacao_id=sid, evento="criacao", de=None, para="criada", ator="sistema", origem="job",
            agora=agora,
            conteudo_enviado={"campos": sorted(campos), "sha256": schemas.sha256_conteudo(campos),
                              "destino": "ensaio", "canal": "crm"})
    destino = catalogo_crm.destino(tipo)
    print(f"criado: {sid} (contato sintético, tipo {tipo} → CRM `{destino.tipo}` em {destino.entidade}"
          f"{', com produto' if destino.produto_id else ''}; crm_sync=pendente)")
    return 0


def listar() -> int:
    """O que `solicitacao.listar` devolve ao contato sintético (dois canais). Sem título/descrição."""
    from app.integracoes.hub import CANAL_APP, HubError, obter_hub

    try:
        registros = obter_hub().solicitacao_listar(CONTATO_SINTETICO, 50)
    except HubError as exc:
        print(f"hub: {exc.codigo}", file=sys.stderr)
        return 1
    if not registros:
        print("o hub não devolveu registros do contato sintético")
    for r in registros:
        canal = "app" if r.canal == CANAL_APP else "minha_apm" if r.canal is not None else "-"
        print(f"{r.registro_id}  {r.entidade:<12} tipo={r.tipo or '-':<28} canal={canal:<9} "
              f"crm={r.statecode}/{r.statuscode} prot={r.protocolo or '-'} "
              f"ultima={r.ultima_interacao_autor or '-'}@{r.ultima_interacao_em or '-'}")
    return 0


def mensagem(registro_id: str) -> int:
    """Mensagem de ensaio na fila (`solicitacao_mensagem`), pelo mesmo domínio da tela."""
    from app.dominio.solicitacoes import esquema, leitura_crm, mensagens, schemas
    from app.dominio.solicitacoes.maquina import SolicitacaoNaoEncontrada, TransicaoInvalida

    if not esquema.paridade_presente():
        print("sql/016 ausente: a fila de mensagens ainda não existe", file=sys.stderr)
        return 2
    try:
        envio = mensagens.enviar(CONTATO_SINTETICO, registro_id, texto=MENSAGEM_ENSAIO,
                                 chave_idempotencia=str(uuid.uuid4()))
    except SolicitacaoNaoEncontrada:
        print("registro não encontrado para o contato sintético", file=sys.stderr)
        return 2
    except leitura_crm.FonteIndisponivel as exc:
        print(f"hub: {exc.codigo}", file=sys.stderr)
        return 1
    except (TransicaoInvalida, mensagens.MensagemNaoPermitida, mensagens.LimiteMensagens,
            schemas.EntradaInvalida) as exc:
        print(f"recusada: {getattr(exc, 'codigo', None) or exc}", file=sys.stderr)
        return 1
    print(f"na fila: {envio.mensagem['id']} (registro {envio.registro_id}); "
          "rode o job enviar_mensagens restrito ao contato e confira no CRM")
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
    from app.dominio.solicitacoes import esquema

    if esquema.paridade_presente():
        with session_scope() as db:
            fila = db.execute(text(
                "SELECT id, registro_id, status, tentativas, erro_codigo, proxima_em, enviada_em "
                "FROM solicitacao_mensagem WHERE contact_id = :c ORDER BY criada_em"), {"c": CONTATO_SINTETICO}).all()
        for m in fila:
            print(f"  mensagem {m.id}  registro={m.registro_id} status={m.status:<8} tent={m.tentativas} "
                  f"erro={m.erro_codigo or '-'} proxima={m.proxima_em} enviada={m.enviada_em or '-'}")
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


def encerrar_antigo() -> int:
    """Cancela na ÁREA os pedidos ainda abertos do contato sintético antigo (P-85): o CRM
    não tem mais o contato nem os registros, então a sincronização nunca os encerraria.
    Só efeito local (transição pela máquina, com trilha); nada é chamado no hub e nada é
    apagado. Reexecutável: sem pedido aberto, não faz nada."""
    from app.database import session_scope
    from app.dominio.solicitacoes import maquina, rotulos

    with session_scope() as db:
        abertos = db.execute(text(
            "SELECT id, status FROM solicitacao WHERE contact_id = :c AND status IN :abertos ORDER BY criada_em"
        ).bindparams(bindparam("abertos", expanding=True)),
            {"c": CONTATO_SINTETICO_ANTIGO, "abertos": list(rotulos.NAO_TERMINAIS)}).all()
    if not abertos:
        print("nenhum pedido aberto do contato sintético antigo")
        return 0
    falhas = 0
    for r in abertos:
        try:
            with session_scope() as db:
                maquina.transitar(db, solicitacao_id=str(r.id), para="cancelada", ator="apm", origem="backoffice",
                                  mensagem=MENSAGEM_ENCERRAR_ANTIGO,
                                  justificativa="P-85: contato sintético antigo excluído do CRM em 2026-11-13",
                                  agora=datetime.now(timezone.utc).replace(tzinfo=None))
            print(f"cancelado: {r.id} (estava {r.status})")
        except (maquina.TransicaoInvalida, maquina.SolicitacaoNaoEncontrada) as exc:
            falhas += 1
            print(f"não cancelado: {r.id} ({type(exc).__name__})", file=sys.stderr)
    return 1 if falhas else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ensaio do espelho no CRM (contato sintético).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    novo = sub.add_parser("criar")
    novo.add_argument("--tipo", default="outro")
    sub.add_parser("estado")
    sub.add_parser("listar")
    sub.add_parser("encerrar-antigo")
    rep = sub.add_parser("repetir")
    rep.add_argument("id")
    msg = sub.add_parser("mensagem")
    msg.add_argument("id")
    args = parser.parse_args(argv)
    if args.cmd == "criar":
        return criar(args.tipo)
    if args.cmd == "estado":
        return estado()
    if args.cmd == "listar":
        return listar()
    if args.cmd == "encerrar-antigo":
        return encerrar_antigo()
    try:
        # `repetir`: id da área (UUID v4). `mensagem`: o pai pode ter nascido no App (qualquer GUID).
        uuid.UUID(args.id, version=4) if args.cmd == "repetir" else uuid.UUID(args.id)
    except ValueError:
        print("id inválido", file=sys.stderr)
        return 2
    return repetir(args.id.lower()) if args.cmd == "repetir" else mensagem(args.id.lower())


if __name__ == "__main__":
    raise SystemExit(main())
