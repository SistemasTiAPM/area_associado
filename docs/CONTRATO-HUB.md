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

## Solicitações (contrato do hub de 2026-11-13: paridade com o App APM; ADR-0023 e ADR-0024)

Origem: mensagem da sessão do `mcp_hub` de 2026-11-13 ("Hub → Minha APM: solicitações, mensagens e produto"),
que **substitui** a versão de 04/11 desta seção. No hub: `docs/PLANO-SOLICITACOES.md`, `PLANO-INTERACOES.md`,
`PLANO-PRODUTO-OPORTUNIDADE.md` e `CATALOGO-CRM-SOLICITACOES.md`. O App APM usa as MESMAS ferramentas e o
MESMO catálogo; o CRM distingue os canais pela conta que chama (Canal "Minha APM" = 100000001, Origem Web = 3),
nunca pela entrada. Regra D-14: o associado vê, no App e na Minha APM, tudo o que abriu por qualquer dos dois
canais, em qualquer estado; o que a Central abriu por telefone/balcão não aparece. A conversa cruza canais.

Código na área: `app/integracoes/hub.py` (+ `hub_stub.py`), `app/dominio/solicitacoes/catalogo_crm.py`,
`catalogo.py`, `situacao_crm.py`, `leitura_crm.py`, `mensagens.py`, `crm.py`; jobs em `app/jobs/solicitacoes.py`
e `app/jobs/mensagens.py`.

### Contas e grants (decisão de 2026-11-13: web lê, job escreve)

| Conta | Escopos | Grants exatos de `solicitacao.*` | Uso |
|---|---|---|---|
| `area-associado` (processo web) | `ferramentas:ler` | `listar`, `interacoes_listar`, `produtos` | lista e detalhe fundidos, conversa, catálogo |
| `area-associado-jobs` (serviço de jobs, `.env.jobs`) | `ler` + `escrever` | `criar`, `listar`, `interagir` | espelho, sincronização, envio das mensagens |

Nunca `solicitacao.*` com curinga. `HUB_ESCRITA_HABILITADA=true` só no `.env.jobs`: o web não pede o escopo
de escrita nem chama `criar`/`interagir` (conferido em teste). Canal e origem vêm do mapa de contas do hub
(`CRM_SOLICITACAO_CONTAS`): **só `criar` e `interagir` exigem a conta no mapa** — a conta web (só leitura) fica
fora; `area-associado-jobs` está no mapa (canal 100000001, origem 3). Conta que escreve sem mapa → 403
`canal_nao_configurado`. Aceito pelo hub em 13/11 (retorno à resposta da área); aplicação no painel: P-78 e P-79.
Produto (`produto_id` e `solicitacao.produtos`) no ar no hub desde 12/11.

**Cota de dado pessoal** (retorno do hub de 13/11): conta as LINHAS pessoais devolvidas, não as chamadas,
somando todas as ferramentas pessoais da conta (situação, perfil, solicitações); zera às **00:00 de Brasília**.
Conta web: 30.000/dia; jobs: 25.000/dia. `listar` custa as linhas que voltam (não o `limite`);
`interacoes_listar` custa **1 por mensagem devolvida**; `criar`, `interagir` e `produtos` não gastam. Na área:
lista em cache por contato (`HUB_LISTA_TTL`, 60 s); conversa com `HUB_CONVERSA_LIMITE` (20) em cache de memória
(`HUB_CONVERSA_TTL`), relida só quando `ultima_interacao_em` da lista muda, quando o job acabou de publicar uma
mensagem ou no "Atualizar conversa"; teto de 30 leituras de conversa por minuto por associado.
**Esgotada** (429 `cota_pii_esgotada`, sem `Retry-After`; cada negação é auditada): as leituras pessoais da
conta ficam suspensas por 15 min no processo (`PAUSA_COTA_S`); escritas e `produtos` seguem; a lista sai
`parcial` e a conversa indisponível.

### Catálogo de tipos (o mesmo do App — `catalogo_crm.TIPOS_CRM`)

