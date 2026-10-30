# 🎨 Vitrine · Prontidão do front-end para a spec v2 (30/09/2026) — levantado em 2026-10-29

Fontes: `docs/spec-v2/ESPECIFICACAO-FUNCIONAL-v2-2026-09-30.md` (citada como **spec Lnnn**), `docs/spec-v2/INDICE-IDS.md`,
inventários de 29/10 (`inventario-codigo.md`, `inventario-requisitos.md`, `inventario-vizinhos.md`), código em
`frontend/`, ADR-0001/0013/0017, `docs/PENDENCIAS.md`. Só leitura; nada foi editado.

Legenda de estado: ✅ cobre · 🟡 parcial · ⬜ não iniciado · ⛔ bloqueado por terceiro/fonte · ⚠️ divergência a decidir ·
🔒 decisão fechada (não reabrir).

**Base factual de partida** (inventario-codigo.md:34): 11 rotas em `frontend/src/rotas.ts:26-46`; páginas reais só
`perfil` e `card` (`frontend/src/App.tsx:14-17`); as outras 9 rendem `EmConstrucao` (`App.tsx:24`); bottom-nav
`home, ben, clube, news, card` (`rotas.ts:48`); PWA inexistente (sem `public/`, manifest ou service worker);
`frontend/dist/` local está **obsoleto** (fontes Figtree, anteriores à ADR-0017) e `frontend/LICENSES.md:5` ainda
cita Figtree, embora `package.json` dependa de `@fontsource/sora`. O build de verdade acontece no estágio Node do
`Dockerfile:7-24` (`npm run check && npm run build`).

**Mockups conhecidos** (ADR-0017 L10-12 fala em "12 mockups" mas lista 13 nomes): login, painel, beneficios, clube,
servicos, ciencia, defesa, eventos, relacionamento, financeiro, carteirinha, onboarding, perfil. Nenhum está no
repositório (`docs/mockups/` não existe; P-39). **Telas da spec sem mockup conhecido: P04, P05, P08 (só a "Fatura de
valor" do rascunho, que a spec dividiu em P06+P08), P14, P15, P17 e os estados de elegibilidade/"Mais" da
navegação.** `servicos` e `defesa` não têm tela própria na spec v2 (viram categorias de P03 e o bloco 6 da home).

---

## Telas

### P01 · Acesso
- **Spec pede** (spec L282-310): CPF com máscara, senha, "continuar conectado", primeiro acesso CPF + nascimento +
  código mascarado, "esqueci a senha", "meus dados mudaram", frase de apoio + WhatsApp, "Conheça a APM"; ex-associado
  vê página de retorno; eventos `login`, `acesso_primeiro`.
- **Existe hoje**: a tela é do IdP `login_associado` (inventario-vizinhos.md:16-21: CPF+senha, OTP só por e-mail,
  sem data de nascimento, sem "continuar conectado", sem "meus dados mudaram"). Na área: `GET /` → 303 ao Login APM;
  `stub_login` e `erro` Jinja no visual antigo (P-24). Página de entrada (`entrada.html`) guardada sem rota.
- **Mockup conhecido?** Sim (`login`), aplicado só em `entrada.css`/`/verificar` (ADR-0017).
- **Falta (front da área)**: P-24 (stub/erro em Sora); "página de retorno" do ex-associado não existe em lugar nenhum
  (o IdP manda inativo à Central) — fora da SPA, decisão com `login_associado` (DEC-V12). Evento `acesso_primeiro`
  é servidor (`associado.primeiro_acesso_em` existe sem evento, INDICE L87).
- **Estado**: 🟡 (IdP cobre o núcleo; o resto é outro repositório). **Fase spec** F1 · ACE-01..05 / roteiro: IdP (fora).

### P02 · Início
- **Spec pede** (spec L313-327, L617-634): saudação com tratamento e categoria, atalho da carteirinha, busca, blocos
  1–9 (pendência, meu valor, próximo passo, recomendados 3–6 cards com "por que estou vendo isto" e dispensar,
  categorias, defesa e representação, agenda, notícias F2, clube F2), um botão principal por bloco, bloco vazio não
  aparece, no máximo 1 patrocinado nos 4 primeiros, "como funciona" em 4 passos no 1º acesso, pendência financeira
  no topo; eventos `home_vista`, `home_bloco_clicado`, `recomendacao_dispensada`.
- **Existe hoje**: `frontend/src/pages/Inicio.tsx` — hero "Olá, {nome}" com selo tipo·situação (L28-38), 2 botões
  (L42-49), 2 atalhos (L7-20) e `EstadoVazio` "Mais da Minha APM a caminho" (L70-73). Sem bloco de dado. Evento:
  só `pagina_ver` (`shell/AppShell.tsx:36`).
- **Mockup conhecido?** Sim (`painel`), mas com valores ilustrativos (R$ 1.842, "4 de 40") que a regra 19 proíbe.
- **Falta**: contêiner `BlocoHome` (título, 1 CTA, link secundário, "por que estou vendo isto", dispensar);
  `CardPendencia`, `CardMeuValor` (variante "o que a sua associação cobre"), `CardProximoPasso` (passo da trilha ou
  pergunta de perfil), grade `Recomendados` (selo patrocinado com texto), atalhos de categorias (8), `CardDefesa`,
  `Agenda` (até 3), "como funciona" (4 passos, só 1º acesso); tratamento Dr./Dra. (DEC-V05); estados: vazio por
  bloco = bloco some; carregando por bloco (skeleton); erro por bloco sem derrubar a home; eventos `home_bloco_clicado`
  (bloco, posição, item) e `recomendacao_dispensada` fora do catálogo (`app/uso.py`; `lib/analytics.ts:12-28`).
  **Pré-requisito**: API de blocos/motor de pontuação (Maestro, §7.3) e catálogo (Fase 4). "a caminho" fere §3.2
  (DIV-V03).
- **Estado**: 🟡 casca. **Fase spec** F1 HOM-01 (regras) / roteiro: Fase 4 (home).

### P03 · Benefícios
- **Spec pede** (spec L330-355): resumo (ativos, disponíveis, valor no ano), filtros Todos/Disponíveis para
  mim/Ativos/Novos, 8 categorias, busca, card com nome + condição em uma linha + selo + botão; ordem disponíveis →
  ativos → "libera em"; "exclusivo para associado efetivo" com caminho; busca sem resultado sugere categorias e
  registra o termo; eventos `busca`, `beneficio_visto`.
- **Existe hoje**: rota `beneficios` → `EmConstrucao` (`App.tsx:24`); `CampoBusca` manda `?q=` para `/beneficios`
  sem filtrar (`shell/CampoBusca.tsx:12,36`); classes `.tag--ok/--info/--novo` (`styles/base.css:214-239`).
- **Mockup conhecido?** Sim (`beneficios`; `servicos` e `defesa` como vistas de categoria).
- **Falta**: página inteira; `BarraResumo` (só com fonte; "valor no ano" depende de P06 → ⛔ até lá, bloco some);
  `FiltroChips` (role `group`/`tablist`, `aria-pressed`); `GradeCategorias`; `CardBeneficio` com os 6 estados §8.1
  (DEC-V09 para rótulos); estado vazio da busca com sugestão de categorias; carregando (skeleton de cards); erro 503
  `fonte_indisponivel` com "tentar novamente"; eventos `busca_global` (gravar termo → DIV-V09), `filtro_aplicar`,
  `categoria_abrir`, `beneficio_abrir` (hoje sem emissor, inventario-codigo.md:25); a11y: lista como `ul`, selo em
  texto, foco no 1º resultado após filtrar? (não — manter foco, anunciar contagem em `aria-live`).
- **Estado**: ⬜. **Fase spec** F1 CAT-02/03 / roteiro: Fase 4 (P-04, P-10, P-22; `sql/009`).

### P04 · Página do benefício e ativação
- **Spec pede** (spec L358-394): rota de detalhe com nome/parceiro/frase, condição × referência (economia), "como
  funciona" ≤4 passos, situação do associado ("disponível desde"/"libera em"), botão por tipo de ativação (1–3 F1;
  4–6 F2), FAQ, contato, regras, "quanto já aproveitou no ano", relacionados; confirmação mostra prazo e próximo
  passo; eventos `beneficio_visto` (origem, estado), `solicitacao_criada`.
- **Existe hoje**: nada; nem rota (`rotas.ts` não tem `beneficios/:slug`; `App.tsx:34-36` gera rota por `caminho`
  plano). `rotaDoCaminho` (`rotas.ts:63-66`) só casa caminho exato → o `AppShell` daria "Página não encontrada" no
  `h1` para qualquer sub-rota.
