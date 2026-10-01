# Minha APM — Especificação da Nova Área do Associado

Oct 1, 2026 · @Sistemas TI

## Visão geral

**Minha APM** é a nova área do associado da Associação Paulista de Medicina: um portal web autenticado onde o médico, residente ou acadêmico associado descobre, ativa e usa benefícios, acompanha quanto a associação economiza para ele ("fatura de valor"), participa de comunidades e eventos e carrega a carteirinha digital. O protótipo navegável foi produzido pela agência Comunicação Encantada e esta spec o descreve para que o Claude Code reproduza a interface fielmente, substituindo dados ilustrativos por integrações reais.

A tese do produto está no rodapé do protótipo e em toda a home: **todo resgate acontece dentro da Minha APM**. Cada ativação registrada vira dado, entra na fatura de valor do associado e sustenta o modelo "Mensalidade Zero" (patrocínio cobre parte ou toda a anuidade).

| Item | Valor |
| --- | --- |
| Nome do produto | Minha APM — área do associado |
| Origem do design | Protótipo HTML navegável (Claude Design), 9 telas, desktop e mobile |
| Personas no protótipo | Dra. Telma Nogueira (médica titular, CRM-SP, associada desde 2014) e João (acadêmico de Medicina, 100% patrocinado) |
| Idioma | Português do Brasil, tom informal-profissional ("bom te ver por aqui") |
| Escopo desta spec | Interface, navegação, componentes, estados e contratos de dados; o backend é descrito pelos dados que a tela consome |
| Fora de escopo | Regras de negócio do patrocínio, cálculo de cashback, catálogo real de parceiros |

Os valores monetários, contagens e textos de notícias do protótipo são placeholders (ex.: R$ 2.480 aproveitados, CRM-SP 000000). Reproduza-os como dados mockados iniciais para fidelidade visual e troque por dados reais nas integrações descritas adiante.

## Fundação visual (design tokens)

A identidade é azul-marinho institucional APM no shell, verde-esmeralda nas ações e no "positivo financeiro", âmbar como acento de evento e patrocínio. Fundo da aplicação cinza-azulado claro; cards brancos com raio generoso. Implemente tudo como variáveis CSS (ou tokens Tailwind) com os valores abaixo.

**Cores**

| Token sugerido | Hex | Uso no protótipo |
| --- | --- | --- |
| `--navy-900` | `#063553` | Início do gradiente dos heroes escuros |
| `--navy-800` | `#083b5a` | Sidebar, drawer mobile, títulos de destaque, chip ativo, numerais "Como funciona" |
| `--navy-700` | `#0a4561` | Fim do gradiente do card Mensalidade Zero |
| `--navy-600` | `#0a3f5f` | Texto de tags `patrocinado`/`notícia` (fundo `#e3ebf2`) |
| `--teal-700` | `#0b5a52` | Hero do Congresso (início), botão "Submeter trabalho", barra Saúde |
| `--teal-600` | `#0e7a66` | Hero do Congresso (fim) |
| `--green-700` | `#0b6e5b` | Texto positivo (R$ 2.480), links "ver extrato", ícones de card, pill "Mensalidade Zero ativa" |
| `--green-600` | `#0e8f78` | Botão primário, item ativo da sidebar, tab ativa do bottom-nav, ponto de status |
| `--green-600-hover` | `#0b7a66` | Hover do botão primário |
| `--mint-400` | `#5fd1b5` / `#3fc3a4` | Acentos sobre fundo navy (badge "ativa", barra 40%) |
| `--mint-100` | `#e2f1ec` / `#e2f3ee` | Fundo de ícone de card, pill de status, tags `ativo` (`#dcefe9` + texto `#0e7a64`) |
| `--amber-500` | `#f5a623` / `#f5b43a` | Bloco de data do Congresso, CTA do Congresso, borda superior do hero de benefícios |
| `--amber-border` | `#efc76b` | Borda de card `patrocinado` |
| `--amber-100` | `#fdebd3` / `#fdf0d8` | Fundo de tag `novo` (texto `#c46a0a`) |
| `--purple` | `#ece8fb` / `#5b45c2` | Tag `publicação` e categoria Educação |
| `--rose` | `#fbe4e8` / `#b23a55` | Categoria Finanças e proteção |
| `--terracotta` | `#fbe7e1` / `#b24d2c` | Categoria Comunidade |
| `--gray-50` | `#edf1f4` | Fundo do body |
| `--gray-100` | `#eef2f5` | Campo de busca, botão menu, trilho de barras, botão secundário |
| `--gray-200` | `#e6eaef` / `#e3e8ee` | Bordas de card e do header |
| `--gray-150` | `#edf0f3` | Divisores internos de card |
| `--ink-900` | `#13233a` | Texto principal |
| `--ink-700` | `#3d4a5a` | Texto de saudação e chips inativos |
| `--ink-600` | `#51606f` | Headings de seção em caixa alta |
| `--ink-500` | `#5b6878` | Texto secundário de cards |
| `--ink-400` | `#6b7a8d` | Metadados, placeholder (`#7d8a9c`), ícone de busca |
| `--navy-muted` | `#9fb7c8` / `#9fc3d6` | Subtítulo da sidebar, labels sobre navy |
| `--whatsapp` | `#1faa59` | Botão de comunidade já ingressada |

**Tipografia**

