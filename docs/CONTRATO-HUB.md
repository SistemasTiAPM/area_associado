# Contrato mcp_hub ↔ Minha APM

Implementado no `mcp_hub` na Fase 2b (19/10/2026, commits `365a531`..`8bb3c43` do repositório
`SistemasTiAPM/mcp_hub`; regra 1 do hub reescrita). A área consome este contrato em
`app/integracoes/hub.py` e roda contra o simulado (`app/integracoes/hub_stub.py`,
`HUB_MODE=stub`) até a provisão real (P-02, P-05, P-29).

## Transporte

- `POST /oauth/token`: `grant_type=client_credentials`, `client_secret_basic`,
  `scope=ferramentas:ler`, mais `ferramentas:escrever` só com `HUB_ESCRITA_HABILITADA=true` na
  área (2026-10-21, pedido do hub). O hub só emite escopos que a conta tem (`invalid_scope` se
  pedir a mais). Com a flag desligada a área não chama ferramenta de escrita: as rotas respondem
  404 `recurso_desligado` antes de tocar o hub. Resposta `{access_token, expires_in}`. A cada chamada o
  escopo do token é intersectado com o da conta atual: revogar no painel vale em até 30 s.
- `POST /api/v1/ferramentas/{nome}` com `{"argumentos": {...}}` e `Authorization: Bearer`.
- Sucesso: `{"colunas", "linhas", "total", "truncado", "modo_pii", "observacoes"}`; a área lê `linhas`.
- Erro: `{"erro", "mensagem", "detalhes"?}` com o HTTP do pipeline. `detalhes` só traz nome do
  campo e motivo, nunca o valor enviado.
- A área chama por `http://mcp_hub:8000` na `rede_publica` com `Host: mcp.apm.org.br`. **A foto
  só passa por aí**: o vhost público do hub limita o corpo a 64 KiB; o hub aceita até 512 KiB
  só em `associado.foto_atualizar` e só para quem tem `ferramentas:escrever`.

## Conta de serviço da área

| Item | Valor |
|---|---|
| Cliente | `area-associado` (`HUB_CLIENT_ID`), segredo em `HUB_CLIENT_SECRET` |
| Escopos da conta | `ferramentas:ler` e `ferramentas:escrever`. **O de escrita só é marcado em produção depois da P-29**; a área só o pede com `HUB_ESCRITA_HABILITADA=true` |
| Origem permitida | CIDR da `rede_publica` |
| Grants | **exatos** (curinga não libera escrita), `modo_pii=completo`, nas 4 ferramentas da Fase 2b abaixo **e**, desde 2026-10-30 (TI-47), em `associado.situacao` e `associado.historico_associacao` (sem coluna pessoal: o modo PII é indiferente). Nunca `associado.*`: liberaria `consultar`/`visao_360`, que devolvem CPF |
| Taxa e cota | por conta (antiga P-03, resolvida no hub): `chamadas_por_minuto` (1–6000) e cota PII própria; os padrões por principal (60/min, 500 PII/dia) não servem a um app |

## Regras para TODAS as ferramentas

1. Chave de entrada é `contact_id` (GUID do Dataverse; o GUID todo zero é recusado). O hub
   lê o contato por `GET /contacts({id})`. **Nenhuma resposta contém CPF** (ADR-0014); a área
   ainda descarta e loga a chave `cpf` se vier.
2. Só transporte REST: as quatro da Fase 2b não aparecem no MCP nem no portal do hub.
   `associado.situacao` e `associado.historico_associacao` são compartilhadas com o IdP
   (`login_associado`) e com o portal do hub; aceitam `cpf` **ou** `contact_id`, mas a área só
   chama por `contact_id` e a saída nunca traz CPF para ninguém.
3. Titular auditado por `contact_id` (`auditoria_titular_contato`). Nas duas compartilhadas o
   hub resolve o CPF do contato **internamente**, grava o HMAC em `auditoria_titular` e descarta;
   a linha de saída não o contém. Pedido LGPD no hub = busca pelo CPF **e** pelo contact_id.