- **Mockup conhecido?** **Não.**
- **Falta**: suporte a sub-rotas no shell (título do `h1` vindo da página, não só de `rotas.ts`); página
  `/area/beneficios/{slug}`; `SeloEstado` (6 estados, texto + ícone); `BotaoAtivacao` por tipo (1 abre externo via
  `LinkExterno` com allowlist — `lib/links.ts:7-15` precisa crescer por benefício, o que exige host vindo da API +
  allowlist no servidor; 2/3 abrem `Dialogo` de confirmação com prazo e próximo passo); `Accordion` (FAQ/regras);
  "aproveitado no ano" só com fonte; relacionados; estados: carregando, erro, "exclusivo para efetivo", "regularize"
  (link ao Financeiro → P08 ⛔), "libera em {data}"; eventos com `origem` (home/catálogo/busca) → querystring ou state
  de navegação. **Pré-requisito**: API detalhe + `POST` de ativação/solicitação (Maestro, Fases 3–4).
- **Estado**: ⬜. **Fase spec** F1 CAT-05/SOL-01 (tipos 1–3) / roteiro: Fase 4 (+ Fase 3 para o tipo 3).

### P05 · Minhas solicitações
- **Spec pede** (spec L397-412): lista (benefício, data, status, prazo, contato), linha do tempo, cancelar antes do
  atendimento, avaliar 0–10, 7 rótulos de status; destaque ao que depende do associado; evento `solicitacao_status`.
- **Existe hoje**: rota `solicitacoes` → `EmConstrucao`; contador no menu lê `solicitacoes_aguardando` fixo 0
  (`shell/MenuLateral.tsx:37-42`; `api/tipos.ts:23`).
- **Mockup conhecido?** **Não** (nem lista nem linha do tempo).
- **Falta**: página lista + detalhe (`/area/solicitacoes/{uuid}` — mesma questão de sub-rota do P04); `LinhaDoTempo`
  (`ol` ordenada, data + rótulo + origem, atual com `aria-current="step"`); `StatusSolicitacao` (7 rótulos × 6
  estados ADR-0003 — DIV-V10); `Dialogo` de cancelar (motivo opcional); `Avaliacao` 0–10 (radiogroup, alvo 44 px);
  formulário "responder" (`aguardando_associado`); estados: vazio ("você ainda não pediu nada" + CTA ao catálogo),
  carregando, erro, sem conexão; eventos `solicitacao_criar/cancelar/responder` já existem no catálogo sem emissor.
  **Pré-requisito**: API Fase 3 (`sql/008`, Maestro/Atlas) — a UI pode começar com o contrato de `tipos.ts` acordado.
- **Estado**: ⬜. **Fase spec** F1 SOL-04 / roteiro: Fase 3 (**próxima**).

### P06 · Meu valor
- **Spec pede** (spec L415-444): período (ano corrente e anteriores), total pago, economia comprovada item a item com
  fonte, proteção incluída separada, total e relação, valor por categoria, "como calculamos" sempre visível, potencial
  rotulado, PDF; "N vezes" só se contribuição > 0 e comprovado+proteção > pago; <3 meses mostra "o que a sua
  associação cobre"; eventos `meu_valor_visto`, `uso_registrado`.
- **Existe hoje**: rota `fatura` sob flag `fatura_valor` (`rotas.ts:31`), flag forçada desligada (P-12), título
  "Fatura de valor" — nome que a spec recomenda abandonar (L421-422). `lib/formato.ts:13-17` já formata moeda.
- **Mockup conhecido?** Parcial (`financeiro` = "Fatura de valor" do rascunho, com carteirinha na mesma tela e
  números ilustrativos); sem "como calculamos", potencial ou período.
- **Falta**: renomear rota/título (DIV-V11); `SeletorPeriodo` (tabs por ano); `Extrato` (tabela responsiva: data,
  benefício, economia, fonte/modalidade); `BlocoProtecao` separado; `ComoCalculamos` (sempre visível — não é
  accordion fechado); `ValorPotencial` com rótulo textual "potencial"; `BotaoBaixar` PDF (gerado no servidor);
  variantes "o que a sua associação cobre" e "valor entregue pela associação" (contribuição 0); evento
  `meu_valor_visto` com período. **Pré-requisito**: fonte VAL-01 (valores de referência aprovados pelo Financeiro,
  solicitações concluídas, importações) → hoje inexistente.
- **Estado**: ⛔ (flag + fonte). **Fase spec** F1 VAL-01 / roteiro: Fase 8 (P-12).

### P07 · Carteirinha digital e validação pública
- **Spec pede** (spec L447-458): nome, categoria, nº de associado, "associado desde", situação, QR; baixar em
  imagem ou PDF; wallet (F2); validação pública sem dados pessoais; eventos `carteirinha_aberta`,
  `carteirinha_validada`.
- **Existe hoje**: `pages/Carteirinha.tsx` — cartão (L84-109), QR (L105-107), situação (L101-103), "na APM desde"
  (L80), Compartilhar com fallback de cópia manual (L43-59, L136-144), Wallet sob flag (L123-131), 3 cards de uso
  (L11-15); `/verificar/{token}` público (`app/publico.py`). Eventos: `pagina_ver`, `carteirinha_compartilhar`,
  `carteirinha_verificar`, `wallet_adicionar`. Nº de associado não aparece no cartão (`num_contato` vem na API,
  `api/carteirinha.ts:8`, mas não é renderizado).
- **Mockup conhecido?** Sim (`carteirinha`).
- **Falta**: **baixar imagem/PDF** (DEC-V08: servidor via Pillow/segno é o caminho seguro); mostrar `num_contato`;
  fallback "Membro" (L94) → "Associado" (voz §3.3); wallet 🔒 F2/flag; `carteirinha_aberta` ≈ `pagina_ver` (ok).
- **Estado**: ✅ núcleo / 🟡 download. **Fase spec** F1 condicionada CAR-01..03 / roteiro: Fase 2a (feita), download
  novo.

### P08 · Financeiro
- **Spec pede** (spec L461-479): situação (em dia/atraso) no topo, valor e forma, mensalidades do ano com status,
  segunda via (PDF, linha digitável, Pix), histórico, declarações (inclusive AMB, carência 1 mês), recorrente em
  cartão (F2); se a cobrança cair, aviso + Central; eventos `financeiro_segunda_via`, `pagamento_confirmado`.
- **Existe hoje**: nada na SPA (sem rota). Flag `erp_financeiro` e ação `fatura_pdf_baixar` existem no servidor.
  Hub: `financeiro.faturas_associado` por CPF, **sem boleto, linha digitável ou Pix** (inventario-vizinhos.md:25);
  P-04 (contact_id) e P-08 (parecer F&O) abertas.
- **Mockup conhecido?** **Não** (o `financeiro` do mockup é a fatura de valor).
- **Falta**: rota `financeiro`; `FaixaSituacao` (em dia/atraso, texto + ícone, nunca só cor); `ListaMensalidades`
  (competência, vencimento, valor, status); `SegundaVia` (botão PDF, `LinhaDigitavel` com copiar + `aria-live`
  "copiado", `PixCopiaCola` + QR SVG via segno — tudo do servidor); `Historico`; `Declaracoes` (lista com "libera em"
  para AMB); estado "cobrança fora do ar" (503 → aviso + Central); eventos novos. **Pré-requisito**: P-04, P-08,
  fonte de 2ª via/Pix (INT-02) — nada disso existe.
- **Estado**: ⛔. **Fase spec** F1 condicionada / roteiro: Fase 7 (`erp_financeiro`), sem 2ª via.

### P09 · Clube de vantagens
- **Spec pede** (spec L482-497): 30–40 ofertas curadas em destaque, oferta da semana, categorias de uso frequente,
  economia no ano (quando houver resgate), "ver todas as ofertas"; F1 = encaminhamento rastreado sem prometer SSO.
- **Existe hoje**: rota `clube` → `EmConstrucao`; `clubapm.com.br` na allowlist (`lib/links.ts:10-11`); ação
  `clube_oferta_usar` no catálogo sem emissor; flag `clube_economia`. Chamada da rota promete "Descontos e cashback"
  (`rotas.ts:29`) — cashback depende de P17 (spec L262) → texto a corrigir.
- **Mockup conhecido?** Sim (`clube`).
- **Falta**: página com `CardOferta` (selo "patrocinado" quando couber), `OfertaDaSemana`, categorias, CTA "Ver todas
  as ofertas" via `LinkExterno` + `clube_oferta_usar`/`clube_acesso`; "economia no ano" só com flag
  `clube_economia` (F2); estado sem curadoria = página só com o CTA (bloco vazio some). **Pré-requisito**: curadoria
  (B10, sem backoffice → seed/catálogo editorial) — EXT.
