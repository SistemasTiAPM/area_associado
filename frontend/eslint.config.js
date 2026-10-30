import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

// Regras de segurança do projeto (CLAUDE.md 13, 15; RNF-21) como lint:
// o build falha se alguém introduzir estilo inline, HTML cru, link externo
// sem o componente seguro ou armazenamento local de dados.
const proibicoes = [
  {
    selector: "JSXAttribute[name.name='style']",
    message: "Estilo inline é proibido (CSP style-src 'self', ADR-0013). Use classe CSS ou custom property via CSSOM.",
  },
  {
    selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
    message: 'HTML cru é proibido: o React já escapa o conteúdo.',
  },
  {
    selector: "JSXOpeningElement[name.name='a'] > JSXAttribute[name.name='target']",
    message: 'Link em nova aba só pelo componente <LinkExterno> (noopener, noreferrer e allowlist de host).',
  },
];

// TI-10 / P-40 (GHSA-wrjc-x8rr-h8h6): destino de navegação montado em tempo de execução
// só passa por `destinoSeguro` (lib/navegacao.ts). Literal (`to="/perfil"`) continua livre.
const navegacaoInsegura = {
  selector:
    "JSXOpeningElement[name.name=/^(Link|NavLink|Navigate)$/] > JSXAttribute[name.name='to'] > JSXExpressionContainer",
  message:
    'Destino variável em <Link>/<NavLink>/<Navigate> só por <LinkInterno> ou useNavegarSeguro (lib/navegacao.ts; TI-10, P-40).',
};

const SEM_ROUTER_6 = {
  name: 'react-router-dom',
  message: 'Use `react-router` 7 (P-40): o pacote react-router-dom saiu do projeto.',
};

const NAVEGACAO_PROGRAMATICA = {
  name: 'react-router',
  importNames: ['useNavigate', 'Navigate', 'redirect', 'redirectDocument', 'replace'],
  message: 'Navegação programática só por useNavegarSeguro/navegarSeguro (lib/navegacao.ts; TI-10, P-40).',
};

/**
 * Exceções da regra de navegação: o módulo seguro, o link seguro e o shell (menu,
 * barra inferior e busca montam destinos a partir de `rotas.ts`, não de dado do usuário).
 */
const EXCECOES_NAVEGACAO = ['src/lib/navegacao.ts', 'src/components/LinkInterno.tsx', 'src/shell/**/*.{ts,tsx}'];

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'playwright-report', 'test-results'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'error',
      'no-restricted-syntax': ['error', ...proibicoes, navegacaoInsegura],
      'no-restricted-imports': ['error', { paths: [SEM_ROUTER_6, NAVEGACAO_PROGRAMATICA] }],
      'no-restricted-globals': [
        'error',
        { name: 'localStorage', message: 'Nada de dado do associado no navegador (RNF-21).' },
        { name: 'sessionStorage', message: 'Nada de dado do associado no navegador (RNF-21).' },
        { name: 'indexedDB', message: 'Nada de dado do associado no navegador (RNF-21).' },
      ],
      'no-restricted-properties': [
        'error',
        { object: 'window', property: 'localStorage', message: 'RNF-21' },
        { object: 'window', property: 'sessionStorage', message: 'RNF-21' },
        { object: 'document', property: 'cookie', message: 'O cookie de sessão é httponly; não manipular cookies no cliente.' },
      ],
      'no-empty': ['error', { allowEmptyCatch: false }],
      'no-console': ['error', { allow: ['error'] }],
      eqeqeq: ['error', 'always'],
      '@typescript-eslint/no-explicit-any': 'error',
    },
  },
  {
    files: EXCECOES_NAVEGACAO,
    rules: {
      'no-restricted-syntax': ['error', ...proibicoes],
      'no-restricted-imports': ['error', { paths: [SEM_ROUTER_6] }],
    },
  },
  {
    files: ['e2e/**/*.ts', '*.config.{ts,js}'],
    languageOptions: { globals: globals.node },
  },
);
