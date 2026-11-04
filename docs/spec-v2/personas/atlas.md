# 🗄️ Atlas (DBA) — prontidão do banco e dos dados para a spec v2 (30/09/2026)

Levantado em 2026-10-29 sobre HEAD `a2af85e`. Fontes: `docs/spec-v2/ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md` (spec), `docs/REQUISITOS-minha-apm.md` (REQ), `sql/000–007`, `scripts/db_check.py`, `app/{audit,uso,database}.py`, `app/dominio/*.py`, ADR-0003/0004/0012/0014, `docs/PENDENCIAS.md` e os três inventários de 29/10 (`inventario-codigo.md`, `inventario-requisitos.md`, `inventario-vizinhos.md`).

Legenda de estado: ✅ existe e atende · 🟡 parcial · ⬜ não existe, construível · ⛔ bloqueado por terceiro ou decisão pendente · ⚠️ diverge da spec ou de decisão fechada · 🔒 decisão que não se reabre.

**Decisões fechadas que regem tudo abaixo (🔒):** MySQL próprio com espelho no CRM (ADR-0003); UPDATE só por GRANT de tabela, DELETE nunca, trilhas só INSERT (ADR-0004); `evento_uso` com catálogo fechado em transação própria (ADR-0012); `contact_id`, nunca CPF (ADR-0014); CRM/ERP só via `mcp_hub` (ADR-0002); WordPress por MySQL direto no job, com cache (ADR-0006).

**Fatos de base (o que existe no RDS hoje):** `sql/001` `schema_migrations` · `sql/002` `evento_log` append-only com CHECK anti-segredo/CPF (`sql/002_evento_log.sql:51-57`) · `sql/003` `feature_flag` só SELECT (`sql/003_feature_flag.sql:9-11`) · `sql/004` `evento_uso` append-only, CHECK de regex em `acao` e anti-CPF em `detalhes` (`sql/004_evento_uso.sql:43-58`), índices `(contact_id, ocorrido_em)`, `(acao, ocorrido_em)`, `(entidade, entidade_id)`, `(ocorrido_em)` (`:39-42`) · `sql/005` `associado` com UPDATE (`sql/005_associado.sql:42`) · `sql/006` `associado_perfil` com UPDATE (`sql/006_associado_perfil.sql:54`) · `sql/007` `email_verificacao` com UPDATE (`sql/007_email_verificacao.sql:49`). Usuário `apm_area` com `SELECT, INSERT, EXECUTE` no schema e `REQUIRE SSL` (`sql/000_schema_e_usuario.sql:21-30`). Allowlist `TABELAS_COM_UPDATE` com 12 nomes, 9 deles sem migração (`scripts/db_check.py:22-35`; `inventario-codigo.md:19`). Catálogo de 36 ações em `app/uso.py:83-120`; 8 emitidas de fato, 28 sem emissor (`inventario-codigo.md:25`).

---

## Itens

### §11.1 · Modelo de dados (15 entidades da spec)

**Spec pede** (spec L926-945): Associado, Filiação, Situação financeira, Perfil declarado, Consentimento, Benefício, Parceiro e contrato, Solicitação, Log de status, Uso e valor, Importação, Conteúdo e evento, Segmento e bloco, Comunicação, Evento de uso, Usuário interno e auditoria.

**Existe hoje:** 4 das 15 têm tabela: Associado (parcial: `associado` + `associado_perfil`, `sql/005`, `sql/006`), Filiação (parcial: só `tipo_associado`, `status_associativo`, `data_filiacao` em `sql/006_associado_perfil.sql:28-30`; sem histórico de categorias, isenção ou remição), Evento de uso (`evento_uso`, `sql/004`), Perfil declarado (nada além dos contatos; sem área de atuação, temas, tratamento, canais). REQ §6 (REQ L984-1016) prevê mais 16 tabelas em `sql/008–012`, nenhuma criada.

**Falta:**
- SQL: Situação financeira (cache mínimo), Consentimento, Benefício/Parceiro como **dados** (REQ L997-998 previa seed só SELECT), Solicitação com os campos novos da spec, Log de status com "conteúdo enviado", Uso e valor, Importação, Segmento/bloco/matriz, Comunicação, Usuário interno/auditoria, Perfil declarado. Ver "Modelo de dados proposto".
- dominio: módulos de solicitações, benefícios/elegibilidade, valor, importação, consentimento.
- API: todos os recursos além de `sessao`, `uso`, `perfil`, `carteirinha` (`inventario-codigo.md:8`).
- jobs: não existe `app/jobs/` nem serviço no compose (`inventario-codigo.md:15`).
- infra: segundo usuário de banco para o backoffice (ver DEC-A03).

**Estado:** 🟡 (4/15). **Fase spec:** F0 (contratos de dados) → F1. **Roteiro:** Fases 3–8 + backoffice sem fase.

### §11.1 · Associado e Filiação × contrato de dados §13.2

**Spec pede** (spec L1147-1152): identificador estável, CPF, nome, nome social, nascimento, e-mail, celular, categoria atual, data de filiação, **histórico de categorias com datas**, situação, isenção/remição, CRM/UF, especialidades, regional, avisos automáticos (filiação criada, categoria alterada, pagamento, vencimento, cancelamento, contato alterado).

**Existe hoje:** `associado_perfil` guarda nome, contatos, endereço, `num_contato`, `crm`, `crm_uf`, `tipo_associado`, `status_associativo`, `data_filiacao`, foto (`sql/006_associado_perfil.sql:17-37`). O hub tem `associado.historico_associacao` **por CPF** (`inventario-vizinhos.md:25`), inutilizável pela área até P-04 (`docs/PENDENCIAS.md:55`). Não há nascimento, especialidade, regional, nome social, histórico de categorias, isenção/remição. Avisos automáticos do CRM: inexistentes (o CRM não empurra; a área puxa via hub).

**Falta:**
- SQL: colunas novas em `associado_perfil` (migração `ALTER` com justificativa): `faixa_carreira` (derivada, 4 valores — **não** a data de nascimento, minimização), `especialidade_cod`, `regional_cod`, `isento_remido`, `nome_social`/`tratamento`; tabela `associado_categoria_hist` (append-only, espelho do histórico do CRM, usada por carência e indicador 9).
- dominio/integrações: `perfil_consultar` do hub precisa devolver esses campos (contrato `docs/CONTRATO-HUB.md`, extensão no hub).
- jobs: `atualizar_perfis` (hoje o cache só renova ao abrir o Perfil, `inventario-codigo.md:11`).

**Estado:** 🟡. **Fase spec:** F0-02 (contrato de dados). **Roteiro:** Fase 4 (elegibilidade depende disso).

### §11.1 / §8.4 · Situação financeira

**Spec pede** (spec L932, L743-749): status, dias de atraso, mensalidades, pagamentos, forma; parâmetro "dias de atraso que suspendem benefícios" configurável; valor pendente.

**Existe hoje:** nada na área. Hub: `financeiro.faturas_associado` por **CPF**, F&O (`inventario-vizinhos.md:25`), sem contact_id (P-04) e sem parecer de licença (P-08, `docs/PENDENCIAS.md:60`). Flag `erp_financeiro` desligada (`sql/003_feature_flag.sql:40`).

**Falta:**
- SQL: `associado_financeiro` (cache mínimo: `contact_id`, `situacao ENUM(em_dia, em_atraso, desconhecida)`, `dias_atraso`, `atualizado_em`, `fonte`); **sem valores** no cache (minimização; valores vêm do hub na hora, só na P08). UPDATE justificado (cache). `parametro` em B13 para `dias_atraso_suspensao`.
- jobs: `sincronizar_financeiro` (diário) pelo hub.
- API/dominio: estado "Suspenso" da elegibilidade só lê o cache.

**Estado:** ⛔ (P-04, P-08, "novo sistema de cobrança" segundo a spec L1126). **Fase spec:** F1 condicionada (P08). **Roteiro:** Fase 7.

### §8.5 · Ciclo da solicitação e log imutável de status

**Spec pede** (spec L754-768): 8 status internos (`criada`, `enviada`, `em_atendimento`, `pendente_associado`, `concluida_positiva`, `concluida_negativa`, `cancelada`, `sem_retorno` marcador); toda mudança no log imutável com data, status anterior, novo, origem, **conteúdo enviado**; mudança manual exige justificativa; associado avalia 0–10 após concluída (spec L405); prazo e contato na lista (L402); responsável e prazo no tipo 3 (L391).

**Existe hoje:** só desenho: ADR-0003 (6 estados, `docs/adr/0003-…:27-39`), REQ §7 (REQ L1027-1091) com transições, `crm_sync` {pendente, ok, erro, falhou} (REQ L1087; ADR-0003:35 diz 3 valores — divergência interna), tipos fechados sem vínculo com benefício/parceiro (REQ L1072-1081). Catálogo tem `solicitacao_criar/cancelar/responder/status_alterado` (`app/uso.py:107-110`). `solicitacoes_aguardando` fixo em 0 (`inventario-codigo.md:8`). Nenhuma tabela.

**Falta:**
- SQL (`sql/008`): `solicitacao` com UPDATE (`status`, `crm_*`, `prazo_retorno_em`, `sem_retorno_em`, `responsavel_id`), colunas novas `beneficio_id`, `parceiro_id`, `tipo_ativacao`, `canal_envio`; `solicitacao_evento` append-only com `origem ENUM(sistema, associado, crm, parceiro_api, importacao, usuario_interno)`, `ator_id`, `justificativa` (obrigatória por CHECK quando `origem='usuario_interno'`), `conteudo_enviado` (ver DEC-A02), `request_id`; `solicitacao_avaliacao` append-only (`nota` 0–10 com CHECK, `comentario` curto sem HTML, 1 por solicitação por índice único).
- dominio: `app/dominio/solicitacoes.py` com tabela de transições para 8 status (ADR nova).
- jobs: outbox para o CRM (ADR-0003 §5), sync de volta, `marcar_sem_retorno` (A05).
- API: `/api/v1/solicitacoes` + cancelar/responder/avaliar.

**Estado:** ⬜ (local) / ⛔ (espelho, P-06 `docs/PENDENCIAS.md:56`). **Fase spec:** F1 (SOL-01, SOL-04). **Roteiro:** Fase 3 (próxima).

### §8.1 · Elegibilidade (6 estados)

**Spec pede** (spec L704-717): disponível = categoria permitida ∧ tempo de filiação ≥ carência ∧ situação financeira permite ∧ região atendida ∧ vigente; estados Disponível, Ativo, Libera em N dias, Não disponível para a categoria, Suspenso, Indisponível na região.

**Existe hoje:** nada além do gate do IdP (tipo/situação obrigatórios, ADR-0016) e flag `totalpass` (`inventario-requisitos.md:64`). REQ `beneficio` previa só `slug, categoria, título, CTA, URL, valor de referência` (REQ L998).

