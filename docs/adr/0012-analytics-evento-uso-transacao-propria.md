# ADR-0012: Analytics em `evento_uso` com transação própria

- **Status:** Aceita
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0004

## Contexto

A spec "Minha APM" exige que **toda ação** do associado gere um evento
`{associadoId, acao, entidade, id, timestamp}`, e a futura "fatura de valor" (ADR-0007) depende
desse histórico para calcular benefícios usados. Trata-se de dado de **produto/negócio**, com
volume alto e identidade clara do associado, diferente da trilha de segurança.

A trilha existente, `evento_log` (`app/audit.py`), foi desenhada para segurança e erro:
identidade **só como HMAC** (`sub`/IP/UA com `LOG_HASH_KEY`), chaves proibidas em `detalhes`
com CHECK na tabela, e `audit.registrar` (`app/audit.py:125-127`) faz **commit/rollback na
sessão SQLAlchemy recebida** e engole falhas. Usar isso para analytics traria dois problemas:
um evento de uso comitaria (ou desfaria) a transação de negócio em andamento, e a categoria do
dado (segurança × produto) ficaria misturada, dificultando retenção (P-15) e consultas.

O front também gera ações que não passam pelo servidor (abrir aba, expandir *card*, trocar
tema), que a spec quer registradas.

## Decisão

1. Tabela própria `area_associado.evento_uso`, **INSERT-only** (ADR-0004):
   `id BIGINT AUTO_INCREMENT`, `ocorrido_em DATETIME(3)`, `contact_id CHAR(36)`,
   `sub_hash CHAR(64)`, `acao VARCHAR(64)`, `entidade VARCHAR(32) NULL`,
   `entidade_id VARCHAR(64) NULL`, `origem ENUM('servidor','ui','job','publico')`,
   `request_id CHAR(32)`, `detalhes JSON NULL` com **CHECK** que recusa as mesmas chaves
   proibidas de `evento_log` (`token`, `cpf`, `senha`, `authorization`, ...) e qualquer string
   com padrão de CPF. Índices `(contact_id, ocorrido_em)`, `(acao, ocorrido_em)`.
2. Módulo `app/uso.py` com `registrar(contact_id, sub_hash, acao, entidade=None,
   entidade_id=None, origem='servidor', detalhes=None, request_id=None)`:
   - valida `acao` contra um **catálogo fechado** (`app/uso_catalogo.py`, ex.:
     `noticia.salvar`, `beneficio.ativar`, `totalpass.abrir`, `clube.oferta_usar`,
     `perfil.foto_enviar`, `solicitacao.criar`, `onboarding.passo`); ação desconhecida → não
     grava e loga `WARNING`;
   - abre **`session_scope()` próprio**, independente da transação de negócio;
   - **nunca lança**; toda falha vai para o log do processo e incrementa um contador exposto em
     `/db-health` (`evento_uso_falhas`), para que a perda de eventos seja visível;
   - é chamado **após o commit** do negócio na rota (nunca dentro da transação), de modo que
     uma falha no analytics não desfaz a ação e uma ação desfeita não gera evento.
3. Eventos **só de UI** são enviados pelo front em lote: `POST /api/v1/uso` com corpo
   `{eventos: [{acao, entidade, entidade_id, ocorrido_em}]}`, **máximo 20 por chamada**,
   `fetch(..., {keepalive: true})` no `pagehide`/intervalo de 30 s; o servidor grava com
   `origem='ui'`, ignora `ocorrido_em` mais de 5 min no passado ou qualquer no futuro
   (substitui por `NOW(3)`), aplica o catálogo e `contact_id` **da sessão** (nunca do corpo).
   Ações que o servidor já registra são recusadas nesse endpoint (evita duplicidade).
4. `evento_log` **continua** para segurança e erro (login, callback, CSRF, hub indisponível,
   falhas), com identidade só por HMAC. `evento_uso` é a única tabela com `contact_id` em claro
   junto de ação de produto.
5. Rota pública da carteirinha (`/verificar/{token}`) registra com `origem='publico'`,
   `contact_id` do token resolvido e `detalhes` sem IP (IP só em `evento_log`, como HMAC).
6. Consultas agregadas para a "fatura de valor" são **views** criadas por migração
   (`vw_uso_mensal`), nunca SQL dinâmico na aplicação.

## Consequências

### Positivas
- Dado de produto desacoplado da trilha de segurança: categorias, retenção e consultas
  separadas.
- Falha de analytics nunca derruba nem desfaz a ação do associado.
- Perda de eventos é mensurável (`/db-health`), não silenciosa.
- O front não pode forjar identidade nem ações do servidor.

### Negativas / riscos
- Uma transação extra por ação (custo aceito; `INSERT` simples com índice).
- Volume cresce com o uso; precisa de política de retenção (P-15) e de partição por mês se
  passar de dezenas de milhões de linhas.
- Catálogo fechado exige disciplina: ação nova sem catálogo é descartada (por design, mas
  precisa de teste que falhe quando o front usar ação fora do catálogo).
- Eventos de UI em lote podem se perder se o navegador descartar o `keepalive` (aceito; não
  são ações de negócio).

### Obrigações decorrentes
- Migração `sql/00N_evento_uso.sql` sem `GRANT UPDATE`; CHECK de chaves proibidas idêntico ao
  de `evento_log` (fator comum em comentário referenciando `002_evento_log.sql`).
- Catálogo compartilhado com o front por geração (`frontend/src/uso_catalogo.ts` gerado de
  `app/uso_catalogo.py` no build; teste que falha se divergirem).
- Testes: `registrar` nunca lança (banco fora), chamada após commit, lote > 20 → 413, ação
  fora do catálogo ignorada, `contact_id` do corpo ignorado, CHECK recusa CPF em `detalhes`,
  contador em `/db-health`.
- P-15: retenção de `evento_uso` (proposta: 24 meses) e de `evento_log` (proposta: 12 meses),
  expurgo administrativo fora de `apm_area`.

## Alternativas descartadas

- **Reutilizar `evento_log`.** `audit.registrar` comita a sessão recebida (acoplamento
  transacional com o negócio), a identidade é só HMAC (impede a "fatura de valor" por
  associado) e misturaria categorias com retenções diferentes.
- **Fila externa (SQS/Redis) com consumidor.** Infraestrutura nova, credencial nova no
  container e complexidade sem necessidade para o volume previsto.
