# Contrato mcp_hub ↔ Minha APM (Fase 2b)

Escrito para quem implementa a extensão no repositório `mcp_hub` (plano próprio lá, regra 1 do
hub). A área já consome este contrato (`app/integracoes/hub.py`) e roda contra o simulado
(`app/integracoes/hub_stub.py`, `HUB_MODE=stub`) até o hub real existir.

## Transporte (já existente no hub)

- `POST /oauth/token`: `grant_type=client_credentials`, `client_secret_basic`,
  `scope=ferramentas:ler ferramentas:escrever`. Resposta `{access_token, expires_in}`.
- `POST /api/v1/ferramentas/{nome}` com `{"argumentos": {...}}` e `Authorization: Bearer`.
- Sucesso: `{"colunas", "linhas", "total", "truncado", "modo_pii", "observacoes"}`; a área lê `linhas`.
- Erro: `{"erro", "mensagem", "detalhes"?}` com o HTTP do pipeline.
- A área chama por `http://mcp_hub:8000` na `rede_publica` com `Host: mcp.apm.org.br`.

## Conta de serviço da área

| Item | Valor |
|---|---|
| Cliente | `area-associado` (`HUB_CLIENT_ID`), segredo em `HUB_CLIENT_SECRET` |
| Escopos | `ferramentas:ler` e `ferramentas:escrever` (o segundo é novo, P-05) |
| Origem permitida | CIDR da `rede_publica` |
| Grants | `modo_pii=completo` nas 4 ferramentas abaixo |
| Cotas | override por conta (P-03): os padrões por principal, 500 PII/dia e 60/min, não servem a um app |

## Regras para TODAS as ferramentas

1. Chave de entrada é `contact_id` (GUID do Dataverse). O hub resolve o contato por
   `GET /contacts({id})`. **Nenhuma resposta contém CPF** (ADR-0014). A área descarta e alerta
   se vier a chave `cpf`.
2. Allowlist fechada de campos, com nomes lógicos do Dataverse confirmados na Metadata API (P-05).
3. As de escrita: `efeito="escrita"`, transporte só REST, auditoria de intenção antes e de
   resultado depois, `If-Match: *` (nunca upsert), 1 retry só em 429/503 com `Retry-After` ≤ 5 s.
4. `entrada_invalida` (400) com `detalhes` para valor recusado pelo CRM; `nao_encontrado` (404)
   para contato inexistente; o resto sai como 5xx.

## Ferramentas

### `associado.perfil_consultar` (leitura)

Entrada `{"contact_id": "<guid>"}`. Saída: uma linha, ou nenhuma se o contato não existir.

| Campo | Origem no `contact` | Observação |
|---|---|---|
| `nome` | `fullname` | |
| `email` | `emailaddress1` | |
| `celular` | `mobilephone` | |
| `telefone` | `telephone1` | |
| `telefone2` | `telephone2` | |
| `endereco` | `address1_line1`, `address1_line2` (número), `address1_line3` (complemento), bairro (campo a confirmar), `address1_city`, `address1_stateorprovince`, `address1_postalcode` | objeto `{logradouro, numero, complemento, bairro, cidade, uf, cep}`; nomes lógicos a confirmar (P-05) |
| `num_contato` | `alf_num_contato` | |
| `crm` / `crm_uf` | `sol_st_numerocrm` / rótulo de `alf_uf_crm` | |
| `tipo_associado` | rótulo de `alf_tipo_associado` | |
| `status_associativo` | rótulo de `alf_status_associativo` | |
| `data_filiacao` | `alf_data_filiacao` | `AAAA-MM-DD` |
| `tem_foto` | `entityimage_timestamp` não nulo | booleano |

### `associado.contato_atualizar` (escrita)

Entrada `{"contact_id", "celular"?, "telefone"?, "telefone2"?, "email"?, "endereco"?}`.
`null` apaga, exceto `celular`, `email` e `endereco`. Valores chegam normalizados pela área:
telefone `(11) 91234-5678`, CEP `01318-901`, UF maiúscula. Saída
`{"contact_id", "campos_alterados": [...]}`.
`email` só é enviado depois do código confirmado e do login recente (ADR-0015).

### `associado.foto_obter` (leitura)

Entrada `{"contact_id"}`. Saída `{"imagem_jpeg_b64": "<base64>" | null}`, vinda de
`/contacts({id})/entityimage/$value`. Reservada para sincronizar a miniatura quando a foto for
trocada fora da área.

### `associado.foto_atualizar` (escrita)

Entrada `{"contact_id", "imagem_jpeg_b64": "<base64>" | null}`. Chega JPEG 512×512 já
normalizado pela área, sem metadados e com até ~150 kB. O hub revalida a assinatura JPEG e o
teto de 256 kB. `null` remove a foto. Saída `{"contact_id", "bytes"}`.

## Comportamento da área diante do hub

| Situação | Área |
|---|---|
| Hub fora / 5xx / timeout (10 s) | leitura: devolve o cache marcado `desatualizado`; escrita: 503 `fonte_indisponivel`, nada muda no cache |
| 401 | renova o token uma vez |
| 400 | 400 `entrada_invalida` com os `detalhes` do hub |
| 429 | 429 `limite_taxa` |
| Chave `cpf` na resposta | descarta e loga anomalia |