**Falta:**
- SQL: em `beneficio`: `vigencia_inicio`, `vigencia_fim`, `carencia_meses`, `regional` (NULL = nacional), `exige_adimplencia`; `beneficio_categoria_associado` (matriz benefício × categoria do associado — §8.3); `beneficio_regiao` (se regional por lista).
- dominio: `app/dominio/elegibilidade.py` função pura `estado(beneficio, perfil, financeiro, ativacoes, hoje)`; insumos: `associado_perfil.data_filiacao`, `tipo_associado`, `regional_cod`, `associado_financeiro.situacao`, `beneficio_ativacao`.
- API: campo `estado` + `libera_em` em `/beneficios` e `/beneficios/{slug}`.

**Estado:** ⬜ (regra) / ⛔ (dados de regional, financeiro, categorias validadas — spec §15.5 L1256-1259). **Fase spec:** F0 (catálogo com regras validadas) → F1. **Roteiro:** Fase 4.

### §8.2 · Carências como dados configuráveis (B13)

**Spec pede** (spec L720-733): tabela de carências por benefício (6/3/2/1 meses), **configurável no backoffice**, regulamento de 01/03/2024; Clube pendente de validação.

**Existe hoje:** nada (`inventario-requisitos.md:64`).

**Falta:**
- SQL: `beneficio.carencia_meses` + histórico de alteração em `beneficio_versao` (ou `backoffice_auditoria` com valor anterior). Carência é atributo do benefício, não tabela própria — evita junção extra e segue a regra "configurável sem desenvolvimento". `associado_categoria_hist` para decidir "mudança de categoria reinicia a contagem?" (spec L740-741, recomendação: não; então a contagem usa `data_filiacao` original).
- dominio: `libera_em = data_filiacao + carencia_meses` (base: `data_filiacao`, DEC-A05).
- jobs: `carencias_vencidas` diário → evento `carencia_vencer` + outbox A03.

**Estado:** ⬜. **Fase spec:** F0 validação → F1. **Roteiro:** Fase 4.

### §8.3 · Matriz benefício × categoria

**Spec pede** (spec L737-741): motor nasce com a matriz benefício × categoria para a regra entrar por configuração.

**Existe hoje:** nada.

**Falta:** SQL: `beneficio_categoria_associado(beneficio_id, categoria_associado ENUM(academico, aspirante, efetivo, remido), permitido, desde)` com UPDATE pelo backoffice; para a F1 a matriz nasce "todos permitidos" (hoje só o tempo de filiação diferencia, spec L737-738). Vocabulário de categoria: o IdP devolve `tipo_associado` como **rótulo** (`inventario-vizinhos.md:20`) — precisa de tabela de-para rótulo → código (EXT-A01).

**Estado:** ⬜. **Fase spec:** F1. **Roteiro:** Fase 4.

### §8.4 / B13 · Parâmetros configuráveis

**Spec pede** (spec L745, L823): dias de atraso, prazos, carências, valores de referência, consentimentos e versões, usuários e perfis — editáveis no backoffice.

**Existe hoje:** `feature_flag` só SELECT pela aplicação, operador por SQL (`sql/003_feature_flag.sql:9-11`). Nenhum parâmetro numérico.

**Falta:** SQL: `parametro(chave PK, valor VARCHAR, tipo ENUM(int, decimal, bool, texto), descricao, atualizado_em, atualizado_por)` com CHECK de chave como `feature_flag` (`sql/003:28`), **UPDATE só pelo usuário do backoffice** (DEC-A03); leitura pela área com cache como `app/flags.py` (TTL 60 s). Se o backoffice não existir na F1, segue o modelo de `feature_flag`: operador por SQL, sem GRANT UPDATE a `apm_area`.

**Estado:** 🟡 (modelo existe para flags). **Fase spec:** F1 (B13). **Roteiro:** Fase 4.

### §8.6 · Uso e valor (modalidades, níveis 1–4, valores de referência)

**Spec pede** (spec L773-783, L985-1000): 5 modalidades (economia por uso, desconto do parceiro, serviço da APM, proteção incluída, estimado — nunca somado); níveis de evidência 1–4 por benefício **e por registro**; valor de referência com fonte, data, aprovação do Financeiro, revisão anual; relação (comprovado + proteção) ÷ pago; P06 exige item a item com data, benefício, economia, fonte (spec L427-432).

**Existe hoje:** nada. REQ previa "Fatura de valor derivada de `beneficio_ativacao` × valor" (REQ L1015) e `valor de referência` como coluna do seed (REQ L998); flag `fatura_valor` forçada desligada (P-12, `docs/PENDENCIAS.md:75`). ADR-0012 §6 prevê views por migração (`docs/adr/0012-…:56-57`).

**Falta:**
- SQL (`sql/011`): `uso_valor` **append-only** (`contact_id`, `beneficio_id`, `parceiro_id` NULL, `solicitacao_id` NULL, `importacao_linha_id` NULL, `data_evento`, `modalidade ENUM(5)`, `nivel_evidencia TINYINT 1..4`, `valor_referencia`, `valor_pago`, `economia` DECIMAL(12,2), `fonte ENUM(apm, parceiro_api, importacao, clube, solicitacao)`, `validado_por`, `validado_em`, `estorna_id` NULL — estorno é linha nova apontando a original; CHECK `economia = valor_referencia - valor_pago` quando os três existem; CHECK `nivel_evidencia = 4` exige `validado_em`); `valor_referencia` append-only (`beneficio_id`, `valor_anual`/`valor_unitario`, `fonte`, `data_fonte`, `aprovado_por`, `aprovado_em`, `vigencia_inicio`, `vigencia_fim`, `revisao_prevista_em`) — a vigente é a de maior `vigencia_inicio ≤ hoje` com `aprovado_em` não nulo; `beneficio.modalidade_mensuracao ENUM(api_acesso_unico, relatorio_padrao, encaminhamento_sem_retorno)`.
- Views (migração): `vw_meu_valor_ano(contact_id, ano, comprovado, protecao, estimado, pago)` — proteção incluída calculada como `valor_anual × meses ativos / 12` sobre `associado_categoria_hist`/`data_filiacao`.
- dominio: `app/dominio/valor.py` (cálculo e regras de exibição de P06: contribuição 0, < 3 meses).
- Total pago: vem da cobrança (hub, P-04/P-08) — até lá a relação não aparece (regra 13/19: número sem fonte não chega ao associado).

**Estado:** ⬜ (estrutura) / ⛔ (total pago e aprovação do Financeiro). **Fase spec:** F1 VAL-01. **Roteiro:** Fase 8 hoje; **propor antecipar a estrutura para a Fase 4** (TI-A07).

### §11.2 · Eventos de uso (28 da spec × 36 de `app/uso.py`)

**Spec pede** (spec L950-983): 28 eventos com propriedades; propriedades comuns a todos: id pseudonimizado, categoria, fase de carreira, especialidade, regional, tempo de casa, dispositivo, UTM, data/hora.

**Existe hoje:** `evento_uso` (`sql/004`), catálogo fechado de 36 ações (`app/uso.py:83-120`), 16 permitidas da UI (`:122`), detalhes da UI só com chaves tipadas (`:162-166`), CPF barrado antes do banco (`:170-171`) e no CHECK (`sql/004:46-58`), identidade sempre da sessão (`app/uso.py:10-12`). 8 ações emitidas (`inventario-codigo.md:25`). Equivalências: 12 de 28 (`inventario-requisitos.md:65`; `INDICE-IDS.md:85-114`).

**Falta:** 16 eventos sem equivalente (`INDICE-IDS.md:87-114`); propriedades comuns ausentes; `beneficio_visto` sem `origem`/`estado`; `conteudo_lido` sem tempo; `busca` sem termo (RNF-16, DIV-A01). Proposta completa em "Catálogo de eventos unificado". O que **não** entra em `evento_uso`: ver DIV-A01 e a seção do catálogo.

**Estado:** 🟡 (tabela e mecanismo prontos; catálogo 43 % coberto). **Fase spec:** F1. **Roteiro:** transversal (cada fase acrescenta ações).

### §11.2.1 · Níveis de evidência e qualidade do dado

**Spec pede** (spec L985-1004): nível 1–4 por benefício e por registro; modalidade de mensuração por benefício; painéis de completude, duplicidade, atraso de retorno, registros sem associação, taxa de conciliação por parceiro.

**Existe hoje:** nada.

**Falta:** SQL: `uso_valor.nivel_evidencia`, `beneficio.modalidade_mensuracao`, `importacao.{linhas_total, linhas_validas, linhas_erro, linhas_sem_associado}`, `parceiro.prazo_retorno_dias`; views `vw_qualidade_parceiro_mes`. O nível de um registro é derivado da fonte: nível 1 = `evento_uso` (visto), 2 = `solicitacao` criada, 3 = `solicitacao` concluída positiva ou `uso_valor` sem validação, 4 = `uso_valor` validado — regra em `dominio/valor.py`, não coluna duplicada em `evento_uso`.

**Estado:** ⬜. **Fase spec:** F1. **Roteiro:** Fase 4/8.

### §11.3 · Indicadores 1–14 (fonte de numerador e denominador)

**Spec pede** (spec L1009-1024). Mapa de fontes:

| # | Indicador | Numerador | Denominador | Fonte disponível hoje? |
|---|---|---|---|---|
| 1 | Associados com acesso | `associado.ultimo_acesso_em` no mês (`sql/005:22`) ou `evento_log` `login_ok` (`contact_id` existe, `sql/002:35`) | base ativa (cadastro) | 🟡 numerador sim; denominador exige contagem do CRM pelo hub (EXT-A05) |
| 2 | Ativação em 30 dias | `uso_valor` nível ≥ 3 ou `solicitacao` concluída, até 30 d de `data_filiacao` | novos do mês (cadastro) | ⬜ |
| 3 | Benefícios em uso 90 d | `COUNT(DISTINCT beneficio_id)` em `uso_valor` nível ≥ 3 | associados ativos | ⬜ |
| 4 | Valor entregue | `vw_meu_valor_ano` | total pago (cobrança, P-08) | ⛔ |
| 5 | Rastro | `solicitacao.status` terminal | `solicitacao` criadas | ⬜ (Fase 3) |
| 6 | Prazo do parceiro | mediana `solicitacao_evento` (`enviada` → primeiro retorno) por `parceiro_id` | — | ⬜ (Fase 3; mediana em MySQL 8.4 via `ROW_NUMBER`, em view) |
| 7 | Conversão por parceiro | `concluida_positiva` | solicitações do parceiro | ⬜ |
| 8 | Novos com origem | cadastro (`filiacao.resumo_periodo` do hub, `inventario-vizinhos.md:25`) | — | ⛔ fora da área; painel lê do hub |
| 9 | Taxa de conversão | `associado_categoria_hist` + leads (`lead`) | — | ⛔ (histórico por CPF no hub, P-04) |
| 10 | Pessoas comunicadas | `comunicacao_envio` (entregue/aberto/clicado via RD) | base ativa | ⬜ (§12) |
| 11 | Renovação × uso | renovação (cadastro) × `uso_valor` por coorte | — | ⛔ (renovação não existe como dado na área) |
| 12 | Cancelamento precoce | `cancelamento_pedido` até 90 d de `data_filiacao` | novos | ⬜ (P14) |
| 13 | Motivo "não utiliza" | `cancelamento_pedido.motivo` | cancelamentos | ⬜ |
| 14 | Saúde técnica | `evento_log` `login_falha` (`inventario-codigo.md:28`), `erro_exibido` (`app/uso.py:119`); LCP/INP não existem (RNF cita CLS, `REQ L876`) | — | 🟡 |

