import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { _reiniciarCampanha, capturarCampanha, consumirCampanha, lerCampanha } from './campanha';

describe('campanha (TI-11): catálogo fechado, leitura única, URL limpa', () => {
  beforeEach(() => {
    _reiniciarCampanha();
    window.history.replaceState(null, '', '/area/beneficios/x');
  });

  afterEach(() => {
    _reiniciarCampanha();
  });

  it('valida utm_* e gatilho e normaliza caixa', () => {
    expect(lerCampanha('?utm_source=RD&utm_medium=e-mail&utm_campaign=Boas_Vindas&g=a03')).toEqual({
      origem: 'rd',
      meio: 'e-mail',
      campanha: 'boas_vindas',
      gatilho: 'A03',
    });
  });

  it('descarta valor fora do catálogo sem derrubar os demais', () => {
    expect(lerCampanha('?utm_source=rd%20station&g=A21&utm_medium=email')).toEqual({ meio: 'email' });
    expect(lerCampanha('?utm_source=' + 'a'.repeat(33))).toBeNull();
    expect(lerCampanha('?utm_source=javascript:alert(1)')).toBeNull();
    expect(lerCampanha('?utm_source=//evil.com')).toBeNull();
    expect(lerCampanha('?g=A0')).toBeNull();
    expect(lerCampanha('?q=cardio&next=//evil')).toBeNull();
    expect(lerCampanha('')).toBeNull();
  });

  it('captura uma vez, remove só os parâmetros de campanha da URL e preserva o resto', () => {
    window.history.replaceState(null, '', '/area/beneficios/x?q=cardio&utm_source=rd&g=A03&utm_medium=x#topo');
    expect(capturarCampanha()).toEqual({ origem: 'rd', meio: 'x', gatilho: 'A03' });
    expect(window.location.pathname + window.location.search + window.location.hash).toBe(
      '/area/beneficios/x?q=cardio#topo',
    );
    // Segunda leitura não volta à URL (já limpa) nem inventa nada.
    window.history.replaceState(null, '', '/area?utm_source=outra');
    expect(capturarCampanha()).toEqual({ origem: 'rd', meio: 'x', gatilho: 'A03' });
  });

  it('remove da URL até o parâmetro inválido (não fica lixo no histórico)', () => {
    window.history.replaceState(null, '', '/area?utm_source=rd%20x&g=zz');
    expect(capturarCampanha()).toBeNull();
    expect(window.location.search).toBe('');
  });

  it('consumir entrega uma vez e esquece', () => {
    window.history.replaceState(null, '', '/area?g=A01');
    expect(consumirCampanha()).toEqual({ gatilho: 'A01' });
    expect(consumirCampanha()).toBeNull();
  });
});
