# ADR-0008: TotalPass por leitura via hub e deep link, sem escrita

- **Status:** Aceita
- **Data:** 2026-10-16
- **Decisores:** Sistemas TI (William) · Claude Code (Sentinela/Atlas/Maestro/Vitrine/Estivador/Integrador)
- **Relacionadas:** ADR-0002

## Contexto

O benefício TotalPass é operado pelo projeto `totalpass` (`totalpass.apm.org.br`, PHP, schema
próprio `apm_totalpass` no RDS). Esse sistema **não expõe API interna** nem tabela compartilhada
com outros serviços; o fluxo de adesão (elegibilidade, plano, pagamento recorrente) é todo dele.

A adesão paga é gravada no CRM na entidade customizada `dxc_adesao_totalpass` (campos
`dxc_numcpf`, `dxc_dataadesao`, `dxc_recorrencia`, `dxc_valorpago`). É elegível o associado com
`alf_status_associativo` igual a 2 ou 3 no `contact`. O `mcp_hub` já possui a ferramenta
`totalpass.adesao_consultar`, hoje **chaveada por CPF**, que a área não possui (ADR-0014).

A spec "Minha APM" mostra o TotalPass como um *card* de benefício com estado (não aderido /
aderido com plano e data) e um botão de ação. Reproduzir o fluxo de adesão dentro da área
duplicaria regras de pagamento que pertencem ao `totalpass`.

## Decisão

1. O TotalPass é um benefício com `tipo_ativacao = 'totalpass'` no catálogo da área
   (`beneficio.tipo_ativacao`), distinto dos benefícios ativáveis localmente.
2. O **estado** é lido pelo hub via `totalpass.adesao_consultar(contact_id)` — após P-04, o
   hub resolve `contact_id → CPF` internamente. Resposta: `elegivel`, `aderido`, `plano`,
   `aderido_em`, `recorrencia`. A área **não** lê `apm_totalpass` nem `dxc_adesao_totalpass`.
3. **Cache de 10 min por `contact_id`** em `associado_perfil.totalpass_cache JSON` +
   `totalpass_cache_em`; hub indisponível → usa o cache se existir, senão o *card* mostra
   "status indisponível" sem CTA de adesão.
4. O CTA abre **`https://totalpass.apm.org.br`** em nova aba com
   `rel="noopener noreferrer"`; a área **não** passa identidade na URL (o `totalpass` faz seu
   próprio login pelo IdP). O clique registra `totalpass.abrir` em `evento_uso` (ADR-0012).
5. **Nenhuma escrita de adesão pela área**: não existe rota que crie, altere ou cancele adesão.
6. Visibilidade governada pela flag `totalpass` (ADR-0007); desligada, o *card* some e a
   rota `GET /api/v1/beneficios/totalpass` responde 404 `recurso_desligado`.
7. Associado não elegível vê o *card* com explicação curta e sem CTA de adesão (texto de P-10).

## Consequências

### Positivas
- Regras de pagamento e adesão continuam em um único lugar (`totalpass`).
- Nenhuma credencial nem esquema do `apm_totalpass` entra na área.
- Degradação graciosa com cache; o hub protege o CRM de consultas repetidas.

### Negativas / riscos
- O estado pode ficar até 10 min defasado após uma adesão feita no `totalpass`; mitigado pelo
  *card* exibir "atualizado há X min" e por invalidação ao voltar à aba (`visibilitychange` →
  refetch com `?forcar=1`, limitado a 1 por minuto por associado).
- Depende de P-04 no hub; até lá a funcionalidade roda com `HUB_MODE=stub` ou flag desligada.
- O deep link não leva ao passo exato do fluxo (depende do `totalpass` aceitar
  `?origem=minha-apm` no futuro).

### Obrigações decorrentes
- P-04 (hub por `contact_id`) e P-02 (hub provisionado) antes de ligar a flag `totalpass`.
- Hub: `totalpass.adesao_consultar` precisa aceitar `contact_id` e devolver `elegivel`
  calculado a partir de `alf_status_associativo`.
- Testes: cache válido/expirado, hub fora com e sem cache, não elegível sem CTA, flag
  desligada → 404, `rel` do link no e2e, evento `totalpass.abrir` gravado.
- P-10: textos de elegibilidade e de "não elegível".

## Alternativas descartadas

- **API interna no `totalpass` com token de serviço.** Possível em fase futura, sob demanda,
  quando houver necessidade de ação (cancelar, trocar plano) dentro da área; hoje só leitura
  não justifica abrir superfície nova no PHP.
- **Ler `apm_totalpass` diretamente.** Exigiria usuário exclusivo com grant em outro schema,
  violando a fronteira de schema por serviço e acoplando a área ao modelo interno do `totalpass`.