**Falta:** views por migração (ADR-0012 §6) `vw_ind_01..14`, cada uma com `mes` e o recorte (regional, categoria) para os painéis; `base_ativa_mensal` (snapshot mensal da contagem do CRM por categoria/regional, gravado por job — único jeito de ter denominador estável sem consultar o CRM em cada painel).

**Estado:** 🟡 (1 e 14 parciais; 5–7, 12–13 construíveis; 2–4, 8–11 dependem de dados externos). **Fase spec:** F1 (B12 v1). **Roteiro:** sem fase (backoffice fora de escopo, REQ L112).

### §11.5 · Painéis (B12) e exportação

**Spec pede** (spec L1037-1043): 5 painéis (Diretoria, Benefícios e parceiros, Operação, Produto, Regionais); patrocinador só agregado; §11.6: agregados com ≥ 20 pessoas por recorte (L1053-1054).

**Existe hoje:** nada; `evento_uso` é fonte (`INDICE-IDS.md:54`).

**Falta:** views com **supressão k-anonimato ≥ 20** embutida (`HAVING COUNT(DISTINCT contact_id) >= 20`) para qualquer recorte que saia para parceiro/patrocinador/regional; usuário de banco **somente leitura das views** (`apm_area_painel`, só `SELECT ON vw_*`) para a ferramenta de painel (F0-06, spec L1137 "ferramenta a definir"); exportação CSV só agregada. Sem ferramenta definida, o painel v1 pode ser uma página do backoffice lendo as views.

**Estado:** ⬜ / ⛔ (F0-06: destino dos eventos e ferramenta). **Fase spec:** F1 (v1). **Roteiro:** sem fase.

### §11.4 · Score de engajamento (tabela diária)

**Spec pede** (spec L1028-1033): 0–100 por associado, recalculado todo dia, 5 componentes, faixas; pesos recalibrados após 3 meses.

**Existe hoje:** nada. Componentes: recência de acesso (`associado.ultimo_acesso_em`), benefícios em uso 90 d (`uso_valor`), comunicação (`comunicacao_envio`), financeiro (`associado_financeiro`), eventos/conteúdo (`evento_uso`).

**Falta:** SQL: `score_engajamento(contact_id, data, score, c_recencia, c_uso, c_comunicacao, c_financeiro, c_conteudo, versao_pesos)` **append-only** (uma linha por associado por dia; PK `(contact_id, data)`; particionada por mês para expurgo por `DROP PARTITION` administrativo); `score_pesos` versionado (B13). Job diário. Volume: base × 365 linhas/ano — ver "Volume".

**Estado:** ⬜. **Fase spec:** F2. **Roteiro:** sem fase (pós-Fase 8).

### §13.3 · Importação do relatório padrão (CSV) — `importacao` / `importacao_linha`

**Spec pede** (spec L1159-1180; §10.3 L862-875; B06 L816): CSV `;` UTF-8 com `cpf;parceiro_id;beneficio_id;tipo;data_evento;status;valor_referencia;valor_pago;economia;id_externo;observacao`; `id_externo` impede duplicidade; validação de CPF, associado, duplicidade, datas, valores; prévia com erros por linha; confirmação; devolução; CPF não associado vira lead (§10.4).

**Existe hoje:** nada. **Conflito direto com ADR-0014** (🔒): a área não aceita CPF em nenhuma rota, não o grava nem o envia ao hub (`docs/adr/0014-…:31-33`). O arquivo da spec chega chaveado por CPF.

**Falta:**
- Resolução do CPF **fora da área** (DIV-A02 / EXT-A02): o upload vai ao `mcp_hub` (ferramenta `importacao.resolver_lote`: recebe o CSV, devolve as linhas com `contact_id` ou `sem_associado`, e cria o lead no CRM/RD para os não associados); a área só recebe e guarda linhas sem CPF. Alternativa: a área recebe o arquivo, mas o descarta da memória após mandar ao hub, nunca persiste; o hub devolve `contact_id` por posição — ainda assim o CPF "entra" na área em trânsito; a recomendação é o upload direto no hub.
- SQL (`sql/011`): `importacao(id, parceiro_id, competencia, arquivo_nome, arquivo_sha256, linhas_total, linhas_validas, linhas_erro, linhas_sem_associado, status ENUM(recebida, validada, confirmada, devolvida), usuario_id, criada_em, confirmada_em)` com UPDATE (`status`, contagens); `importacao_linha(id, importacao_id, numero, contact_id NULL, parceiro_id, beneficio_id, tipo, data_evento, status_linha, valor_referencia, valor_pago, economia, id_externo, observacao ≤ 200, erro_codigo, uso_valor_id NULL)` append-only + **índice único `(parceiro_id, id_externo)`** (idempotência: reenvio do mesmo arquivo não duplica; linha repetida vira `erro_codigo = duplicada`) + CHECK anti-CPF em `observacao` (mesma regex de `sql/004:55-56`). Confirmar = INSERT em `uso_valor` (nível 3; nível 4 após validação do Financeiro) com `importacao_linha_id`.
- jobs: `processar_importacao` (validação e prévia); nunca no processo web (arquivo até alguns MB, parsing em memória).
- CPF em `observacao` ou em qualquer coluna textual: o CHECK recusa a linha inteira — o job precisa filtrar antes (padrão de `app/uso.py:46-48`).

**Estado:** ⚠️ (spec × ADR-0014) / ⬜. **Fase spec:** F1 (B06). **Roteiro:** sem fase; dependente de P-04 ampliado.

### §12 · Outbox de comunicação (`comunicacao_evento`) e log de envios (B09)

**Spec pede** (spec L1065-1071, L1078-1099, L1103-1114): evento → campo/evento no RD → fluxo → clique volta com UTM e código do gatilho; 20 gatilhos (F1: A01–A06, A09, A16, A17, A18); limite 2 msg/semana, WhatsApp 1; prioridade entre fluxos; supressão; consentimento por canal; horário; log de envios, notificações no app, supressões e descadastros (B09).

**Existe hoje:** nada na área. RD Station integrado em `app_facial_recognition` (ligado) e `totalpass` (desligado) com tabela `rdstation_eventos` e cron próprio (`inventario-vizinhos.md:36`). A área não tem credencial do RD.

**Falta:**
- SQL (`sql/0NN`): `comunicacao_evento` (outbox: `id`, `gatilho ENUM(A01..A20)`, `contact_id`, `referencia_tipo/id` (solicitação, benefício…), `canal_preferido`, `criado_em`, `enviar_apos` (janela 8h–20h), `status ENUM(pendente, enviado, suprimido, erro, falhou)`, `tentativas`, `proxima_tentativa_em`, `supressao_motivo`, `rd_evento_id`) com UPDATE (`status`, tentativas); `comunicacao_envio` append-only (`comunicacao_evento_id`, `canal`, `enviado_em`, `entregue_em`, `aberto_em`, `clicado_em`, `origem_retorno ENUM(rd_webhook, utm)`); `comunicacao_supressao` append-only (`contact_id`, `motivo ENUM(limite_semana, financeiro, cancelamento, sem_consentimento, recomendado_recente)`, `gatilho`, `em`); descadastro = consentimento retirado (§11.6), não tabela própria. Índice único `(gatilho, contact_id, referencia_id)` para não disparar duas vezes o mesmo gatilho pela mesma causa. Limite semanal: consulta sobre `comunicacao_envio` dos últimos 7 dias antes de marcar `enviado`.
- integrações: `app/integracoes/rdstation.py` (só no serviço de jobs; credencial OAuth2 em `Settings`; EXT-A04); recebimento de webhook do RD (entregue/aberto/clicado) é rota pública nova → `limit_req` + assinatura (Sentinela).
- Transacionais (A04, A06, código de e-mail) saem do próprio sistema (spec L1067-1068): SMTP já existe (`app/integracoes/email.py`), P-27.

**Estado:** ⬜ / ⛔ (credencial RD, EXT-A04; WhatsApp/SMS pendente de contrato, spec L1136). **Fase spec:** F1 (log) / F2 (completo). **Roteiro:** sem fase.

### §11.6 / P13 · Consentimentos versionados e direitos do titular

**Spec pede** (spec L934, L1048-1057, L546-547, L1196): consentimento por finalidade, canal, valor, data, origem, versão do texto; histórico; baixar meus dados; pedir exclusão com fila no backoffice; registro de acesso a dados pessoais no backoffice.

**Existe hoje:** só minimização estrutural (CHECKs, HMAC, `contact_id`) (`inventario-codigo.md:46`). Nenhuma tabela.

**Falta:**
- SQL: `consentimento_texto(id, finalidade ENUM(ofertas_parceiros, whatsapp_relacionamento, …), canal, versao, texto, vigente_desde, criado_por)` só INSERT (texto novo = linha nova, nunca editar); `consentimento(id, contact_id, consentimento_texto_id, valor TINYINT(1), origem ENUM(perfil, onboarding, backoffice, importacao), request_id, ocorrido_em)` **append-only** — o estado atual é a última linha por `(contact_id, finalidade, canal)`; view `vw_consentimento_atual`. Evento `consentimento_alterar` em `evento_uso`.
- `preferencia_canal(contact_id PK, canal_preferido, frequencia, atualizado_em)` com UPDATE (é perfil declarado, não trilha); `perfil_declarado` (área de atuação, temas, tratamento) idem.
- `titular_pedido(id, contact_id, tipo ENUM(exportacao, exclusao), status, pedido_em, atendido_em, atendido_por, observacao)` com UPDATE (status). "Exclusão" na área = anonimização administrativa (ADR-0004 §3: DELETE nunca pela aplicação; expurgo é ato do operador) — procedimento em `docs/` (TI-A14).
- "Baixar meus dados": job gera o pacote (JSON) a partir de `associado_perfil`, `solicitacao`, `uso_valor`, `consentimento`, `evento_uso` do `contact_id`; entregue por link assinado com validade curta, nunca anexado ao e-mail.

**Estado:** ⬜. **Fase spec:** F1 (PER-03, B13). **Roteiro:** sem fase; proposto para a Fase 3 junto do perfil.

