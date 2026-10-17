import { describe, expect, it } from 'vitest';
import { MENSAGEM_CENTRAL, urlExternaSegura, urlWhatsapp } from './links';

describe('links externos (RF-SH-12)', () => {
  it.each([
    'javascript:alert(1)',
    'http://clubapm.com.br',
    'data:text/html,oi',
    'https://evil.example.com',
    'https://clubapm.com.br.evil.com/',
    'https://user:senha@clubapm.com.br/',
    '//clubapm.com.br',
    'não é url',
  ])('recusa %s', (url) => {
    expect(urlExternaSegura(url)).toBeNull();
  });

  it('aceita https em host permitido', () => {
    expect(urlExternaSegura('https://clubapm.com.br/oferta?x=1')).toBe('https://clubapm.com.br/oferta?x=1');
    expect(urlExternaSegura('https://WA.ME/551131886200')).toBe('https://wa.me/551131886200');
  });

  it('monta o link da Central com a mensagem codificada', () => {
    const url = urlWhatsapp('551131886200', MENSAGEM_CENTRAL);
    expect(url).toMatch(/^https:\/\/wa\.me\/551131886200\?text=Ol%C3%A1/);
  });

  it('recusa número de WhatsApp malformado', () => {
    expect(urlWhatsapp('11 3188-6200', 'x')).toBeNull();
    expect(urlWhatsapp('0551131886200', 'x')).toBeNull();
  });
});