4. Escrita: `efeito=escrita`, intenção gravada antes (sem ela, 503 `auditoria_indisponivel` e
   nada vai ao CRM), resultado depois; `If-Match: *` (nunca cria contato); credencial própria do
   hub com papel Read + Write em Contact; 1 retry só em 401 e 429/503 (`Retry-After` ≤ 5 s).

## Ferramentas

### `associado.perfil_consultar` (leitura)

Entrada `{"contact_id": "<guid>"}`. Saída: uma linha, ou nenhuma se o contato não existir.

| Campo | Origem no `contact` | Observação |
|---|---|---|
| `contact_id` | `contactid` | minúsculas |
| `nome` | `fullname` | espaços normalizados |
| `email` | `emailaddress1` | |
| `celular` / `telefone` / `telefone2` | `mobilephone` / `telephone1` / `telephone2` | como estão no CRM (P-32) |
| `endereco` | ver abaixo | objeto ou `null` |
| `endereco_disponivel` | flag + Metadata do hub | `false` = o hub não lê nem grava endereço; a área mostra só o aviso |
| `num_contato` | `alf_num_contato` | |
| `crm` / `crm_uf` | `sol_st_numerocrm` / rótulo de `alf_uf_crm` | `crm_uf` **sempre sigla de 2 letras ou `null`** (rótulo por extenso é convertido, nunca cortado) |
| `tipo_associado` | rótulo de `alf_tipo_associado` | |
| `status_associativo` | rótulo de `alf_status_associativo` | |
| `data_filiacao` | `alf_data_filiacao` | `AAAA-MM-DD` |
| `tem_foto` | `entityimage_timestamp` não nulo | booleano |

**Endereço** — mesmo padrão que a APM usa no lead; o hub só lê e grava com
`CRM_ENDERECO_HABILITADO=true` **e** a Metadata confirmando os 7 atributos como texto
atualizável (P-31):

| Campo | Atributo do `contact` |
|---|---|
| `logradouro` | `address1_line1` |
| `numero` | `alf_numero_endereco` |
| `complemento` | `address1_line2` |
| `bairro` | `alf_bairro` |
| `cidade` | `address1_city` |
| `uf` | `address1_stateorprovince` (sai como sigla) |
| `cep` | `address1_postalcode` (gravado só com dígitos; sai `00000-000`) |

### `associado.situacao` (leitura) — TI-47, 2026-10-30

Situação associativa em **uma** linha, sem nome, e-mail, telefone ou CPF. Base da verificação
pública em tempo quase real (TI-45, Onda 2) e do job noturno de situação (TI-55). Entrada
`{"contact_id": "<guid>"}`. Saída: uma linha, ou nenhuma (`total: 0`) se o contato não existir.
Hub: 12 s de teto; a área usa `HUB_TIMEOUT`.

| Campo | Origem | Observação |
|---|---|---|
| `contact_id` | `contactid` | minúsculas |
| `status_associativo` | rótulo de `alf_status_associativo` | texto do CRM, muda com idioma/edição |
| `status_associativo_codigo` | `alf_status_associativo` | int do option set (`2` = Ativo, `3` = Pendente) |
| `situacao_normalizada` | tabela versionada no hub (`app/tools/associado.py`) | **enum fechado** `ativo` \| `suspenso` \| `cancelado` \| `outro`. Código mapeado vence o rótulo; código desconhecido cai no rótulo exato (sem acento/caixa); o resto é `outro`. Só `2`/`3` têm código confirmado no tenant (M-9 do hub); suspenso/cancelado entram pelo rótulo até lá |
| `tipo_associado` | rótulo de `alf_tipo_associado` | |
| `data_filiacao` | `alf_data_filiacao` | `AAAA-MM-DD` |
| `statecode` | `statecode` do contato | int: `0` ativo, `1` inativo (registro desativado no CRM). **Não** entra na normalização |
| `situacao_registro` | rótulo de `statecode` | |
| `associacao_status` / `associacao_status_codigo` | `sol_associacao` mais recente (`sol_dt_dataassociacao desc, createdon desc`) | `100000001` = ativa; `null` se o contato não tem associação |
| `associacao_data` / `associacao_criada_em` | idem | `AAAA-MM-DD` / ISO `-03:00` |