### §9 · Usuário interno, perfis e auditoria do backoffice

**Spec pede** (spec L789-790, L795-804, L945, L1198): 8 perfis, 2FA, toda ação registrada com perfil, ação, data, **valor anterior**; log imutável de ações.

**Existe hoje:** nada. REQ L112: "backoffice próprio" fora de escopo; atendimento no CRM. `feature_flag` só por operador (`INDICE-IDS.md:55`).

**Falta (condicionado a DEC-A03):**
- SQL: `usuario_interno(id, email, nome, perfil ENUM(8), ativo, criado_em, desativado_em)` com UPDATE; **sem senha na área** — autenticação pelo Entra ID/IdP corporativo (OIDC, mesmo padrão da área) para herdar o 2FA, nunca hash de senha próprio; `backoffice_auditoria(id, usuario_id, acao, tabela, registro_id, valor_anterior JSON, valor_novo JSON, justificativa, request_id, ocorrido_em)` **append-only** com CHECK anti-segredo/CPF (mesma lista de `app/audit.py:29-31`); `acesso_dado_pessoal` (registro de leitura da visão 360 — B02; spec L1196-1197) append-only.
- infra: **usuário de banco distinto** `apm_area_bo` com GRANT UPDATE nas tabelas de catálogo/configuração (`beneficio`, `parceiro`, `parametro`, `valor_referencia`, `importacao`, `solicitacao`) e **sem** UPDATE nas tabelas do associado; o `apm_area` (web do associado) continua sem UPDATE em catálogo. O `db_check.py` passa a validar dois usuários (allowlist por usuário).

**Estado:** ⛔ (decisão de produto: backoffice próprio × CRM × ferramenta). **Fase spec:** F1 (B01–B06, B12, B13). **Roteiro:** fora de escopo (REQ L112) — conflito com a spec (DIV-A03).

### `job_execucao`

**Spec pede:** implícito em §10 (importações, fila, alertas de integração em B01 L811) e RNF-17 do REQ (`REQ L881`).

**Existe hoje:** nome na allowlist (`scripts/db_check.py:33`), previsto em `sql/012` Fase 3 (REQ L1012) — numeração fora da ordem de fase. Nenhum job existe (`inventario-codigo.md:15`).

**Falta:** SQL `job_execucao(id, job VARCHAR(48) CHECK regex, iniciado_em, terminado_em, status ENUM(executando, ok, erro, abortado), itens_lidos, itens_gravados, itens_erro, erro_resumo VARCHAR(500) sem segredo/CPF (CHECK), host, versao_app)` com UPDATE (`terminado_em`, `status`, contagens) — justificativa: a linha nasce no início e fecha no fim; índice `(job, iniciado_em)`; **trava de concorrência** por `GET_LOCK('job:<nome>')` (não por linha), para o serviço de jobs poder rodar com réplica. Retenção: 90 dias (P-15).

**Estado:** ⬜. **Fase spec:** F1. **Roteiro:** Fase 3 (junto do outbox) — renumerar para `sql/009` (TI-A03).

### Retenção, purga (P-15) e "prazo de guarda definido pelo jurídico"

**Spec pede** (spec L1057): prazo de guarda de logs de solicitação e auditoria definido pelo jurídico.

**Existe hoje:** propostas em comentário: `evento_log` `request` 12 meses (`sql/002:14-17`), `evento_uso` 24 meses (`sql/004:19-22`; ADR-0012:85-86), `email_verificacao` 30 dias (`sql/007:18-19`); P-15 aberta (`docs/PENDENCIAS.md:85`); purga por `DELETE … LIMIT` do operador. `evento_uso` tem PK só `id` (`sql/004:38`), sem partição.

**Falta:**
- Decisão do jurídico por tabela (EXT-A06): `solicitacao`/`solicitacao_evento` (prazo civil ≥ 5 anos é a hipótese), `backoffice_auditoria`, `consentimento` (enquanto durar a relação + prazo), `uso_valor` (fiscal, repasses), `evento_uso` (24 meses), `score_engajamento` (90 dias de histórico bastam), `comunicacao_envio` (12 meses), `job_execucao` (90 dias), `importacao_linha` (igual a `uso_valor`).
- Mecanismo: converter as tabelas de volume (`evento_uso`, `score_engajamento`, `comunicacao_envio`, `evento_log`) para `PARTITION BY RANGE (TO_DAYS(ocorrido_em))` mensal com PK `(id, ocorrido_em)` — o expurgo vira `ALTER TABLE … DROP PARTITION` administrativo, instantâneo, sem `DELETE` em lotes e sem fragmentar o InnoDB. Fazer **agora**, com a tabela pequena (TI-A02). Consentimento e trilhas de solicitação nunca se purgam por partição (guarda longa).
- Documento `docs/RETENCAO.md` com a tabela e o procedimento (usuário administrativo, janela, conferência).

**Estado:** 🟡 (propostas sem decisão). **Fase spec:** F0 (critérios de LGPD). **Roteiro:** P-15 "após Fase 5" — antecipar.

### Volume e cotas (P-41)

**Spec pede:** nada explícito; §14 cita disponibilidade e cópia diária com teste de restauração (L1202-1203).

**Existe hoje:** P-41 aberta (`docs/PENDENCIAS.md:99`): hub provisório 120 chamadas/min e 5.000 PII/dia; `PERFIL_CACHE_TTL` 24 h; pool 5+10 por worker × 2 workers (`inventario-codigo.md:31`). Base ativa: número não consta em nenhum documento do repositório.

**Falta:** estimativa com a base ativa (EXT-A05). Ordem de grandeza por associado: login = 1 upsert `associado` + 1 upsert `associado_perfil` + 1 `evento_log`; sessão típica = 5–15 `evento_uso` (lotes de até 20, `app/uso.py:39`); score = 1 linha/dia; comunicação = ≤ 2/semana. Para 10 mil associados com 30 % de acesso mensal: `evento_uso` ≈ 30–50 mil linhas/mês (irrelevante para o InnoDB), `score_engajamento` ≈ 300 mil linhas/mês (particionar). Jobs novos adicionam ao hub: `atualizar_perfis` (1 chamada por associado por dia = 10 mil/dia, estoura a cota PII de 5.000 — **negociar cota ou renovar só quem acessou nos últimos 90 dias**), `sincronizar_financeiro` idem. Backup: RDS automático; falta **teste de restauração** documentado (TI-A15, com Estivador).

**Estado:** 🟡. **Fase spec:** F0. **Roteiro:** P-41.

### Migrações previstas no REQUISITOS × o que muda com a spec v2

**REQ §6 previa** (REQ L1001-1012): `sql/008` solicitacao + solicitacao_evento · `sql/009` beneficio_categoria, beneficio (seed, SELECT), beneficio_ativacao · `sql/010` noticia_cache, evento_cache, tema, associado_tema, noticia_salva, evento_inscricao · `sql/011` comunidade, comunidade_adesao, onboarding_passo, onboarding_progresso · `sql/012` job_execucao. Roteiro de PENDENCIAS cita "sql/007 seed" na Fase 4 (`docs/PENDENCIAS.md:113`) — erro, 007 é `email_verificacao` (`inventario-codigo.md:43`).

**O que muda:** `beneficio` deixa de ser seed só SELECT e vira catálogo com regras, vigência, carência, matriz, parceiro, valor de referência versionado e UPDATE pelo backoffice (ADR nova); `solicitacao` ganha 8 status, benefício/parceiro, prazo, responsável, avaliação e log com origem/justificativa (ADR-0003 revisada); entram `uso_valor`, `importacao(_linha)`, `consentimento(_texto)`, `preferencia_canal`, `perfil_declarado`, `associado_financeiro`, `associado_categoria_hist`, `parametro`, `comunicacao_*`, `usuario_interno`, `backoffice_auditoria`, `score_engajamento`, `base_ativa_mensal`, views `vw_*`; `job_execucao` sobe para `sql/009`; `onboarding_passo` passa a ser por categoria (spec L519-535), não só Acadêmico (REQ L1010 "6 passos", LA-21).

**Estado:** ⚠️ (REQ §6 desatualizado para a spec v2). **Fase:** F0 (revisar REQ §6 antes da Fase 3).

---

## Modelo de dados proposto

Convenções (mantidas de REQ L980-982): `contact_id CHAR(36)` com CHECK de GUID (padrão de `sql/005:28-30`), `sub_hash CHAR(64)` onde houver correlação com `evento_log`, datas `DATETIME(6)` UTC, JSON com CHECK anti-segredo/CPF (lista de `app/audit.py:29-31` + regex de `sql/004:55-56`), remoção lógica por coluna, `GRANT UPDATE` na própria migração com comentário de justificativa. Numeração abaixo é **reserva** na ordem de aplicação; o número definitivo é o da migração quando ela for aprovada.

