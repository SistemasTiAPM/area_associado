# Índice de identificadores da spec v2 (30/09/2026)

Mapa de cada identificador usado em [`ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md`](ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md)
para a seção da spec, o que já temos (REQUISITOS/ADR/código) e o item do
[`../LEVANTAMENTO-TECNICO-spec-v2.md`](../LEVANTAMENTO-TECNICO-spec-v2.md). Atualizado em 2026-10-29.
"Nosso" = `docs/REQUISITOS-minha-apm.md` (RF-xx), `docs/adr/`, código em `app/` e `frontend/`.

## Fases

| ID | Significado | Nosso roteiro (`docs/PENDENCIAS.md`) |
|---|---|---|
| F0 | gate de fundação (§15.1): base conciliada, fonte de autenticação/situação, catálogo com carências, contratos de dados, destino dos eventos/LGPD | ≈ Fase 0 (docs) + o que a fase 1–2b já provou (autenticação e situação via IdP/hub) |
| F1 | escopo protegido (§15.2): P01, P02, P03/P04, P05, P06 v1, P09, P13/P14, B01–B06, B12, B13; P07/P08 condicionais | ≈ fases 1, 2a, 2b (feitas), 3 e 4 (a fazer) + backoffice (sem fase) |
| F2 | comportamento, tipos 4–6, P10, P11, P15, clube integrado, wallet, trilha completa | ≈ fases 5, 6, 7, 8 |
| F3 | P16 comunidade, P17 patrocínio/cartão, congresso integrado | ≈ fase 6 (comunidade) e 8 (patrocínio) |

## Páginas do associado (§5.2, §6)

| ID | Página | Spec | Nosso | Levantamento |
|---|---|---|---|---|
| P01 | Acesso | §6 P01, ACE-01..05 | RF-AU-01..10; IdP `login_associado` (CPF+senha, 1º acesso por código, recuperação, lockout) | §3.1 |
| P02 | Início | §6 P02, §7 | RF-HO-01..11; `frontend/src/pages/Inicio.tsx` (só saudação e atalhos) | §3.2 |
| P03 | Benefícios | §6 P03, CAT-02/03 | RF-BE-01..06; rota `beneficios` em construção | §3.3 |
| P04 | Página do benefício e ativação | §6 P04, tipos 1–6, CAT-05, SOL-01 | sem rota de detalhe; RF-BE-07..10 (ativar/gerenciar) | §3.4 |
| P05 | Minhas solicitações | §6 P05, §8.5, SOL-04 | RF-SO-01..07, ADR-0003 (6 status), rota em construção | §3.5 |
| P06 | Meu valor | §6 P06, §8.6, VAL-01/03 | RF-FA-01..05 "Fatura de valor", flag `fatura_valor` (forçada desligada), ADR-0007 | §3.6 |
| P07 | Carteirinha digital e validação pública | §6 P07, CAR-01..03, WAL-01 | RF-CA-01..06; `app/api/v1/carteirinha.py`, `app/publico.py`, `Carteirinha.tsx` | §3.7 |
| P08 | Financeiro | §6 P08, INT-02, FIN-01/03/04 | só RF-FA-05 (valor pago via ERP), flag `erp_financeiro`, ADR-0010, P-08 | §3.8 |
| P09 | Clube de vantagens | §6 P09, CLU-01..03 | RF-CL-01..05, ADR-0009 (link), flag `clube_economia` | §3.9 |
| P10 | Eventos e congresso | §6 P10, EVE-01/02, CON-01 | RF-EV-01..05, ADR-0006 (WordPress) | §3.10 |
| P11 | Notícias e ciência | §6 P11, NEWS-01 | RF-NE-01..07, ADR-0006, P-07, P-21 | §3.11 |
| P12 | Trilha de ativação (90 dias) | §6 P12, HOM-01, TRI-01 | RF-ON-01..11 (só Acadêmico), rota `onboarding` | §3.12 |
| P13 | Perfil, preferências e privacidade | §6 P13, PER-02/03 | RF-PE-01..09, `Perfil.tsx`, `app/api/v1/perfil.py`, ADR-0015 | §3.13 |
| P14 | Ajuda e atendimento | §6 P14, AJU-01/02 | só FAB WhatsApp (RF-SH-08) | §3.14 |
| P15 | Notificações | §6 P15, NOT-02 | nada ("sem sino", ADR-0017) | §3.15 |
| P16 | Comunidade | §6 P16, DIR-01, COM-01, MEN-01, ENC-01 | RF-CO-01..07, flag `comunidade_posts` | §3.16 |
| P17 | Mensalidade patrocinada e cartão | §6 P17, MZ-01, CARD-01 | RF-HO-02, RF-ON-07/09; flags `mensalidade_zero`, `patrocinio`; P-12 | §3.17 |

