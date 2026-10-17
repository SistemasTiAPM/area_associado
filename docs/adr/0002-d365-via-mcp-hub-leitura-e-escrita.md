# ADR-0002: Dynamics 365 somente via mcp_hub (leitura e escrita)

- **Status:** Aceita
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0003, ADR-0005, ADR-0010, ADR-0014

## Contexto

O levantamento dos projetos irmãos encontrou **cinco clientes Dynamics diferentes** na APM
(`login_associado`, `appapm`, `totalpass`, `apm-parceiros`, `app_facial_recognition`), cada um com
seu próprio *app registration* no Entra ID, cache de token, tratamento de erro e política de
retry. Nenhum deles compartilha código; cada um repete a mesma superfície de risco.

O `mcp_hub` (`/home/ubuntu/mcp_hub`, `mcp.apm.org.br`, criado em 2026-10-16, ainda **não
provisionado** — pendência P-02) nasceu para centralizar a leitura de CRM (Dataverse) e ERP
(Finance & Operations) com conectores maduros: cache de token, disjuntor (*circuit breaker*),
proteção anti-SSRF e trilha de auditoria. Expõe ferramentas por REST em
`/api/v1/ferramentas/{nome}`, com OAuth 2.0 `client_credentials` por conta de serviço. Suas
regras internas relevantes: **regra 1** — escrita exige plano próprio, papel próprio no conector e
trilha específica; **regra 8** — o hub usa credencial própria no Entra, nunca reaproveitada de
outro aplicativo.

As ferramentas existentes `associado.consultar` e `totalpass.adesao_consultar` exigem **CPF**
como chave, e a área só dispõe de `contact_id` (GUID do `contact`) e `sub` (HMAC do CPF)
emitidos pelo IdP (ver ADR-0014). A spec "Minha APM" exige leitura (perfil, benefícios, adesões)
e **escrita** (atualizar contato, foto, solicitações), algo que o hub ainda não oferece.

## Decisão

1. **A área nunca fala com Dataverse nem com F&O.** Toda leitura e toda escrita no Dynamics
   passa pelo `mcp_hub`. Não existe *app registration* da área no Entra, nem `msal`/`azure-*`
   em `requirements.txt`.
2. **Extensão do hub**, a ser planejada e aprovada no repositório do hub (plano próprio lá):
   - `Ferramenta.efeito = leitura | escrita` e `Ferramenta.transportes`; ferramentas de
     **escrita só por REST** (nunca pelo transporte MCP para agentes).
   - Escopos por conta de serviço: `ferramentas:ler` e `ferramentas:escrever`; a conta da
     área recebe ambos, demais contas só `ler`.
   - Auditoria de intenção **bloqueante** antes da escrita (falha ao registrar → escrita não
     ocorre) e tabela `auditoria_escrita` com o diff aplicado.
   - Conector `dataverse_escrita.py` com credencial própria e papel de segurança mínimo no
     Dataverse (pendência P-05: *app registration* de escrita no Entra).
   - Ferramentas novas: `associado.contato_atualizar`, `associado.foto_atualizar`,
     `solicitacao.espelhar`, `solicitacao.status_atualizar`, `solicitacao.alteracoes_consultar`.
   - Leitura por `contact_id` nas ferramentas existentes (pendência P-04): o hub resolve
     `contact_id → CPF` internamente quando a fonte exige.
   - Cotas por conta de serviço (pendência P-03) para que a área não esgote o limite do
     Dataverse (6.000 req/5 min) para os demais consumidores.
3. **Cliente na área**: módulo `app/integracoes/hub.py`.
   - Token: `POST http://mcp_hub:8000/oauth/token` na `rede_publica`, header
     `Host: mcp.apm.org.br`, autenticação `client_secret_basic` (`HUB_CLIENT_ID`,
     `HUB_CLIENT_SECRET` em `Settings`). Evita *hairpin* pela Cloudflare, igual ao back-channel
     do IdP.
   - O *access token* do hub vive **só em memória do processo** (um por worker), renovado no
     `exp - 60 s` e **uma única vez** ao receber 401; nunca em sessão, banco ou log.
   - `httpx.Client` com `timeout=10` (connect/read/write/pool), sem redirecionamentos, e toda
     chamada nas rotas via `run_in_threadpool`.
   - Erros do hub mapeados para códigos próprios (`hub_indisponivel` → 503,
     `hub_recusou` → 502, `nao_encontrado` → 404) e registrados em `evento_log` sem payload.
   - `HUB_MODE = real | stub`; `stub` lê fixtures de `app/integracoes/fixtures/` e é
     **proibido com `APP_ENV=production`** (validador em `config.py`, mesmo padrão de
     `AUTH_MODE`).
4. **ERP é somente leitura** pelo hub (ADR-0010); nenhuma ferramenta `financeiro.*` de escrita
   será criada.

## Consequências

### Positivas
- Uma única credencial Dynamics de escrita na APM, com trilha e cotas em um só lugar.
- A área não carrega SDK Microsoft, não guarda segredos do Entra e não precisa conhecer o
  esquema do Dataverse.
- Disjuntor e cache do hub protegem o CRM de rajadas vindas da área.
- O CPF nunca transita pela área (ADR-0014).

### Negativas / riscos
- **Dependência dura do hub**: hub fora → área sem perfil, benefícios e solicitações
  espelhadas. Mitigado por cache local (ADR-0003, ADR-0008) e por telas que degradam com
  mensagem explícita.
- O hub ainda não está provisionado (P-02) e a escrita ainda não existe: a área nasce em
  `HUB_MODE=stub` e só vira real após P-02/P-04/P-05.
- Mais um salto de rede e mais um ponto de latência.
- O plano de escrita no hub é trabalho em outro repositório, com aprovação própria.

### Obrigações decorrentes
- P-02, P-03, P-04, P-05 antes de `HUB_MODE=real` em produção.
- `scripts/check_hub.py`: valida token, escopos e lista de ferramentas esperadas (falha com
  exit 1 se faltar alguma).
- Regra nova no `CLAUDE.md`: "Rota não fala com Dynamics: delega a `app/integracoes/hub.py`".
- Testes com o hub mockado (`respx`/`httpx.MockTransport`), nunca tocando rede: renovação
  única em 401, timeout, mapeamento de erros, segredo ausente no log.
- Vhost: nenhuma rota nova pública; o hub só é alcançado pela rede Docker interna.

## Alternativas descartadas

- **App registration próprio da área com conectores copiados do `login_associado`/`appapm`.**
  Criaria o sexto cliente Dynamics, duplicaria token cache, disjuntor e auditoria, e espalharia
  mais uma credencial de escrita.
- **Reaproveitar o app registration de outro aplicativo (appapm/Portal MBE).** Viola a regra de
  credencial própria do hub e o registro do appapm está exposto (segredo em configuração legada),
  o que contaminaria a trilha de auditoria da área.
