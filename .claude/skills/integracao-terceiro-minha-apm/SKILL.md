---
name: integracao-terceiro-minha-apm
description: Roteiro do Integrador para qualquer fonte de dados ou parceiro novo na Minha APM (área do associado da APM) — RD Station, Qualicorp, Clube Certo/clubapm, TotalPass, IESAPM/plataformas de eventos, WordPress/Portal MBE, WhatsApp/SMS, ferramenta nova no mcp_hub, parceiro com API, parceiro sem API (CSV do plano B), cadastro/cobrança — com ADR própria, contrato documentado, cliente em app/integracoes com timeout e erro tipado, modo stub proibido em produção, allowlist de hosts, script check_<fonte>, vhost e a pendência P-xx para o que é do terceiro. Use SEMPRE que o pedido envolver "integrar", "chamar a API de", "receber arquivo/relatório do parceiro", "webhook", "enviar para o RD", "acesso único/SSO com parceiro", ou um EXT-nn do levantamento — mesmo que a integração pareça só um link.
---

# Integração com terceiro na Minha APM

Toda integração passa por quatro perguntas antes do código: **quem é o dono externo**, **qual é o
contrato** (campos, autenticação, limites, canal), **o que acontece quando a fonte cai** e **como
isso roda sem o terceiro** (stub/flag) para o resto do produto não travar. A spec v2 (§13) e o
levantamento (`docs/LEVANTAMENTO-TECNICO-spec-v2.md`, lista EXT-nn) já dizem o estado de cada uma;
comece por lá e por `docs/spec-v2/INDICE-IDS.md`.

## Regras que não se negociam (CLAUDE.md 4, 5, 16, 18, 21)

- **CRM e ERP só via `mcp_hub`**, por ferramenta tipada com allowlist de campos; a área nunca fala
  com Dataverse ou F&O. Ferramenta nova = mudança no repositório do hub (`/home/ubuntu/mcp_hub`,
  alias `github-mcp-hub`) + grant exato na conta `area-associado` + contrato em
  `docs/CONTRATO-HUB.md`. Chave de entrada é `contact_id`; o hub resolve CPF quando a fonte exige
  (ADR-0014). Escrita só com `HUB_ESCRITA_HABILITADA=true` e escopo `ferramentas:escrever`.
- **WordPress só pelo job** (ADR-0006), usuário RO próprio (P-07), nunca no processo web.
- **Parceiro novo exige ADR própria** (ADR-0009 §4): define `tipo_ativacao`, autenticação, trilha,
  limites de chamada, o que fica registrado e o que volta (status, uso, economia).
- Cliente em `app/integracoes/<fonte>.py`: timeout explícito (connect e total), **sem seguir
  redirect**, erro tipado (`<Fonte>Error(codigo, status)` como `HubError`), resposta com teto de
  bytes, nunca logar corpo de resposta de terceiro, nunca logar segredo; credencial só em
  `Settings` (`.env`), nunca em sessão, banco ou log.
- `<FONTE>_MODE=real|stub` no `Settings` com validador: **stub proibido em `APP_ENV=production`**;
  stub determinístico em `app/integracoes/<fonte>_stub.py` para testes e construção; a sessão
  expõe `dados_demonstracao` enquanto algo for stub.
- Hosts de saída em allowlist no `Settings` (molde `PARCEIROS_HOSTS` na ADR-0009; `CSP_IMG_HOSTS`
  para imagens); URL fora da lista = ignorada + `evento_log`.
- **Fail-closed**: fonte fora → 503 `fonte_indisponivel` na tela que depende dela; leitura devolve
  cache marcado `desatualizado` quando houver; escrita sem confirmação = resultado incerto, nada
  muda no cache.
- Dado pessoal mínimo para o terceiro (spec §11.6); dado de saúde nunca; agregados ≥ 20 pessoas.

## Rotina

