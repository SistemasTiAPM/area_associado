# Contrato mcp_hub ↔ Minha APM

Implementado no `mcp_hub` na Fase 2b (19/10/2026, commits `365a531`..`8bb3c43` do repositório
`SistemasTiAPM/mcp_hub`; regra 1 do hub reescrita). A área consome este contrato em
`app/integracoes/hub.py` e roda contra o simulado (`app/integracoes/hub_stub.py`,
`HUB_MODE=stub`) até a provisão real (P-02, P-05, P-29).

## Transporte

- `POST /oauth/token`: `grant_type=client_credentials`, `client_secret_basic`,
  `scope=ferramentas:ler ferramentas:escrever`. O hub só emite escopos que a conta tem
  (`invalid_scope` se pedir a mais). Resposta `{access_token, expires_in}`. A cada chamada o
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
| Escopos da conta | `ferramentas:ler` e `ferramentas:escrever`. **O de escrita só é marcado em produção depois da P-29** |
| Origem permitida | CIDR da `rede_publica` |
| Grants | **exatos** (curinga não libera escrita), `modo_pii=completo`, nas 4 ferramentas abaixo |
| Taxa e cota | por conta (antiga P-03, resolvida no hub): `chamadas_por_minuto` (1–6000) e cota PII própria; os padrões por principal (60/min, 500 PII/dia) não servem a um app |

## Regras para TODAS as ferramentas

1. Chave de entrada é `contact_id` (GUID do Dataverse; o GUID todo zero é recusado). O hub
   lê o contato por `GET /contacts({id})`. **Nenhuma resposta contém CPF** (ADR-0014); a área
   ainda descarta e loga a chave `cpf` se vier.
2. Só transporte REST: as quatro não aparecem no MCP nem no portal do hub.
3. Titular auditado por `contact_id` (`auditoria_titular_contato`). Pedido LGPD no hub = busca
   pelo CPF **e** pelo contact_id.
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

## Erros

| HTTP | `erro` | Quando | Área |
|---|---|---|---|
| 400 | `entrada_invalida` | validação do hub ou valor recusado pelo CRM | 400 com os `detalhes` |
| 404 | `nao_encontrado` | contato inexistente no PATCH | 404 |
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
