"""Unidades do scripts/db_check.py (TI-03): allowlist por usuário, tabela da
allowlist sem grant (ADR-0004 §6) e partições da sql/008. Nada toca banco."""

import pytest

from scripts import db_check
from scripts.db_check import (
    POLITICAS,
    TABELAS_COM_UPDATE,
    avaliar_allowlist,
    avaliar_grants,
    avaliar_particoes,
    grants_de_update,
)

_S = "area_associado"
_WEB = [
    "GRANT USAGE ON *.* TO `apm_area`@`%`",
    "GRANT SELECT, INSERT, EXECUTE ON `area_associado`.* TO `apm_area`@`%`",
    "GRANT UPDATE ON `area_associado`.`associado` TO `apm_area`@`%`",
    "GRANT UPDATE ON `area_associado`.`associado_perfil` TO `apm_area`@`%`",
    "GRANT UPDATE ON `area_associado`.`email_verificacao` TO `apm_area`@`%`",
]


# ------------------------------------------------------------- allowlist
def test_allowlist_so_com_tabelas_migradas():
    # Prospectivas (noticia_cache, job_execucao...) entram com a migração, não antes.
    assert TABELAS_COM_UPDATE == frozenset({"associado", "associado_perfil", "email_verificacao",
                                            "solicitacao", "job_execucao", "comunicacao_evento", "notificacao",
                                            "solicitacao_mensagem", "solicitacao_leitura"})
    assert POLITICAS["apm_area"].tabelas_com_update == TABELAS_COM_UPDATE
    # Trilhas e configuração da Onda 2 nunca recebem UPDATE do processo web (ADR-0004, ADR-0022).
    for tabela in ("solicitacao_evento", "comunicacao_envio", "comunicacao_supressao", "fila_ligacao",
                   "parametro", "faq", "texto_sistema"):
        assert tabela not in TABELAS_COM_UPDATE, tabela


# SHOW GRANTS real do ensaio da Onda 2 (MySQL 8.4.11, sql/000→013): UPDATE por coluna.
_ONDA2 = [
    *_WEB,
    "GRANT UPDATE (`atualizado_em`, `enviar_apos`, `externo_id`, `proxima_tentativa_em`, `status`, "
    "`supressao_motivo`, `tentativas`) ON `area_associado`.`comunicacao_evento` TO `apm_area`@`%`",
    "GRANT UPDATE (`lida_em`) ON `area_associado`.`notificacao` TO `apm_area`@`%`",
    "GRANT UPDATE (`atualizada_em`, `avaliacao_comentario`, `avaliacao_nota`, `avaliada_em`, `cancel_motivo`, "
    "`concluida_em`, `crm_id`, `crm_proxima_em`, `crm_sync`, `crm_tentativas`, `enviada_em`, `responsavel`, "
    "`resultado`, `sem_retorno_desde`, `status`) ON `area_associado`.`solicitacao` TO `apm_area`@`%`",
]


def test_grant_por_coluna_conta_como_update_da_tabela():
    assert avaliar_grants(_ONDA2, _S, "apm_area@%") == []
    assert grants_de_update(_ONDA2, _S) >= {"solicitacao", "comunicacao_evento", "notificacao"}
    existentes = {"associado", "associado_perfil", "email_verificacao", "solicitacao", "solicitacao_evento",
                  "comunicacao_evento", "notificacao", "parametro"}
    assert avaliar_allowlist(_ONDA2, _S, existentes, "apm_area@%") == []
    # A trilha nunca: UPDATE (mesmo por coluna) em solicitacao_evento é violação.
    ruim = [*_ONDA2, "GRANT UPDATE (`mensagem_publica`) ON `area_associado`.`solicitacao_evento` TO `apm_area`@`%`"]
    v = avaliar_grants(ruim, _S, "apm_area@%")
    assert len(v) == 1 and "solicitacao_evento" in v[0]
    # Migração 012 aplicada pela metade (sem o grant de notificacao) falha.
    sem_notif = [g for g in _ONDA2 if "`notificacao`" not in g]
    v = avaliar_allowlist(sem_notif, _S, existentes, "apm_area@%")
    assert len(v) == 1 and "notificacao" in v[0]


