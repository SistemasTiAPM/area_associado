import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import type { Carteirinha } from '../api/carteirinha';
import { _reiniciarAnalytics, enviarFila } from '../lib/analytics';
import { fabricarSessao, montarApp, respostaJson } from '../test/utilidades';

const API = '/api/v1/carteirinha';

function carteirinha(parcial: Partial<Carteirinha> = {}): Carteirinha {
  return {
    nome: 'TELMA NOGUEIRA',
    crm: '123456',
    crm_uf: 'SP',
    num_contato: '80012345',
    tipo_associado: 'Efetivo',
    status_associativo: 'Ativo',
    membro_desde: '2014',
    verificado_em: '2026-10-17T10:00:00Z',
    revogada: false,
    url_verificacao: 'https://minha.apm.org.br/verificar/ABCDEFGHIJKLMNOPQRST',
    qr: '/api/v1/carteirinha/qr.svg',
    ...parcial,
  };
}

describe('Carteirinha digital — número, downloads e revogação (P07; RF-CA-07, RF-CA-08)', () => {
  beforeEach(() => _reiniciarAnalytics());

  it('carregando: anuncia o estado', async () => {
    montarApp('/carteirinha', fabricarSessao(), (url) => (url === API ? (new Promise(() => {}) as never) : undefined));
    expect(await screen.findByText('Carregando sua carteirinha…')).toHaveAttribute('aria-busy', 'true');
  });

  it('erro: mensagem, request_id, tentar novamente e erro_exibido', async () => {
    const usuario = userEvent.setup();
    let tentativas = 0;
    const { chamadas } = montarApp('/carteirinha', fabricarSessao(), (url) => {
      if (url !== API) return undefined;
      tentativas += 1;
      return tentativas === 1
        ? respostaJson({ erro: 'fonte_indisponivel', mensagem: 'Não conseguimos consultar seu cadastro agora.', request_id: '00112233aabbccdd' }, 503)
        : respostaJson(carteirinha());
    });
    const alerta = await waitFor(() => {
      const a = screen.getAllByRole('alert').find((el) => el.textContent?.includes('Não conseguimos consultar'));
      expect(a).toBeDefined();
      return a as HTMLElement;
    });
    expect(within(alerta as HTMLElement).getByText('00112233aabbccdd')).toBeInTheDocument();
    await usuario.click(within(alerta as HTMLElement).getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByRole('figure', { name: 'Carteirinha digital de TELMA NOGUEIRA' })).toBeInTheDocument();
    enviarFila(true);
    const eventos = chamadas
      .filter((c) => c.url === '/api/v1/uso')
      .flatMap((c) => (JSON.parse(String(c.init?.body)) as { eventos: { acao: string }[] }).eventos);
    expect(eventos).toContainEqual(expect.objectContaining({ acao: 'erro_exibido' }));
  });

  it('mostra o número de associado e os downloads de mesma origem, sem nova aba', async () => {
    montarApp('/carteirinha', fabricarSessao(), (url) => (url === API ? respostaJson(carteirinha()) : undefined));
    const cartao = await screen.findByRole('figure', { name: 'Carteirinha digital de TELMA NOGUEIRA' });
    expect(within(cartao).getByText('Associado nº 80012345')).toBeInTheDocument();
    const imagem = screen.getByRole('link', { name: 'Baixar imagem' });
    const pdf = screen.getByRole('link', { name: 'Baixar PDF' });
    expect(imagem).toHaveAttribute('href', '/api/v1/carteirinha/imagem.png');
    expect(pdf).toHaveAttribute('href', '/api/v1/carteirinha/documento.pdf');
    for (const link of [imagem, pdf]) {
      expect(link).toHaveAttribute('download');
      expect(link).not.toHaveAttribute('target');
    }
  });

  it('sem número de associado a linha não aparece', async () => {
    montarApp('/carteirinha', fabricarSessao(), (url) => (url === API ? respostaJson(carteirinha({ num_contato: null })) : undefined));
    await screen.findByRole('figure');
    expect(screen.queryByText(/Associado nº/)).toBeNull();
  });

  it('revogada: sem QR, sem compartilhar, sem downloads, com o texto e o caminho para a Central', async () => {
    const { chamadas } = montarApp('/carteirinha', fabricarSessao({ recursos: { solicitacoes: true, ajuda: true }, flags: { wallet: true } }), (url) =>
      url === API ? respostaJson(carteirinha({ revogada: true, qr: null, url_verificacao: null })) : undefined,
    );
    const cartao = await screen.findByRole('figure', { name: 'Carteirinha digital de TELMA NOGUEIRA' });
    expect(within(cartao).queryByRole('img')).toBeNull();
    expect(within(cartao).getByText('Sem validade')).toBeInTheDocument();
    expect(screen.getByText('Esta carteirinha está sem validade. Fale com a Central.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Falar com a Central' })).toHaveAttribute('href', '/ajuda');
    expect(screen.queryByRole('button', { name: 'Compartilhar' })).toBeNull();
    expect(screen.queryByRole('button', { name: /Wallet/ })).toBeNull();
    expect(screen.queryByRole('link', { name: /Baixar/ })).toBeNull();
    expect(screen.queryByRole('list', { name: 'Onde usar a carteirinha' })).toBeNull();
    expect(chamadas.some((c) => c.url.includes('qr.svg'))).toBe(false);
  });

  it('revogada sem a Ajuda pronta: texto sem link para rota em construção', async () => {
    montarApp('/carteirinha', fabricarSessao(), (url) =>
      url === API ? respostaJson(carteirinha({ revogada: true, qr: null, url_verificacao: null })) : undefined,
    );
    expect(await screen.findByText('Esta carteirinha está sem validade. Fale com a Central.')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Falar com a Central' })).toBeNull();
  });

  it('compartilhar com 409 carteirinha_revogada recarrega e passa ao estado sem validade', async () => {
    const usuario = userEvent.setup();
    let leituras = 0;
    montarApp('/carteirinha', fabricarSessao(), (url) => {
      if (url === API) {
        leituras += 1;
        return respostaJson(leituras === 1 ? carteirinha() : carteirinha({ revogada: true, qr: null, url_verificacao: null }));
      }
      if (url === '/api/v1/carteirinha/compartilhar')
        return respostaJson({ erro: 'carteirinha_revogada', mensagem: 'Esta carteirinha está sem validade.', request_id: null }, 409);
      return undefined;
    });
    await usuario.click(await screen.findByRole('button', { name: 'Compartilhar' }));
    expect(await screen.findByText('Esta carteirinha está sem validade. Fale com a Central.')).toBeInTheDocument();
    expect(leituras).toBe(2);
  });
});