| Papel | Família | Tamanho / peso |
| --- | --- | --- |
| Base | Figtree (Google Fonts), fallback `system-ui, sans-serif`; antialiased | 14–15 px, peso 400–500 |
| Logotipo "APM" | Figtree | 40 px (sidebar) / 32 px (drawer), peso 800, letter-spacing −1 px, line-height .9 |
| Legenda do logo | Figtree | 7–7.5 px, peso 700, caixa alta |
| Título de página (h1) | Figtree | 20 px, peso 700, letter-spacing −.2 px |
| Título de hero (h2) | Figtree | 26–30 px, peso 800 |
| Heading de seção (h3) | Figtree | 13 px, peso 700, letter-spacing 1.3 px, CAIXA ALTA, cor `--ink-600` |
| Título de card (h4) | Figtree | 16.5 px, peso 700 |
| Número-destaque | Figtree | 30–32 px, peso 800, letter-spacing −.5/−.6 px |
| Placeholders de mídia | JetBrains Mono | 9–11 px ("imagem", "foto da oferta", "QR") |

**Forma, espaçamento e movimento**

| Propriedade | Valor |
| --- | --- |
| Raio de card grande / hero | 20–22 px |
| Raio de card padrão | 16 px (14 px em sub-cards) |
| Raio de botão / input / ícone | 10–12 px; pills `999px` |
| Padding de card | 18 px (padrão) · 22 px (hero/card grande) |
| Gap entre seções | 28 px · entre cards 14–16 px |
| Largura máxima do conteúdo | 1320 px, centralizado |
| Sombra de card | `0 1px 2px rgba(19,35,58,.04), 0 6px 16px -10px rgba(19,35,58,.12)` |
| Sombra hover de card | `0 14px 28px -16px rgba(19,35,58,.35)` + `translateY(-3px)` |
| Sombra de hero navy | `0 14px 30px -18px rgba(6,53,83,.7)` |
| Easing padrão | `cubic-bezier(.2,.8,.2,1)`; transições 180–220 ms |
| Entrada de página | filhos do root: fade + `translateY(14px)`, 420 ms, stagger 60 ms (máx. 6) |
| Entrada de cards (filtro) | fade + `translateY(8px) scale(.985)`, 320 ms, stagger 28 ms (máx. 12) |
| Toast | fade + `translate(-50%,14px)`, 280 ms |
| Drawer mobile | `translateX(-100%)→0`, 300 ms; scrim fade 250 ms |
| Acessibilidade de movimento | desativar tudo em `prefers-reduced-motion: reduce` e via prop `animations=false` |

## Estrutura, navegação e responsividade

A aplicação é um SPA com shell fixo (sidebar + header sticky) e nove rotas renderizadas na mesma área de conteúdo. A rota ativa persiste em `localStorage` (chave `mapm.page`) e trocar de página rola para o topo. Breakpoints: **mobile < 900 px** (sidebar vira drawer + bottom-nav), **≥ 1100 px** mostra a pill "Mensalidade Zero ativa" no header, **≥ 1180 px** ativa o layout de duas colunas (conteúdo + aside de 300–330 px).

**Shell desktop**

| Região | Especificação |
| --- | --- |
| Sidebar | 248 px, sticky, altura 100vh, fundo `--navy-800`, texto branco, padding `28px 14px 16px`. Topo: logotipo "APM" + legenda, depois "Minha APM / área do associado". Divisor `rgba(255,255,255,.12)`. Nav vertical com gap 4 px. Rodapé (`margin-top:auto`): bloco `rgba(0,0,0,.18)` com "Mensalidade Zero / patrocínio ativo · 2026" |
| Item de nav | Botão `padding 11px 14px`, raio 12 px, ícone 18 px + label 14.5 px. Ativo: fundo `--green-600`, peso 700. Inativo: transparente, branco, peso 500. Item "Onboarding acadêmico" separado com `margin-top:14px` e cor `#7fdcc4` quando inativo |
| Header | Sticky, branco, borda inferior `#e3e8ee`, padding `14px 32px`, conteúdo até 1320 px. Esquerda: h1 com título da rota. Centro: busca (`flex:1 1 160px`, max 380 px, altura 42 px, fundo `--gray-100`, raio 12 px, placeholder "Buscar benefício, parceiro, evento...", botão × quando há texto). Direita: pill de status + avatar circular 40 px com iniciais ("TN", fundo `#f2d9c7`, texto `#8a4b2a`, borda branca 2 px + anel `#d7dee6`) que leva à Carteirinha |
| Área de conteúdo | `max-width 1320px`, padding `28px 32px 40px`, coluna com gap 28 px. Cada rota é um bloco condicional |
| Flutuantes | Botão "Central APM" (WhatsApp, `wa.me/<número>`, mensagem pré-preenchida) fixo no canto inferior direito, `bottom 24px`; toast centralizado na base (`bottom 32px`) com ícone check, auto-dismiss em 2,6 s |

**Shell mobile (< 900 px)**

| Região | Especificação |
| --- | --- |
| Header | Padding `10px 16px`; botão hambúrguer 44×44 (fundo `--gray-100`, raio 12) à esquerda do h1; busca vai para a última posição (`order:9`) ocupando a linha inteira |
| Drawer | 280 px (máx. 86vw), fixo à esquerda, `z-index 41`, mesma paleta da sidebar, botão × 44×44 no topo; scrim `rgba(6,30,46,.5)` fecha ao toque |
| Bottom-nav | Fixo na base com 5 abas: Início, Benefícios, Clube, Notícias, Carteirinha. Ícone 21 px + label; ativo `--green-600`, inativo `--ink-400` |
| Conteúdo | Padding `18px 16px 150px` (reserva para bottom-nav); WhatsApp em `bottom 84px`; toast em `bottom 140px` |

**Mapa de rotas**

| id | Título (h1 e sidebar) | Ícone | Bottom-nav |
| --- | --- | --- | --- |
| `home` | Início | home | sim |
| `ben` | Meus benefícios | bag | sim ("Benefícios") |
| `clube` | Clube de vantagens | gift | sim ("Clube") |
| `news` | Notícias e ciência | news | sim ("Notícias") |
| `fatura` | Fatura de valor | receipt | não |
| `com` | Comunidade | user | não |
| `evt` | Congresso e eventos | cal | não |
| `card` | Carteirinha digital | card | sim |
| `onb` | Onboarding acadêmico | star | não |