Regra da área (`SituacaoCrm.ativa` em `app/integracoes/hub.py`): **ativo = `situacao_normalizada == "ativo"` e
`statecode == 0`**; qualquer outra combinação não é "ativo". Valor de `situacao_normalizada` fora do
enum vira `outro` no cliente (fail-closed) e gera log de anomalia. Nada é gravado localmente a
partir desta ferramenta nesta onda; o uso em `carteirinha.resolver` é TI-45.

### `associado.historico_associacao` (leitura) — TI-47, 2026-10-30

Registros de `sol_associacao` do contato, do mais recente ao mais antigo (até 50). Entrada
`{"contact_id": "<guid>"}`. Saída: 0..50 linhas com `contact_id`, `nome` (PII `nome`, mascarado
sem grant `completo`), `status_associacao` (rótulo), `status_associacao_codigo` (int),
`data_associacao`, `criada_em`, `modificada_em`, `situacao_registro`. **Sem `cpf`.** Reservada ao
histórico de categorias (A13 / `diff_cadastro`, TI-55); a área ainda não a chama — confirmar
antes se `sol_associacao` registra categoria (levantamento §8.2).

### `associado.contato_atualizar` (escrita)

Entrada `{"contact_id", "celular"?, "telefone"?, "telefone2"?, "email"?, "endereco"?}`.
Ausente = não muda. `null` apaga só `telefone` e `telefone2`. O hub renormaliza: telefone
`(11) 91234-5678` / `(11) 3188-6200` (DDD válido; celular com 9 dígitos começando com 9), e-mail
em minúsculas com **até 100 caracteres** (limite do `emailaddress1`), endereço completo (todos
os campos, exceto `complemento`), UF em sigla, CEP com 8 dígitos, sem caractere de controle.
Saída `{"contact_id", "campos_alterados": [...]}` (nomes do contrato).

- Endereço sem disponibilidade: **409 `endereco_indisponivel` antes de qualquer PATCH** (nem os
  outros campos do mesmo pedido são gravados).
- Campo do endereço maior que o `MaxLength` do CRM: 400 com `detalhes` `endereco.<campo>`.
- `email` só é enviado depois do código confirmado e do login recente (ADR-0015).

### `associado.foto_obter` (leitura)

Entrada `{"contact_id"}`. Saída `{"contact_id", "imagem_jpeg_b64": "<base64>" | null}`, vinda de
`/contacts({id})/entityimage/$value?size=full` (teto de 1 MiB no hub). Reservada para sincronizar
a miniatura quando a foto for trocada fora da área.

### `associado.foto_atualizar` (escrita)

Entrada `{"contact_id", "imagem_jpeg_b64": "<base64>" | null}` (a chave é obrigatória). O hub
exige base64 válido, até 256 KiB, JPEG (SOI/EOI) de **512×512** lido do marcador SOF. `null`
remove a foto. Saída `{"contact_id", "bytes"}`. Se o CRM guarda a imagem cheia ou só 144×144 é
P-30 (homologação).

## Solicitações (Onda 5, P-06)

