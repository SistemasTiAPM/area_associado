import { describe, expect, it } from 'vitest';
import { ApiError } from './client';
import { liberaEmDe, novaChaveIdempotencia, obterSolicitacao } from './solicitacoes';

describe('api de solicitações', () => {
  it('libera_em de 409 nao_elegivel: item de detalhes (formato do servidor), corpo ou objeto', () => {
    const doServidor = new ApiError(409, 'nao_elegivel', 'x', null, [{ campo: 'libera_em', mensagem: '2026-11-20' }]);
    expect(liberaEmDe(doServidor)?.toISOString()).toBe('2026-11-20T12:00:00.000Z');
    expect(liberaEmDe(new ApiError(409, 'nao_elegivel', 'x', null, undefined, { libera_em: '2026-12-01' }))?.getUTCDate()).toBe(1);
    expect(liberaEmDe(new ApiError(409, 'nao_elegivel', 'x', null, [{ campo: 'libera_em', mensagem: 'amanhã' }]))).toBeNull();
    expect(liberaEmDe(new ApiError(409, 'estado_invalido', 'x', null, [{ campo: 'libera_em', mensagem: '2026-11-20' }]))).toBeNull();
    expect(liberaEmDe(new Error('x'))).toBeNull();
  });

  it('chave de idempotência é UUID v4 e muda a cada formulário', () => {
    const a = novaChaveIdempotencia();
    expect(a).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(novaChaveIdempotencia()).not.toBe(a);
  });

  it('id fora do formato vira "não encontrada" sem montar URL', () => {
    expect(() => obterSolicitacao('../uso')).toThrow(ApiError);
    expect(() => obterSolicitacao('a/b')).toThrow(/Não encontramos/);
  });
});