O slug vai gravado no CRM e decide se o registro aceita mensagens. **Mudança de catálogo: combinar pelo
William, App e Minha APM mudam juntos.** Conferido contra esta tabela em `tests/test_paridade_unidades.py`.

| slug | entidade | grupo | assunto_id | time_id | produto_id |
|---|---|---|---|---|---|
| alteracao_cadastral | ocorrencia | — | e2d19f07-29e1-e811-a974-000d3ac1b8d2 | 312dcfcf-0714-e911-a952-000d3ac1be86 | — |
| duvida | ocorrencia | — | 64fb455c-c4e1-e811-a974-000d3ac1b8d2 | 312dcfcf-0714-e911-a952-000d3ac1be86 | — |
| segunda_via_boleto | ocorrencia | — | 710f6a32-29e1-e811-a974-000d3ac1b8d2 | 312dcfcf-0714-e911-a952-000d3ac1be86 | — |
| outros | ocorrencia | — | 64fb455c-c4e1-e811-a974-000d3ac1b8d2 | 312dcfcf-0714-e911-a952-000d3ac1be86 | — |
| defesa_profissional | ocorrencia | — | 774db512-2bfb-ed11-8f6e-000d3ac16b52 | 810c580c-c8cc-ed11-a7c6-000d3ac16b52 | — |
| planos_de_saude | oportunidade | — | — | 7bb27bfb-0714-e911-a952-000d3ac1be86 | 217ad212-6d88-e911-a968-000d3ac1b6c7 |
| seguro_vida | oportunidade | seguros | — | 7bb27bfb-0714-e911-a952-000d3ac1be86 | 51fff108-6e88-e911-a968-000d3ac1b6c7 |
| seguro_vida_dit | oportunidade | seguros | — | 7bb27bfb-0714-e911-a952-000d3ac1be86 | 6e87d9fe-87e9-eb11-bacb-0022483785cc |
| seguro_carro | oportunidade | seguros | — | 7bb27bfb-0714-e911-a952-000d3ac1be86 | c0fce926-6e88-e911-a968-000d3ac1b6c7 |
| seguro_residencial | oportunidade | seguros | — | 7bb27bfb-0714-e911-a952-000d3ac1be86 | d26d429c-5ef5-eb11-94ef-002248370ae9 |
| seguro_viagem | oportunidade | seguros | — | 7bb27bfb-0714-e911-a952-000d3ac1be86 | b8cfc64a-6e88-e911-a968-000d3ac1b6c7 |
| seguro_pet | oportunidade | seguros | — | 7bb27bfb-0714-e911-a952-000d3ac1be86 | f200d262-6e88-e911-a968-000d3ac1b6c7 |
| seguro_responsabilidade_civil | oportunidade | seguros | — | 7bb27bfb-0714-e911-a952-000d3ac1be86 | 3edf4a52-6a14-ef11-9f89-6045bd3ae7ae |
| assessoria_aposentadoria | oportunidade | — | — | 9b92ec59-c106-ed11-82e5-000d3ac16b52 | 11bcef28-8625-e911-a963-000d3ac1b38b |
| contabilidade | oportunidade | — | — | 66665b46-d8e5-e811-a979-000d3ac1b2cd | cb0f0d4d-8625-e911-a963-000d3ac1b38b |
| despachante | oportunidade | — | — | 4d111e0f-7e1e-ed11-b83d-000d3ac16b52 | f6fdd73e-8525-e911-a963-000d3ac1b38b |
| apm_facilities | oportunidade | — | — | 3afbea3a-7d1e-ed11-b83d-000d3ac16b52 | 27ad3e28-53f5-eb11-94ef-002248370ae9 |
| seguros (legado) | oportunidade | — | — | 7bb27bfb-0714-e911-a952-000d3ac1be86 | — |