| Migração | Tabela | Finalidade | Colunas-chave | UPDATE? (justificativa) | Append-only | Índices / CHECKs | Fase spec / roteiro |
|---|---|---|---|---|---|---|---|
| `sql/008` | `solicitacao` | fonte da verdade do pedido (ADR-0003) | `id CHAR(36)` uuid, `contact_id`, `sub_hash`, `tipo`, `tipo_ativacao` 1–6, `beneficio_id` NULL, `parceiro_id` NULL, `status ENUM(8)`, `sem_retorno_em` NULL (marcador), `prazo_retorno_em`, `responsavel_id` NULL, `dados JSON` ≤ 16 kB, `chave_idempotencia`, `crm_id`, `crm_sync`, `crm_tentativas`, `crm_proxima_em`, `criada_em`, `atualizada_em`, `concluida_em` | **sim** — transição de status, outbox CRM, marcador de prazo, responsável | não | `(contact_id, status)`, `(crm_sync, crm_proxima_em)`, `(status, prazo_retorno_em)` p/ A05, `(parceiro_id, criada_em)` p/ ind. 6–7, único `(contact_id, chave_idempotencia)`; CHECK anti-CPF em `dados`; CHECK `sem_retorno_em IS NULL OR status IN ('enviada','em_atendimento','pendente_associado')` | F1 SOL-01 / Fase 3 |
| `sql/008` | `solicitacao_evento` | log imutável de status (§8.5) | `solicitacao_id`, `de_status` NULL, `para_status`, `origem ENUM(sistema, associado, crm, parceiro_api, importacao, usuario_interno)`, `ator_id` NULL, `justificativa` VARCHAR(500) NULL, `mensagem_publica`, `conteudo_enviado` (ver DEC-A02), `request_id`, `ocorrido_em` | **não** | sim | `(solicitacao_id, ocorrido_em)`; CHECK `origem <> 'usuario_interno' OR justificativa IS NOT NULL`; CHECK anti-CPF em JSON/texto | F1 / Fase 3 |
| `sql/008` | `solicitacao_avaliacao` | "como foi?" 0–10 (spec L405, A06) | `solicitacao_id` único, `contact_id`, `nota TINYINT`, `comentario` VARCHAR(500) NULL, `ocorrido_em` | não | sim (1 por solicitação) | CHECK `nota BETWEEN 0 AND 10`; anti-CPF em `comentario` | F1 / Fase 3 |
| `sql/009` | `job_execucao` | rastro de cada execução de job | `job`, `iniciado_em`, `terminado_em`, `status`, contagens, `erro_resumo` | **sim** — fechar a linha aberta no início | não | `(job, iniciado_em)`; CHECK regex em `job`; CHECK anti-segredo em `erro_resumo` | F1 / Fase 3 |
| `sql/010` | `parceiro` | B04: dados, requisito técnico, prazo, repasse | `id` (código APM, ex. `PAR017`), `nome`, `requisito ENUM(api, relatorio, portal)`, `prazo_retorno_dias`, `vigencia_inicio/fim`, `contato JSON` (sem CPF), `ativo` | **sim**, só pelo usuário do backoffice (DEC-A03); `apm_area` só lê | não | único `id`; CHECK regex do código | F1 B04 / Fase 4 |
| `sql/010` | `beneficio_categoria` | 8 categorias da spec (L339-341) | `slug`, `nome`, `grupo`, `ordem`, `ativo` | backoffice | não | — | F1 / Fase 4 |
| `sql/010` | `beneficio` | ficha B03 (catálogo como dado) | `id` (`BEN042`), `slug`, `categoria_slug`, `parceiro_id` NULL, textos, `tipo_ativacao` 1–6, `destino`, `carencia_meses`, `exige_adimplencia`, `regional` NULL, `modalidade_mensuracao`, `nivel_evidencia_max`, `prazo_retorno_dias` NULL (sobrepõe o do parceiro), `vigencia_inicio/fim`, `status ENUM(rascunho, aprovado, publicado, encerrado)`, `publicado_em`, `patrocinado`, `ordem`, `criado_em` | backoffice (rascunho → publicado; vigência); `apm_area` só lê | não (histórico em `beneficio_versao`) | `(status, vigencia_inicio, vigencia_fim)`, `(categoria_slug)`; CHECK `carencia_meses BETWEEN 0 AND 12`; CHECK status × datas | F1 CAT-02/CAT-05 / Fase 4 |
| `sql/010` | `beneficio_versao` | histórico da ficha (B03 "histórico") | `beneficio_id`, `versao`, `snapshot JSON`, `usuario_id`, `criado_em` | não | sim | único `(beneficio_id, versao)` | F1 / Fase 4 |
| `sql/010` | `beneficio_categoria_associado` | matriz benefício × categoria do associado (§8.3) | `beneficio_id`, `categoria_associado ENUM(academico, aspirante, efetivo, remido)`, `permitido`, `desde` | backoffice | não | PK composta | F1 / Fase 4 |
| `sql/010` | `beneficio_afinidade` | matriz de afinidade por segmento (§7.3, B08) | `beneficio_id`, `segmento` (faixa de carreira / área de atuação), `pontos 0..3` | backoffice | não | PK composta; CHECK pontos | F1 HOM-01 / Fase 4 |
| `sql/010` | `beneficio_ativacao` | associado × benefício (tipo 1; "Ativo") | `contact_id`, `beneficio_id`, `ativo`, `ativado_em`, `desativado_em` | **sim** — desativar (ADR-0004 §3) | não | único `(contact_id, beneficio_id)` | F1 / Fase 4 |
| `sql/010` | `recomendacao_dispensa` | "sai por 60 dias" (§7.3 L650) | `contact_id`, `beneficio_id`, `motivo ENUM`, `dispensada_em` | não | sim (a vigência é calculada: 60 d da última linha) | `(contact_id, beneficio_id, dispensada_em)` | F1 / Fase 4 |
| `sql/010` | `parametro` | B13: dias de atraso, prazos, pesos | `chave` PK, `valor`, `tipo`, `descricao`, `atualizado_em`, `atualizado_por` | backoffice (ou operador por SQL como `feature_flag`) | não | CHECK regex da chave (`sql/003:28`) | F1 / Fase 4 |
| `sql/010` | `associado_categoria_hist` | histórico de categorias (carência, ind. 9, A13) | `contact_id`, `categoria`, `desde`, `ate` NULL, `fonte ENUM(crm, importacao)`, `gravado_em` | não | sim | `(contact_id, desde)` | F1 / Fase 4 (⛔ P-04) |
| `sql/010` | `associado_perfil` (ALTER) | campos de personalização | `+faixa_carreira`, `+especialidade_cod`, `+regional_cod`, `+nome_social`, `+isento_remido` | já tem | — | — | F1 / Fase 4 |
| `sql/010` | `perfil_declarado` | P13: área de atuação, temas, tratamento | `contact_id` PK, `area_atuacao SET`, `tratamento`, `atualizado_em` | **sim** — é perfil editável | não | — | F1 PER-02 / Fase 3–4 |
| `sql/011` | `valor_referencia` | §8.6: fonte, data, aprovação, revisão anual | `beneficio_id`, `valor`, `base ENUM(anual, por_uso)`, `fonte`, `data_fonte`, `aprovado_por`, `aprovado_em`, `vigencia_inicio`, `vigencia_fim` NULL, `revisao_prevista_em` | não — valor novo = linha nova; "aprovar" = INSERT da linha aprovada (rascunho sem `aprovado_em` não vale) | sim | `(beneficio_id, vigencia_inicio)`; CHECK `valor >= 0` | F1 VAL-01 / Fase 4 |
| `sql/011` | `uso_valor` | fonte única do Meu valor e dos painéis | ver §8.6 acima | não — estorno é linha com `estorna_id`; validação do Financeiro é linha nova de nível 4 apontando a de nível 3 (`valida_id`) | sim | `(contact_id, data_evento)`, `(beneficio_id, data_evento)`, `(parceiro_id, data_evento)`, `(nivel_evidencia)`; CHECKs de coerência; anti-CPF em `observacao` | F1 VAL-01 / Fase 4 (antecipar) |
| `sql/011` | `importacao` | B06 cabeçalho do arquivo | ver §13.3 | **sim** — status e contagens | não | `(parceiro_id, competencia)` | F1 B06 / sem fase |
| `sql/011` | `importacao_linha` | linhas do CSV **sem CPF** | ver §13.3 | não — erro de linha é coluna preenchida na inserção; correção = nova importação | sim | **único `(parceiro_id, id_externo)`**; anti-CPF | F1 B06 / sem fase |
| `sql/011` | `lead` | §10.4 interesse de não associado | `id`, `origem ENUM(importacao, parceiro_api, formulario, evento)`, `nome`, `email`, `telefone`, `cpf_hash` (HMAC, **nunca CPF**; a correlação é do hub/CRM), `resultado ENUM`, `contatado_em` | sim — resultado | não | `(origem, criado_em)` | F1 B05 / ⛔ (DEC-A03: lead pertence ao CRM/RD, não à área) |
| `sql/012` | `noticia_cache`, `evento_cache`, `tema`, `associado_tema`, `noticia_salva`, `evento_inscricao` | como REQ L1003-1008 | — | cache e "desfazer" (já justificados) | não | — | F2 / Fase 5 |
| `sql/013` | `consentimento_texto` | versões do texto | ver §11.6 | não | sim | único `(finalidade, canal, versao)` | F1 PER-03 / Fase 3 |
| `sql/013` | `consentimento` | decisões do titular | ver §11.6 | não | sim | `(contact_id, consentimento_texto_id, ocorrido_em)`; view `vw_consentimento_atual` | F1 / Fase 3 |
| `sql/013` | `preferencia_canal` | canais e frequência | `contact_id` PK, `canal_preferido`, `frequencia`, `atualizado_em` | sim — perfil | não | — | F1 / Fase 3 |
| `sql/013` | `titular_pedido` | fila LGPD (exportar, excluir) | ver §11.6 | sim — status | não | `(status, pedido_em)` | F1 / Fase 3 |
| `sql/014` | `comunicacao_evento` | outbox para RD / app | ver §12 | sim — status, tentativas | não | único `(gatilho, contact_id, referencia_id)`; `(status, enviar_apos)` | F1 log / sem fase |
| `sql/014` | `comunicacao_envio` | log de envios e retorno | ver §12 | não | sim (particionar) | `(contact_id, enviado_em)` | F1 / sem fase |
| `sql/014` | `comunicacao_supressao` | por que não enviou | ver §12 | não | sim | `(contact_id, em)` | F2 / sem fase |
| `sql/014` | `notificacao` | P15 notificações no app | `contact_id`, `tipo`, `titulo`, `referencia`, `criada_em`, `lida_em` NULL | **sim** — `lida_em` | não | `(contact_id, lida_em, criada_em)` | F2 / sem fase |
| `sql/016` | `comunidade`, `comunidade_adesao`, `onboarding_passo` (por categoria), `onboarding_progresso` | REQ L1009-1012 | — | como REQ | `onboarding_progresso` sim | — | F2–F3 / Fase 6 |
| `sql/017` | `usuario_interno`, `backoffice_auditoria`, `acesso_dado_pessoal` | §9 | ver §9 | `usuario_interno` sim (ativar/desativar, perfil); trilhas não | trilhas sim | anti-segredo nas trilhas | F1 / ⛔ DEC-A03 |
| `sql/018` | `associado_financeiro` | cache mínimo da cobrança | ver §8.4 | sim — cache | não | — | F1 cond. / Fase 7 (⛔ P-04, P-08) |
| `sql/019` | `score_engajamento`, `score_pesos` | §11.4 | ver §11.4 | não | sim (particionar por mês) | PK `(contact_id, data)` | F2 / sem fase |
| `sql/020` | `base_ativa_mensal` | denominadores dos indicadores | `mes`, `categoria`, `regional`, `total`, `novos`, `cancelados`, `gravado_em` | não | sim | PK `(mes, categoria, regional)` | F1 B12 / sem fase |
| `sql/021` | views `vw_ind_01..14`, `vw_meu_valor_ano`, `vw_qualidade_parceiro_mes`, `vw_consentimento_atual` | ADR-0012 §6 | — | — | — | k ≥ 20 nas de recorte; usuário `apm_area_painel` só `SELECT` nas views | F1 / sem fase |
| `sql/0NN` (cedo) | `evento_uso`, `evento_log` (ALTER) | partição mensal p/ expurgo sem DELETE | PK `(id, ocorrido_em)`, `PARTITION BY RANGE (TO_DAYS(ocorrido_em))` | — | — | manter índices atuais | F0 / agora (TI-A02) |

Tabelas que **não** devem existir na área: CPF em qualquer forma (ADR-0014), senha de usuário interno (DEC-A03), payload de comunicação (texto da mensagem vive no RD), dado de saúde (spec L1051), valor pago/mensalidades do associado além do cache de situação (vem do hub na hora).

