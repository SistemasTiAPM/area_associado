# ADR-0017: Mockups da agência como referência visual da Minha APM

- **Status:** Aceita
- **Data:** 2026-10-20
- **Decisores:** Sistemas TI (William) · Claude Code (Vitrine/Sentinela)
- **Relacionadas:** ADR-0001, ADR-0011, ADR-0013

## Contexto

A agência entregou 12 mockups HTML (`login`, `painel`, `beneficios`, `clube`, `servicos`,
`ciencia`, `defesa`, `eventos`, `relacionamento`, `financeiro`, `carteirinha`, `onboarding`,
`perfil` — `*.dc.html`), com outra linguagem visual: fonte Sora, paleta `#004165`/`#00675A`/
`#009581`, trilho lateral em pílula de "vidro" (`backdrop-filter`), cabeçalho em degradê que se
dissolve sobre o conteúdo, fundo com campos de cor e cards translúcidos. A `docs/SPEC-minha-apm.md`
descrevia outra "Fundação visual" (Figtree, sidebar navy sólida, cards brancos), e o CLAUDE.md
(regra 13) dizia que a spec vence em UI.

Os mockups não são implementáveis como estão: estilo inline em todo elemento, fonte do Google
Fonts, filtro SVG de refração injetado por JavaScript (`#lg-refract`), fundo sorteado por JS,
fotos de banco de imagens e números ilustrativos (R$ 1.842, "4 de 40 benefícios", parcelas da
anuidade) apresentados como reais.

## Decisão

1. **Os mockups da agência passam a ser a referência visual** (cor, tipografia, forma,
   superfície e movimento). A spec continua valendo para **estrutura, conteúdo e comportamento**
   (rotas, menu, regras, contratos de API, flags). Em conflito com segurança, vence a Sentinela.
2. A linguagem é traduzida para o projeto assim:
   - Sora self-hosted (`@fontsource/sora`, OFL) no lugar da Figtree, na SPA e na landing;
   - paleta do mockup em `frontend/src/styles/tokens.css`, com variantes `-texto` para os pares
     que falham em WCAG AA (branco sobre `#009581` = 3,74 → texto em `#00675A`);
   - "vidro" com `backdrop-filter: blur() saturate()` e base branca translúcida (garante
     contraste); **sem** o filtro de refração SVG (exigia JS e só funciona no Chromium);
   - fundo com campos de cor **estáticos** em CSS, sem JavaScript;
   - menu em trilho de pílula com **ícone + nome** (variante `railLabels` do mockup);
   - cabeçalho em degradê com máscara; o `h1` continua sendo o título da rota (foco e leitores
     de tela), com sobretítulo e uma chamada editorial por rota (`rotas.ts`);
   - entrada de página em 520 ms com intervalo de 90 ms, desligada em `prefers-reduced-motion`
     e pela flag `animations`; sem count-up de números.
3. **Nenhum número, valor ou recomendação ilustrativa do mockup chega ao associado** (regra 19,
   REQUISITOS LA-14). Telas sem fonte de dados ficam "em construção" ou atrás de flag. Sem sino de
   notificações até existir fonte. Textos com gênero ("associada") viram neutros (LA-19).
4. Fotos do mockup só entram quando a Comunicação entregar os arquivos com direito de uso (P-38);
   até lá, gradientes e formas decorativas em CSS.

## Consequências

### Positivas
- Uma linguagem visual única entre landing (`/`) e área (`/area`), aprovada pela agência.
- A conformidade de segurança se mantém: CSP sem inline, sem CDN, sem JS de enfeite.

### Negativas / riscos
- `backdrop-filter` pesa em aparelhos fracos; há fallback opaco onde não é suportado.
- A landing (Jinja) mantém uma cópia comentada dos tokens em `app/static/entrada.css`; mudar a
  paleta exige mudar os dois arquivos.
- A seção "Fundação visual" da spec fica histórica; quem consultar a spec precisa seguir o aviso
  para este ADR e para `tokens.css`.

### Obrigações decorrentes
- Telas novas (fases 3 a 8) seguem o mockup correspondente, com a mesma tradução (item 2).
- P-38: fotos e números do mockup só com arquivo/fonte entregues.
- P-39: os `*.dc.html` e os assets entram no repositório (`docs/mockups/`) para servir de
  referência versionada.
- e2e: axe mede o estado final (espera o fim das animações).

## Alternativas descartadas
- **Manter a "Fundação visual" da spec:** o usuário escolheu o mockup como referência.
- **Copiar o HTML do mockup:** violaria a CSP (estilo inline, Google Fonts, JS de refração) e
  mostraria dados falsos como reais.
- **Trilho só com ícones (padrão do mockup):** com 11 itens, a identificação por ícone fica
  difícil; o usuário escolheu ícone + nome.
