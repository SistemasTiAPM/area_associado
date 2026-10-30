"""Serviço de jobs `area-associado-jobs` (ADR-0019; runbook em docs/JOBS.md).

Mesmo código e mesma imagem do web, outro processo: `python -m app.jobs`.

- `agenda`       — "próxima execução" por job (intervalo com jitter ou horário diário local);
- `base`         — execução de UM job: prontidão, trava `GET_LOCK('area_job_<nome>', 0)`,
                   linha em `job_execucao` aberta e fechada, contagens, falhas seguidas →
                   `evento_log`, heartbeat;
- `politica`     — recuo da outbox (1, 2, 4, … 60 min; 10 tentativas), classificação de
                   erro do hub e do SMTP, resumo de erro sem segredo;
- `registro`     — a tabela de jobs (nome, agenda, prontidão, função);
- `rastro`       — leitura de `job_execucao` para `/db-health` e `scripts/alertas.sh`;
- `solicitacoes`, `comunicacao`, `carteirinha` — os jobs.

Dry-run por padrão (`JOBS_APLICAR=0`): job com efeito EXTERNO (escrita no CRM,
e-mail) só registra o que faria; job de efeito local roda sempre.
"""
