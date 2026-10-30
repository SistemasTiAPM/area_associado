# ADR-0022: Usuário de banco próprio do backoffice (`apm_area_bo`) e usuário só-leitura dos painéis

- **Status:** Aceita (parte de banco da decisão sobre o backoffice; hospedagem e identidade ficam para ADR própria)
- **Data:** 2026-10-30
- **Decisores:** Sistemas TI (William) · Claude Code (Atlas/Sentinela)
- **Relacionadas:** ADR-0004, ADR-0014, ADR-0021

## Contexto

A spec v2 (§9, §3 item 8) exige catálogo, carências, parâmetros, textos e valores de referência **editáveis
sem desenvolvedor**, por 8 perfis, com 2FA e trilha imutável. Isso implica `UPDATE` em tabelas de
catálogo/configuração — hoje a aplicação (`apm_area`) só recebe `UPDATE` tabela a tabela, por migração
justificada (ADR-0004), e o REQUISITOS v0.1 previa o catálogo como seed só `SELECT`. Onde o backoffice vai
viver e como autentica (Entra ID, Cloudflare Access, container próprio) é decisão institucional que ainda
depende de P-65/P-62 (`docs/LEVANTAMENTO-TECNICO-spec-v2.md` §4, DEC-03). O usuário decidiu em 30/10 fechar
**só a parte de banco** agora, para que as migrações da Fase 4 não precisem ser reescritas.

## Decisão

1. **Dois usuários de aplicação além do `apm_area`**, criados por migração própria quando as tabelas
   existirem:
   - `apm_area_bo` (backoffice): `SELECT` no schema + `UPDATE` **só** nas tabelas de catálogo e
     configuração (`parceiro`, `beneficio`, `beneficio_categoria`, `beneficio_categoria_associado`,
     `beneficio_afinidade`, `parametro`, `destaque_editorial`, `faq`, `texto_sistema`, `trilha_passo`, `importacao`, `solicitacao`
     (status com justificativa), `titular_pedido`, `usuario_interno`) e `INSERT` nas trilhas
     (`beneficio_versao`, `backoffice_auditoria`, `acesso_dado_pessoal`, `solicitacao_evento`, `valor_referencia` —
     aprovar um valor é INSERT de linha aprovada, nunca UPDATE). **Sem**
     `UPDATE` nas tabelas do associado (`associado`, `associado_perfil`, `beneficio_ativacao`,
     `perfil_declarado`, `consentimento`…). `DELETE` nunca. `REQUIRE SSL`.
   - `apm_area_painel` (painéis): só `SELECT` nas views `vw_*` (com k-anonimato ≥ 20 nos recortes), nada nas
     tabelas base.
2. **`apm_area` (web do associado) continua só leitura do catálogo/configuração**: ganha `UPDATE` apenas nas
   tabelas do associado já previstas (ADR-0004).
3. **`scripts/db_check.py` valida por usuário**: allowlist de `UPDATE` própria para cada um; falha se uma
   tabela da allowlist existir sem o grant (ADR-0004 §6), se houver `UPDATE` fora da allowlist, `DELETE` em
   qualquer tabela, ou privilégio em outro schema; a allowlist só lista tabelas já migradas.
4. **Trilhas do backoffice** nascem append-only com CHECK anti-segredo/CPF: `backoffice_auditoria`
   (usuário, ação, tabela, registro, valor anterior/novo, justificativa, `request_id`) e
   `acesso_dado_pessoal` (quem leu qual `contact_id`, quais campos).
5. **Sem senha de usuário interno na área**: `usuario_interno` guarda identidade externa (OIDC corporativo)
   e perfil; a autenticação é da ADR futura do backoffice.
6. Até existir backoffice, mutações de catálogo/configuração são **ato do operador por SQL** com registro em
   `beneficio_versao`/`backoffice_auditoria` por script administrativo (fora do `apm_area`), como hoje com
   `feature_flag`.

## Consequências

### Positivas
- Separação de credencial por superfície: um XSS na área não ganha `UPDATE` no catálogo; um bug do backoffice
  não altera dado do associado.
- As migrações da Fase 4 nascem certas, independentemente de onde o backoffice for hospedado.

### Negativas / riscos
- Dois `.env` (ou duas credenciais) a provisionar e replicar no cofre; `db_check` mais complexo.
- Até o backoffice existir, "editável sem desenvolvedor" não é atendido (limitação registrada em
  `PENDENCIAS.md`).

### Obrigações decorrentes
- `scripts/db_check.py` com allowlist por usuário (TI-03, Onda 1).
- Migração de criação de `apm_area_bo` e `apm_area_painel` junto da `sql/012` (catálogo) e `sql/022` (views).
- `docs/PROVISIONAMENTO.md`: credenciais separadas, cofre, rotação.
- ADR futura (Onda 6): hospedagem, identidade (Entra ID), 2FA, perfis → grupos.

## Alternativas descartadas
- **`GRANT UPDATE` ao `apm_area` nas tabelas de catálogo**: amplia o privilégio do processo público.
- **Catálogo só por migração (`sql/`)**: contraria a spec (§3 item 8) e vira gargalo da TI.
- **Decidir hospedagem/identidade agora**: depende de tenant/MFA institucionais (P-65) ainda sem resposta.
