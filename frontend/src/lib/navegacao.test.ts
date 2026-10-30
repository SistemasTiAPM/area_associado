import { describe, expect, it, vi } from 'vitest';
import { destinoSeguro, navegarSeguro } from './navegacao';

/** TI-10 / P-40 (GHSA-wrjc-x8rr-h8h6): só rotas conhecidas da Minha APM viram destino. */
describe('destinoSeguro', () => {
  it.each([
    '/',
    '/perfil',
    '/ajuda',
    '/solicitacoes',
    '/solicitacoes/0f8c2a8e-4b1d-4c55-9d2e-1a2b3c4d5e6f',
    '/beneficios/escola-de-idiomas',
    '/beneficios?q=idiomas%20online',
    '/perfil#contato',
  ])('aceita %s', (destino) => {
    expect(destinoSeguro(destino)).toBe(destino);
  });

  it.each([
    ['barra invertida', '/\\evil.com'],
    ['barra invertida no meio', '/perfil\\..\\x'],
    ['protocolo relativo', '//evil.com'],
    ['esquema', 'https://evil.com'],
    ['javascript', 'javascript:alert(1)'],
    ['relativo sem barra', 'perfil'],
    ['controle', '/perfil\n'],
    ['tab', '/per\tfil'],
    ['espaço', '/perfil x'],
    ['separador Unicode', `/perfil${String.fromCharCode(0x2028)}`],
    ['codificado', '/%5Cevil.com'],
    ['barra codificada', '/%2F%2Fevil.com'],
    ['ponto-ponto', '/solicitacoes/..'],
    ['barra dupla no meio', '/solicitacoes//x'],
    ['rota desconhecida', '/admin'],
    ['basename repetido', '/area/perfil'],
    ['sub-rota em rota sem sub-rota', '/perfil/abc'],
    ['dois segmentos', '/solicitacoes/a/b'],
    ['consulta com barra invertida', '/beneficios?q=\\x'],
    ['vazio', ''],
    ['grande demais', `/beneficios?q=${'a'.repeat(600)}`],
  ])('recusa %s', (_nome, destino) => {
    expect(destinoSeguro(destino)).toBeNull();
  });

  it('recusa o que não é texto', () => {
    expect(destinoSeguro(undefined)).toBeNull();
    expect(destinoSeguro(null)).toBeNull();
    expect(destinoSeguro({ pathname: '/perfil' })).toBeNull();
  });
});

describe('navegarSeguro', () => {
  it('navega só para destino aprovado e avisa a recusa no console', () => {
    const navegar = vi.fn();
    const erro = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    expect(navegarSeguro(navegar, '/solicitacoes/abc', { replace: true })).toBe(true);
    expect(navegar).toHaveBeenCalledWith('/solicitacoes/abc', { replace: true });
    expect(navegarSeguro(navegar, '/\\evil.com')).toBe(false);
    expect(navegar).toHaveBeenCalledTimes(1);
    expect(erro).toHaveBeenCalledTimes(1);
  });
});