**Busca global.** Digitar no campo do header em qualquer rota que não seja `ben` ou `news` redireciona para `ben` com filtro "Tudo" e categoria limpa; em `ben` filtra benefícios por título, descrição e grupo; em `news` filtra notícias por título e metadados. Limpar o campo mantém a rota.

**Grids.** Cards de benefício: `repeat(auto-fill, minmax(220px, 1fr))` na home e `minmax(250px,1fr)` em destaques; categorias `minmax(190px,1fr)`; cards duplos do topo da home `repeat(auto-fit, minmax(270px,1fr))`; passos "Como funciona" `minmax(170px,1fr)`.

## Telas

Cada tela abaixo lista seus blocos na ordem em que aparecem, de cima para baixo, com os textos literais do protótipo. Textos entre aspas são conteúdo a reproduzir; valores em R$ e contagens são mocks iniciais.

### 1. Início (`home`)

Layout em duas colunas a partir de 1180 px (`minmax(0,1fr) 300px`); abaixo disso o aside vai para o final.

1. Saudação: "Olá, **Dra. Telma** — bom te ver por aqui." (15 px, `--ink-700`).
2. Linha de dois cards (`auto-fit, minmax(270px,1fr)`):
   - **Card Mensalidade Zero** (gradiente 150° `#063553→#0a4561`, branco, raio 20, sombra navy): label "MENSALIDADE ZERO" + badge "● ativa" (borda e texto mint); ícone escudo 38×38 em `rgba(255,255,255,.1)` + "100% coberta" (30 px/800); barra segmentada 9 px (40% mint `#3fc3a4` / 60% `#8aa3b5`); legenda "R$ 28 você · 40%", "R$ 42 patrocínio · 60%", "total R$ 70"; nota em caixa `rgba(255,255,255,.08)`: "O patrocínio do Banco parceiro cobre 60% da sua anuidade. Você só vê o valor, nunca a fatura."
   - **Card Fatura de valor · 2026** (branco, borda `--gray-200`): label + pill verde "↗ 7× o que você pagou"; "R$ 2.480" (32 px/800, `--green-700`); "já aproveitados em benefícios · você pagou R$ 336 no ano"; 3 barras de progresso (grid `20px 1fr 80px auto`): Consultório R$ 790 `#1f5d8c`, Tecnologia e IA R$ 540 `#2aa58a`, Saúde e bem-estar R$ 360 `#0b5a52` (largura = valor/900); link "ver extrato completo →" para `fatura`.
3. **Banner do Congresso** (gradiente 110° `#0b5a52→#0e7a66`): bloco de data âmbar 62×66 "26 / SET"; label "CONGRESSO APM 2026 · INSCRIÇÕES ABERTAS"; título "Medicina, IA e gestão: o consultório do futuro"; texto "Três dias, cinco trilhas — IA, gestão, comercial, marketing e ciência. Vaga com condição de associado e certificado."; CTA âmbar "Garantir minha vaga" → vira "Vaga garantida ✓" (estado persistido na sessão; segundo clique abre `evt`); link "ver programação →".
4. Seção "RECOMENDADOS PARA A SUA SITUAÇÃO": 3 cards de benefício (ids 4, 0, 5 do catálogo: Coworking médico, Escriba de IA, Antecipação de recebíveis).
5. Seção "DESTAQUES PARA VOCÊ": 3 cards fixos — Terapia online (patrocinado, "a partir de R$ 50", "Conhecer" → `ben` filtrado em Saúde), Marketing médico (novo, "diagnóstico grátis", "Saber mais" → toast "Diagnóstico solicitado. A equipe entra em contato."), Clube de vantagens (tag "oferta da semana", "cashback ativo", "Ver ofertas" → `clube`).
6. Seção "SEUS BENEFÍCIOS POR CATEGORIA" + subtítulo "Todos fazem parte do seu **Clube de benefícios APM**.": 8 tiles-botão (ícone 42×42 colorido, título 15 px, contagem 12.5 px; hover borda `#9fd3c5` + sombra verde). Ver tabela de categorias em Dados.
7. Seção "COMO FUNCIONA": painel gradiente `#e5efef→#e9f0f2`, título "Tudo acontece dentro da Minha APM", 4 passos numerados (círculo navy 26 px): Descobre / Ativa aqui / Usa / Vira valor e dado; rodapé: "Cada resgate registrado prova, em número, quanto a APM economiza para você — e sustenta o patrocínio que mantém a sua mensalidade zero."
8. **Aside "Notícias e ciência"** (card branco): link "ver todas" → `news`; chips Tudo/Notícias/Ciência; lista de até 5 notícias (thumb 62×54 hachurado, tag de tipo 10 px, título 13.5 px, fonte 11.5 px); box mint "Publique o seu trabalho" com texto "61% dos associados usam as redes para divulgar o que produzem. Submeta seu estudo à revista da APM." e botão teal "Submeter trabalho" (toast).

### 2. Meus benefícios (`ben`)

1. **Hero** (gradiente 118° `#063553 0% → #0a4561 58% → #115b58 100%`, borda superior 2 px âmbar, raio 22, padding `28px 32px`): label "CLUBE DE BENEFÍCIOS APM", h2 "Tudo o que a sua associação faz por você"; 3 estatísticas (R$ 2.480 aproveitados em 2026 · R$ 86 cashback no mês · 40+ benefícios ativos); selo "MEMBRO" com escudo à direita; forma decorativa absoluta no canto.
2. Barra de filtros: chips Tudo / Patrocinados / Novos / Ativos (ativo = fundo navy); chip removível com a categoria quando veio de um tile da home; texto "Resultados para “{q}”" quando há busca.
3. Grupos por categoria (h3 em caixa alta com o nome do grupo), cada um com grid de cards de benefício. Grupos: TECNOLOGIA E IA, CONSULTÓRIO E FINANÇAS, SAÚDE, BEM-ESTAR E PROTEÇÃO, EDUCAÇÃO E CARREIRA. Grupos vazios não aparecem.
4. Estado vazio: card "Nenhum benefício encontrado" / "Tente outro termo ou fale com a Central de Relacionamento." + botão "Limpar filtros".