---

## Catálogo de eventos unificado

Princípio: manter os nomes já em código (`app/uso.py`, `frontend/src/lib/analytics.ts`) — renomear agora quebra 8 emissores e 47 testes do front por ganho só cosmético; o nome da spec entra como **coluna "nome na spec"** em REQ §8 e nas views (`vw_ind_*` traduzem). Acréscimos seguem o padrão `substantivo_verbo`. Propriedades comuns da spec **não** entram em cada linha (ver DIV-A01): categoria, faixa de carreira, especialidade, regional e tempo de casa são **dimensões** obtidas por junção com `associado_perfil`/`associado_categoria_hist` na data do evento; só o que não é derivável vai em `detalhes`.

| Spec (§11.2) | Atual (`app/uso.py`) | Proposta | `entidade` / `detalhes` tipados | Origem |
|---|---|---|---|---|
| `acesso_primeiro` | — (`associado.primeiro_acesso_em`, `sql/005:21`) | **acrescentar** `acesso_primeiro` — emitido em `registrar_acesso` quando o upsert insere (`app/dominio/associado.py:28-32`; usar `ROW_COUNT()=1`) | `associado`; `dias_desde_filiacao` (int), `metodo` ENUM(email, celular) vem do IdP (`amr`) | servidor |
| `login` | `evento_log` `login_ok`/`login_falha` (`inventario-codigo.md:28`) | **manter em `evento_log`** (ADR-0012 §4 🔒); indicador 1/14 lê `evento_log.contact_id` | — | — |
| `home_vista` | `pagina_ver(rota=/area)` | **manter** + `detalhes.blocos` (lista de slugs dos blocos exibidos, validada por enum) e `segmento` (código) | `rota` | ui |
| `home_bloco_clicado` | — (`categoria_abrir` cobre só o bloco 5) | **acrescentar** `home_bloco_clicar` | `home_bloco`; `bloco` slug, `posicao` int, `item` slug | ui |
| `busca` | `busca_global` (sem termo, `app/uso.py:85`) | **manter**; termo **não** entra em `evento_uso` (RNF-16 🔒); "busca sem resultado vira ajuste de catálogo" → tabela `busca_sem_resultado(termo_normalizado, contagem, ultima_em)` **sem contact_id**, agregada por job a partir de um buffer em memória? Não — sem buffer: gravar direto `termo_normalizado` (≤ 48 chars, só letras/dígitos/espaço, sem `contact_id`, sem `request_id`) em `busca_sem_resultado` append-only (DIV-A01) | `rota`; `resultados`, `tamanho` | ui |
| `beneficio_visto` | `beneficio_abrir` (CTA, `app/uso.py:91`) | **renomear semântica**: `beneficio_abrir` passa a ser "página do benefício aberta" + `detalhes.origem` ENUM(home, catalogo, busca, email, trilha) e `estado` ENUM(6 estados §8.1); o clique no CTA externo vira `beneficio_acessar` (tipo 1) | `beneficio` | ui (visto) / servidor (acessar, grava `beneficio_ativacao`) |
| `recomendacao_dispensada` | — | **acrescentar** `recomendacao_dispensar` (grava `recomendacao_dispensa`) | `beneficio`; `motivo` ENUM | servidor |
| `solicitacao_criada` | `solicitacao_criar` | **manter** + `detalhes.tipo_ativacao` (1–6) e `beneficio` slug | `solicitacao` | servidor |
| `solicitacao_status` | `solicitacao_status_alterado` (só `job`, `app/uso.py:110`) | **manter**; abrir origem para `servidor` (atendente/backoffice) e `job`; `detalhes.de`, `para`, `origem` ENUM(sistema, parceiro, importacao, usuario) | `solicitacao` | servidor, job |
| `uso_registrado` | — | **acrescentar** `uso_registrar` — `entidade_id` = `uso_valor.id`; **sem valores em `detalhes`** (dinheiro vive em `uso_valor`, DIV-A01); `detalhes.fonte`, `nivel` | `uso_valor` | servidor, job |
| `carencia_vencida` | — | **acrescentar** `carencia_vencer` (job diário) | `beneficio`; `liberado_em` | job |
| `carteirinha_aberta` | `pagina_ver(rota=/area/carteirinha)` | **manter**; `detalhes.origem` em `pagina_ver` é genérico demais → acrescentar `carteirinha_abrir` só se a spec exigir origem; recomendação: derivar da `pagina_ver` | `rota` | ui |
| `carteirinha_validada` | `carteirinha_verificar` (`publico`) | **manter** + `detalhes.resultado` ENUM(ativo, inativo, nao_confirmado) | `carteirinha` | publico |
| `financeiro_segunda_via` | — | **acrescentar** `fatura_segunda_via` (`fatura_pdf_baixar` já existe para PDF; unificar em `fatura_segunda_via` com `detalhes.forma` ENUM(pdf, linha_digitavel, pix)) e **retirar** `fatura_pdf_baixar` (sem emissor) | `fatura`; `competencia` AAAA-MM | servidor |
| `pagamento_confirmado` | — | **acrescentar** `pagamento_confirmar` (job de sync financeiro; só competência e forma, **sem valor**) | `fatura`; `competencia`, `forma` | job |
| `meu_valor_visto` | `pagina_ver(rota=/area/fatura)` | **manter** `pagina_ver`; "valor exibido" **não** entra (é derivável de `vw_meu_valor_ano` na data) | `rota`; `periodo` | ui |
| `clube_acesso` | `clube_oferta_usar` | **manter** + `detalhes.origem` | `oferta` | ui |
| `clube_resgate` | — | **acrescentar** `clube_resgatar` (F2, integração do clube → `uso_valor`) | `uso_valor` | job |
| `evento_inscricao` | `evento_inscrever`, `congresso_garantir_vaga` | **manter** os dois (congresso tem regra própria); `detalhes.perfil_preco` ENUM | `evento` | servidor |
| `evento_presenca` | — | **acrescentar** `evento_presenca_registrar` (F2) | `evento`; `tipo` ENUM(presenca, certificado) | job |
| `conteudo_lido` | `noticia_abrir` | **manter** + `detalhes.tema` slug; tempo de leitura: `noticia_ler_tempo` opcional da UI com `segundos` int ≤ 3600 (lote no `pagehide`) | `noticia` | ui |
| `tema_seguido` | `tema_seguir`, `tema_deixar` | **manter** | `tema` | servidor |
| `trilha_passo` | `onboarding_passo_concluir` | **manter** + `detalhes.dia_jornada` int | `onboarding_passo` | servidor (passo concluído por evento real, spec L533) |
| `perfil_atualizado` | `perfil_contato_atualizar`, `perfil_foto_atualizar` | **manter** + acrescentar `perfil_declarado_atualizar` (`detalhes.campos` lista de nomes de campo, nunca valores) | `associado_perfil`, `perfil_declarado` | servidor |
| `consentimento` | — | **acrescentar** `consentimento_alterar` | `consentimento`; `finalidade`, `canal`, `valor`, `versao` | servidor |
| `notificacao` | — | **acrescentar** `notificacao_abrir` (ui) e `notificacao_criar` (job) (F2) | `notificacao`; `tipo` | ui, job |
| `ajuda_contato` | `central_whatsapp_abrir` | **manter** + acrescentar `ajuda_contatar` com `detalhes.canal` ENUM(whatsapp, telefone, formulario), `assunto` ENUM; migrar o emissor atual | `central` | ui |
| `cancelamento_pedido` | — (`solicitacao_cancelar` é outra coisa) | **acrescentar** `cancelamento_pedir` (P14) | `associado`; `motivo` ENUM(nao_uso, preco, mudanca, insatisfacao, outro) | servidor |
| — | `solicitacao_avaliar` | **acrescentar** (A06, spec L405) | `solicitacao`; `nota` 0–10 | servidor |
| — | `beneficio_ativar`, `beneficio_desativar`, `beneficio_gerenciar`, `totalpass_abrir`, `plantoes_abrir`, `filtro_aplicar`, `categoria_abrir`, `noticia_salvar/dessalvar`, `congresso_programacao_abrir`, `comunidade_*`, `programa_saber_mais`, `rede_entrar`, `solicitacao_cancelar/responder`, `carteirinha_compartilhar`, `wallet_adicionar`, `erro_exibido` | **manter** (granularidade útil aos painéis Produto/Operação) | — | — |

Propriedades comuns — onde ficam: `dispositivo` → classe grossa (`mobile`/`desktop`/`pwa`) derivada **no servidor** do UA (nunca o UA; `evento_log` já guarda `ua_hash`), em `detalhes.disp` de `pagina_ver` apenas; `UTM/código do gatilho` → `detalhes.gatilho` em `pagina_ver` de entrada, validado contra `comunicacao_evento.id` (regex, nunca texto livre; parâmetros `utm_*` descartados). Categoria, faixa, especialidade, regional e tempo de casa → junção na consulta. `segmento` (código curto) só em `home_vista`, porque a regra de segmentação muda e o painel precisa saber qual foi aplicada.

Mecânica que **não muda** (🔒): catálogo fechado, `contact_id` da sessão, lote ≤ 20, transação própria, nunca lança, CHECK anti-CPF. O front recebe os nomes novos por `ACOES_UI` (`app/uso.py:122`) e `AcaoUi` (`frontend/src/lib/analytics.ts:12-28`) — sem gerador compartilhado hoje (ADR-0012 obrigação pendente), o teste que compara os dois conjuntos precisa existir (TI-A05).

---

## Propostas

### TI — tarefas internas