# SHOW GRANTS real do ensaio da frente C (MySQL 8.4.11, sql/000→014): job_execucao por coluna.
_JOBS = [
    *_ONDA2,
    "GRANT UPDATE (`erro_resumo`, `itens_erro`, `itens_gravados`, `itens_lidos`, `posicao`, `status`, "
    "`terminado_em`) ON `area_associado`.`job_execucao` TO `apm_area`@`%`",
]


def test_job_execucao_por_coluna_na_allowlist():
    existentes = {"associado", "associado_perfil", "email_verificacao", "solicitacao", "comunicacao_evento",
                  "notificacao", "job_execucao"}
    assert avaliar_grants(_JOBS, _S, "apm_area@%") == []
    assert avaliar_allowlist(_JOBS, _S, existentes, "apm_area@%") == []
    # sql/011 aplicada pela metade (tabela sem o GRANT) é violação (ADR-0004 §6).
    v = avaliar_allowlist(_ONDA2, _S, existentes, "apm_area@%")
    assert len(v) == 1 and "job_execucao" in v[0]
    # Antes da 011, a ausência da tabela não é violação.
    assert avaliar_allowlist(_ONDA2, _S, existentes - {"job_execucao"}, "apm_area@%") == []
    # DELETE em job_execucao, mesmo por tabela, nunca.
    ruim = [*_JOBS, "GRANT DELETE ON `area_associado`.`job_execucao` TO `apm_area`@`%`"]
    assert avaliar_grants(ruim, _S, "apm_area@%")


def test_grants_do_web_conformes_com_usuario_qualificado():
    assert avaliar_grants(_WEB, _S, "apm_area@%") == []
    assert avaliar_grants(_WEB, _S) == []  # padrão continua apm_area


def test_tabela_da_allowlist_existente_sem_grant_falha():
    sem_perfil = [g for g in _WEB if "associado_perfil" not in g]
    existentes = {"associado", "associado_perfil", "email_verificacao", "evento_log"}
    v = avaliar_allowlist(sem_perfil, _S, existentes, "apm_area@%")
    assert len(v) == 1 and "associado_perfil" in v[0] and "sem GRANT UPDATE" in v[0]


def test_tabela_da_allowlist_ainda_nao_criada_nao_e_violacao():
    so_associado = _WEB[:3]
    assert avaliar_allowlist(so_associado, _S, {"associado", "evento_log"}) == []


def test_grants_de_update_ignora_schema_e_outros_schemas():
    grants = [*_WEB, "GRANT UPDATE ON `outro`.`associado` TO `apm_area`@`%`",
              "GRANT UPDATE ON `area_associado`.* TO `apm_area`@`%`"]
    assert grants_de_update(grants, _S) == {"associado", "associado_perfil", "email_verificacao"}


def test_usuario_sem_politica_falha_fechado():
    v = avaliar_grants(_WEB, _S, "apm_bd@%")
    assert v and "sem política" in v[0]
    assert avaliar_allowlist(_WEB, _S, {"associado"}, "apm_bd@%") == []


# ----------------------------------------------------------- outros usuários
def test_backoffice_tem_politica_propria_sem_update_ate_a_migracao():
    base = [
        "GRANT USAGE ON *.* TO `apm_area_bo`@`%`",
        "GRANT SELECT, INSERT, EXECUTE ON `area_associado`.* TO `apm_area_bo`@`%`",
    ]
    assert avaliar_grants(base, _S, "apm_area_bo@%") == []
    v = avaliar_grants([*base, "GRANT UPDATE ON `area_associado`.`beneficio` TO `apm_area_bo`@`%`"],
                       _S, "apm_area_bo@%")
    assert v and "fora da allowlist" in v[0]
    # UPDATE do web NÃO vale para o backoffice: allowlists são independentes.
    v = avaliar_grants([*base, "GRANT UPDATE ON `area_associado`.`associado` TO `apm_area_bo`@`%`"],
                       _S, "apm_area_bo@%")
    assert v and "fora da allowlist" in v[0]


