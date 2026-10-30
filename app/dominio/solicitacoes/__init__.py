"""Solicitações do associado (P05; ADR-0003 + ADR-0018; REQUISITOS §3.12 e §7).

- `maquina`    — tabela de transições (única fonte) e `transitar` transacional;
- `schemas`    — allowlist de campos por `tipo_servico`, validação e normalização;
- `rotulos`    — rótulos pt-BR (status, tipos, atores, finalidades, motivos);
- `parametros` — leitura de `parametro` (sql/013) com valores-padrão seguros;
- `servico`    — criar, listar, detalhar, cancelar, responder, avaliar.

Nenhuma função daqui fala HTTP: a rota (`app/api/v1/solicitacoes.py`) traduz
as exceções de domínio no contrato único de erro.
"""