- **Estado**: ⬜ (simples). **Fase spec** F1 link / roteiro: Fase 6.

### P10 · Eventos e congresso
- **Spec pede** (spec L500-507): agenda filtrável (especialidade, região, formato), página do evento, inscrição com
  preço por perfil, minhas inscrições, certificados, aulas gravadas, congresso em destaque; carência 3 meses.
- **Existe hoje**: rota `eventos` → `EmConstrucao`; ações `evento_inscrever`, `congresso_*` sem emissor.
- **Mockup conhecido?** Sim (`eventos`), sem página do evento, inscrições ou certificados.
- **Falta**: lista com filtros (3 facetas → `FiltroChips` + `select`), `CardEvento` com data (`formato.ts:24-30`
  já tem `mesCurto`/`diaDoMes`), sub-rota `/area/eventos/{id}`, "libera em" (carência), "minhas inscrições",
  `ImagemSegura` (capas do WordPress sob `CSP_IMG_HOSTS`). **Pré-requisito**: cache do portal (Fase 5, P-07) e
  fonte de inscrição (IESAPM, F0-01).
- **Estado**: ⬜. **Fase spec** F2 / roteiro: Fase 5.

### P11 · Notícias e ciência
- **Spec pede** (spec L510-516): conteúdo por temas seguidos/especialidade, filtros (tudo, notícias, ciência, defesa,
  eventos), seguir temas, salvar, chamada para submeter trabalho; fontes WP, MBE, biblioteca.
- **Existe hoje**: rota `noticias` → `EmConstrucao`; `CampoBusca` reconhece `/noticias` (`CampoBusca.tsx:5`); ações
  `noticia_*`, `tema_*` sem emissor.
- **Mockup conhecido?** Sim (`ciencia`; `defesa` para o filtro de defesa profissional).
- **Falta**: lista + filtros, `ChipTema` (seguir/deixar, `aria-pressed`), salvar/dessalvar (botão com estado
  textual), "salvos", `ImagemSegura` com `loading="lazy"` + proporção fixa (CLS), leitura abre no portal via
  `LinkExterno` (`apm.org.br` já na allowlist). **Pré-requisito**: Fase 5 (P-07, P-21).
- **Estado**: ⬜. **Fase spec** F2 NEWS-01 / roteiro: Fase 5.

### P12 · Trilha de ativação (90 dias)
- **Spec pede** (spec L519-534): para todo novo associado e acadêmico; barra de progresso, 5–6 passos por categoria,
  o que cada passo libera, data de liberação com carência, "o que a sua associação cobre"; passo concluído por evento
  real; some ao terminar ou no dia 90; F1 = bloco simples de 3 passos na home.
- **Existe hoje**: rota `onboarding` só para `tipo === 'Acadêmico'` (`rotas.ts:37-45`) → `EmConstrucao`; ação
  `onboarding_passo_concluir` sem emissor.
- **Mockup conhecido?** Sim (`onboarding`), só acadêmico, com "mensalidade R$ 0 patrocinada" (proibido sem P17).
- **Falta**: `BarraProgresso` (valor por custom property via CSSOM, ADR-0013 §3; `role="progressbar"` com
  `aria-valuenow`); `PassoTrilha` (feito/disponível/"libera em {data}", sem botão "marcar como feito" — conclusão
  é por evento real); bloco de 3 passos na home (F1); visibilidade por "tempo de casa ≤ 90 dias" em vez de
  `somenteTipo` (DIV-V13). **Pré-requisito**: API da trilha (Fase 6) + data de filiação na sessão.
- **Estado**: ⬜. **Fase spec** F1 bloco / F2 TRI-01 / roteiro: Fase 6.

### P13 · Perfil, preferências e privacidade
- **Spec pede** (spec L537-553): dados do cadastro, como prefere ser chamado, especialidades e área de atuação,
  região e temas, canais preferidos e frequência, consentimentos por finalidade com histórico, baixar meus dados e
  pedir exclusão; "complete seu perfil" dizendo o que melhora; perfil progressivo (1 pergunta por visita no bloco 3).
- **Existe hoje**: `pages/Perfil.tsx` — foto (L36-122), cadastro só leitura (L125-148), contato editável/leitura
  (L161-323), e-mail com código e step-up (L328-458), avisos `desatualizado`/`edicao_disponivel` (L504-514).
  Campo com erro ligado por `aria-describedby` (`components/Campo.tsx`).
- **Mockup conhecido?** Sim (`perfil`), sem consentimentos/LGPD.
- **Falta**: `SecaoTratamento` ("como prefere ser chamado" → alimenta a saudação, DEC-V05); `SecaoAtuacao`
  (checkbox group); `SecaoInteresses` (região, temas); `SecaoCanais` (e-mail/WhatsApp/SMS + frequência — SMS não
  existe no IdP, inventario-vizinhos.md:17); `SecaoConsentimentos` (switch acessível `role="switch"`, texto da
  versão, histórico em lista); `BaixarMeusDados` (download gerado no servidor) e `PedirExclusao` (`Dialogo` + vira
  solicitação); `CompleteSeuPerfil` (barra + "o que melhora"); `PerguntaPerfil` (componente reutilizado no bloco 3
  da home); título "Perfil e privacidade" (DIV-V14); evento `consentimento`. **Pré-requisito**: tabelas de perfil
  declarado e consentimento (Atlas) + API (Maestro) — nada existe.
- **Estado**: 🟡 (cadastro/contato/e-mail/foto feitos; preferências e LGPD ⬜). **Fase spec** F1 PER-02/03 /
  roteiro: sem fase (proposta: Fase 3b).

### P14 · Ajuda e atendimento
- **Spec pede** (spec L556-564): FAQ editável com busca; Central por WhatsApp, telefone ou formulário, com horário;
  pedidos comuns; cancelamento acessível com motivo obrigatório em lista curta, oferta de conversa, vai à Central
  (A16); evento `ajuda_contato`, `cancelamento_pedido`.
- **Existe hoje**: só o FAB `BotaoWhatsapp` (`shell/BotaoWhatsapp.tsx`) com mensagem fixa "Olá! Vim pela Minha APM…"
  (`lib/links.ts:31`, com exclamação — fere §3.3). Sem rota, sem FAQ.
- **Mockup conhecido?** **Não.**
- **Falta**: rota `ajuda`; `BuscaFaq` (filtro local, `aria-live` com contagem) + `Accordion`; `CanaisCentral`
  (WhatsApp/telefone `tel:` — precisa de allowlist de esquema em `urlExternaSegura`, hoje só `https:`,
  `lib/links.ts:25` — e horário); "pedidos comuns" como atalhos para solicitações; `FormularioCancelamento`
  (radiogroup de motivos, "quero conversar" opcional, confirmação com prazo); eventos `ajuda_contato` (assunto,
  canal) e `cancelamento_pedido` (motivo). **Pré-requisito**: fonte da FAQ (sem backoffice → seed editorial, EXT) e
  tipo `cancelamento` nas solicitações (Fase 3).
- **Estado**: ⬜. **Fase spec** F1 AJU-01/02 / roteiro: sem fase (proposta: junto da Fase 3).

### P15 · Notificações
- **Spec pede** (spec L567-571): ícone com contagem no topo, tipos, lida/não lida, atalho a preferências.
- **Existe hoje**: nada, por decisão ("sem sino até existir fonte", `shell/Cabecalho.tsx:25`, ADR-0017 §3).
- **Mockup conhecido?** **Não** (o sino do mockup `painel` era decorativo).
- **Falta**: tudo, quando houver fonte (B09/gatilhos). **Estado**: 🔒 ⬜. **Fase spec** F2 NOT-02 / roteiro: nenhuma.

### P16 · Comunidade
- **Spec pede** (spec L574-580): diretório de especialistas e grupos moderados primeiro; mentoria depois;
  encaminhamento só com parecer jurídico. F3.
- **Existe hoje**: rota `comunidade` visível no menu → `EmConstrucao`; flag `comunidade_posts`; ações
  `comunidade_*`, `rede_entrar` sem emissor.
- **Mockup conhecido?** Provavelmente (`relacionamento`) — confirmar com a agência.
- **Falta**: tudo; e, pela spec, a rota **não deveria estar no menu** antes de F3 (DIV-V15, DEC-V02).
- **Estado**: ⬜. **Fase spec** F3 / roteiro: Fase 6.

### P17 · Mensalidade patrocinada e cartão
- **Spec pede** (spec L583-590): só com contrato; nasce desligada; o associado vê quanto o patrocínio cobre.
- **Existe hoje**: pill "Mensalidade Zero ativa" (`Cabecalho.tsx:57-62`) e bloco na sidebar com texto fixo
  "patrocínio ativo · 2026" (`MenuLateral.tsx:86-91`) sob flag `mensalidade_zero`, forçada desligada (P-12). O
  texto "· 2026" é literal — se a flag ligar, mostra ano errado em 2027.