- `seguros` (legado): nunca ofertado; reconhecido na lista e aceita mensagens.
- Rótulos de tela, ordem e carência (meses) iguais aos do App: Planos de Saúde; Seguro de Vida; Seguro de
  Vida – DIT adicional; Seguro Auto; Seguro Residencial; Seguro Viagem; Seguro Pet; Seguro de Responsabilidade
  Civil (grupo "Seguros"); Defesa Profissional (3); Assessoria para Aposentadoria (3); Contabilidade (2);
  Despachante (2); APM Facilities; Alteração cadastral; Dúvidas e perguntas; Segunda via de boleto; Outros
  assuntos. Carências a confirmar (P-81).
- **Tipos antigos da área** (não existem no App) são traduzidos no envio: `outro → outros`,
  `alteracao_cadastro → alteracao_cadastral`; `declaracao_associado`, `cancelamento_associacao`, `cartao_apm`,
  `diagnostico_marketing`, `submeter_trabalho`, `mentoria_*` → `outros`, com `Minha APM: <rótulo>` no título.
  `exclusao_dados` e pedido de benefício não vão ao CRM (`crm_sync='retido'`).
- A tela "Nova solicitação" oferece os 15 tipos novos; `alteracao_cadastral` e `outros` continuam nascendo
  pelos formulários próprios da área (perfil/Ajuda).

### `solicitacao.criar` (escrita — só o job)

Entrada: `contact_id`; `registro_id` (UUID v4 = `solicitacao.id`; idempotente: repetir devolve o mesmo
registro com `criada: false`); `entidade` (`ocorrencia`|`oportunidade`); `tipo` (slug do catálogo);
`titulo` (1–200) e `descricao` (10–2000), texto puro medido em unidades UTF-16; `assunto_id` (obrigatório em
ocorrência, `null` em oportunidade); `time_id`; `produto_id` **só em oportunidade** (omitido quando vazio; em
ocorrência o hub responde 400 — a área valida antes de sair).
Saída (1 linha): `contact_id, registro_id, entidade, criada, protocolo, statecode, statuscode, criado_em`.
Resposta fora do formato = `escrita_indeterminada` (repete com o mesmo id). O CRM completa sozinho Tipo de
Cliente, Lista de Preços e a linha do produto.

Texto: nos tipos do catálogo comum, título = nome do tipo e descrição = o texto do associado (como o App);
nos tipos antigos, `Minha APM: <rótulo>` e os campos do formulário em linhas "rótulo: valor". Nunca CPF,
e-mail ou telefone.

### `solicitacao.produtos` (leitura, sem dado pessoal — web)

Entrada `{"produto_ids": [...]}` (1–50 GUIDs, sem repetição). Uma linha por id: `produto_id, numero, nome,
ativo`; id inexistente → `ativo: false`. A área chama com os produtos dos tipos ofertáveis, guarda por
`HUB_PRODUTOS_TTL` (720 s) em memória, tenta de novo só 120 s depois de uma falha, mantém o último resultado
bom e, sem nenhum, usa o catálogo local. Tipo com produto inativo **some da tela** e `POST /solicitacoes`
responde 422 `servico_indisponivel`. O `nome` do CRM é descartado (nunca vai ao associado).

### `solicitacao.listar` (leitura — web e job)

Entrada `{contact_id, limite 1..50}`. Linhas, mais recentes primeiro, dos DOIS canais, em qualquer estado:
`contact_id, registro_id, entidade, protocolo, assunto_id, tipo, canal, titulo, descricao, statecode,
statuscode, criado_em, atualizado_em, ultima_interacao_em, ultima_interacao_autor, pode_enviar_mensagem`.
`pode_enviar_mensagem` (adendo de 2026-11-13; booleano, nunca nulo): `interagir` aceitaria uma mensagem naquele
registro agora — é estado do registro, igual para a conta web e a de jobs; não inclui o limite de 10/h e 40/dia.
Coluna ausente ou não booleana = comportamento anterior. `canal`: 100000000 App
APM, 100000001 Minha APM. A área descarta `titulo`; `descricao` fica só em trânsito (detalhe do registro
aberto pelo App), nunca em banco ou log. Web: `HUB_LISTA_LIMITE` (50) com cache; job: `JOBS_SYNC_LIMITE` (10,
ampliando a 50).

### Situação e rótulos na tela (os mesmos do App — `situacao_crm.py`)