| ID | Tarefa | Camada | Repo | Tam. | Pré-requisito | Começa hoje? |
|---|---|---|---|---|---|---|
| TI-A01 | Revisar REQ §6–§8 para a spec v2: 8 status, catálogo como dado, `uso_valor`, consentimento, comunicação, renumeração `sql/008+`; corrigir "sql/007 seed" em PENDENCIAS L113 e `crm_sync` 3×4 valores (ADR-0003:35 × REQ L1087) | docs | area_associado | M | — | sim |
| TI-A02 | Migração `ALTER` em `evento_uso` e `evento_log`: PK `(id, ocorrido_em)` + `PARTITION BY RANGE (TO_DAYS(ocorrido_em))` mensal, partições pré-criadas 24 meses + `MAXVALUE`; job administrativo documentado para criar partições futuras; testa em MySQL 8.4 descartável; registra em `schema_migrations` | SQL / docs | area_associado | P | tabelas ainda pequenas (quanto antes, menor o rebuild) | sim |
| TI-A03 | `sql/008` solicitacao + solicitacao_evento + solicitacao_avaliacao e `sql/009` job_execucao (texto da seção "Modelo"), com `GRANT UPDATE` justificado, CHECKs e índices; atualizar `TABELAS_COM_UPDATE` | SQL | area_associado | M | DEC-A01 (8 status) e DEC-A02 (conteúdo enviado) | após decisão (1 dia) |
| TI-A04 | `db_check.py`: (a) falhar quando tabela da allowlist **existe** sem o grant (ADR-0004 §6, não implementado em `scripts/db_check.py:85-86`); (b) allowlist só com tabelas migradas (hoje 9 nomes prospectivos, `:22-35`); (c) suporte a 2.º usuário (`apm_area_bo`, `apm_area_painel`) com allowlist própria; (d) conferir `PARTITION` presente nas tabelas de volume | scripts / tests | area_associado | P | TI-A02 para (d) | sim (a, b) |
| TI-A05 | `app/uso.py`: acrescentar as ações da tabela do catálogo (com `detalhes_ui` tipados), retirar `fatura_pdf_baixar`, emitir `acesso_primeiro` em `registrar_acesso`; teste que falha se `AcaoUi` (front) ≠ `ACOES_UI` | dominio / front / tests | area_associado | M | — | sim (ações da Fase 3 agora; o resto na fase de cada tela) |
| TI-A06 | `busca_sem_resultado` (append-only, sem identidade) + gravação via `uso.py` com normalização e allowlist de caracteres | SQL / dominio | area_associado | P | DIV-A01 aprovada | após DIV-A01 |
| TI-A07 | `sql/010` catálogo como dado (parceiro, beneficio, versão, categorias, matriz, afinidade, ativação, dispensa, parametro, categoria_hist, ALTER perfil, perfil_declarado) + `sql/011` valor (valor_referencia, uso_valor, importacao, importacao_linha) — **antecipar a estrutura de valor para a Fase 4** (hoje Fase 8) | SQL | area_associado | G | DEC-A03 (quem faz UPDATE), EXT-A01 (categorias), §15.5 da spec | SQL rascunhável hoje; aplicar só com catálogo validado |
| TI-A08 | `app/dominio/elegibilidade.py` (função pura, 6 estados) e `app/dominio/valor.py` (níveis 1–4, regras de P06), com testes de tabela | dominio | area_associado | M | TI-A07 | sim (sem banco, só contrato) |
| TI-A09 | `sql/013` consentimento_texto, consentimento, preferencia_canal, titular_pedido + `app/dominio/consentimento.py` + ação `consentimento_alterar` | SQL / dominio / API | area_associado | M | textos e finalidades do jurídico (EXT-A06) | estrutura sim; textos não |
| TI-A10 | `sql/014` comunicacao_evento/envio/supressao/notificacao + job `enviar_comunicacao` (só grava e marca `suprimido` enquanto não houver credencial do RD) | SQL / jobs | area_associado | M | EXT-A04 para enviar de fato | estrutura sim |
| TI-A11 | Serviço `area-associado-jobs` no compose (RNF-19) + `app/jobs/` com agendador, `job_execucao`, `GET_LOCK` por job; primeiros jobs: outbox CRM, sync CRM, `marcar_sem_retorno`, `carencias_vencidas`, `atualizar_perfis` | jobs / infra | area_associado | M | TI-A03 | sim (Estivador + Atlas) |
| TI-A12 | Views `sql/021` (`vw_ind_*`, `vw_meu_valor_ano`, `vw_qualidade_parceiro_mes`, `vw_consentimento_atual`) com k ≥ 20 nas de recorte; usuário `apm_area_painel` só `SELECT` nas views; `base_ativa_mensal` por job | SQL | area_associado | M | TI-A07, DEC-A04 (ferramenta de painel) | definições das views sim |
| TI-A13 | `docs/RETENCAO.md`: tabela × prazo × mecanismo (partição / anonimização / nunca) + procedimento administrativo; fecha P-15 | docs | area_associado | P | EXT-A06 (prazos do jurídico) | rascunho sim |
| TI-A14 | Procedimento de **anonimização** do titular (ADR-0004: sem DELETE): `associado_perfil` zerado, `perfil_declarado` zerado, `contact_id` mantido nas trilhas (pseudônimo), `titular_pedido` fechado — script administrativo fora do `apm_area` | docs / scripts | area_associado | P | TI-A09 | sim |
| TI-A15 | Teste de restauração do snapshot do RDS para um `area_associado_restore` + conferência de `schema_migrations` (spec §14 L1202-1203) | infra / docs | area_associado | P | acesso administrativo do operador | sim (com Estivador) |
| TI-A16 | Estimativa de volume para P-41 com a base ativa; renovação de perfil só para quem acessou em 90 d; cota PII do hub | docs | area_associado / mcp_hub | P | EXT-A05 | parcial |
| TI-A17 | ADRs novas (ver seção "Riscos e ADRs candidatas") | docs | area_associado | M | decisões DEC-A01..A05 | após decisões |

### EXT — dependências externas

| ID | O quê | De quem | Destrava | Enquanto isso | Pendência |
|---|---|---|---|---|---|
| EXT-A01 | Vocabulário fechado de **categoria do associado** (acadêmico, aspirante, efetivo, remido… códigos) e de-para com o rótulo `tipo_associado` do IdP/CRM; contagem e categorias da base conciliada (spec §15.5) | CRM admin / Negócio | matriz §8.3, carências, indicadores, `associado_categoria_hist` | guardar o rótulo como hoje (`sql/006:28`) e tratar como código provisório | novo (P-42) |
| EXT-A02 | `mcp_hub`: ferramenta de **resolução em lote CPF → contact_id para importação** (`importacao.resolver_lote`) + criação de lead para CPF não associado; e `associado.historico_associacao` por `contact_id` | mcp_hub | §13.3 importação (B06), ind. 9, A13 | importação não existe; nenhuma solução provisória que traga CPF à área | P-04 (ampliar) |
| EXT-A03 | `mcp_hub`: `perfil_consultar` devolvendo `faixa_carreira` (derivada no hub da data de nascimento, **sem a data**), `especialidade_cod`, `regional_cod`, `nome_social`, `isento_remido`; `financeiro.situacao` por `contact_id` (só situação e dias) | mcp_hub / CRM admin | personalização §7.1, elegibilidade §8.1, estado "Suspenso" | colunas ficam NULL; elegibilidade ignora região e financeiro (fail-open explícito e registrado) | P-04 / P-08 |
| EXT-A04 | Credencial OAuth2 do RD Station para a área (ou decisão de reaproveitar o conector do `app_facial_recognition`) + mapa evento → campo/evento do RD + webhook de retorno | Marketing / RD | §12 envio real, indicador 10 | outbox grava e marca `suprimido: sem_credencial`; transacionais por SMTP (P-27) | novo (P-43) |
| EXT-A05 | Tamanho da **base ativa** por categoria e regional (número) e estimativa de acessos | Negócio / CRM | P-41, `base_ativa_mensal`, dimensionamento de partições e cota do hub | hipótese de trabalho de 10 mil (explicitada como hipótese) | P-41 |
| EXT-A06 | **Prazos de guarda** por tabela (solicitação, auditoria, consentimento, uso/valor, evento_uso, comunicação) e textos/finalidades de consentimento com versão inicial | Jurídico / encarregado de dados | P-15, TI-A09, TI-A13 | propostas atuais nos comentários das migrações; consentimento sem texto não vai ao ar | P-15 (ampliar) |
| EXT-A07 | Catálogo inicial validado: lista de benefícios com carência, categorias permitidas, tipo de ativação, modalidade de mensuração, parceiro, prazo de retorno, **valor de referência aprovado pelo Financeiro** | Benefícios / Financeiro | `sql/010`/`011` com dados; P03/P04/P06 | tabelas vazias; telas em `EmConstrucao` | P-10 (ampliar) |
| EXT-A08 | Decisão do negócio sobre "mudança de categoria reinicia carência?" (spec L740-741) e carência do Clube | Benefícios / Jurídico | `dominio/elegibilidade.py` | recomendação da spec (não reinicia; base = `data_filiacao`) | novo (P-44) |
| EXT-A09 | Entidade do CRM para o espelho das solicitações e campos do "retorno do parceiro" | CRM admin | outbox Fase 3 | fila local funciona sem espelho | P-06 |

### DIV — divergências (spec × decisões fechadas / documentos)

| ID | Divergência | Posição do Atlas |
|---|---|---|
| DIV-A01 | Spec §11.2 pede propriedades pessoais em todo evento (especialidade, regional, fase, UTM) e o **termo de busca** (L960, L354); RNF-16 (REQ L879) proíbe texto livre em `evento_uso` e ADR-0012 fixa minimização | Dimensões por junção, não por linha; termo só em `busca_sem_resultado` **sem identidade** (nem `contact_id`, nem `request_id`), normalizado e limitado. Valores monetários nunca em `evento_uso` (ficam em `uso_valor`). Registrar em PENDENCIAS como divergência aceita (regra 13). |
| DIV-A02 | Spec §13.3 chaveia a importação por **CPF**; ADR-0014 🔒 proíbe CPF na área | Upload e resolução no `mcp_hub` (EXT-A02); a área recebe `contact_id`/`sem_associado`. A coluna `cpf` do layout continua existindo para o parceiro — quem a lê é o hub. |
| DIV-A03 | Spec §9 exige backoffice próprio com 8 perfis, 2FA e auditoria na F1; REQ L112 o declara fora de escopo ("atendimento no CRM") | Não é decisão do Atlas; ver DEC-A03. O modelo de dados aqui já separa "catálogo/configuração" (UPDATE pelo backoffice) de "dados do associado" (UPDATE pelo web), para que a decisão não force reescrever migrações. |
| DIV-A04 | Spec §8.5: 8 status + `sem_retorno` marcador; ADR-0003 e REQ §7: 6 status | Ver DEC-A01. `sem_retorno` como **coluna** (`sem_retorno_em`), não como status — a spec já o chama de marcador. |
| DIV-A05 | Spec §8.5: "conteúdo enviado" no log; minimização (ADR-0014, RNF-16) | Ver DEC-A02. |
| DIV-A06 | REQ L998: `beneficio` como seed só SELECT; spec B03/B13: editável sem desenvolvimento, com rascunho/aprovação/histórico | Catálogo vira dado com UPDATE pelo usuário do backoffice (ou, sem backoffice, por SQL do operador com `beneficio_versao` como histórico). ADR nova. |
| DIV-A07 | ADR-0004 §6 exige que `db_check.py` falhe em "tabela da allowlist sem o grant"; o código só verifica o inverso (`scripts/db_check.py:85-86`) e a allowlist lista 9 tabelas inexistentes | TI-A04. |
| DIV-A08 | `job_execucao` em `sql/012` (REQ L1012) mas Fase 3; roteiro cita `sql/007 seed` (PENDENCIAS L113) | Renumerar: `job_execucao` = `sql/009`. TI-A01. |
| DIV-A09 | Spec §14: "cópia de segurança diária com teste de restauração"; PROVISIONAMENTO só cobre `.env` no Secrets Manager (`docs/PROVISIONAMENTO.md:125-130`) | TI-A15. |
| DIV-A10 | Spec P12: trilha por categoria (acadêmico e efetivo novo); REQ: onboarding só Acadêmico, 6 passos fixos (REQ L1010, LA-21) | `onboarding_passo.categoria_associado` + passo concluído **por evento real** (spec L533): o job marca o passo a partir de `evento_uso`/`uso_valor`, não a UI. |