- **Mockup conhecido?** Só a faixa no `painel`/`onboarding`.
- **Falta**: nada a fazer até contrato; ao ligar, substituir o texto fixo por dado (quanto cobre) e sinalizar
  patrocinador. **Estado**: 🔒 ⛔. **Fase spec** F3 / roteiro: Fase 8.

---

## Navegação e shell

Diff item a item entre §3.1 (spec L128-137) e `rotas.ts` / `NavInferior.tsx` / `MenuLateral.tsx` / `Cabecalho.tsx`.

| Item da spec | Hoje | Diferença / ação |
|---|---|---|
| Barra inferior: **Início, Benefícios, Carteirinha, Meu valor, Mais** | `ORDEM_INFERIOR = home, ben, clube, news, card` (`rotas.ts:48`) | Clube e Notícias saem; Carteirinha sobe para 3ª; "Meu valor" depende da flag `fatura_valor` (forçada off) → com a regra atual a barra teria 4 abas (DEC-V01); "Mais" não existe como aba — o drawer abre pelo hambúrguer do cabeçalho (`Cabecalho.tsx:38-47`). Ação: aba "Mais" como `button` que abre o `Drawer` (foco preso já existe, `useFocoPreso.ts`). |
| "Mais" abre: Financeiro, Minhas solicitações, Clube, Eventos, Notícias e ciência, Perfil e privacidade, Ajuda, Sair | Drawer = `MenuLateral` completo (`Drawer.tsx:35-43`): Início, Meus benefícios, Clube, Notícias, (Fatura), Comunidade, Congresso e eventos, Carteirinha, Minhas solicitações, (Onboarding), Meu perfil, Sair | Faltam rotas **Financeiro** e **Ajuda**; sobra **Comunidade** (F3) e **Onboarding** como página (F1 = bloco na home); ordem diferente; drawer repete os itens da barra (aceitável se "Mais" listar só o restante). |
| Menu lateral "mesmos itens, mesma ordem" | ordem de `ROTAS` (`rotas.ts:26-46`): Início, Benefícios, Clube, Notícias, Fatura, Comunidade, Eventos, Carteirinha, Perfil (rodapé), Solicitações, Onboarding | Reordenar para: Início, Benefícios, Carteirinha, Meu valor, Financeiro, Minhas solicitações, Clube, Eventos, Notícias e ciência, Perfil e privacidade, Ajuda, Sair. Perfil no rodapé com avatar é escolha do mockup (ADR-0017) — manter o lugar, trocar o nome. |
| Nomes | "Meus benefícios", "Fatura de valor", "Congresso e eventos", "Meu perfil", "Onboarding acadêmico" | Spec: "Benefícios", "Meu valor" (título "Extrato de valor"), "Eventos", "Perfil e privacidade", "Trilha de ativação". Chamadas editoriais (`chamada`) vêm do mockup; "Descontos e cashback" (`rotas.ts:29`) promete cashback (P17) → trocar. |
| Topo fixo: marca, busca, notificações (F2), perfil | `Cabecalho.tsx`: hambúrguer, data/“Minha APM”, `h1`, busca, pill MZ, chip de perfil. **Sem marca** no cabeçalho (marca só em `MenuLateral.tsx:49-58`, invisível no mobile fora do drawer); sem sino 🔒 | Marca no mobile: hoje o sobretítulo "Minha APM" (`Cabecalho.tsx:33`) faz as vezes; decidir se basta (DIV-V19). Cabeçalho não é fixo (rola com a página) — a spec diz "topo fixo"; o mockup tem degradê que se dissolve; manter mockup (ADR-0017) e registrar. |
| Busca global: benefícios, parceiros, eventos, notícias, FAQ, **com sugestões** | `CampoBusca.tsx`: só navega para `/beneficios?q=` (L36-41); sem sugestões; sem evento `busca_global`; `role="search"` ✓, rótulo ✓ | Virar combobox (`role="combobox"` + `aria-expanded` + listbox, padrão APG) com sugestões por tipo; precisa de endpoint ou índice local (DEC-V06); registrar `busca_global` (termo × RNF-16, DIV-V09). |
| Carteirinha e busca a um toque de qualquer tela | Carteirinha na barra inferior e no trilho ✓; busca no cabeçalho de toda rota ✓ | ✓ |
| Contador de "aguardando você" | `MenuLateral.tsx:37-42` lê `solicitacoes_aguardando` fixo 0 | Vira real na Fase 3 (Maestro). |
| Sair | `FormularioSair.tsx` (POST com CSRF) ✓ | Spec põe "Sair" dentro de "Mais" ✓ (já está no drawer). |
| Ordem de atenção §3.2 (pendência → valor → próximo passo → defesa → recomendações) | Não há motor; `Inicio.tsx` é fixo | Vem com P02 (TI-V11). |
| 1 botão principal por bloco | `Inicio.tsx:42-49` tem 2 botões no hero (claro + vidro) | Adequar: 1 primário + 1 link de texto (`.link-texto`, `base.css:196`). |
| Bloco vazio não aparece; nada de "em breve" | `Inicio.tsx:70-73` e `EmConstrucao.tsx:10` dizem "a caminho"/"em construção" | Aceito só na fase de construção (ADR-0017 §3). Para o cutover: DEC-V02 / TI-V28. |

---

## Componentes

Existentes: `Avatar`, `Campo`, `EstadoVazio`, `Icon` (28 ícones), `LinkExterno`, `Toast` (único, 2,6 s,
`ToastContext.tsx:7-13`), `Drawer` + `useFocoPreso`, `CampoBusca`, `NavInferior`, `MenuLateral`, `Cabecalho`,
`BotaoWhatsapp`, `FormularioSair`; CSS: `.botao` (primário/secundário/claro/vidro, `base.css:131-194`), `.tag`
(ok/info/novo), `.selo`, `.aviso`, `.cartao`, `.carregando`, `.pill-status`, `.hero-inicio`, `.atalho`, `.carteirinha`,
`.dados-perfil`, `.grade-campos`.

| Componente | Existe? | Variantes/estados a criar | Telas |
|---|---|---|---|
| `BlocoHome` (contêiner: título, 1 CTA, link secundário, "por que estou vendo isto", dispensar) | não | visível/oculto por conteúdo; carregando (skeleton); erro isolado | P02 |
| `CardPendencia` | não | pagamento, documentação, solicitação, carência liberada, renovação | P02 |
| `CardMeuValor` | não | com valor; "o que a sua associação cobre"; "valor entregue" (contribuição 0) | P02, P06 |
| `CardProximoPasso` / `PerguntaPerfil` | não | passo da trilha; pergunta de perfil (1 por visita); resposta inline | P02, P12, P13 |
| `CardBeneficio` | não | 6 estados §8.1; selo novo/ativo/patrocinado/"libera em"; compacto (home) e catálogo | P02, P03, P04 (relacionados) |
| `SeloEstado` (texto + ícone, nunca só cor) | parcial (`.tag` 3 cores sem ícone) | disponível, ativo, libera em {data}, exclusivo efetivo, suspenso, indisponível na região, novo, patrocinado | P03, P04, P05, P10 |
| `FiltroChips` | não | single (Todos/Disponíveis/Ativos/Novos) e multi (temas); `aria-pressed`; contagem em `aria-live` | P03, P10, P11 |
| `BarraResumo` | não | 3 números com contexto; some sem fonte | P03 |
| `GradeCategorias` | não | 8 categorias com ícone (faltam ícones em `Icon.tsx`) | P02, P03 |
| `BotaoAtivacao` | não | tipo 1 (externo, `LinkExterno`), 2/3 (abre `Dialogo`), 4–6 (F2); desabilitado com motivo textual | P04 |
| `Dialogo` (modal acessível) | parcial (`Drawer` tem foco preso; não é genérico) | confirmar/cancelar; destrutivo; com formulário | P04, P05, P13, P14 |
| `Accordion` | não | FAQ, regras, "como funciona" | P04, P14 |
| `LinhaDoTempo` | não | passo atual, passado, futuro; origem (APM/parceiro/você) | P05 |
| `StatusSolicitacao` | não | 7 rótulos (DEC-V09) | P05, P02 |
| `Avaliacao` 0–10 | não | radiogroup 11 alvos ≥44 px; enviado/obrigado | P05 |
| `SeletorPeriodo` (tabs) | não | ano corrente/anteriores | P06, P08 |
| `Extrato` (tabela responsiva) | não | item com fonte/modalidade; total; vazio | P06, P08 |
| `ComoCalculamos` | não | sempre visível (não recolhido) | P06 |
| `ValorPotencial` | não | rótulo textual "potencial", nunca somado | P06, P03 |
| `BotaoBaixar` | não | PDF, imagem; ocupado; erro | P06, P07, P08, P13 |
| `FaixaSituacao` | parcial (`.aviso`) | em dia, em atraso, fora do ar | P08, P02 |
| `LinhaDigitavel` / `PixCopiaCola` | não | copiar + "copiado" (`aria-live`), QR SVG | P08 |
| `BarraProgresso` | não | `role=progressbar`, valor por custom property (CSSOM, ADR-0013) | P12, P13 |
| `PassoTrilha` | não | feito, disponível, "libera em", bloqueado | P12, P02 |
| `Switch` de consentimento | não | ligado/desligado, versão do texto, histórico | P13 |
| `CheckboxGroup` / `RadioGroup` | não | atuação, motivos de cancelamento | P13, P14 |
| `Combobox` de busca com sugestões | não (`CampoBusca` simples) | sugestões por tipo; sem resultado | shell, P03, P14 |
| `ImagemSegura` | não | host em `CSP_IMG_HOSTS` → `img` lazy com proporção; senão placeholder | P10, P11, P09, P04 |
| `Skeleton` | não (`.carregando` é texto) | card, lista, bloco | todas |
| `EstadoErro` com `request_id` e "tentar novamente" | parcial (só em `SessaoContext.tsx:73-90` e inline nas páginas) | 503 fonte indisponível, sem conexão, 404 recurso desligado | todas |
| `ControleFonte` (A−/A/A+) | não | 3 passos; persistência (DEC-V03) | shell |
| `AbaMais` (bottom-nav → drawer) | não | `aria-expanded`, `aria-controls` | shell |
| `Sino` | não 🔒 | — | P15 (F2) |

