// Fontes self-hosted (P-14): só os subsets latin e latin-ext, font-display swap.
import '@fontsource/figtree/latin-400.css';
import '@fontsource/figtree/latin-ext-400.css';
import '@fontsource/figtree/latin-500.css';
import '@fontsource/figtree/latin-ext-500.css';
import '@fontsource/figtree/latin-600.css';
import '@fontsource/figtree/latin-ext-600.css';
import '@fontsource/figtree/latin-700.css';
import '@fontsource/figtree/latin-ext-700.css';
import '@fontsource/figtree/latin-800.css';
import '@fontsource/figtree/latin-ext-800.css';
import '@fontsource/jetbrains-mono/latin-400.css';
import './styles/tokens.css';
import './styles/base.css';
import './styles/shell.css';
import './styles/paginas.css';
import './styles/motion.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import { instalarEnvioAoSair } from './lib/analytics';

const raiz = document.getElementById('raiz');
if (!raiz) throw new Error('Elemento #raiz ausente do index.html');

instalarEnvioAoSair();
createRoot(raiz).render(
  <StrictMode>
    <BrowserRouter basename="/area" future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
