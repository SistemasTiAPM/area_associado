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

## Solicitações (P-06 resolvida pelo hub em 2026-11-04; ADR-0023)

**Contrato do hub**, implantado e ensaiado em produção em 2026-11-04: `mcp_hub/docs/PLANO-SOLICITACOES.md`
(decisões D-1..D-13) e `mcp_hub/docs/CATALOGO-CRM-SOLICITACOES.md` (GUIDs e códigos do tenant). A proposta
anterior da área (`task` + `espelhar`/`status_atualizar`/`alteracoes_consultar`) foi **substituída**: o hub
cria `incident` (ocorrência) ou `opportunity` (oportunidade) e lista por contato. Cliente:
`app/integracoes/hub.py` (`solicitacao_criar`, `solicitacao_listar`); simulado em `hub_stub.py`; jobs em
`app/jobs/solicitacoes.py`; catálogo em `app/dominio/solicitacoes/catalogo_crm.py`; texto em
`app/dominio/solicitacoes/crm.py`.

Regras comuns:

- Conta **`area-associado-jobs`** (`.env.jobs`): `ferramentas:ler` + `ferramentas:escrever`, grants exatos em
  `solicitacao.criar` e `solicitacao.listar` (nunca `solicitacao.*`), mais `associado.situacao` e
  `associado.perfil_consultar` (M-8). `HUB_ESCRITA_HABILITADA=true` só no `.env.jobs`; o web segue só leitura.
- **Canal e origem** o hub grava pela CONTA chamadora (`CRM_SOLICITACAO_CONTAS` no `.env` do hub):
  `area-associado-jobs` → canal `100000001` "Minha APM", origem `3` Web. Conta sem mapa → 403
  `canal_nao_configurado` antes de qualquer chamada ao CRM.
- **Sem CPF**, sem e-mail, sem telefone no texto: só o que o associado preencheu no formulário do tipo.
- **Cota PII conta LINHAS**: `listar` com 10 linhas gasta 10; `criar` não gasta.

### `solicitacao.criar` (escrita, só REST)

| Campo | Regra | Origem na área |
|---|---|---|
| `contact_id` | GUID | dono do pedido |
| `registro_id` | UUID v4 minúsculo = chave primária no CRM (`incidentid`/`opportunityid`); **idempotente** (o hub faz GET antes do POST) | `solicitacao.id` (por isso `crm_id = id`) |
| `entidade` | `ocorrencia` \| `oportunidade` | catálogo |
| `tipo` | `^[a-z0-9_]{2,50}$` → `alf_tipo_solicitacao` | `tipo_servico` |
| `titulo` | ≤ 200 unidades UTF-16 | `Minha APM: <rótulo do tipo>` (no formulário livre, o assunto dado pelo associado) |
| `descricao` | 10–2000 unidades UTF-16, texto puro | cabeçalho fixo + "rótulo: valor" por campo do formulário (texto longo em bloco) |
| `assunto_id` | GUID `subject`; obrigatório em ocorrência, `null` em oportunidade | catálogo |
| `time_id` | GUID `team` dono | catálogo (Central de Relacionamento) |

Saída: **uma** linha `{contact_id, registro_id, entidade, criada, protocolo, statecode, statuscode, criado_em}`.
`criada=false` = já existia (repetição). `protocolo` = `ticketnumber` (`CAS-######-XXXXXX`), só em ocorrência.
Resposta fora disso (outro `registro_id`, ocorrência sem protocolo, códigos não inteiros) = **resultado
incerto**: a área trata como `escrita_indeterminada` e repete com o mesmo `registro_id`.

Limite de texto garantido **na origem**: o formulário livre (`outro`) aceita assunto ≤ 120 e mensagem ≤ 1700
unidades UTF-16 (API e `maxLength` do navegador medem igual); o pior caso de cada tipo cabe nas 2000 sem
corte (teste). Corte só como defesa, marcado `[texto cortado pela Minha APM]`, nunca no meio de um emoji.

### `solicitacao.listar` (leitura, só REST)

