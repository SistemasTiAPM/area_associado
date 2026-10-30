import { describe, expect, it } from 'vitest';
import { MENSAGEM_CENTRAL, urlExternaSegura, urlTelefone, urlWhatsapp } from './links';

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

describe('telefone (RF-AJ-02: `tel:` na allowlist de esquemas)', () => {
  it.each([
    ['tel:+551131886200', 'tel:+551131886200'],
    ['TEL:1131886200', 'tel:1131886200'],
    ['08007701234', 'tel:08007701234'],
  ])('aceita %s', (entrada, esperado) => {
    expect(urlTelefone(entrada)).toBe(esperado);
  });

  it.each(['tel:+55 11 3188-6200', 'tel:1131886200;ext=2', 'tel:abc', 'javascript:alert(1)', 'tel:123', 'tel:+1234567890123456', 'sms:1131886200', ''])(
    'recusa %s',
    (entrada) => {
      expect(urlTelefone(entrada)).toBeNull();
    },
  );
});