---

## RNF de front

### PWA (spec L1192-1193)
- **Existe**: `index.html` com `theme-color` (L6), `apple-touch-icon` (L9) e favicon 32; `app/static/favicon-192.png`;
  CSP já tem `manifest-src 'self'` (`app/main.py:103`). **Não existe**: `manifest.webmanifest`, service worker,
  `frontend/public/`, ícone 512/maskable (inventario-codigo.md:34).
- **Restrições**: `/area` é servido com sessão obrigatória e `Cache-Control: no-store` (`app/spa.py:3-5`,
  `main.py:185`) → um SW **não pode** cachear o `index.html` nem `/api/`; `script-src 'self'` permite SW da própria
  origem, mas o escopo `/area/` exige o SW servido de `/` ou cabeçalho `Service-Worker-Allowed` (Maestro); `worker-src`
  não está na CSP (herda `default-src 'self'`, ok). A CSP é da Sentinela → **ADR**.
- **Caminho**: (1) manifest-only já torna instalável (Chrome não exige mais SW para instalar; iOS usa manifest +
  `apple-touch-icon`) com `start_url: /area`, `scope: /area/`, `display: standalone`, `lang: pt-BR`; (2) SW mínimo
  só para assets `/static/spa/assets/*` (já imutáveis) e uma página "sem conexão" — nunca `/area` nem `/api`
  (DEC-V07). Medir: Lighthouse "installable"; e2e checa `link[rel=manifest]` e ausência de violação CSP.

### Desempenho (spec L1190-1191: LCP < 2,5 s e INP < 200 ms, p75 celular; RNF-11 nosso: bundle ≤ 250 kB, CLS < 0,1)
- **Existe**: build `dist` obsoleto mostra 199 kB JS + 19 kB CSS (sem gzip) + fontes; assets imutáveis com hash
  (`vite.config.ts:11-19`); sem imagem no hero (gradiente CSS) — bom para LCP; `modulePreload.polyfill=false`.
  **Nenhuma medição** (sem Lighthouse, sem web-vitals, sem orçamento no CI).
- **Riscos**: (a) entrada de página anima `opacity: 0 → 1` nos filhos diretos do `main` (`motion.css:28-46`, até
  450 ms de atraso + 520 ms) — elementos com opacidade 0 não contam como candidato LCP até aparecer: o LCP do
  conteúdo pode cair perto de 1 s depois do paint; o `h1` do cabeçalho fica fora da animação, o que ajuda; medir
  antes de mexer; (b) `backdrop-filter` em cards, trilho e bottom-nav (`base.css:109-122`, `shell.css` mobile) pesa em
  Android fraco → INP/rolagem; (c) 2 round-trips antes de qualquer dado (`/sessao` → página → `/perfil`), sem
  skeleton; (d) Sora em 4 pesos × 2 subsets + mono = 9 arquivos (`main.tsx:2-10`); (e) uma única chunk — ao chegar
  15 telas, `React.lazy` por rota (import dinâmico é compatível com a CSP).
- **Como medir**: Lighthouse via Playwright (Chromium) em `mobile-390`/360 com throttling "Moto G Power"
  equivalente, orçamento (`budget.json`: LCP, INP/TBT, CLS, JS ≤ 250 kB) falhando o `npm run e2e`; opcional RUM:
  `web-vitals` (self-hosted, npm) enviando `web_vital` por `registrarUso` → exige ação nova no catálogo e tratamento
  de números em `detalhes` (Maestro/Atlas, DEC). O indicador 14 da spec (L1024) pede LCP diário → RUM é o único
  jeito de obter p75 real.

### WCAG 2.2 AA (spec L1199-1201; REQUISITOS RNF-10 ainda diz 2.1)
- **Existe**: axe com tags `wcag2a, wcag2aa, wcag21a, wcag21aa` em 4 rotas (`e2e/shell.spec.ts:127-138`); foco
  visível global (`base.css:63-67`); skip link (`base.css:86-101`); foco no `h1` por rota (`AppShell.tsx:42`);
  drawer com foco preso e retorno (`useFocoPreso.ts`); `role=status`/`alert` sempre no DOM (`ToastContext.tsx:68-84`);
  `Campo` com `aria-describedby`; `prefers-reduced-motion` (`motion.css:52-60`); `aria-current` na navegação;
  contraste com variantes `-texto` (P-22, `tokens.css:6-13`).
- **Critérios novos do 2.2 × estado**:
  - 2.4.11 *Foco não obscurecido (mínimo)*: barra inferior fixa (52 px + 12 px), FAB WhatsApp (`bottom: 92px`) e
    toast (`bottom: 156px`) sobrepõem o conteúdo no mobile; `.principal` tem `padding-bottom: 150px`
    (`shell.css` L+611/11) mas **não há `scroll-padding-bottom`** → elemento focado por Tab no fim da lista pode ficar
    sob a barra. Ação: `scroll-padding-bottom` no `html` (mobile) e testar com Tab até o rodapé.
  - 2.5.7 *Arrastar*: nada usa arrasto hoje; carrosséis futuros (recomendados) precisam de setas.
  - 2.5.8 *Tamanho do alvo (24 px)*: tudo passa; **a spec exige 44 px** (L1187): `.botao` tem `min-height: 42px`
    (`base.css:136`), `.busca__limpar` 32 px (`shell.css:404-405`); `.link-texto` inline (isento). Ajustar.
  - 3.2.6 *Ajuda consistente*: FAB "Central APM" no mesmo lugar em toda rota ✓ (quando `SHOW_WHATSAPP`); a página
    Ajuda (P14) e o link no menu reforçam.
  - 3.3.7 *Entrada redundante*: formulários pré-preenchidos ✓ (`Perfil.tsx:189-198`); o cancelamento (P14) não pode
    pedir de novo o que o cadastro sabe.
  - 3.3.8 *Autenticação acessível*: na área, o código de e-mail aceita colar e `autocomplete="one-time-code"`
    (`Perfil.tsx:440`) ✓; o login é do IdP — verificar que o campo de OTP do `login_associado` não bloqueia colar
    (fora deste repositório).
  - 2.4.12/2.4.13 e 3.3.9 são AAA (fora).
- **Pendências 2.1 ainda abertas**: axe só em 4 rotas e só em Chromium; nenhuma checagem de zoom 200 %/reflow a
  320 px (1.4.10) nem de `prefers-contrast`; textos com ícone decorativo ok (`Icon` `aria-hidden`).
- **Como medir**: adicionar `wcag22aa` às tags do axe (axe-core ≥ 4.8 já suporta; `@axe-core/playwright 4.14.0`
  em `package.json`), rodar em **toda** rota nova, projeto `mobile-360`, teste de reflow (sem rolagem horizontal já
  existe: `shell.spec.ts:53-56`), teste de Tab até o último controle visível acima da barra.

