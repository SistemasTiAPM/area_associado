# ADR-0016: Cadastro sem tipo ou situação recusa o login (P-20)

- **Status:** Aceita
- **Data:** 2026-10-17
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela)
- **Relacionadas:** ADR-0014

## Contexto

Com o escopo `carteirinha`, o userinfo do Login APM traz `tipo_associado` e `associado`
(situação) lidos do CRM na hora. A persona decide rota inicial, itens de menu e regras de
benefício. O IdP já barra quem não está Ativo, mas um cadastro pode chegar sem esses rótulos.

## Decisão

Com o escopo `carteirinha` pedido, userinfo sem `tipo_associado` **ou** sem `associado` faz o
callback falhar com `OidcError("persona_incompleta", 403)`: nenhuma sessão é aberta, o evento vai
para `evento_log` (`login_falha`, motivo `persona_incompleta`) e o associado vê a página de erro
pedindo contato com a Central de Relacionamento (`app/oidc.py:_carteirinha`, `app/main.py`).

## Consequências

### Positivas
- A área nunca decide persona por palpite (fail-closed, regra 5 do CLAUDE.md).
- O problema de cadastro fica visível para o atendimento.

### Negativas / riscos
- Associado ativo com cadastro incompleto fica sem acesso até a correção no CRM.

### Obrigações decorrentes
- Monitorar `login_falha` com motivo `persona_incompleta` depois do cutover.

## Alternativas descartadas
- **Abrir sessão sem persona:** menos atrito, mas espalha decisões de "persona desconhecida" por
  todas as telas.