### 3. Clube de vantagens (`clube`)

1. Link "‹ voltar para o início".
2. Hero: label "CLUBE DE VANTAGENS APM", h2 "Vantagens e descontos para usar todo dia", estatísticas R$ 1.240 economizados em 2026 · R$ 86 cashback → mensalidade · 30 mil parceiros.
3. **Oferta da semana**: placeholder "foto da oferta" (mono) + label "★ OFERTA DA SEMANA · TERMINA EM 3 DIAS", h3 "30% no iFood + 5% de cashback", texto "Uma nova oferta em destaque toda semana, escolhida para o seu perfil.", link-botão "Usar agora" → `https://clubapm.com.br` (nova aba).
4. Duas colunas: grupos de ofertas "PARA USAR TODA SEMANA" (Farmácias 60% + cashback, Mercado e delivery cashback 5%, Combustível cashback, Telemedicina incluso, Cinema 50%) e "RECOMENDADO PARA VOCÊ" (Viagens até 15%, Eletrônicos até 30%, Casa e decoração cashback, Moda e esporte até 25%); cada card com ícone, tag, título, descrição e link "Usar" para clubapm.com.br.
5. Aside: "Sua economia no clube" (este mês R$ 180 · em 2026 R$ 1.240 · cashback vira crédito – R$ 86 · na sua mensalidade R$ 0 este mês); "Por que usar por aqui" ("Todo resgate acontece dentro da Minha APM. Por isso ele entra na sua fatura de valor e o cashback abate a sua mensalidade, automaticamente."); "Tecnologia do clube" ("Marca APM, infraestrutura Clube Certo · 30 mil parceiros nacionais e regionais.").

### 4. Notícias e ciência (`news`)

1. Hero: label "PERSONALIZADO PARA VOCÊ", h2 "Notícias e ciência", texto "Notícias, notas, acontecimentos, trabalhos e publicações científicas, filtrados pelos temas que você escolhe seguir."; indicadores "{n} temas seguidos", "atualizado hoje", "{n} salvos".
2. Chips de tema: Todos + temas seguidos (padrão: Cardiologia, IA na saúde, Gestão & carreira, Defesa profissional, Saúde mental).
3. Lista de artigos (card horizontal: thumb com texto "imagem" em mono, 84 px no mobile / 128 px no desktop; tag de tipo colorida; h4; meta "fonte · data · tema"; botão marcador que alterna salvo, fundo mint quando salvo). Estado vazio: "Nenhum conteúdo neste tema ainda."
4. Aside: "Personalize o seu radar" (texto + botões "+ Oncologia", "+ Pediatria", "+ Telemedicina" que adicionam o tema e disparam toast "Agora você segue X"); "Salvos para depois" (lista curta com título abreviado e tipo; vazio: "Toque no marcador de um conteúdo para salvar."); "Publique o seu trabalho" (igual à home).

### 5. Fatura de valor (`fatura`)

1. Card principal: h3 "Sua fatura de valor", subtítulo "janeiro a junho de 2026 · economia comprovada item a item", total "R$ 2.480" à direita; 5 linhas (ícone, título, descrição, valor): Coworking médico (32 horas de consultório · economia vs. mercado) R$ 790 · Escriba de IA (patrocinado · valor de mercado equivalente) R$ 540 · Terapia subsidiada (4 sessões · diferença vs. preço cheio) R$ 360 · Defesa profissional e seguros (cobertura inclusa no associado) R$ 410 · Cursos e congresso (condição de associado) R$ 380; botão "Baixar PDF da fatura" (toast "PDF da fatura gerado").
2. Card secundário "Carteirinha digital" — "Seu selo de associado APM, sempre no bolso e verificável pelo paciente." + botão "+ Adicionar à Wallet" → `card`.

### 6. Comunidade (`com`)

1. "SUAS COMUNIDADES": 4 cards horizontais — Mulheres na Medicina (1.240 membros · pauta do público que mais cresce, ao vivo), Cardiologia · sua especialidade (380 membros · discussões de caso e diretrizes), Jovens médicos e residentes (920 membros · carreira, plantões e saúde mental, ao vivo), Embaixadores acadêmicos (64 faculdades · leva a APM para dentro do campus). Indicador "● ativa agora" quando `live`. Botão: "Entrar" → vira "Abrir" (verde WhatsApp `#1faa59`, com ícone de chat) e abre `wa.me` com "Olá! Quero acessar o grupo {nome} da APM."; Embaixadores usa "Saber mais" (toast).
2. "CONVERSAS EM DESTAQUE": 3 posts (avatar com iniciais, nome, "{n} respostas · há {t}", texto) — Dra. Marina S., Dr. Paulo R., Dra. Lúcia M.
3. Aside: "Rede de encaminhamento" ("Indique e receba pacientes entre associados. 320 médicos já estão na rede da sua região.", busca "Buscar especialista por área...", botão "Entrar na rede" → "Você está na rede ✓"); "Mentoria titular ↔ jovem" (texto + botões "Quero um mentor" / "Quero ser mentor", ambos toast); "Próximos encontros" (12 JUL Encontro Mulheres na Medicina · online · 19h; 20 JUL Happy hour científico · presencial · sede APM).

### 7. Congresso e eventos (`evt`)