Entrada `{"contact_id", "limite": 1..50}` (padrão do hub 20; a área usa `JOBS_SYNC_LIMITE` = 10 e amplia
para 50 só quando o pedido não está na primeira página). Linhas, mais recentes primeiro:
`registro_id, entidade, protocolo, assunto_id, tipo, canal, titulo, descricao, statecode, statuscode,
criado_em, atualizado_em` (+ `contact_id`). Registros abertos pela Central vêm com `canal`, `titulo` e
`descricao` `null` — e **também gastam linha da cota**. A área descarta `titulo`/`descricao` (não guarda texto
do CRM) e casa só por `registro_id`.

### Mapeamento `statecode/statuscode` → status da área

A área só transita quando o par **muda** em relação ao último visto (`crm_estado`/`crm_status`): depois de
o associado agir, o CRM continua no estado anterior. Códigos padrão do Dataverse (customização do tenant a
confirmar — P-76):

| Ocorrência | Área |
|---|---|
| 0/1 Em andamento | nada — é o status de **criação** (ninguém da Central abriu) |
| 0/1 vindo de outro estado | `em_atendimento` (a Central retomou, ex.: saiu de "Aguardando detalhes") |
| 0/2 Em espera, 0/4 Pesquisando | `em_atendimento` |
| 0/3 Aguardando detalhes | `pendente_associado`, com a mensagem padrão + protocolo (o CRM não manda texto) |
| 1/* Resolvida | `concluida_positiva` |
| 2/6 Cancelada | `concluida_negativa` |
| 2/2000 Mesclada; 0/x desconhecido | nada + divergência no `evento_log` (uma vez por mudança) |

Oportunidade: 0/1 nada, 0/2 `em_atendimento`, 1/* `concluida_positiva`, 2/* `concluida_negativa`. Caminho pela
máquina com `(apm, crm)`, passando por `em_atendimento` quando preciso (inclusive de `pendente_associado`, P-66).

### O que NÃO existe no hub (e o que a área faz)

| Falta | Consequência na área |
|---|---|
| Ferramenta de status (`status_atualizar`): o app user do hub não tem Write em incident/opportunity | Pedido já no CRM: **cancelar e responder pela área são recusados** (409 `na_central`) e a tela orienta a falar com a Central pelo protocolo. Mudança local depois do envio (ex.: backoffice) fica `crm_sync='retido'` + aviso `solicitacao_transicao_retida` — reprocessável quando a ferramenta existir (P-74) |
| Consulta por cursor (`alteracoes_desde`) | Sincronização por contato com cadência (`JOBS_SYNC_CADENCIA_H` = 6 h) e teto diário de linhas (`JOBS_SYNC_LINHAS_DIA` = 5.000); com cursor filtrado pelo canal Minha APM o custo cairia para dezenas de linhas/dia (P-75) |
| Campo de mensagem pública | `pendente_associado` vindo do CRM usa texto fixo (`rotulos.MENSAGEM_PENDENTE_CRM`) + protocolo |

### Erros das duas ferramentas

| HTTP / `erro` | Classe no job | Efeito |
|---|---|---|
| 429 `fonte_limitada` / `limite_taxa` + `Retry-After` (1..60 s) | sistêmico | para a rodada; o processo inteiro não chama o hub até o prazo; nenhuma tentativa gasta |
| 504 `escrita_indeterminada` | transitório | repete com o mesmo `registro_id` (seguro), recuo 1, 2, 4 … 60 min |
| 404 `nao_encontrado` do **contato** | permanente | `falhou` + `evento_log` |
| 404 `nao_encontrado` de **assunto/time** | sistêmico (`catalogo_crm_invalido`) | catálogo errado: para a rodada, não marca `falhou` (a área lê `detalhes[].campo`; até o hub mandar, a mensagem fixa — P-76) |
| 409 `conflito` | permanente | `falhou` + `evento_log` severidade erro (o `registro_id` é de outro contato) |
| 403 `canal_nao_configurado` | sistêmico | conta sem mapa no hub: para a rodada |
| 400 `entrada_invalida` | permanente | `falhou` |

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