**Contrato proposto pela área em 2026-10-30 (frente C da Onda 2); as três ferramentas ainda NÃO existem
no hub.** A área já tem cliente (`app/integracoes/hub.py`), simulado (`hub_stub.py`) e o serviço de jobs
que as chama (`app/jobs/solicitacoes.py`) — **só com `JOBS_APLICAR=1`**. Até a P-06, uma chamada real
recebe o 404 genérico do hub ("ferramenta inexistente/sem grant"), que vira `HubError("fonte_indisponivel")`:
o job registra, recua (1, 2, 4 … 60 min) e não quebra. Implementação no hub = TI-50, com a P-06
(entidade, mapeamento de status, campo de mensagem pública).

Regras comuns:

- Chave = `contact_id` (GUID) + `solicitacao_id` (UUID v4 gerado pela área, correlação e idempotência).
  **Sem CPF** em entrada ou saída: o hub recusa (400) a chave `cpf` e texto com padrão de CPF em `campos`.
- Entidade no CRM: **`task` regarding contact** (`regardingobjectid_contact@odata.bind`), com o
  `solicitacao_id` gravado num atributo próprio (nome a definir na P-06, ex.: `alf_id_externo`, com
  índice/alternate key). Credencial própria do hub com papel **só Create/Write em `task`** (nunca em contact).
- Conta: o espelho e o sync rodam no serviço de jobs, conta **`area-associado-jobs`** (`.env.jobs`);
  `espelhar`/`status_atualizar` exigem `ferramentas:escrever` nela (hoje só `ler`, M-8) e
  `HUB_ESCRITA_HABILITADA=true` no `.env.jobs`. Grants exatos nas três (nunca `solicitacao.*`).
- Escrita: mesmo pipeline das escritas da Fase 2b (intenção auditada antes, resultado depois, 1 retry só em
  401/429/503, timeout de 25 s no hub; a área espera `HUB_TIMEOUT_ESCRITA`). 504 `escrita_indeterminada`
  é seguro de repetir: as duas escritas são idempotentes pela chave.

### `solicitacao.espelhar` (escrita)

Entrada:

| Campo | Tipo | Observação |
|---|---|---|
| `contact_id` | GUID | dono do pedido |
| `solicitacao_id` | UUID v4 | chave de idempotência: se já existe `task` com ela, devolve a existente (`criada: false`) |
| `tipo` | texto ou `null` | `tipo_servico` da área (`outro`, `declaracao_associado`, `alteracao_cadastro`, `cancelamento_associacao`, …); `null` quando vier de benefício |
| `titulo` | texto ≤ 200 | `Minha APM: <rótulo do tipo>` → `subject` |
| `status` | enum da área | status atual (`criada`, ou outro se mudou antes do espelho) |
| `criada_em` | ISO UTC | `2026-10-30T12:00:00Z` |
| `prazo_retorno_dias` | int 1–365 | → `scheduledend` = criação + prazo |
| `campos` | objeto | o que o associado preencheu (allowlist do tipo na área; ≤ 16 kB; sem CPF) → `description` formatada pelo hub (rótulo: valor), nunca HTML |
| `beneficio_id` / `parceiro_id` | texto | só em pedido nascido do catálogo (Fase 4) |

Saída: **uma** linha `{"solicitacao_id", "crm_id": "<activityid>", "criada": bool}`. Sem `crm_id` GUID
válido a área trata como resultado incerto e repete (idempotente).

### `solicitacao.status_atualizar` (escrita)

Entrada `{"contact_id", "solicitacao_id", "crm_id", "status", "mensagem_associado"?, "cancel_motivo"?}`.
`status` é o status atual da área; `mensagem_associado` (≤ 2000) é a resposta do associado quando a última
transição foi dele (`pendente_associado → em_atendimento`), gravada como nota/anotação na `task`;
`cancel_motivo` (≤ 200) quando o associado cancelou. Mapeamento área → `task`: `cancelada` → `statecode=2`;
`em_atendimento` → "Em andamento"; demais só anotação. Saída: uma linha `{"solicitacao_id", "crm_id"}`.
Erros: 404 `nao_encontrado` se a `task` não existe ou não é daquele `contact_id`/`solicitacao_id` (a área
marca `falhou` direto — permanente).

