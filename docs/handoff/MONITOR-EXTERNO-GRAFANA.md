# Handoff: monitor externo dos sites da APM no Grafana (P-61 / TI-75)

Para: a sessão do Claude Code que roda no servidor do Grafana.
De: a sessão do projeto `area_associado` (Minha APM), em 2026-11-03.
Quem aprova: William (operador). Ele é o único humano envolvido e responde às perguntas abaixo.

## 1. Objetivo

Criar, no Grafana deste servidor, uma checagem externa de disponibilidade dos 7 sites que rodam na
EC2 `52.67.3.198` (AWS sa-east-1, atrás do Cloudflare), com alerta quando algum cair.

Hoje não existe nenhum monitor externo. O último era o health check do ALB, removido em 14/09/2026.
Se a EC2, o `nginx_porteiro` (proxy de borda dos 7 sites) ou o Cloudflare pararem, ninguém é avisado.
Este monitor resolve isso. Ele complementa o script interno `~/verificar-pos-reboot.sh` da EC2, que só
roda quando alguém executa.

**Pronto quando:** as 9 checagens da §3 estão ativas, as 4 regras da §4 existem, um alerta de teste
chegou ao contato do William e o bloco da §7 foi devolvido preenchido.

## 2. Primeiro, descubra o que este servidor tem (somente leitura)

Antes de instalar qualquer coisa, responda:

1. Versão do Grafana. É Grafana Cloud ou self-hosted? Como roda: Docker, systemd ou pacote?
2. Que fontes de dados existem: Prometheus, Loki, Mimir, Infinity?
3. Já existe `blackbox_exporter`? Existe o plugin **Synthetic Monitoring**?
4. O Grafana Alerting (unificado) está ativo? Que contact points existem?
5. **Onde fica o servidor?** Precisa ser fora da EC2 `52.67.3.198`. Se for outra máquina da mesma
   conta AWS em sa-east-1, funciona, mas avise na §7: uma queda da região derruba os dois juntos.
6. Qual é o IP público de saída do servidor (`curl -s https://api.ipify.org`)?

Com isso, escolha **um** caminho, nesta ordem de preferência:

- **A. Grafana Cloud com Synthetic Monitoring:** crie checagens HTTP com as sondas públicas de São
  Paulo e de mais uma região. Não instala nada.
- **B. Self-hosted com Prometheus:** use o `blackbox_exporter` (rodando ou instalado em container) e
  um job de scrape `probe` com os alvos da §3, mais regras no Grafana Alerting.
- **C. Self-hosted sem Prometheus:** suba Prometheus e `blackbox_exporter` em Docker Compose, com
  usuário não-root, sem porta pública, só ouvindo em localhost ou na rede interna. Ligue o Prometheus
  como fonte de dados do Grafana.

Instalar componente (caminho C ou `blackbox_exporter` no B) é mudança de sistema: descreva o plano ao
William e espere o "ok" dele antes.

## 3. O que checar

Intervalo de **60 s**, timeout de **10 s**, IPv4. User-Agent fixo e identificável:
`APM-Uptime/1.0 (+monitor interno APM)`. Todas são `GET` sem autenticação, sem cookie e sem corpo.

| # | URL | Esperado | Observação |
|---|---|---|---|
| 1 | `https://minha.apm.org.br/health` | 200, corpo contém `"status":"ok"` | Área do associado |
| 2 | `https://mcp.apm.org.br/health` | 200, corpo contém `"status":"ok"` | Hub de integração. A raiz `/` dá 403 por desenho: não use a raiz |
| 3 | `https://login.apm.org.br/health` | 200, corpo contém `"status":"ok"` | Login APM (IdP) |
| 4 | `https://app.apm.org.br/` | 200 seguindo redirect | Responde 302 para `/login.php`. Seguir redirect e esperar 200 |
| 5 | `https://totalpass.apm.org.br/` | 200 | |
| 6 | `https://parceiros.apm.org.br/` | 200 | |
| 7 | `https://formulario.apm.org.br/` | 200 | |
| 8 | `https://minha.apm.org.br/db-health` | **403**, sem seguir redirect | Checagem de **segurança**: é sonda interna bloqueada na borda. Se vier 200, o bloqueio do vhost caiu |
| 9 | `https://minha.apm.org.br/health` | validade do certificado TLS | O que se vê de fora é o certificado de borda do Cloudflare (renovação automática). Alerta é só uma rede de segurança |

Medido em 2026-11-03 a partir da EC2: todos os alvos respondem em menos de 0,3 s. Os User-Agents
`Blackbox Exporter/0.25.0` e `Grafana Synthetic Monitoring` não são barrados pelo Cloudflare. Se de
**outro IP** alguma checagem receber 403 com o header `cf-mitigated`, o Cloudflare está desafiando a
sonda. **Não mexa no Cloudflare**: anote o IP e a URL na §7, e o William cria a regra de exceção.