## Backoffice (§9)

| ID | Módulo | Fase | Nosso | Levantamento |
|---|---|---|---|---|
| B01 | Painel do dia | F1 | nada | §4 |
| B02 | Associados, visão 360 | F1 | nada (hub tem `associado.visao_360` por CPF) | §4 |
| B03 | Benefícios | F1 | seed previsto em `sql/009` + `app/dominio/catalogo.py` (REQUISITOS §6) | §4 |
| B04 | Parceiros e contratos | F1 | `apm-parceiros` (outro sistema, cadastro de parceiros) | §4 |
| B05 | Solicitações e leads | F1 | atendimento previsto na `task` do CRM (ADR-0003) | §4 |
| B06 | Importações | F1 | nada | §4 |
| B07 | Home e conteúdo | F1→F2 | nada | §4 |
| B08 | Segmentos | F1→F2 | nada | §4 |
| B09 | Comunicação | log F1, completo F2 | nada | §4 |
| B10 | Clube | F2 | nada | §4 |
| B11 | Eventos | F2 | nada | §4 |
| B12 | Painéis e relatórios | v1 F1 | nada (`evento_uso` existe como fonte) | §4 |
| B13 | Configurações e LGPD | F1 | `feature_flag` (operador por SQL) | §4 |
| Perfis | 8 perfis + 2FA (§9.1) | F1 | nada | §4 |

## Tipos de ativação (§6 P04) e status de solicitação (§8.5)

| ID | Nome | Fase | Nosso |
|---|---|---|---|
| Tipo 1 | Acesso direto | F1 | RF-BE-09 `url_acesso`, RF-BE-10 TotalPass (ADR-0008) |
| Tipo 2 | Encaminhamento ao parceiro | F1 | fora de escopo (ADR-0009) |
| Tipo 3 | Serviço da APM | F1 | tipos fechados de `solicitacao` (ADR-0003) |
| Tipo 4 | Reserva | F2 | nada |
| Tipo 5 | Inscrição | F2 | RF-EV-02/05 (interesse local) |
| Tipo 6 | Resgate no clube | F2 | `clube_oferta_usar` (só clique) |
| `criada` | Recebida pela APM | — | `aberta` |
| `enviada` | Enviada ao parceiro | — | não existe (≈ `crm_sync=ok`, técnico) |
| `em_atendimento` | Em atendimento | — | `em_analise` |
| `pendente_associado` | O parceiro precisa de algo seu | — | `aguardando_associado` |
| `concluida_positiva` | Concluída | — | `concluida` |
| `concluida_negativa` | Não seguiu | — | `recusada` |
| `cancelada` | Cancelada | — | `cancelada` (só associado) |
| `sem_retorno` | Aguardando o parceiro (marcador) | — | não existe |

## Blocos da home (§7.2), estados de elegibilidade (§8.1) e carências (§8.2)

Blocos 1 Pendência · 2 Meu valor · 3 Próximo passo · 4 Recomendados · 5 Categorias · 6 Defesa e representação · 7 Agenda · 8 Notícias (F2) · 9 Clube (F2); ADM-05 destaque editorial. Nosso: blocos fixos da SPEC antiga (RF-HO-01..11), sem motor.
Estados: Disponível · Ativo · Libera em N dias · Não disponível para a categoria · Suspenso · Indisponível na região. Nosso: nada.
Carências: 6 m veículos · 3 m locação, aposentadoria, defesa, congressos/cursos longos · 2 m despachante, contabilidade, vigilância, anúncios, DIT · 1 m AMB prova de título, idiomas, Hotel Fazenda · Clube pendente. Nosso: nada.

## Eventos de uso (§11.2) × `app/uso.py`