### `solicitacao.alteracoes_consultar` (leitura)

Entrada `{"cursor": "<opaco>" | null, "limite": 1..200}`. Devolve as `task`s **criadas pela área** (com
`solicitacao_id`) alteradas depois do cursor, em ordem `modifiedon, activityid`; `null` = desde o início.
O hub trata `odata.nextLink` por dentro. Cada linha:

| Campo | Observação |
|---|---|
| `solicitacao_id`, `crm_id`, `contact_id` | a área confere os três contra o pedido local; divergência → `evento_log`, nada aplicado |
| `situacao` | enum fechado: `nao_iniciada` \| `em_andamento` \| `aguardando_associado` \| `concluida` \| `nao_seguiu` \| `cancelada` |
| `mensagem_publica` | texto ao associado (obrigatório em `aguardando_associado`); **nunca** a descrição interna da `task` (campo definido na P-06) |
| `modificado_em` | ISO com fuso |
| `cursor` | posição opaca **depois** desta linha (`[A-Za-z0-9_.:+=/-]{1,200}`); a área guarda a da última linha aplicada em `job_execucao.posicao` |

Mapeamento na área (REQUISITOS §7.5): `nao_iniciada` → nada (a área não regride); `em_andamento` →
`em_atendimento`; `aguardando_associado` → `pendente_associado` (via `em_atendimento` se preciso);
`concluida` → `concluida_positiva`; `nao_seguiu` e `cancelada` → `concluida_negativa` (a P-06 ainda precisa
distinguir "não seguiu" de "cancelada pela APM"). Transição fora da tabela da máquina, terminal local ou
espelho local pendente → não aplica (o local prevalece; divergência em `evento_log`; cancelamento local é
reenviado). Linha fora do contrato → a rodada para sem avançar o cursor.

## Erros

| HTTP | `erro` | Quando | Área |
|---|---|---|---|
| 400 | `entrada_invalida` | validação do hub ou valor recusado pelo CRM | 400 com os `detalhes` |
| 404 | `nao_encontrado` | contato inexistente no PATCH | 404 |
| 409 | `cpf_duplicado` | `situacao`/`historico`: mais de um contato com o CPF do contato pedido (só acontece por `cpf`; por `contact_id` não há busca) | 503 `fonte_indisponivel`; nunca escolher um |
| 404 | (outro) | ferramenta inexistente, sem grant, sem escopo ou transporte errado — resposta única | 503 `fonte_indisponivel` (integração) |
| 409 | `endereco_indisponivel` | endereço sem flag/Metadata | 409, a área marca o endereço como indisponível |
| 413 | `corpo_grande` | corpo acima do teto da ferramenta | 503 (a área nunca manda isso) |
| 429 | `limite_taxa` | taxa da conta | 429 |
| 503 | `fonte_indisponivel`, `fonte_limitada`, `fonte_nao_configurada`, `auditoria_indisponivel` | CRM fora, limitado, sem credencial, trilha fora | 503 |
| 504 | `escrita_indeterminada`, `tempo_esgotado` | enviada ao CRM sem confirmação | 503; nada muda no cache; a próxima leitura traz o que o CRM tem |

## Comportamento da área diante do hub

| Situação | Área |
|---|---|
| Hub fora / 5xx / timeout | leitura: devolve o cache marcado `desatualizado`; escrita: 503 `fonte_indisponivel`, nada muda no cache |
| Timeouts | leitura `HUB_TIMEOUT` (10 s); escrita `HUB_TIMEOUT_ESCRITA` (30 s, acima dos 25 s do hub) |
| 401 | renova o token uma vez |
| `endereco_disponivel=false` | perfil mostra só o aviso; `PUT /perfil/contato` com endereço → 409 sem chamar o hub (o worker que ainda não perguntou deixa o hub decidir) |
| Chave `cpf` na resposta | descarta e loga anomalia |
