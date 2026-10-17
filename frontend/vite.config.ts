/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// A SPA é servida pelo FastAPI: index.html em /area/*, assets em /static/spa/
// (ADR-0001). Nada de CDN, nada inline (ADR-0013).
export default defineConfig({
  base: '/static/spa/',
  plugins: [react()],
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    emptyOutDir: true,
    sourcemap: false,
    // 0 = nunca embutir asset como data: URI. Fonte em data: violaria
    // `font-src 'self'`; manter tudo como arquivo com hash e cache imutável.
    assetsInlineLimit: 0,
    modulePreload: { polyfill: false },
    chunkSizeWarningLimit: 250,
  },
  server: {
    // Desenvolvimento local: o backend roda em :8000 (uvicorn/compose override).
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/static/favicon-32.png': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
    unstubGlobals: true,
  },
});