1. Hero do Congresso: label, h2 "Medicina, IA e gestão: o consultório do futuro", texto "O maior encontro da APM ganha cinco trilhas e patrocínio âncora. Ciência de ponta, gestão e tecnologia no mesmo palco."; chips de info "26 a 28 de setembro", "São Paulo · híbrido", "certificado incluso"; CTA "Garantir minha vaga" (mesmo estado da home) + link "ver programação completa →" (apm.org.br); contador "88 dias para o congresso".
2. "TRILHAS DO CONGRESSO": 5 cards — IA na medicina (escriba, diagnóstico, ética), Gestão de consultório (finanças, equipe, processos), Comercial e captação (Doctoralia, agenda, pacientes), Marketing médico (presença digital ética), Atualização científica (consensos e novas diretrizes).
3. "AGENDA DE EVENTOS": lista em card único, linhas com bloco de data (dia/mês), título, descrição, tag Online (mint) ou Presencial (azul) e botão "Inscrever" → "Inscrito ✓" (toast "Inscrição confirmada: {título}"). Itens: 12 JUL Webinar: antibioticoterapia em 2026 (Infectologia · 19h, Online); 25 JUL VII Jornada de Dor na Mulher (Dor · parceria SOGESP, Presencial); 02 AGO Curso IESAPM: gestão de consultório (Gestão · 4 encontros, Online); 15 AGO Encontro de Cardiologia (Cardiologia · casos clínicos, Presencial).

### 8. Carteirinha digital (`card`)

Duas colunas: à esquerda a **carteirinha** (card navy com forma decorativa, logotipo APM + legenda, selo "MEMBRO"; nome "Dra. Telma Nogueira", "CRM-SP 000000 · associada desde 2014", "válida até 12/2026"; quadrado QR placeholder); à direita h2 "Sua carteirinha digital", texto "Apresente em parceiros, eventos e no consultório. O QR code permite que qualquer pessoa confirme que você é associada APM.", botões "+ Adicionar à Wallet" (toast) e "Compartilhar" (toast "Link de verificação copiado").

### 9. Onboarding acadêmico (`onb`)

Persona João (acadêmico, 100% patrocinado).

1. Hero: avatar "JS", label "BEM-VINDO À APM", h2 "Olá, João. A sua jornada começa aqui.", texto "Você é acadêmico de Medicina, e a sua associação é 100% patrocinada. Vamos ativar os seus primeiros benefícios — leva 5 minutos."; chips "mensalidade R$ 0 · patrocinada", "R$ 1.500+ em benefícios/ano", "trilha de 90 dias".
2. Card de progresso: percentual grande, "Sua ativação", "**{feitos}** de {total} passos · {R$ desbloqueados} desbloqueados", barra de progresso.
3. "SUA TRILHA DE ATIVAÇÃO · PRIMEIROS 90 DIAS": 6 cards de passo — Complete seu perfil (Concluir), Ative a TotalPass (R$ 1.200/ano, Ativar), Whitebook e Portal MBE (R$ 300/ano, Acessar), Entre na comunidade (Entrar), Garanta vaga no Congresso (R$ 690/ano, Garantir), Peça um mentor (Pedir). Passo concluído: fundo mint, borda `#bfe4d8`, tag "feito", meta "concluído", sem botão. Pendente: tag âmbar "● R$ X/ano" quando há valor, meta "passo N". O primeiro passo vem concluído por padrão.
4. "O QUE A SUA MENSALIDADE COBRE": TotalPass · academias e bem-estar R$ 1.200/ano · Portal MBE, biblioteca e cursos IESAPM R$ 300/ano · Congresso e eventos (acadêmico) R$ 690/ano · Clube de benefícios e seguros R$ 300/ano; linha "Valor para você ≈ R$ 2.490/ano"; "O que você paga: R$ 0 · o patrocinador cobre".
5. "BENEFÍCIOS QUE JÁ COMBINAM COM VOCÊ": Banco de plantões e vagas (340 vagas hoje, novo) e Cartão APM com cashback (sem anuidade, patrocinado).
6. "VOCÊ NÃO ESTÁ SOZINHO": Comunidade de jovens médicos (920 membros, → `com`), Mentoria com titulares (210 mentores, → `com`), Congresso APM 2026 (set 2026, grátis para acadêmico).
7. Botão final "Ir para a Minha APM →".

**Rodapé de todas as telas**: "Rascunho de interface (wireframe navegável) · Comunicação Encantada para a APM · fotos e dados ilustrativos" — remover na implementação real.

## Componentes

O protótipo reutiliza poucos padrões; implemente-os como componentes isolados e componha as telas a partir deles. Todos os ícones são SVG inline de linha, viewBox 24, `stroke-width 1.8`, `stroke-linecap/linejoin round`, cor `currentColor`, tamanhos 13–22 px — reproduza o conjunto de 48 paths do protótipo ou mapeie para Lucide (home, shopping-bag, gift, newspaper, receipt, user, users, calendar, credit-card, star, search, heart, megaphone, cpu, tablet, video, building, banknote, shield, graduation-cap, plus, pill, shopping-cart, fuel, film, chevron-left, bookmark, check, menu, x, message-circle, clock, map-pin, plane, tv, sofa, shirt, scale, flag, bar-chart, trending-up).

