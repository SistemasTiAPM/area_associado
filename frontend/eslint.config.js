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
      'no-restricted-syntax': ['error', ...proibicoes],
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
    files: ['e2e/**/*.ts', '*.config.{ts,js}'],
    languageOptions: { globals: globals.node },
  },
);