| par `statecode/statuscode` | situação | rótulo |
|---|---|---|
| 1/* | `concluida` | Concluída (provisório, P-80) |
| 2/* | `cancelada` | Cancelada (provisório, P-80) |
| 0/1 | `aberta` | Aberta (provisório, P-80) |
| 0/3 em ocorrência; 0/100000002 | `aguardando_associado` | "A Central aguarda seu retorno" / "A APM aguarda seu retorno" |
| 0/qualquer outro (inclui 100000001); statecode desconhecido | `em_andamento` | "Aguardando a Central/APM" se o último autor é o associado; senão "Em andamento" |

Ordem e regra confirmadas pelo hub em 13/11. O texto segue a **entidade**: "a Central" em ocorrência, "a APM"
em oportunidade e em entidade desconhecida. (Quem assina a conversa é por tipo: Central de Relacionamento nos
tipos de atendimento geral — `alteracao_cadastral`, `duvida`, `segunda_via_boleto`, `outros` — e em ocorrência de
tipo desconhecido; Equipe APM em `defesa_profissional` e em toda oportunidade.) Os textos de `aberta`,
`em_andamento`, `concluida` e `cancelada` estão no app Flutter (P-80). Situações **abertas** (unicidade e caixa de
envio): `aberta`, `em_andamento`, `aguardando_associado`. Datas no horário de Brasília. O que ainda não chegou
ao CRM mantém os rótulos da spec v2 §8.5.

**Carência e unicidade são regra de cada cliente (o hub não aplica)** e por isso idênticas às do App: carência em
meses de calendário desde a data de associação; um registro aberto por slug, só entre tipos do catálogo.
Consequência aceita pelo William (DIV-49): os tipos da área traduzidos para `outros`, enquanto abertos, impedem
"Outros assuntos" no App.

### Mapeamento `statecode/statuscode` → status da área (job de sincronização)

Transita só quando o par MUDA em relação ao último visto (`crm_estado/crm_status`).

| Entidade | Par | Status na área |
|---|---|---|
| ocorrência | 0/1 na criação | nada |
| ocorrência | 0/1 vindo de outro estado | `em_atendimento` |
| ocorrência | 0/2, 0/4 | `em_atendimento` |
| ocorrência | 0/3 | `pendente_associado` + mensagem padrão + protocolo |
| ambas | 0/100000001 (respondido pelo associado) | `em_atendimento` |
| ambas | 0/100000002 (respondido pela Central) | `pendente_associado` + "Há uma nova mensagem para você na conversa…" |
| ocorrência | 1/* | `concluida_positiva` |
| ocorrência | 2/6 | `concluida_negativa` |
| ocorrência | 2/2000 ou desconhecido | nada + divergência no `evento_log` |
| oportunidade | 0/1 nada · 0/2 `em_atendimento` · 1/* `concluida_positiva` · 2/* `concluida_negativa` | |

### Conversa na Timeline

**`solicitacao.interacoes_listar` (leitura — web).** Entrada `contact_id, registro_id` (o pai), `entidade`,
`limite 1..50`. Linhas: `contact_id, registro_id, entidade, interacao_id, autor, canal, texto, criado_em` —
`autor` ∈ {`associado`, `central`} (outro valor é descartado). Pai de outro contato, de outro canal ou
inexistente → lista vazia. O texto nunca é gravado nem logado pela área.

**`solicitacao.interagir` (escrita — só o job).** Entrada `contact_id, registro_id, entidade, interacao_id`
(UUID v4 = `solicitacao_mensagem.id`; idempotente), `texto` (2–2000, texto puro). Saída `contact_id,
registro_id, entidade, interacao_id, criada, criado_em`. Só aceita se o pai é do contato, aberto por
autoatendimento, de tipo do catálogo, não bloqueado pela Central e com `statecode 0`. Limite por associado:
**10 por hora e 40 por dia, somando App e Minha APM** → 429 `limite_titular` com `Retry-After` (até 3600 s).

Na área: `POST /api/v1/solicitacoes/{id}/mensagens` grava na outbox e responde 202; o job `enviar_mensagens`
publica e **apaga o texto** ao confirmar. A caixa de envio só aparece com `pode_enviar`: situação aberta, tipo do
catálogo, canal 100000000/100000001 e registro não bloqueado; encerrado = só leitura, com "Abrir nova
solicitação". **Bloqueio pela Central:** caixa de envio = regra local **E** `pode_enviar_mensagem` da lista.
Registro aberto com `false` → sem campo nem botão, com o texto "A Central desativou o envio de mensagens nesta
solicitação. Ela continua em atendimento e você acompanha as respostas por aqui." — **diferente do texto
sugerido pelo hub e usado no App** ("Esta conversa foi encerrada pela Central…"), por decisão do William no
ensaio de 13/11: bloquear o envio não encerra a ocorrência, e abrir outra do mesmo tipo seria recusado (
`motivo_bloqueio = nao_permitida`; o `POST` responde
403 `mensagem_nao_permitida`). A Central pode desbloquear: a coluna manda. O 403 `interacao_nao_permitida`
aprendido na fila (mensagem `falhou`) só vale enquanto o hub não disse nada mais novo — lista indisponível,
registro fora dela, coluna ausente ou falha posterior à leitura (cache de `HUB_LISTA_TTL`). 403 e 409
`registro_fechado` continuam possíveis entre a lista e o envio.

### O que NÃO existe no hub (e o que a área faz)

- **Ferramenta de status/cancelamento:** não existe **por desenho** (a credencial do hub não altera ocorrência
  nem oportunidade). Com o registro aberto, o associado pede o cancelamento **pela conversa** e a Central
  cancela; fechado, fala com a Central. `POST …/cancelar` segue 409 `na_central`; mudança local posterior vira
  `crm_sync='retido'`.
- **Cursor de alterações:** a sincronização segue por contato a cada 6 h com teto de linhas (P-75); a tela lê o
  par ao vivo.

### Erros das ferramentas `solicitacao.*`

| HTTP | `erro` do hub | Na área (`HubError`) | Efeito |
|---|---|---|---|
| 400 | `entrada_invalida` | `entrada_invalida` | permanente (bug de integração; log sem dado pessoal) |
| 403 | `canal_nao_configurado` | `canal_nao_configurado` | sistêmico: para a rodada |
| 403 | `interacao_nao_permitida` | `interacao_nao_permitida` | mensagem `falhou` (aviso); a tela esconde o envio |
| 404 | `nao_encontrado` (contato/registro) | `nao_encontrado` | permanente |
| 404 | `nao_encontrado` (assunto/time/produto) | `catalogo_crm_invalido` | sistêmico: catálogo da área errado |
| 409 | `conflito` | `conflito` | permanente (id reaproveitado em outro registro) |
| 409 | `registro_fechado` | `registro_fechado` | mensagem `falhou` (aviso); só leitura |
| 422 | `produto_inativo` | `produto_inativo` | pedido cancelado pelo sistema: "Este serviço não está disponível no momento." |
| 429 | `limite_titular` | `limite_titular` (sem pausa do processo) | mensagens do contato adiadas pelo `Retry-After` |
| 429 | `limite_taxa` (60 s) / `fonte_limitada` (1–60 s) | `limite_taxa` | pausa o processo pelo `Retry-After` |
| 429 | `cota_pii_esgotada` (sem `Retry-After`) | `cota_esgotada` | leituras pessoais da conta suspensas por 15 min; sistêmico no job |
| 503 | `produto_indisponivel` | `produto_indisponivel` | reenvio imediato do MESMO pedido sem `produto_id` |
| 503 | `interacao_desabilitada` | `interacao_desabilitada` | sistêmico no job; na tela, 503 `mensagens_indisponiveis` |
| 504 | `escrita_indeterminada` / `tempo_esgotado` | `escrita_indeterminada` | transitório: repete com o mesmo id; recuo 1…60 min |
| outros | — | `fonte_indisponivel` | transitório; lista da área sai `parcial` |

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