| Componente | Anatomia | Variantes / estados |
| --- | --- | --- |
| `BenefitCard` | Card branco raio 16, padding 18, coluna gap 10. Topo: ícone 44×44 em quadrado mint (`#e2f1ec`, texto `--green-700`) + `Tag` opcional à direita. h4 16.5/700. Parágrafo 14 px `--ink-500` (`flex:1`). Rodapé com borda superior `--gray-150`: meta 13 px à esquerda, botão primário à direita | Borda `#efc76b` quando `patrocinado`, senão transparente. CTA "Ativar" vira "Gerenciar" após ativação e a tag vira `ativo` (ou mantém `patrocinado`). Hover: eleva 3 px + sombra forte. Clique em "Ativar" alterna estado e dispara toast "{título} ativado"; outros CTAs disparam toast "Abrindo {título}…" |
| `Tag` | Pill 11 px/700, padding `3px 9px`, raio 999 | `patrocinado` (`#e3ebf2`/`#0a3f5f`), `novo` (`#fdebd3`/`#c46a0a`), `ativo` (`#dcefe9`/`#0e7a64`), `oferta da semana` (= patrocinado), `feito` (transparente/verde). Tipos de notícia: `ciência` mint, `publicação` roxo, `notícia` azul, `evento` âmbar, `nota` cinza (`#eceef0`/`#4b5563`) |
| `Chip` (filtro) | Botão pill 12.5 px/600, padding `6px 12px`, borda 1 px | Ativo: fundo e borda `--navy-800`, texto branco. Inativo: fundo branco, borda `#e0e6ec`, texto `--ink-700`. Usado em filtros de benefícios, temas de notícia, abas da home |
| `PrimaryButton` | Fundo `--green-600`, branco, raio 10, padding `9px 16px`, 13.5 px/700, `white-space:nowrap` | Hover `--green-600-hover`; active `scale(.97)`. Variante âmbar (Congresso): fundo `#f5a623`, texto `--ink-900`, raio 12, padding `12px 20px`, hover `brightness(1.06)`. Variante teal (`#0b5a52`) em "Submeter trabalho" |
| `SecondaryButton` | Fundo `--gray-100`, texto `--navy-800`, raio 10 | Estado confirmado: fundo `#e2f3ee`, texto `--green-700`, label com "✓" ("Inscrito ✓", "Você está na rede ✓") |
| `TextLink` | Botão sem fundo, `--green-700`, 13–13.5 px/600–700, seta "→" ou "‹" | "ver extrato completo →", "ver todas", "voltar para o início" |
| `SectionHeading` | h3 13 px/700, letter-spacing 1.3, caixa alta, `--ink-600` | Opcional subtítulo 14 px `--ink-500` abaixo |
| `HeroPanel` | Seção raio 20–22, gradiente navy ou teal, texto branco, padding `20–28px 22–32px`, `overflow:hidden`, forma decorativa absoluta | Label 11.5–12 px/700 letter-spacing 1.3 em cor muted; h2; parágrafo; linha de `StatBlock`s ou chips de info (ícone 15 px + texto); `borda-top 2px #f5b43a` na variante de benefícios |
| `StatBlock` | Valor 22–26 px/800 + label 12 px muted, empilhados | Usado em heroes (3 por hero) |
| `ProgressBar` | Trilho 6–9 px raio 99 `--gray-100`; preenchimento colorido | Variante segmentada (dois `flex` com gap 4 px) no card Mensalidade Zero; variante por item na Fatura (largura = valor/900) |
| `CategoryTile` | Botão branco raio 16, padding 18, min-height 124, ícone 42×42 com `bg`/`fg` próprios, título 15/700, contagem 12.5 `--ink-400` | Hover: eleva, borda `#9fd3c5`, sombra `0 12px 24px -14px rgba(14,143,120,.5)` |
| `NewsItem` | Thumb (62×54 na home; 84/128 px na lista) com `repeating-linear-gradient(135deg,#eef2f5 0 6px,#e5eaef 6px 12px)` ou texto "imagem" mono; `Tag` de tipo; título 13.5/700; meta 11.5 `--ink-400`; botão marcador | Marcador preenchido e fundo `#e2f3ee`/texto `--green-600` quando salvo; toast "Salvo para depois" ao salvar |
| `OfferCard` (clube) | Ícone + `Tag` de desconto, título, descrição, link "Usar" externo | Abre clubapm.com.br em nova aba |
| `CommunityCard` | Card horizontal: ícone, título, descrição, indicador "● ativa agora", botão | Botão "Entrar" (secundário) → "Abrir" (fundo `#1faa59`, branco, ícone chat) |
| `AgendaRow` | Bloco data (dia 18 px/800 + mês 10 px), título, descrição, `Tag` Online/Presencial, botão | Primeira linha sem divisor; demais com borda superior `--gray-150` |
| `StepCard` (onboarding) | `BenefitCard` com meta "passo N"/"concluído" e tag de valor | Concluído: fundo `#e2f1ec`, borda `#bfe4d8`, tag "feito", sem botão |
| `DigitalCard` | Card navy raio 20 com logotipo, selo MEMBRO, nome, CRM, validade e QR 64×64 branco | Mock: "QR" em mono; real: QR com URL de verificação pública |
| `Toast` | Fixo, centralizado horizontalmente, fundo `--ink-900`, branco, raio 12, ícone check 15 px | Auto-dismiss 2,6 s; uma mensagem por vez (nova substitui a anterior) |
| `WhatsAppFab` | Link fixo canto inferior direito, fundo `#1faa59`, ícone chat 20 px + "Central APM" | Prop `showWhatsapp` (bool) e `whatsapp` (número, padrão `551131886200`) |
| `SearchField` | Label-container `--gray-100` raio 12 altura 42, ícone lupa 17 px, input transparente 14 px, botão × 14 px quando há texto | Placeholder "Buscar benefício, parceiro, evento..." |
| `Avatar` | Círculo com iniciais, 40 px (header) / 36 px (posts) / 56 px (onboarding) | Cores por pessoa (TN `#f2d9c7`/`#8a4b2a`) |

## Dados e integrações

O protótipo é 100% client-side com dados em constantes e estado em memória; só a rota persiste em `localStorage`. Para a implementação, cada constante vira um endpoint (ou view) e cada ação local vira uma chamada ao backend. A tabela abaixo é o contrato: o nome, os campos que a tela realmente consome e a fonte provável no ambiente APM.