No caminho B/C, os módulos do `blackbox.yml` ficam assim:

```yaml
modules:
  apm_http_ok:
    prober: http
    timeout: 10s
    http:
      method: GET
      preferred_ip_protocol: ip4
      follow_redirects: true
      valid_status_codes: [200]
      fail_if_not_ssl: true
      headers:
        User-Agent: "APM-Uptime/1.0 (+monitor interno APM)"
  apm_health_json:
    prober: http
    timeout: 10s
    http:
      method: GET
      preferred_ip_protocol: ip4
      follow_redirects: false
      valid_status_codes: [200]
      fail_if_not_ssl: true
      fail_if_body_not_matches_regexp: ['"status"\s*:\s*"ok"']
      headers:
        User-Agent: "APM-Uptime/1.0 (+monitor interno APM)"
  apm_bloqueado_403:
    prober: http
    timeout: 10s
    http:
      method: GET
      preferred_ip_protocol: ip4
      follow_redirects: false
      valid_status_codes: [403]
      headers:
        User-Agent: "APM-Uptime/1.0 (+monitor interno APM)"
```

Os alvos 1 a 3 usam `apm_health_json`, os de 4 a 7 usam `apm_http_ok` e o alvo 8 usa `apm_bloqueado_403`.
O certificado (alvo 9) sai da métrica `probe_ssl_earliest_cert_expiry` do alvo 1. Use o relabel padrão
do blackbox (`__param_target`, `instance`, `__address__` apontando para o exporter) e um label
`site` com o nome curto (`minha`, `mcp`, `login`, `app`, `totalpass`, `parceiros`, `formulario`).

## 4. Regras de alerta

Mensagens em português, com o nome do site e a URL. Ponha no corpo de todas:
"Na EC2: `bash ~/verificar-pos-reboot.sh` mostra o que caiu."

| Regra | Condição | Pendente por | Severidade |
|---|---|---|---|
| Site fora do ar | `probe_success == 0` nos alvos 1 a 7 | 3 min | crítica |
| Sonda interna exposta | `probe_success == 0` no alvo 8 (veio algo diferente de 403) | 3 min | crítica, de segurança |
| Site lento | `probe_duration_seconds > 5` | 10 min | aviso |
| Certificado de borda perto de vencer | `probe_ssl_earliest_cert_expiry - time() < 14 * 86400` | 1 h | aviso |

Agrupe por `site`, para que uma queda geral da EC2 vire uma notificação com os 7 nomes e não 7
e-mails. Repita a cada 4 h enquanto o alerta estiver ativo, e envie também a resolução.
No caminho A, use os alertas por checagem do Synthetic Monitoring com os mesmos limites.

**Contato:** pergunte ao William o e-mail (e se quer outro canal, como Telegram ou Slack). Não
invente endereço. Depois de criar, dispare um alerta de teste e confirme com ele que chegou.

## 5. Limites

- Não monitore rotas autenticadas nem nada sob `/api/`. Não faça varredura nem teste de carga.
  Uma requisição por alvo por minuto, por sonda, é o teto.
- Não guarde segredo nenhum: as checagens são públicas e anônimas.
- Não altere o Cloudflare, o DNS nem a EC2. Este trabalho é só no servidor do Grafana.
- Se o Grafana for exposto à internet, a página do painel não pode ficar sem login.

## 6. Contexto que pode ajudar

- Checar pelo IP `52.67.3.198` dá timeout (testado da própria EC2; a hipótese é que o security group
  só libere o Cloudflare na 443). Sempre use os nomes.
- Desde 03/11 o porteiro fecha a conexão (código 444) para qualquer host que não seja um dos 7 nomes.
- A origem ainda usa um certificado temporário vencido (pendência P-01), e o Cloudflare está em modo
  *Full*. Quando a P-01 for feita, a zona passa para *Full (strict)*. Se nesse dia os sites derem erro
  526, este monitor é quem vai avisar.
- Existe um Datadog pago sem uso definido. Depois que este monitor estiver de pé, o William decide se
  cancela. Não precisa fazer nada sobre isso.

## 7. Devolva este bloco preenchido

O William cola a resposta na sessão do `area_associado`, que registra em `docs/CONCLUIDO.md` e fecha a P-61.

```
MONITOR EXTERNO — resposta da sessão do Grafana
data:                       ?
caminho escolhido:          A | B | C
grafana (versão, onde):     ?
servidor (provedor/região): ?
IP público de saída:        ?
checagens ativas (1–9):     ? (nome de cada uma no Grafana)
regras de alerta:           ? (nome, condição, pendente por)
contact point:              ? (tipo e destino, sem segredo)
alerta de teste:            enviado em ?, William confirmou: sim | não
cf-mitigated / 403:         nenhum | lista de URL + IP
pendências/observações:     ?
```