### Fonte ajustável (spec §3 item 10, L125-126; §14 "texto ampliável sem quebrar")
- **Existe**: zoom do navegador funciona (viewport sem `maximum-scale`, `index.html:5`); `text-size-adjust: 100%`
  (`base.css:9-12`). **Não existe** controle de fonte; todos os tamanhos são **px** (`tokens.css:112-119`,
  `--fs-base: 14px`), o que ignora a preferência "tamanho da fonte" do navegador (só `rem`/`em` a respeitam) e
  parte de 14 px para um público 58 % acima de 51 anos — o mockup é 14 px, a spec quer "fonte grande".
- **Caminho**: migrar tokens tipográficos para `rem` (1 rem = 16 px por padrão), base `0.9375rem`→ avaliar 1 rem;
  `ControleFonte` com 3 passos via atributo `data-fonte` no `html` (mesmo padrão de `data-animacoes`,
  `SessaoContext.tsx:17-20`) — sem inline. **Persistência** é o nó: `localStorage` é proibido por lint
  (`eslint.config.js` `no-restricted-globals`) e RNF-21; alternativas em DEC-V03. Medir: teste com fonte 200 % sem
  rolagem horizontal a 360 px; axe `reflow`.

### Compatibilidade (spec L1187-1189: Safari iPhone e Chrome Android, 2 últimas versões, 360 px)
- **Existe**: `-webkit-backdrop-filter` (`base.css:111`), `env(safe-area-inset-bottom)` (`shell.css`), `@supports`
  fallback opaco; Playwright **só Chromium** em 1440 e **390** px (`playwright.config.ts:24-30`); `locale pt-BR`.
- **Falta**: projeto WebKit (`devices['iPhone 13']`) e viewport **360**; `min-height: 100vh` (`shell.css:20`,
  `.tela-estado`) → `100dvh/100svh` no iOS Safari (barra de endereço); `display: contents` em `.topo__acoes`
  (`shell.css` L+611/37-39) — já é seguro para `div` no Safari ≥ 15.4, só confirmar; `navigator.clipboard` tem
  fallback ✓ (`Carteirinha.tsx:46-55`); `fetch keepalive` ✓ no Safari ≥ 13.
- **Como medir**: `npx playwright install webkit` no ambiente de e2e (Estivador), rodar `shell.spec`/`fase2.spec`
  nos 3 projetos; checagem manual trimestral em iPhone real (EXT-V08 inclui idosos).

### Identidade visual, textos e i18n
- Paleta: `#004165` (`--navy-900`), `#009581` (`--green-600`), `#00675A` (`--green-700`) já são tokens; `#616365`
  (cinza do brandbook) **não** existe (`tokens.css:46-51` usa `#5e6e75`/`#8a979d`). Fonte: Sora (ADR-0017) ×
  Verdana (spec L1211-1212) → DIV-V01, 🔒 do lado do usuário.
- Botão principal: spec pede verde `#009581` (L155); mockup/tokens usam gradiente navy (`base.css:152-156`); branco
  sobre `#009581` = 3,74 (P-22) → DIV-V04.
- Voz §3.3 × textos: exclamação em `MENSAGEM_CENTRAL` (`lib/links.ts:31`) ✗; "Olá, {nome}" sem Dr./Dra.
  (`Inicio.tsx:37`, LA-19) ✗/DEC; botão "Meu perfil" sem verbo (`Inicio.tsx:46-48`) ✗; "Membro" (`Carteirinha.tsx:94`)
  ✗; erros dizem o que fazer ✓ (`client.ts:15-16`, `SessaoContext.tsx:77-86`, `NaoEncontrada.tsx`); "Associado"
  vem do rótulo do CRM ✓; nenhum número sem contexto ✓ (não há números).
- i18n: `lang="pt-BR"` ✓, `Intl` pt-BR + fuso São Paulo (`formato.ts`, `Cabecalho.tsx:19`) ✓; sem framework de
  i18n (correto: só pt-BR).
- Testes: Vitest 47 (`shell.test.tsx` 14, `fase2.test.tsx` 9, utilitários), e2e 20 em 2 arquivos, axe em 4 rotas;
  nenhuma tela nova tem teste porque não existe; padrão a replicar: 1 `*.test.tsx` por página + 1 bloco e2e por
  tela com CSP + axe (`wcag22aa`) + 360/390/1440.

---

## Propostas

### TI (tarefas da Vitrine)