| Entidade | Campos consumidos pela UI | Fonte provável | Observação |
| --- | --- | --- | --- |
| `Associado` | nome de exibição ("Dra. Telma"), iniciais, nome completo, CRM + UF, ano de associação, validade da carteirinha, tipo (titular, residente, acadêmico), status de patrocínio | Dynamics 365 / Entra ID (login APM já existente) | Define a persona: acadêmico 100% patrocinado entra em `onb` por padrão |
| `Mensalidade` | valor total mensal (R$ 70), parcela do associado (R$ 28 · 40%), parcela do patrocínio (R$ 42 · 60%), patrocinador ("Banco parceiro"), status (ativa) | Dynamics 365 F&O (financeiro) | Regra do protótipo: o associado vê o valor, nunca a fatura do patrocinador |
| `FaturaDeValor` | total do período, valor pago pelo associado no ano (R$ 336), múltiplo ("7×"), itens `{icone, titulo, descricao, valor}`, agregação por área para as 3 barras da home, período ("janeiro a junho de 2026") | Cálculo próprio a partir dos resgates registrados | Exportar PDF é uma ação real a implementar |
| `Beneficio` | `id, grupo, icone, titulo, descricao, meta (custo/condição), cta, tag (patrocinado/novo/ativo/null)` | Catálogo próprio (CMS ou tabela) | 19 itens no protótipo em 4 grupos; "Ativar" registra resgate e muda estado para ativo |
| `AtivacaoBeneficio` | conjunto de ids ativos por associado | Backend próprio | Alimenta filtro "Ativos", contagem no hero e a Fatura de valor |
| `Categoria` (tiles da home) | título, ícone, contagem, cores `bg/fg`, destino (`grupo` de benefício, ou rota `com`/`clube`) | Estático / CMS | 8 tiles: Tecnologia e IA, Consultório e prática, Saúde mental e bem-estar, Finanças e proteção, Educação e carreira, Defesa e jurídico, Comunidade (→ `com`), Vida e lazer (→ `clube`) |
| `OfertaClube` | grupo, ícone, título, descrição, tag de desconto, link externo | Clube Certo (marca APM) — `clubapm.com.br` | Oferta da semana com validade; economia mensal/anual e cashback → crédito na mensalidade |
| `Noticia` | `id, tipo (ciência/publicação/notícia/evento/nota), titulo, fonte, data relativa, tema, titulo curto` | Portal MBE, revista APM, site institucional, IESAPM | 8 itens no protótipo; filtro por tema e salvar/dessalvar por associado |
| `TemaSeguido` / `Salvo` | lista de temas do associado; ids salvos | Perfil do associado | Sugestões: Oncologia, Pediatria, Telemedicina |
| `Comunidade` | ícone, nome, descrição com contagem, `live`, ingressado, tipo (grupo ou programa) | Backend próprio + WhatsApp (link `wa.me`) | Entrar registra adesão; abrir leva ao grupo. Rede de encaminhamento e mentoria são opt-ins separados |
| `Post` | iniciais, autor, "{n} respostas · {tempo}", texto, cores do avatar | Backend próprio ou feed externo | Somente leitura no protótipo |
| `Evento` | dia, mês, tipo, título, local/descrição, condição (gratuito, 40% off), modalidade (Online/Presencial), inscrito | Sistema de eventos APM | Congresso 2026: 26–28 set, híbrido, 5 trilhas, contador de dias |
| `Inscricao` | ids de eventos inscritos + flag do Congresso | Backend próprio | Toast de confirmação |
| `Onboarding` | passos `{icone, titulo, descricao, valorAnual, cta}`, concluídos, coberturas `{label, valor/ano}`, total ≈ R$ 2.490/ano | Backend próprio | 6 passos; o primeiro já concluído |
| `Carteirinha` | nome, CRM-UF, desde, validade, URL de verificação para o QR | Dynamics 365 + endpoint público de verificação | Wallet (Apple/Google) e compartilhar link |
| `Configuracao` | `whatsapp` (string, padrão 551131886200), `showWhatsapp` (bool), `animations` (bool) | Variáveis de ambiente / config | Eram props editáveis do protótipo |

**Ações da UI que precisam de backend** (hoje viram apenas toast): ativar benefício, solicitar diagnóstico de marketing, submeter trabalho, exportar PDF da fatura, entrar em comunidade, entrar na rede de encaminhamento, pedir/ser mentor, inscrever em evento, garantir vaga no Congresso, adicionar à Wallet, compartilhar carteirinha, seguir tema, salvar notícia, concluir passo de onboarding, pedir cartão APM, abrir banco de plantões.

**Analytics.** O produto promete "cada resgate vira dado": instrumente todas as ações acima com evento `{associadoId, acao, entidade, id, timestamp}` desde a primeira versão, pois a Fatura de valor e o relatório para patrocinadores dependem disso.

## Requisitos não funcionais