@pytest.mark.parametrize("grant,trecho", [
    ("GRANT SELECT ON `area_associado`.`vw_ind_01` TO `apm_area_painel`@`%`", None),
    ("GRANT SELECT ON `area_associado`.`associado_perfil` TO `apm_area_painel`@`%`", "fora do padrão"),
    ("GRANT SELECT ON `area_associado`.* TO `apm_area_painel`@`%`", "nível do schema só nada"),
    ("GRANT SELECT, INSERT ON `area_associado`.`vw_ind_01` TO `apm_area_painel`@`%`", "além de"),
    ("GRANT UPDATE ON `area_associado`.`vw_ind_01` TO `apm_area_painel`@`%`", "além de"),
])
def test_painel_so_select_em_views(grant, trecho):
    grants = ["GRANT USAGE ON *.* TO `apm_area_painel`@`%`", grant]
    v = avaliar_grants(grants, _S, "apm_area_painel@%")
    if trecho is None:
        assert v == []
    else:
        assert v and trecho in v[0]


# --------------------------------------------------------------- partições
_HOJE = 740000  # TO_DAYS fictício


def _grade(ultimo_limite: int, com_max: bool = True):
    itens = [(f"p{i:02d}", str(ultimo_limite - 30 * (3 - i))) for i in range(4)]
    if com_max:
        itens.append(("pMAX", "MAXVALUE"))
    return itens


def test_sem_008_registrada_tabela_sem_particao_e_so_aviso():
    falhas, avisos = avaliar_particoes(set(), {"evento_log": [(None, None)], "evento_uso": [(None, None)]}, _HOJE)
    assert falhas == []
    assert len(avisos) == 2 and all("ainda não aplicada" in a for a in avisos)


def test_com_008_registrada_tabela_sem_particao_falha():
    falhas, avisos = avaliar_particoes({"001", "008"}, {"evento_log": [(None, None)],
                                                          "evento_uso": _grade(_HOJE + 400)}, _HOJE)
    assert len(falhas) == 1 and "evento_log" in falhas[0] and "registrada" in falhas[0]
    assert avisos == []


def test_tabela_inexistente_nao_e_avaliada():
    falhas, avisos = avaliar_particoes({"008"}, {}, _HOJE)
    assert falhas == [] and avisos == []


def test_grade_longa_e_conforme():
    falhas, avisos = avaliar_particoes({"008"}, {"evento_log": _grade(_HOJE + 400),
                                                 "evento_uso": _grade(_HOJE + 400)}, _HOJE)
    assert falhas == [] and avisos == []


def test_grade_perto_do_fim_avisa():
    _, avisos = avaliar_particoes({"008"}, {"evento_log": _grade(_HOJE + 45),
                                            "evento_uso": _grade(_HOJE + 400)}, _HOJE)
    assert len(avisos) == 1 and "evento_log" in avisos[0] and "45 dias" in avisos[0]


def test_grade_vencida_avisa_pmax():
    _, avisos = avaliar_particoes({"008"}, {"evento_log": _grade(_HOJE - 10),
                                            "evento_uso": _grade(_HOJE + 400)}, _HOJE)
    assert len(avisos) == 1 and "vencida" in avisos[0] and "pMAX" in avisos[0]


def test_sem_pmax_falha():
    falhas, _ = avaliar_particoes({"008"}, {"evento_log": _grade(_HOJE + 400, com_max=False),
                                            "evento_uso": _grade(_HOJE + 400)}, _HOJE)
    assert len(falhas) == 1 and "MAXVALUE" in falhas[0]


def test_constantes_da_008():
    assert db_check.MIGRACAO_PARTICAO == "008"
    assert db_check.TABELAS_PARTICIONADAS == {"evento_uso", "evento_log"}