1. **Levantar** (sem código): o que a spec pede (§13.1/13.2/13.3 e os gatilhos §12.2 que dependem
   da fonte), o que já existe em repos irmãos (RD Station está implementado em
   `/home/ubuntu/app_facial_recognition` e `/home/ubuntu/totalpass`; ferramentas do hub em
   `/home/ubuntu/mcp_hub/app/tools/`; IdP em `/home/ubuntu/login_associado`), dono externo,
   credencial, ambiente de homologação, limites, canal (API, webhook, SFTP, CSV, link).
2. **Contrato**: `docs/CONTRATO-<FONTE>.md` no molde de `CONTRATO-HUB.md` (transporte, conta,
   regras, ferramentas/endpoints, erros, comportamento da área). O que o terceiro precisa entregar
   vira `P-xx` em `docs/PENDENCIAS.md` com dono, "bloqueia" e estado `aguardando terceiro`.
3. **ADR** (`docs/adr/NNNN-*.md`, template no README): decisão, consequências, obrigações.
4. **Plano + aprovação** (skill `nova-fase-minha-apm`, §0).
5. **Código**: `Settings` (modo, URL, credencial, timeouts, allowlist, validadores); cliente real e
   stub; erro tipado mapeado em `app/api/erros.py`; flag se a funcionalidade visível depende da
   fonte; job em `app/jobs/` quando for lote/outbox/importação (lock, idempotência por
   `id_externo`, `job_execucao`, backoff com teto, alerta em `evento_log`).
6. **Script** `scripts/check_<fonte>.py`: autentica, chama uma leitura inócua, imprime só nomes de
   campos e contagens (nunca valores pessoais); sai 1 se falhar. Vhost: `limit_req` para rota
   pública nova (webhook de retorno, por exemplo) e 403 para rota interna.
7. **Testes**: unidade com stub (timeout, 401 renova uma vez, erro mapeado, redirect recusado,
   host fora da allowlist, CPF na resposta descartado); integração marcada `mysql` quando grava.
8. **Fechar**: PENDENCIAS/CONCLUIDO/levantamento (`EXT-nn` → estado), CLAUDE.md se a tabela de
   stack mudou.

## Casos típicos

| Caso | Caminho |
|---|---|
| Parceiro **sem API** (CSV §13.3) | job importador com validação linha a linha, `parceiro_id+id_externo` idempotente, CPF→`contact_id` via hub **no job** e descarte imediato do CPF; recepção por canal autenticado (upload no backoffice, SFTP ou bucket — DEC do levantamento); devolução de erros ao parceiro sem dado pessoal |
| Parceiro **com API** (tipo 2) | ADR própria; outbox `solicitacao` → envio com retry e teto; retorno por webhook (rota pública com assinatura e `limit_req`) ou polling; status mapeado para os 8 da spec |
| **Acesso direto / acesso único** (tipos 1 e 6) | nunca repassar token do IdP; se SSO, ADR própria com protocolo (OIDC do `login_associado` como IdP do parceiro é a opção preferida); sem SSO = deep link em allowlist + evento de uso |
| **RD Station** | reaproveitar autenticação OAuth2 e mapeamento de campos já usados no `app_facial_recognition`/`totalpass`; outbox `comunicacao_evento` na área; campos × eventos de conversão; descadastro refletido na hora; UTM e código do gatilho nos links |
| **Ferramenta nova no hub** (situação, financeiro, histórico de categorias, espelho de solicitação) | spec da ferramenta no contrato (entrada por `contact_id`, saída sem CPF, `modo_pii`, limites), implementação no repo do hub com ensaio, grant exato, `check_hub` estendido, cota revista (P-41) |
| **WordPress / Portal MBE** | só no job (ADR-0006); mapear post types antes (P-21); cache local; nunca credencial da Locaweb no processo web |

## Quando parar e perguntar

- Não existe dono externo nominal, credencial de homologação ou contrato: é EXT, não código.
- A fonte exige CPF e não há como o hub resolver `contact_id` → CPF: parar; isso muda a ADR-0014.
- O terceiro quer receber mais dado pessoal do que a spec §11.6 permite.
- A integração precisaria de token do IdP contínuo, de escrita no ERP ou de DELETE no banco.