| Área | Requisito |
| --- | --- |
| Autenticação | Sessão via Login APM (Entra ID) já integrado em projetos anteriores da TI; todas as rotas exigem associado autenticado. A persona e o estado de patrocínio vêm do token/perfil e decidem a rota inicial (`onb` para acadêmico sem onboarding concluído, senão `home`) |
| Responsividade | Mobile-first abaixo de 900 px com drawer e bottom-nav; sem rolagem horizontal; alvos de toque ≥ 44 px (botões de menu, fechar e marcadores já seguem isso no protótipo) |
| Acessibilidade | Contraste AA em todos os pares de cor listados nos tokens (verificar `#9fb7c8` sobre navy e `#6b7a8d` sobre branco em textos pequenos); foco visível em botões e chips; `aria-pressed` em chips e marcadores; `aria-live="polite"` no toast; drawer com `role="dialog"`, foco preso e fechamento por Esc; honrar `prefers-reduced-motion` |
| Performance | Figtree carregada com `font-display: swap` e subset latin/latin-ext; ícones SVG inline (sem icon-font); listas de benefícios e notícias paginadas ou lazy quando o catálogo real crescer; imagens de notícias e ofertas com `loading="lazy"` e proporção fixa para evitar layout shift |
| Persistência local | Apenas a rota ativa em `localStorage` (`mapm.page`). Ativações, inscrições, temas e salvos ficam no backend; nunca no browser |
| Links externos | `clubapm.com.br`, `apm.org.br` e `wa.me` abrem em nova aba com `rel="noopener"` |
| Idioma e formato | pt-BR; moeda `R$ 1.240` (ponto de milhar, sem centavos quando inteiro, via `toLocaleString('pt-BR')`); meses em caixa alta de 3 letras nos blocos de data (SET, OUT, JUL) |
| Privacidade | O associado nunca vê a fatura do patrocinador, só o valor coberto; o QR da carteirinha aponta para verificação pública que expõe apenas nome, status e validade |
| Observabilidade | Log de eventos de uso (ver Analytics em Dados) desde a primeira versão; erros de chamada ao backend exibidos como toast com mensagem amigável, nunca silenciosos |

## Instruções para o Claude Code

Exporte este documento como Markdown e salve na raiz do repositório como `docs/SPEC-minha-apm.md`; referencie-o no `CLAUDE.md` do projeto com a instrução: "A interface da área do associado segue `docs/SPEC-minha-apm.md`; em dúvida de layout, cor, texto ou comportamento, a spec vence." Depois siga a ordem abaixo.

1. **Confirmar a stack.** Antes de codar, perguntar (ou ler do repositório) o framework em uso — React/Vite, Next.js ou outro — e se há Tailwind. Não introduzir biblioteca de UI pronta: os componentes são simples o bastante para serem próprios.
2. **Tokens primeiro.** Criar `tokens.css` (ou `tailwind.config`) com todas as cores, tipografia, raios, sombras e easing da seção Fundação visual. Carregar Figtree (400/500/600/700/800) e JetBrains Mono do Google Fonts com `display=swap`. Nenhum hex pode aparecer solto nos componentes.
3. **Ícones.** Criar `Icon.tsx` com o mapa de 48 paths do protótipo (ou mapear para `lucide-react` conforme a tabela de Componentes), props `name`, `size` (padrão 18) e `fill`.
4. **Shell.** Implementar `AppShell` com sidebar, header, drawer, bottom-nav, WhatsApp FAB e Toast exatamente como na seção Estrutura; roteamento pelas 9 rotas com persistência da rota em `localStorage` (`mapm.page`) e scroll ao topo na troca.
5. **Componentes.** Implementar os 20 componentes da tabela, cada um em arquivo próprio, com as variantes e estados listados. Validar `BenefitCard` e `Tag` primeiro: são usados em 6 das 9 telas.
6. **Dados mockados.** Criar `mocks/` reproduzindo as constantes do protótipo (19 benefícios, 8 notícias, 8 categorias, 9 ofertas, 4 comunidades, 3 posts, 4 eventos + Congresso, 6 passos de onboarding, 4 coberturas, 5 itens de fatura) e um `store` em memória para ativações, inscrições, temas, salvos, comunidades e passos. A camada de dados deve ter interface única (`api.ts`) para troca posterior pelo backend sem tocar na UI.
7. **Telas.** Implementar na ordem `home` → `ben` → `clube` → `news` → `fatura` → `evt` → `com` → `card` → `onb`, cada uma compondo os componentes e seguindo a lista de blocos da seção Telas, textos literais incluídos.
8. **Comportamentos.** Busca global com redirecionamento para `ben`, filtros e estados vazios, toasts de confirmação com os textos exatos, CTA que muda de rótulo após a ação (Ativar → Gerenciar, Inscrever → Inscrito ✓, Garantir minha vaga → Vaga garantida ✓, Entrar → Abrir).
9. **Animações.** Entrada de página e de cards com Web Animations API (ou CSS) nos tempos da seção Fundação visual, desligadas em `prefers-reduced-motion` e por flag de configuração.
10. **Integrações.** Só depois da UI validada contra o protótipo, substituir `mocks/` pelos endpoints da seção Dados, começando por Associado (Entra ID) e Beneficio/AtivacaoBeneficio.

**Critérios de aceite da réplica visual**

- [ ] Em 1440 px, a home exibe sidebar 248 px, header com busca e pill, duas colunas com aside de 300 px, e os 8 blocos na ordem especificada.
- [ ] Em 390 px, sidebar some, hambúrguer abre drawer com scrim, bottom-nav mostra 5 abas, busca ocupa a linha inteira e o conteúdo tem padding inferior para o bottom-nav.
- [ ] Todas as 9 rotas abrem pelo menu, pelo bottom-nav e por recarga da página (rota persistida).
- [ ] Cards `patrocinado` têm borda `#efc76b`; tags usam exatamente os pares de cor da tabela de Componentes.
- [ ] Digitar no header fora de `ben`/`news` leva a `ben` com resultados filtrados; limpar filtros restaura os 4 grupos.
- [ ] Ativar um benefício muda o CTA para "Gerenciar", a tag para `ativo`, incrementa o contador do hero e dispara o toast.
- [ ] Inscrever em evento, garantir vaga, entrar em comunidade, seguir tema e salvar notícia alteram o estado e o rótulo conforme a spec.
- [ ] Nenhuma animação roda com `prefers-reduced-motion: reduce`.
- [ ] Rodapé "Rascunho de interface…" removido; textos, moeda e datas em pt-BR.
- [ ] Lighthouse: acessibilidade ≥ 90 nas rotas `home`, `ben` e `card`.
