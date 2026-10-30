# Licenças de terceiros embutidas no build da SPA

| Componente | Origem | Licença |
|---|---|---|
| Sora (400, 500, 600, 700; subsets latin e latin-ext) | `@fontsource/sora` (Google Fonts) | SIL Open Font License 1.1 |
| JetBrains Mono (400, subset latin) | `@fontsource/jetbrains-mono` | SIL Open Font License 1.1 |
| React, React DOM, React Router | npm | MIT |

As fontes são servidas pela própria aplicação (`/static/spa/assets/`), sem CDN (ADR-0001,
ADR-0017). O texto integral das licenças acompanha os pacotes em `node_modules/@fontsource/*/LICENSE`.
Ícones são SVG próprios (`src/components/Icon.tsx`); não há biblioteca de ícones nem de UI.
