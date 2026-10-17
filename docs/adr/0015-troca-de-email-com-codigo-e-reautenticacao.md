# ADR-0015: Troca de e-mail com código no novo endereço e reautenticação recente

- **Status:** Aceita
- **Data:** 2026-10-17
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Integrador)
- **Relacionadas:** ADR-0002, ADR-0012, ADR-0014

## Contexto

O e-mail do contato no CRM é o canal que o Login APM usa para o código de primeiro acesso e de
recuperação de senha (`login_associado/app/notifications.py`, OTP por e-mail). Quem troca esse
e-mail controla a recuperação da conta. Permitir a troca direta pela área significaria que uma
sessão sequestrada (cookie roubado, computador compartilhado) toma a conta de vez.

O usuário escolheu, entre "somente por solicitação", "direto com código" e "direto sem
verificação", a troca **direta com código enviado ao novo endereço**.

## Decisão

1. A troca exige **login recente no IdP**: `auth_time` do id_token (guardado na sessão como
   `idp_at`) a no máximo `REAUTH_MAX_IDADE` (padrão 900 s). Não vale a hora do login na área,
   que o SSO silencioso renova sem pedir senha. Sem login recente: `403
   reautenticacao_necessaria` e a SPA leva a `/auth/login?reauth=1` (`prompt=login`).
2. **Código de 6 dígitos** (`secrets.randbelow`) enviado ao **novo** endereço; validade
   `EMAIL_CODIGO_TTL` (padrão 10 min); 5 tentativas; 60 s entre envios; 5 envios por hora por
   associado; pedido novo invalida os pendentes; código usado não volta a valer.
3. O banco (`email_verificacao`, `sql/007`) guarda só **HMAC** do e-mail novo e do código
   (`LOG_HASH_KEY`), com comparação em tempo constante. Nem o e-mail nem o código são
   recuperáveis a partir da tabela.
4. O pedido só é marcado como usado **depois** de o CRM (via mcp_hub) confirmar a troca.
5. O endereço **antigo** recebe aviso de que o e-mail de acesso foi alterado, com o contato da
   Central (melhor esforço: falha de entrega é logada, não desfaz a troca).
6. Envio por SMTP com STARTTLS e certificado verificado, mesmo padrão do Login APM. `SMTP_MODE=stub`
   (proibido em produção) não envia nada e, fora de produção, devolve o código na API para teste.

## Consequências

### Positivas
- Sessão roubada não basta para trocar o canal de recuperação: precisa da senha (step-up) e da
  caixa de entrada nova.
- O titular é avisado no endereço antigo.

### Negativas / riscos
- Depende de credencial SMTP própria da área (P-27). Sem ela, a troca fica indisponível em produção.
- A área passa a enviar e-mail: entregabilidade (SPF/DKIM do remetente) é responsabilidade da TI.

### Obrigações decorrentes
- P-27: credencial SMTP e remetente autorizados.
- Testes de integração cobrem código errado, código de outro e-mail, esgotamento persistido,
  reenvio e step-up (`tests/test_fase2_integracao.py`).

## Alternativas descartadas
- **Somente por solicitação aprovada:** mais segura, porém lenta para o associado (escolha do usuário).
- **Direto sem verificação:** abre tomada de conta.