| ID | Tarefa | Camada | Repo | Tam. | Pré-requisito | Hoje? |
|---|---|---|---|---|---|---|
| TI-V01 | Navegação §3.1: reordenar `ROTAS`, renomear títulos, bottom-nav Início/Benefícios/Carteirinha/Meu valor/**Mais** (abre o `Drawer`), drawer lista só o restante; criar rotas `financeiro` e `ajuda` (vazias sob flag/visibilidade) | shell | area_associado | M | DEC-V01, DEC-V02; plano (shell) | não (plano) |
| TI-V02 | Voz §3.3: tirar exclamação (`links.ts:31`), verbo nos botões (`Inicio.tsx:46`), "Membro"→"Associado", chamada do Clube sem "cashback", 1 CTA primário no hero | texto | area_associado | P | — | **sim** (fast-path) |
| TI-V03 | Tokens tipográficos em `rem` + `ControleFonte` (3 passos, `data-fonte` no `html`) + base ≥ 15 px avaliada com a agência | CSS/shell | area_associado | M | DEC-V03 (persistência), EXT-V03 | parcial (rem sim; controle depois da DEC) |
| TI-V04 | Alvos 44 px (`.botao`, `.busca__limpar`), `scroll-padding-bottom` mobile (2.4.11), `100dvh` | CSS | area_associado | P | — | **sim** |
| TI-V05 | axe com `wcag22aa` em todas as rotas; projetos Playwright `webkit-iphone` e `mobile-360`; teste de Tab até o rodapé | testes | area_associado | P | WebKit instalado no host de e2e (Estivador) | sim (Chromium) |
| TI-V06 | Busca global como combobox com sugestões + `busca_global` | shell/api | area_associado | M | DEC-V06; endpoint ou índice (Maestro) | não |
| TI-V07 | P03 catálogo: `BarraResumo`, `FiltroChips`, `GradeCategorias`, `CardBeneficio`, vazio com sugestão, erro 503 | página | area_associado | G | API `/beneficios` (Maestro, Fase 4), `sql/009` (Atlas), catálogo curado (EXT-V10), DEC-V09 | não |
| TI-V08 | P04 página do benefício: sub-rotas no shell (`h1` da página), `/beneficios/{slug}`, `SeloEstado`, `BotaoAtivacao`, `Dialogo`, `Accordion`, relacionados | página | area_associado | G | API detalhe + ativação (Maestro Fases 3–4); allowlist de hosts por benefício (Sentinela) | não |
| TI-V09 | Primitivos puros com Vitest: `SeloEstado`, `Dialogo`, `Accordion`, `Combobox`, `Tabs`, `BarraProgresso` (CSSOM), `Skeleton`, `EstadoErro`, `RadioGroup/CheckboxGroup`, `ImagemSegura` | componentes | area_associado | M | DEC-V09 só para os rótulos | **sim** (fast-path; sem API) |
| TI-V10 | P05 solicitações: lista, detalhe, `LinhaDoTempo`, `StatusSolicitacao`, cancelar, `Avaliacao`, responder; emissores `solicitacao_*` | página | area_associado | G | API Fase 3 (Maestro/Atlas `sql/008`); DIV-V10 | contrato primeiro |
| TI-V11 | P02 home em blocos: `BlocoHome` + cards 1–7 (notícias/clube F2), "por que estou vendo isto", dispensar, "como funciona" no 1º acesso; emissores `home_bloco_clicado`, `recomendacao_dispensada` | página | area_associado | G | API de blocos/motor (Maestro); catálogo (Fase 4); ações novas no catálogo de uso | por etapas (categorias e próximo passo primeiro) |
| TI-V12 | P06 Meu valor: renomear rota, `SeletorPeriodo`, `Extrato`, `ComoCalculamos`, `ValorPotencial`, PDF | página | area_associado | G | VAL-01 fonte + flag (P-12) ⛔ | não |
| TI-V13 | P07 baixar imagem/PDF (botões) + `num_contato` no cartão | página | area_associado | P (front) | DEC-V08; endpoint PNG/PDF (Maestro) | parte (número) sim |
| TI-V14 | P08 Financeiro: `FaixaSituacao`, `ListaMensalidades`, `SegundaVia` (PDF, `LinhaDigitavel`, `PixCopiaCola` + QR), histórico, `Declaracoes`, estado "cobrança fora do ar" | página | area_associado | G | P-04, P-08, hub sem 2ª via/Pix ⛔ | não |
| TI-V15 | P12 trilha: `BarraProgresso`, `PassoTrilha`, bloco de 3 passos na home (F1), visibilidade por tempo de casa | página | area_associado | M | API da trilha (Fase 6); `data_filiacao` na sessão (Maestro) | não |
| TI-V16 | P13 extensão: tratamento, atuação, interesses, canais, consentimentos, baixar dados, pedir exclusão, "complete seu perfil", `PerguntaPerfil` | página | area_associado | G | tabelas e API de perfil declarado/consentimento (Atlas/Maestro); textos de consentimento (jurídico, EXT) | não |
| TI-V17 | P14 Ajuda: FAQ com busca local, canais com horário (`tel:` na allowlist de esquemas), pedidos comuns, `FormularioCancelamento` | página | area_associado | M | fonte da FAQ (EXT-V05), tipo `cancelamento` em solicitações (Fase 3) | esqueleto sim; conteúdo não |
| TI-V18 | PWA: `manifest.webmanifest` + ícones 192/512 maskable (rota estática), depois SW mínimo | shell/infra | area_associado | M | ADR (Sentinela/Maestro), EXT-V07 ícones, DEC-V07 | manifest após ADR |
| TI-V19 | Medição: Lighthouse no e2e com orçamento (LCP/INP/CLS/JS); `React.lazy` por rota; avaliar RUM `web-vitals` | testes/build | area_associado | M | RUM exige ação nova no catálogo (Maestro/Atlas) | laboratório sim |
| TI-V20 | Eventos de uso: estender `AcaoUi` (`analytics.ts:12-28`) e emitir `busca_global`, `filtro_aplicar`, `categoria_abrir`, `beneficio_abrir` (+origem/estado), `home_bloco_clicado`, `recomendacao_dispensada`, `consentimento`, `cancelamento_pedido`, `ajuda_contato` | lib | area_associado | P–M | catálogo em `app/uso.py` (Maestro/Atlas) | junto de cada tela |
| TI-V21 | `ImagemSegura` (host ∈ `CSP_IMG_HOSTS` entregue por `/sessao` ou pela API, `loading=lazy`, proporção fixa) | componente | area_associado | P | expor a lista no `/sessao` (Maestro) | componente sim |
| TI-V22 | Higiene: `LICENSES.md` (Figtree→Sora), limpar `frontend/dist` obsoleto, ADR-0017 "12 × 13 mockups" | docs | area_associado | P | — | **sim** |
| TI-V23 | P-24: `stub_login`/`erro` Jinja no visual Sora | templates | area_associado | P | — | sim (cutover) |
| TI-V24 | P-40: React Router 7 antes das telas da Fase 3 (migração cresce com cada página nova) | deps | area_associado | M | Sentinela (dependência); DEC-V11 | não (plano) |
| TI-V25 | Rotas sem página saem do menu/barra no cutover (`rotaVisivel` + "implementada"), sem "a caminho" | shell | area_associado | P | DEC-V02 | após DEC |
| TI-V26 | Padrão de teste por tela nova: `*.test.tsx` (estados vazio/erro/carregando/sucesso, eventos emitidos) + bloco e2e (CSP, axe 2.2, 3 viewports) | testes | area_associado | P por tela | — | sim (template) |

### EXT (o que precisa vir de fora)

| ID | O que exatamente | De quem | Destrava | Enquanto isso | Ref. |
|---|---|---|---|---|---|
| EXT-V01 | Pacote completo dos `*.dc.html` + `assets/` + `support.js` para versionar em `docs/mockups/` | agência | fidelidade visual das fases 3–8; confirmar `relacionamento` = P16 | tradução por `tokens.css` a partir do que foi colado em 20/10 | P-39 |
| EXT-V02 | Mockups inexistentes: P04 (página do benefício, 6 estados), P05 (lista + linha do tempo + avaliação), P06 v2 ("como calculamos", potencial, período), P08 (situação, 2ª via, Pix, declarações), P14 (FAQ, canais, cancelamento), P13 (consentimentos, baixar dados), P12 por categoria, P15, aba "Mais" e os selos textuais | agência (Encantada) | TI-V07/08/10/12/14/16/17 com visual aprovado | construir com os componentes existentes e a linguagem do ADR-0017; aceite depois | novo |
| EXT-V03 | Decisão formal sobre identidade: Sora/mockup (ADR-0017) × Verdana + `#616365` do brandbook (spec §14) | Marketing APM + agência | fecha DIV-V01 | ADR-0017 vale (🔒 do usuário) | novo |
| EXT-V04 | Imagens com direito de uso (hero, selos, capas) e ícones oficiais (logo SVG, 192/512 maskable) | Comunicação APM | TI-V18, cards com foto | gradientes CSS | P-38 (+ ícones: novo) |
| EXT-V05 | Textos finais na voz §3.3: títulos/chamadas de rota, estados vazios e de erro, rótulos dos 6 estados e 7 status, "como calculamos", FAQ inicial (≥ 20 perguntas), motivos de cancelamento, textos de consentimento (versionados) | Encantada executa / Marketing APM responde (RACI, spec L915); consentimentos com jurídico | TI-V02, TI-V07, TI-V10, TI-V16, TI-V17 | textos provisórios marcados como proposta (LA-25) | novo; LA-25 |
| EXT-V06 | Validação das variantes de contraste `-texto` e dos pares das tags | agência | P-22 | variantes atuais | P-22 |
| EXT-V07 | Catálogo curado (30–40), 8 categorias finais, carências validadas, benefícios por tipo de ativação | Benefícios e parcerias | P03/P04 (gate F0, spec L1221-1224) | nenhum card real | novo (F0) |
| EXT-V08 | Testes de usabilidade com associados de faixas etárias diferentes (spec L1200-1201) + 1 iPhone real para o e2e manual | Marketing/Encantada | aceite de P02/P03 e do tamanho de fonte | axe + Playwright | novo |
| EXT-V09 | Regra de tratamento Dr./Dra.: fonte do gênero no CRM ou campo "como prefere ser chamado" | negócio / CRM admin | DEC-V05 | "Olá, Nome" | LA-19 |
| EXT-V10 | Fonte da FAQ e dos "pedidos comuns" sem backoffice (quem edita, onde) | Marketing APM | TI-V17 | seed versionado no repositório | novo |

### DIV (divergências a registrar em `docs/PENDENCIAS.md`)

| ID | Divergência | Onde | Encaminhamento |
|---|---|---|---|
| DIV-V01 | Identidade: spec §14 Verdana + `#616365` × ADR-0017 Sora/mockup (`tokens.css:110`) | spec L1211-1212 | 🔒 mockup; levar ao Marketing como divergência formal (EXT-V03) |
| DIV-V02 | Bottom-nav e ordem/nomes do menu | spec L130-133 × `rotas.ts:26-48` | TI-V01 após DEC-V01/02 |
| DIV-V03 | "Nada de em breve" × `EmConstrucao`/"a caminho" | spec L159 × `Inicio.tsx:70-73`, `EmConstrucao.tsx:10` | aceito em construção (ADR-0017 §3); some no cutover (TI-V25) |
| DIV-V04 | Botão principal verde `#009581` × gradiente navy do mockup × contraste 3,74 | spec L155 × `base.css:152-156` × P-22 | DEC-V04 |
| DIV-V05 | WCAG 2.2 × RNF-10 (2.1) e tags do axe | spec L1199 × `e2e/shell.spec.ts:135` | TI-V05 + atualizar REQUISITOS (Maestro/doc) |
| DIV-V06 | 360 px e Safari iOS × e2e 390 px só Chromium | spec L1187-1189 × `playwright.config.ts:24-30` | TI-V05 |
| DIV-V07 | Alvos 44 px × `.botao` 42 px, `.busca__limpar` 32 px | spec L1187 × `base.css:136`, `shell.css:404` | TI-V04 |
| DIV-V08 | Fonte ajustável e "fonte grande" × tokens em px, base 14 px | spec L125-126 × `tokens.css:112-119` | TI-V03 + DEC-V03 |
| DIV-V09 | Busca registra o termo (ajuste de catálogo) × RNF-16 não grava termo | spec L353-354, L960 × `app/uso.py` | DEC-V06 (LGPD: termo sem identidade?) — Maestro/Atlas/Sentinela |
| DIV-V10 | 7 rótulos de status × 6 estados ADR-0003 (sem "Enviada ao parceiro" e "Aguardando o parceiro") | spec L407-409 × INDICE L68-75 | plano da Fase 3 (Maestro/Atlas); front precisa do vocabulário (DEC-V09) |
| DIV-V11 | "Fatura de valor" / rota `fatura` × "Meu valor"/"Extrato de valor"; Financeiro é outra página | spec L421-422 × `rotas.ts:31` | TI-V01 (renomear rota: `/area/meu-valor` e `/area/financeiro`) |
| DIV-V12 | "Olá, Dra. Helena" × "Olá, Nome" | spec L163-164 × `Inicio.tsx:37` | DEC-V05 / EXT-V09 |
| DIV-V13 | Trilha para todo novo associado (F1 bloco na home) × página só Acadêmico | spec L521-534 × `rotas.ts:37-45` | TI-V15 |
| DIV-V14 | "Perfil e privacidade" (consentimentos, LGPD) × "Meu perfil" | spec L537-547 × `rotas.ts:35` | TI-V01, TI-V16 |
| DIV-V15 | Comunidade (F3) e Onboarding visíveis no menu hoje | spec L251 × `rotas.ts:32,37-45` | DEC-V02 |
| DIV-V16 | `LICENSES.md` cita Figtree; `dist/` local com Figtree | `frontend/LICENSES.md:5` × `package.json` | TI-V22 |
| DIV-V17 | PWA pedido × ADR-0001/0013 e `/area` `no-store` com sessão | spec L1192 × `app/spa.py`, `main.py:185` | ADR nova (TI-V18, DEC-V07) |
| DIV-V18 | Sino de notificações (F2) × "sem sino até existir fonte" | spec L134, L569 × `Cabecalho.tsx:25` | 🔒 coerente; só quando houver fonte |
| DIV-V19 | Marca no topo fixo × marca só no trilho/drawer; cabeçalho não fixo | spec L134 × `Cabecalho.tsx`, `MenuLateral.tsx:49-58` | manter mockup; registrar |
| DIV-V20 | Clube promete "cashback" na chamada × cashback só com P17 | `rotas.ts:29` × spec L262 | TI-V02 |
| DIV-V21 | Carteirinha sem nº de associado × spec pede "número de associado" | spec L449 × `Carteirinha.tsx:97-104` | TI-V13 |

### DEC (decisões que o usuário precisa tomar)

| ID | Decisão | Opções | Recomendação da Vitrine |
|---|---|---|---|
| DEC-V01 | "Meu valor" na barra inferior com `fatura_valor` forçada desligada | (a) barra com 4 abas até existir fonte; (b) aba leva a "o que a sua associação cobre" sem valores; (c) manter Clube na 4ª posição até P06 | (a): regra 19 e "bloco vazio não aparece"; a barra reflui com `repeat(auto-fit)` |
| DEC-V02 | Rotas sem página (Clube, Notícias, Eventos, Comunidade, Solicitações, Onboarding) | (a) manter `EmConstrucao` só em construção e esconder no cutover (`rotaVisivel`); (b) esconder já | (a) agora, (b) obrigatório no cutover — a agência acompanha o progresso pelas rotas |
| DEC-V03 | Onde persistir o tamanho de fonte | (a) preferência no servidor (perfil declarado, `/sessao`); (b) exceção pontual de `localStorage` para preferência não pessoal (ajuste do lint); (c) só zoom do navegador | (a) quando P13 existir; até lá (c) + tokens em `rem` (respeita a preferência do navegador) |
| DEC-V04 | Cor do botão principal | (a) gradiente navy do mockup; (b) verde `#009581` com texto ≥ 18,66 px bold ou fundo `#00675A` | (a) pelo ADR-0017; registrar DIV-V04 para a agência |
| DEC-V05 | Tratamento Dr./Dra. | (a) campo "como prefere ser chamado" (P13) com padrão neutro; (b) gênero do CRM via hub | (a): não depende do CRM e respeita a escolha; até lá "Olá, Nome" |
| DEC-V06 | Busca global | (a) endpoint `/api/v1/busca` com sugestões por tipo; (b) índice local das listas já carregadas; gravar termo? | (a) a partir da Fase 4; termo gravado só em "sem resultado", truncado, sem identidade (Sentinela/Atlas) |
| DEC-V07 | Escopo do PWA | (a) manifest-only (instalável) agora; (b) + SW de assets e página offline (ADR) | (a) agora após ADR curta; (b) depois de medir |
| DEC-V08 | Baixar carteirinha | (a) PNG/PDF gerados no servidor (Pillow/segno existem); (b) canvas no cliente | (a): mesma imagem para todos, sem lógica de dado no cliente, cacheável por ETag |
| DEC-V09 | Vocabulário dos 6 estados de elegibilidade e dos 7 status — aprovação antes dos componentes | Marketing/Benefícios | adotar os textos da spec L710-717 e L756-765 como proposta até o aceite |
| DEC-V10 | WebKit no CI | (a) instalar no host de e2e; (b) só manual em iPhone | (a) + (b) trimestral |
| DEC-V11 | P-40 React Router 7 antes da Fase 3 | (a) migrar agora (3 páginas); (b) bloquear `\` nos destinos e migrar depois | (a): custo cresce a cada tela |
| DEC-V12 | "Página de retorno" do ex-associado (P01) | (a) IdP mostra; (b) landing guardada (`entrada.html`) ganha variante; (c) Central | fora da SPA; alinhar com `login_associado` |

---

## Riscos e ADRs candidatas

**ADRs candidatas**
1. **PWA** (manifest, SW, política de cache × `no-store` de `/area`, `worker-src`, escopo) — Sentinela + Maestro + Vitrine.
2. **Medição de desempenho** (laboratório no CI + RUM por `evento_uso`; números em `detalhes`; orçamento) — Maestro/Atlas/Vitrine.
3. **Preferências de acessibilidade do associado** (fonte, movimento) e onde vivem (RNF-21) — Vitrine/Sentinela.
4. **Aditivo à ADR-0017** se o Marketing exigir Verdana/paleta do brandbook (DIV-V01) ou botão verde (DIV-V04).
5. **Vocabulário de estados na UI** (elegibilidade §8.1 e status §8.5) junto do plano da Fase 3/4 — Maestro/Atlas/Vitrine.
6. **Sub-rotas na SPA** (`/beneficios/{slug}`, `/solicitacoes/{uuid}`, `/eventos/{id}`): título do `h1` por página,
   `pagina_ver` com id truncado, `safe_next` — pequena, mas muda `rotas.ts`/`AppShell` e o analytics.

**Riscos**
- Animação de entrada com `opacity: 0` pode empurrar o LCP (medir antes de qualquer tela nova; fácil de limitar ao 1º filho).
- `backdrop-filter` em muitos cards (catálogo com 40 itens) → INP/rolagem no Android de entrada; prever variante
  opaca para listas longas.
- Bundle único: 15 telas sem `React.lazy` estouram o orçamento de 250 kB.
- Fonte 14 px em px para público 51+: risco de aceite nos testes com associados (EXT-V08).
- `lib/links.ts` com allowlist fixa: benefícios tipo 1 com hosts variados exigem allowlist vinda do servidor
  (Sentinela) — sem isso o botão "Acessar" renderiza sem link (`LinkExterno.tsx:19-21`).
- Sub-rotas: hoje qualquer `/area/beneficios/x` dá `h1` "Página não encontrada" (`rotas.ts:63-66`).
- Spec repetidamente exige coisas sem fonte (valor no ano, economia, 2ª via): a tentação de preencher com texto
  ilustrativo contraria a regra 19 — manter "bloco some".
- P-40 (open redirect por `\` no React Router 6) ganha superfície com rotas parametrizadas.

## Ordem sugerida

1. **Hoje, fast-path** (sem API, sem plano): TI-V02 textos · TI-V04 alvos/scroll-padding/dvh · TI-V05 axe 2.2 +
   360 px (WebKit quando o host permitir) · TI-V22 higiene · TI-V09 primitivos com Vitest · TI-V21 `ImagemSegura` ·
   TI-V26 template de teste.
2. **Decisões curtas com o usuário**: DEC-V01, V02, V04, V09, V11 → então TI-V01 navegação (plano de shell), TI-V24
   React Router 7, TI-V25.
3. **Fase 3 (próxima)**: contrato de `tipos.ts` com o Maestro → TI-V10 P05 + TI-V20 eventos; junto: TI-V17 Ajuda
   (cancelamento como tipo de solicitação) e TI-V13 número/download da carteirinha.
4. **Fase 3b (proposta nova)**: TI-V16 P13 preferências/consentimentos (F1 na spec; precisa de Atlas/Maestro).
5. **Fase 4**: TI-V07 catálogo, TI-V08 página do benefício, TI-V11 home em blocos (1–7), TI-V06 busca; EXT-V07 e
   EXT-V02 antes do aceite.
6. **Transversal, em paralelo** (ADRs): TI-V18 PWA (DEC-V07), TI-V19 medição + `React.lazy`, TI-V03 fonte ajustável
   (DEC-V03).
7. **Fases 5–6**: P10, P11 (ImagemSegura, cache do portal), P12 trilha, P09 clube; **7–8**: P08, P06, wallet — só
   com fonte e flag.