| Spec | Nosso (`app/uso.py`) | Observação |
|---|---|---|
| acesso_primeiro | — | `associado.primeiro_acesso_em` existe, sem evento |
| login | `evento_log` login_ok/login_falha | fora de `evento_uso` por desenho |
| home_vista | pagina_ver(rota=home) | sem "blocos exibidos" |
| home_bloco_clicado | — | ≈ categoria_abrir |
| busca | busca_global | termo não gravado (RNF-16) |
| beneficio_visto | beneficio_abrir | sem origem/estado |
| recomendacao_dispensada | — | |
| solicitacao_criada | solicitacao_criar | |
| solicitacao_status | solicitacao_status_alterado | |
| uso_registrado | — | |
| carencia_vencida | — | |
| carteirinha_aberta | pagina_ver(rota=carteirinha) | |
| carteirinha_validada | carteirinha_verificar | |
| financeiro_segunda_via | — | |
| pagamento_confirmado | — | |
| meu_valor_visto | pagina_ver(rota=fatura) | |
| clube_acesso | clube_oferta_usar | |
| clube_resgate | — | |
| evento_inscricao | evento_inscrever, congresso_garantir_vaga | |
| evento_presenca | — | |
| conteudo_lido | noticia_abrir | sem tempo de leitura |
| tema_seguido | tema_seguir, tema_deixar | |
| trilha_passo | onboarding_passo_concluir | |
| perfil_atualizado | perfil_contato_atualizar, perfil_foto_atualizar | |
| consentimento | — | |
| notificacao | — | |
| ajuda_contato | central_whatsapp_abrir | |
| cancelamento_pedido | — | solicitacao_cancelar é outra coisa |

## Gatilhos (§12.2)

A01 filiação confirmada · A02 1º acesso não feito · A03 carência vencida · A04 solicitação criada · A05 sem retorno no prazo · A06 concluída · A07 visto 2× sem ativar · A08 resumo mensal · A09 mensalidade vencida · A10 renovação · A11 sem acesso/uso 90 d · A12 score em risco · A13 mudança de categoria · A14 evento publicado · A15 novo benefício · A16 cancelamento · A17 interesse de não associado · A18 aniversário/Dia do Médico · A19 documentação pendente · A20 trilha parada. F1: A01–A06, A09, A16, A17, A18. Nosso: nenhum; RD Station integrado só em `app_facial_recognition` e `totalpass`.

## Indicadores (§11.3), painéis (§11.5), integrações (§13.1)

Indicadores 1–14 (ver spec); painéis Diretoria, Benefícios e parceiros, Operação, Produto, Regionais. Integrações: cadastro, cobrança, login atual, API de consulta de associação, RD Station, parceiros com API, parceiros sem API (CSV §13.3), Qualicorp, clube, eventos/IESAPM, WordPress/MBE/biblioteca, WhatsApp/SMS, analytics. Nosso: IdP e hub (cadastro, login), WordPress planejado (ADR-0006), resto ausente.

## Códigos de item citados sem definição própria

| Código | Onde | Lê-se como |
|---|---|---|
| ACE-01, ACE-02, ACE-03, ACE-04, ACE-05 | P01 | acesso; ACE-05 = limite de tentativas por CPF e rede |
| HOM-01 | P02, P12 | regras da home F1 e bloco simples de 3 passos |
| CAT-02, CAT-03, CAT-05 | P03, P04 | catálogo, filtros, página do benefício |
| SOL-01, SOL-04 | P04, P05 | criação de solicitação; acompanhamento |
| VAL-01, VAL-03 | P06 | valor v1; PDF anual/parceiros com API |
| CAR-01, CAR-02, CAR-03 | P07 | carteirinha, QR, validação pública |
| INT-01, INT-02 | §13.1, P08 | camada de integração do cadastro; cobrança |
| FIN-01, FIN-03, FIN-04 | P08 | financeiro F1; recorrente em cartão F2 |
| CLU-01, CLU-02, CLU-03 | P09, P02 | clube integrado F2 (CLU-02 = retorno de economia ao Meu valor, CLU-03 = bloco da home) |
| EVE-01, EVE-02, CON-01 | P10 | eventos F2; congresso nativo F3 |
| NEWS-01 | P11, P02 | notícias F2 |
| TRI-01 | P12 | trilha completa F2 |
| PER-02, PER-03 | P13 | perfil F1 |
| AJU-01, AJU-02 | P14 | ajuda e cancelamento F1 |
| NOT-02 | P15 | notificações F2 |
| REC-01 | P02, §7.5 | recomendação v2 com A/B |
| WAL-01 | P07 | carteira do celular F2 |
| PAR-01 | §9.1 | portal do parceiro F2 |
| ADM-05 | §7.2 | destaque editorial |
| DIR-01, COM-01, MEN-01, ENC-01 | P16 | diretório, grupo moderado, mentoria, encaminhamento F3 |
| MZ-01, CARD-01 | P17 | mensalidade patrocinada, cartão F3 |
| F0-01, F0-02, F0-03, F0-06 | §13.1 | mapear eventos/IESAPM; contrato de dados; decisão do login; destino dos eventos |