### DEC — decisões a tomar (com recomendação)

| ID | Decisão | Opções | Prós / contras | Recomendação |
|---|---|---|---|---|
| DEC-A01 | Máquina de estados da solicitação: 6 (ADR-0003) ou 8 (spec) | **(a)** manter 6 e mapear os rótulos da spec na UI; **(b)** adotar os 8 da spec com `sem_retorno_em` como marcador; **(c)** 8 + `sem_retorno` como status | (a) não representa "enviada ao parceiro" nem "não seguiu" vs "recusada"; (b) alinha com o backoffice e com indicadores 5–7, exige ADR que revise a 0003 e mapeamento CRM (P-06) para 7 status; (c) estado terminal ambíguo, transições explodem | **(b)**. ADR-0018 substitui o §1 da ADR-0003 (status) e mantém o resto (outbox, otimista, 409). |
| DEC-A02 | "Conteúdo enviado" no log imutável | **(a)** JSON completo do que foi ao parceiro; **(b)** `campos_enviados` (lista de nomes) + `sha256` do payload + `destino` + `canal`; **(c)** payload cifrado com chave própria | (a) replica dado pessoal em trilha de guarda longa, viola minimização; (b) prova o que e quando foi enviado sem copiar dado pessoal, reconstrução pelo `solicitacao.dados` + `associado_perfil` na data (histórico aproximado); (c) complexidade de chave e rotação para pouco ganho | **(b)**. O `solicitacao.dados` (que o associado preencheu) continua na tabela principal, com CHECK anti-CPF. |
| DEC-A03 | Onde vive o backoffice e **quem tem UPDATE** no catálogo/configuração | **(a)** módulo na própria área (`/admin`, OIDC Entra ID, usuário de banco `apm_area_bo`); **(b)** backoffice como app separado (mesma imagem, outro container, outro usuário de banco); **(c)** sem backoffice: operador por SQL + CRM | (a) reutiliza sessão/CSRF/CSP, mas mistura superfícies e cookies `__Host-` no mesmo host; (b) isolamento de credencial e de rede, custo de outro serviço; (c) contraria a spec F1 (B01–B06, B12, B13), fila manual | **(b)** para a estrutura de dados e credenciais (segundo usuário `apm_area_bo`, allowlist própria), decisão de produto sobre a tela com Maestro/Sentinela. Até lá: (c) com `beneficio_versao` e `backoffice_auditoria` alimentados por script administrativo. |
| DEC-A04 | Destino dos eventos e ferramenta de painéis (F0-06) | **(a)** views no MySQL + página do backoffice; **(b)** views + ferramenta externa (Metabase/Grafana) com usuário só-leitura `apm_area_painel`; **(c)** exportar `evento_uso` para analytics externo (Clarity/GA) | (a) sem dependência nova, limitado; (b) painéis prontos, exige container e credencial a mais na `rede_publica`; (c) manda identificador pseudonimizado para terceiro — exige base legal e contrato, contraria "analytics com identificador pseudonimizado" só se o pseudônimo for re-hasheado | **(b)**; nunca (c) com `contact_id` (se um dia, só `sub_hash` re-hasheado e agregados k ≥ 20). |
| DEC-A05 | Base da carência | **(a)** `data_filiacao` do CRM; **(b)** início da categoria atual (`associado_categoria_hist`) | (a) simples, segue a recomendação da spec L741; (b) exige histórico (P-04) | **(a)** com `parametro.carencia_reinicia_por_categoria=false` para trocar sem deploy se o negócio decidir diferente (EXT-A08). |
| DEC-A06 | Partição de `evento_uso` agora | **(a)** sim (TI-A02); **(b)** adiar até volume | (a) rebuild barato hoje, expurgo sem DELETE; (b) rebuild com tabela grande e purga por lotes | **(a)**. |
| DEC-A07 | Consentimento append-only × linha mutável | **(a)** append-only + view do estado atual; **(b)** tabela com UPDATE e histórico à parte | (a) prova de auditoria completa, consultas um pouco mais caras (índice resolve); (b) duas tabelas para o mesmo fato | **(a)** — é trilha jurídica, mesma classe de `evento_log` (ADR-0004 §4). |

---

## Riscos e ADRs candidatas

**Riscos**
1. **CPF pela porta da importação.** O layout §13.3 é a única entrada de dado por CPF no produto; sem a ferramenta do hub (EXT-A02), a pressão será "subir o CSV na área". Mitigação: a rota de importação nasce no backoffice (DEC-A03) apontando para o hub; teste de contrato que recusa coluna `cpf` em qualquer corpo da área (ADR-0014 obrigações, `docs/adr/0014-…:73-75`).
2. **Valor sem fonte chega ao associado.** `uso_valor` sem `valor_referencia` aprovada ou com nível < 4 somado no "comprovado" fere a spec L996 e a regra 13. Mitigação: CHECK de nível, view que só soma nível 4 + proteção com aprovação, flag `fatura_valor` só liga com `valor_referencia` aprovada no catálogo.
3. **Denominadores inexistentes.** Indicadores 1, 2, 4, 9, 11 dependem do CRM/cobrança (base ativa, novos, renovação, total pago). Sem `base_ativa_mensal` e P-04/P-08, os painéis mostram só numeradores — rotular como tal.
4. **`contact_id` muda em merge de contato** (ADR-0014:64-65): `uso_valor`, `consentimento` e `solicitacao` ficam órfãos do GUID novo. Mitigação: `sub_hash` em toda tabela de guarda longa (já é convenção) e job de reconciliação quando o IdP emitir GUID diferente para o mesmo `sub`.
5. **Dois usuários de banco e allowlists divergentes.** Sem TI-A04(c) o `db_check` não enxerga o `apm_area_bo`.
6. **Volume de `score_engajamento` e `comunicacao_envio`.** Linha por associado por dia; sem partição, a purga vira `DELETE` em lotes contra a ADR-0004 na prática operacional.
7. **CHECK com `REGEXP_LIKE(CAST(json))` em toda inserção** (`sql/004:55-56`): custo linear no tamanho de `detalhes` (≤ 2000 chars, `app/uso.py:40`); aceitável, mas não replicar em colunas grandes (`beneficio_versao.snapshot`): nesses casos validar na aplicação e manter CHECK só de chaves.
8. **Jobs sem trava** rodando em dois containers (deploy sobreposto) duplicam outbox e comunicação. `GET_LOCK` por job + índice único `(gatilho, contact_id, referencia_id)`.
9. **Retenção decidida tarde**: consentimento e `solicitacao_evento` são de guarda longa; se o jurídico fixar prazo curto para `evento_uso` (ex. 12 meses), o indicador 11 (renovação por coorte) perde a base — levantar isso na EXT-A06.

**ADRs candidatas**
- **ADR-0018 — Ciclo da solicitação com 8 status e marcador `sem_retorno`** (revisa ADR-0003 §1–3; mantém outbox, controle otimista e 409).
- **ADR-0019 — Catálogo de benefícios como dado com elegibilidade, carência e matriz configuráveis** (substitui o seed só SELECT de REQ §6; introduz `beneficio_versao`, `parametro`, usuário `apm_area_bo`).
- **ADR-0020 — `uso_valor` e níveis de evidência como fonte única do Meu valor e dos painéis** (append-only, estorno/validação por linha, valor de referência versionado e aprovado).
- **ADR-0021 — Consentimento versionado append-only e direitos do titular sem DELETE** (anonimização administrativa).
- **ADR-0022 — Importação do plano B resolvida no `mcp_hub`** (CPF nunca entra na área; `importacao_linha` só com `contact_id`; idempotência por `(parceiro_id, id_externo)`).
- **ADR-0023 — Outbox de comunicação para o RD Station e log de envios** (gatilhos, supressão, limite semanal, webhook de retorno).
- **ADR-0024 — Dimensões analíticas por junção, pseudonimização e k-anonimato nos painéis** (o que entra e o que não entra em `evento_uso`; `busca_sem_resultado` sem identidade; usuário `apm_area_painel`).
- **ADR-0025 — Retenção por partição mensal e expurgo administrativo** (fecha P-15; `evento_uso`, `evento_log`, `score_engajamento`, `comunicacao_envio`).
- **ADR-0026 — Backoffice: usuário de banco e credencial separados** (depende da DEC-A03).

---

## Ordem sugerida

1. **Agora, sem dependência externa:** TI-A01 (REQ §6–§8 revisado), TI-A04 (a, b) (`db_check` honesto), TI-A02 (partição de `evento_uso`/`evento_log` enquanto são pequenas), TI-A13 rascunho (retenção), TI-A15 (teste de restauração). Abrir EXT-A01, A05, A06, A07 e A08 em PENDENCIAS.
2. **Decisões curtas com o usuário:** DEC-A01, DEC-A02, DEC-A05, DEC-A06, DEC-A07 → ADR-0018, 0021, 0025. Depois TI-A03 (`sql/008`, `sql/009`) e TI-A05 (ações da Fase 3), destravando a **Fase 3** com a máquina de 8 status já certa (evita migrar status depois).
3. **Fase 3 ampliada:** TI-A11 (serviço de jobs, `job_execucao`, outbox, `marcar_sem_retorno`), TI-A09 (consentimento e preferências — P13 é F1 e a estrutura não depende de terceiros; textos chegam da EXT-A06).
4. **Antes da Fase 4:** DEC-A03 (backoffice e `apm_area_bo`) e DEC-A04 (painéis) → ADR-0019, 0020, 0024, 0026; EXT-A01/A07 (categorias e catálogo validado). Então TI-A07 (`sql/010`, `sql/011`), TI-A08 (elegibilidade e valor puros), TI-A12 (views e `base_ativa_mensal`).
5. **Com o hub (P-04 ampliado, EXT-A02/A03):** `associado_categoria_hist`, `associado_financeiro`, importação (ADR-0022), ferramentas por `contact_id`.
6. **Com o RD (EXT-A04):** TI-A10 passa de "só grava" para "envia"; webhook de retorno (Sentinela + Maestro).
7. **F2:** `sql/012` conteúdo (Fase 5), `sql/016` comunidade/onboarding por categoria (Fase 6), `sql/019` score, notificações.

Nada acima altera as decisões fechadas: continua MySQL próprio com espelho no CRM, UPDATE por grant de tabela, DELETE nunca, trilhas só INSERT, `evento_uso` com catálogo fechado em transação própria, `contact_id` nunca CPF, CRM/ERP só pelo hub e WordPress só pelo job com cache.
