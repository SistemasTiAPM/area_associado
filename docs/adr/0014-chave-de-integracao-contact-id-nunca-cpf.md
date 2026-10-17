# ADR-0014: Chave de integração é `contact_id`, nunca CPF

- **Status:** Aceita
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0002, ADR-0011

## Contexto

O IdP `login_associado` emite no `id_token` e no `userinfo` dois identificadores: `sub`, um
**HMAC do CPF** (estável, não reversível sem a chave do IdP), e `contact_id`, o **GUID do
`contact`** no Dataverse. O `CLAUDE.md` proíbe CPF completo na sessão e em `detalhes` de
`evento_log` (filtro e CHECK), e o cookie leva só `cpf_mask` para exibição.

Os sistemas de origem, porém, são chaveados por CPF: o CRM usa `sol_st_cpf` no `contact` e
`dxc_numcpf` em `dxc_adesao_totalpass`; o ERP usa `BrazilianCNPJOrCPF` em `CustomersV3`; o
`totalpass` identifica por CPF; e as ferramentas atuais do `mcp_hub` (`associado.consultar`,
`totalpass.adesao_consultar`) recebem CPF. Para integrar, a área teria de carregar o CPF — o
que exigiria guardá-lo em sessão ou banco, contrariando a regra e o princípio de minimização
da LGPD.

Além disso, a carteirinha digital precisa de um **token público** verificável por terceiros
(`/verificar/{token}`), que não pode expor CPF nem ser enumerável.

## Decisão

1. **Nas tabelas e APIs da área, a chave do associado é `contact_id CHAR(36)`** (GUID em
   minúsculas, validado por regex no `Settings`/pydantic). Toda tabela com dado do associado
   tem `contact_id` e, para correlação com `evento_log`, `sub_hash CHAR(64)` (= `sub` do IdP,
   que já é HMAC). Nenhuma tabela tem coluna de CPF, nem mascarado.
2. **O CPF nunca sai do IdP ou do hub para a área.** A área não aceita CPF em nenhuma rota, não
   o grava, não o loga e não o envia ao hub. `cpf_mask` existe apenas na sessão para exibição e
   nunca é persistido.
3. **O hub resolve `contact_id → CPF` internamente** quando a fonte exige (pendência P-04):
   consulta o `contact` por GUID, obtém `sol_st_cpf` e chama a fonte; o CPF não aparece na
   resposta nem na trilha do hub (só o `contact_id` e o hash). Até P-04, as funcionalidades
   dependentes ficam em `HUB_MODE=stub` ou atrás de flag desligada (ADR-0007).
4. **Token público da carteirinha** = `base32(HMAC-SHA256(CARTEIRINHA_HMAC_KEY,
   contact_id))` truncado a 20 caracteres (100 bits), chave dedicada em `Settings`
   (`CARTEIRINHA_HMAC_KEY`, ≥ 32 bytes), gravado em `associado.carteirinha_token` com
   índice único. A rota `/verificar/{token}` busca por igualdade, responde com dados mínimos
   (nome, situação e validade — nada mais, conforme a spec) e tem `limit_req` estrito no vhost. Rotação da chave
   regenera todos os tokens por job (procedimento a documentar na Fase 2).
5. **Logs e JSON**: `evento_log.detalhes`, `evento_uso.detalhes`, `solicitacao.campos` e
   `solicitacao.resposta` têm CHECK que recusa chaves `cpf` e valores com padrão
   `\d{3}\.?\d{3}\.?\d{3}-?\d{2}`; o filtro de `audit.py` é reutilizado por `uso.py` e pelos
   schemas de solicitação. Formulário de alteração cadastral **não** tem campo CPF.
6. `sub` (HMAC) continua como identidade de segurança em `evento_log`; `contact_id` é a
   identidade de negócio em `evento_uso` e nas tabelas de domínio. Nenhuma tabela usa `email`
   ou `num_contato` como chave.

## Consequências

### Positivas
- Minimização de dado pessoal: a área não guarda nem transporta CPF; um vazamento do banco da
  área não expõe CPF.
- Conformidade com o `CLAUDE.md` e com a LGPD sem exceções.
- Chave estável e única (GUID do Dataverse), independente de correções cadastrais de CPF.
- Carteirinha verificável sem expor identificador real nem permitir enumeração.

### Negativas / riscos
- Dependência do hub para qualquer fonte chaveada por CPF (P-04); o hub passa a concentrar a
  resolução e precisa proteger essa etapa (cache por `contact_id`, sem CPF em log).
- Se um `contact` for mesclado/duplicado no CRM, o `contact_id` muda; o IdP precisa emitir o
  GUID vigente, e dados históricos ficam com o GUID antigo (correlacionáveis por `sub_hash`).
- O token da carteirinha é determinístico por chave: rotação exige regenerar tokens
  publicados (QR impresso fica inválido) — escopo de P-09.

### Obrigações decorrentes
- P-04 no hub antes de qualquer funcionalidade que dependa de fonte por CPF.
- P-09: escopo da carteirinha (campos exibidos, validade, política de rotação).
- `Settings.CARTEIRINHA_HMAC_KEY` obrigatória em production, distinta de `SECRET_KEY`.
- Testes: regex de GUID, CHECK recusa CPF em todos os JSON, rota pública com `limit_req`,
  token não enumerável (teste de entropia/tamanho), rota recusa parâmetro `cpf` em qualquer
  forma (query, corpo, header), `cpf_mask` ausente em todas as tabelas (teste de schema).
- Regra nova no `CLAUDE.md`: "chave do associado é `contact_id`; CPF nunca entra na área".

## Alternativas descartadas

- **CPF em sessão cifrada (ADR-0011).** Mesmo cifrado, viola a regra do `CLAUDE.md` e o
  princípio de minimização; o CPF passaria a transitar em cada requisição e chegaria aos logs
  por acidente com facilidade.
- **`num_contato` (número de associado) como chave.** Não há garantia de unicidade nem de
  estabilidade no CRM (reemissão, migrações históricas), e continuaria exigindo resolução para
  CPF nas fontes.
