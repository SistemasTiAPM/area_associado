# ADR-0011: Cookie de sessão cifrado

- **Status:** Proposta (aguarda P-17)
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0013

## Contexto

A sessão da área usa o `SessionMiddleware` do Starlette, que **assina** o cookie com
`itsdangerous` (`TimestampSigner`) mas **não cifra**: o payload é JSON em base64, legível por
qualquer parte que obtenha o cookie (log de proxy mal configurado, extensão de navegador,
captura em dispositivo compartilhado). A assinatura impede adulteração, não leitura.

O conteúdo gravado por `store_identity` (`app/session_guard.py:64-78`) é `sub`, `cid`
(`contact_id`), `nome`, `email`, `cpf_mask`, `auth_at`, `amr`, `idt` e `csrf`. Nome, e-mail e
CPF mascarado são dados pessoais; `cid` é a chave de integração (ADR-0014). A SPA ainda vai exigir
`tipo` (categoria do associado) e `status` (situação associativa) na sessão para decidir o que
renderizar sem uma ida ao hub a cada navegação.

O `CLAUDE.md` já proíbe CPF completo e tokens na sessão; o cookie é `Secure`, `HttpOnly`,
`same_site=lax` (obrigatório por causa do callback cross-site, regra 7). A pendência P-17 é
confirmar com o usuário se a cifra do cookie é desejada ou se a sessão deve migrar para o servidor.

## Decisão

Proposta, condicionada à confirmação em P-17:

1. Novo módulo `app/sessao.py` com `SessaoCifradaMiddleware`, subclasse de
   `starlette.middleware.sessions.SessionMiddleware`, que **cifra o JSON com Fernet**
   (`cryptography`, AES-128-CBC + HMAC-SHA256, com timestamp) **antes** de assinar com
   `itsdangerous`, e decifra após verificar a assinatura. Falha em qualquer etapa → sessão vazia
   (nunca exceção para o associado) e evento `sessao.invalida` em `evento_log`.
2. Chave: `SESSION_ENC_KEY` em `Settings` (≥ 32 bytes, base64 url-safe). Ausente fora de
   `development`, a chave é **derivada de `SECRET_KEY` por HKDF-SHA256** com `info =
   b"area_associado/sessao/v1"`; em `production`, `SESSION_ENC_KEY` explícita é obrigatória
   (validador). Rotação: `SESSION_ENC_KEYS_ANTIGAS` aceita decifrar com chaves anteriores
   (`MultiFernet`), gravando sempre com a atual.
3. Nome do cookie **`__Host-area`** fora de `development` (exige `Secure`, sem `Domain`,
   `Path=/`); em `development` continua `area_sessao` para funcionar em `http://localhost`.
4. `same_site=lax` **mantido** (regra 7 do `CLAUDE.md`: callback é navegação cross-site).
   `HttpOnly` e `Secure` mantidos. Teto absoluto `SESSION_ABSOLUTE_MAX` mantido e verificado
   **após** decifrar (`auth_at`).
5. Conteúdo da sessão passa a incluir `tipo` e `status` (strings curtas, enum), além do atual.
   Continua proibido: CPF completo, access/refresh token, foto, qualquer payload do hub.
6. **Teste de tamanho**: a sessão máxima (nome 120 chars, e-mail 254 chars, todos os campos)
   cifrada e assinada deve ficar **abaixo de 4 kB**; o teste falha se exceder 3.500 bytes para
   manter margem.
7. Logout e troca de chave invalidam a sessão por não conseguir decifrar — comportamento
   desejado; o associado faz SSO silencioso no IdP.

## Consequências

### Positivas
- Dados pessoais no cookie deixam de ser legíveis por quem o capture; a assinatura continua
  impedindo adulteração.
- Sem infraestrutura nova (sem tabela de sessão, sem `UPDATE`/`DELETE`, sem Redis).
- `__Host-` elimina ataques de *cookie tossing* por subdomínio.

### Negativas / riscos
- `cryptography` entra em `requirements.txt` (já é dependência transitiva do `pyjwt[crypto]`;
  passa a ser explícita e fixada).
- Rotação de chave precisa de procedimento no `docs/PROVISIONAMENTO.md`; rotacionar sem
  `SESSION_ENC_KEYS_ANTIGAS` derruba todas as sessões ao mesmo tempo (aceitável, mas deve ser
  planejado).
- Cookie ~30% maior pelo overhead do Fernet; o teste de tamanho é a guarda.
- Cifra no cookie **não** permite revogação server-side; sessão roubada continua válida até o
  teto absoluto — mesma situação de hoje.

### Obrigações decorrentes
- **P-17**: confirmação do usuário antes de implementar; a ADR muda para "Aceita" com a data.
- `Settings`: `SESSION_ENC_KEY`, `SESSION_ENC_KEYS_ANTIGAS`, validadores por ambiente.
- Testes: ida e volta cifrar/decifrar, cookie adulterado → sessão vazia, chave antiga aceita,
  chave errada → vazia sem exceção, tamanho < 3.500 bytes, `__Host-` só fora de development,
  `same_site=lax` preservado, callback OIDC completo com o novo middleware.
- Atualizar `CLAUDE.md` (Sessão 1 "Sessão") e `docs/CUTOVER.md` (geração de `SESSION_ENC_KEY`
  no Secrets Manager `prod/area-associado/env`).

## Alternativas descartadas

- **Sessão no servidor (tabela `sessao` + cookie com ID opaco).** Permite revogação, mas exige
  `UPDATE`/`DELETE` em tabela nova, limpeza periódica e mais uma consulta por requisição;
  infraestrutura que a regra 4 do `CLAUDE.md` reservou para necessidade explícita (token
  contínuo), que não existe.
- **Manter apenas assinatura.** PII legível em base64 por qualquer portador do cookie; a
  inclusão de `tipo`/`status` aumenta o conteúdo exposto.
