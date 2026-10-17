import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Perfil } from '../api/perfil';
import { fabricarSessao, montarApp, respostaJson } from '../test/utilidades';

function perfil(parcial: Partial<Perfil> = {}): Perfil {
  return {
    nome: 'TELMA NOGUEIRA', email: 'telma@exemplo.org', celular: '(11) 91234-5678', telefone: null, telefone2: null,
    endereco: { logradouro: 'Rua A', numero: '10', complemento: null, bairro: 'Centro', cidade: 'São Paulo', uf: 'SP', cep: '01000-000' },
    num_contato: '80012345', crm: '123456', crm_uf: 'SP', tipo_associado: 'Efetivo', status_associativo: 'Ativo',
    data_filiacao: '2014-03-01', tem_foto: false, foto_versao: null, atualizado_em: '2026-10-17T10:00:00Z',
    desatualizado: false, email_exige_reautenticacao: false, ...parcial,
  };
}

const corpo = (init: RequestInit | undefined) => JSON.parse(String(init?.body ?? '{}')) as Record<string, unknown>;
const cabecalho = (init: RequestInit | undefined, nome: string) => (init?.headers as Record<string, string>)[nome];

describe('Meu perfil (RF-PE)', () => {
  afterEach(() => vi.useRealTimers());

  it('mostra cadastro somente leitura e aviso de dados desatualizados', async () => {
    montarApp('/perfil', fabricarSessao(), (url) =>
      url === '/api/v1/perfil' ? respostaJson(perfil({ desatualizado: true })) : undefined);
    expect(await screen.findByText('TELMA NOGUEIRA')).toBeInTheDocument();
    expect(screen.getByText('123456 · SP')).toBeInTheDocument();
    expect(screen.getByText('01/03/2014')).toBeInTheDocument();
    expect(screen.getByText(/Não conseguimos consultar seu cadastro agora/)).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'Nome' })).toBeNull(); // nome não é editável
  });

  it('salva só os campos alterados, com CSRF, e mostra erro no campo', async () => {
    const usuario = userEvent.setup();
    let envio: Record<string, unknown> | null = null;
    montarApp('/perfil', fabricarSessao(), (url, init) => {
      if (url === '/api/v1/perfil') return respostaJson(perfil());
      if (url === '/api/v1/perfil/contato') {
        envio = corpo(init);
        expect(cabecalho(init, 'X-CSRF-Token')).toBe('token-csrf-teste');
        return respostaJson({ erro: 'entrada_invalida', mensagem: 'Confira os dados.', request_id: 'abc',
          detalhes: [{ campo: 'telefone', mensagem: 'telefone inválido: use DDD + número' }] }, 400);
      }
      return undefined;
    });
    const telefone = await screen.findByLabelText('Telefone (opcional)');
    await usuario.type(telefone, '123');
    await usuario.click(screen.getByRole('button', { name: 'Salvar alterações' }));
    await waitFor(() => expect(envio).toEqual({ telefone: '123' }));
    expect(await screen.findByText('telefone inválido: use DDD + número')).toBeInTheDocument();
    expect(telefone).toHaveAttribute('aria-invalid', 'true');
    expect(telefone.getAttribute('aria-describedby')).toContain('telefone-erro');
  });

  it('troca de e-mail sem login recente pede confirmação de identidade', async () => {
    const usuario = userEvent.setup();
    montarApp('/perfil', fabricarSessao(), (url) =>
      url === '/api/v1/perfil' ? respostaJson(perfil({ email_exige_reautenticacao: true })) : undefined);
    await usuario.click(await screen.findByRole('button', { name: 'Alterar e-mail' }));
    expect(screen.getByRole('link', { name: 'Confirmar minha identidade' })).toHaveAttribute(
      'href', '/auth/login?reauth=1&next=%2Farea%2Fperfil');
  });

  it('troca de e-mail com código: pede, confirma e atualiza', async () => {
    const usuario = userEvent.setup();
    montarApp('/perfil', fabricarSessao(), (url, init) => {
      if (url === '/api/v1/perfil') return respostaJson(perfil());
      if (url === '/api/v1/perfil/email') {
        expect(corpo(init)).toEqual({ email: 'nova@exemplo.org' });
        return respostaJson({ enviado_para: 'n***@exemplo.org', expira_em: '2026-10-17T10:10:00Z', codigo_teste: '123456' }, 202);
      }
      if (url === '/api/v1/perfil/email/confirmar') {
        expect(corpo(init)).toEqual({ email: 'nova@exemplo.org', codigo: '123456' });
        return respostaJson(perfil({ email: 'nova@exemplo.org' }));
      }
      return undefined;
    });
    await usuario.click(await screen.findByRole('button', { name: 'Alterar e-mail' }));
    await usuario.type(screen.getByLabelText('Novo e-mail'), 'nova@exemplo.org');
    await usuario.click(screen.getByRole('button', { name: 'Enviar código' }));
    expect(await screen.findByText('n***@exemplo.org')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reenviar código \(\d+s\)/ })).toBeDisabled();
    await usuario.type(screen.getByLabelText('Código'), '12a3456');
    expect(screen.getByLabelText('Código')).toHaveValue('123456');
    await usuario.click(screen.getByRole('button', { name: 'Confirmar' }));
    expect(await screen.findByText('nova@exemplo.org')).toBeInTheDocument();
  });
});

describe('Carteirinha digital (RF-CA)', () => {
  const dados = {
    nome: 'TELMA NOGUEIRA', crm: '123456', crm_uf: 'SP', num_contato: '80012345', tipo_associado: 'Efetivo',
    status_associativo: 'Ativo', membro_desde: '2014', verificado_em: '2026-10-17T10:00:00Z',
    url_verificacao: 'https://associado.apm.org.br/verificar/ABCDEFGHIJKLMNOPQRST', qr: '/api/v1/carteirinha/qr.svg',
  };
  const rotas = (url: string) => {
    if (url === '/api/v1/carteirinha') return respostaJson(dados);
    if (url === '/api/v1/carteirinha/compartilhar') return respostaJson({ url: dados.url_verificacao });
    return undefined;
  };

  it('mostra o cartão da spec, sem validade e sem Wallet com a flag desligada', async () => {
    montarApp('/carteirinha', fabricarSessao(), rotas);
    const cartao = await screen.findByRole('figure', { name: 'Carteirinha digital de TELMA NOGUEIRA' });
    expect(within(cartao).getByText('CRM-SP 123456 · na APM desde 2014')).toBeInTheDocument();
    expect(within(cartao).getByRole('img', { name: /QR code/ })).toHaveAttribute('src', '/api/v1/carteirinha/qr.svg');
    expect(screen.queryByText(/válida até/)).toBeNull();
    expect(screen.queryByRole('button', { name: /Wallet/ })).toBeNull();
  });

  it('Compartilhar copia o link; sem área de transferência mostra para cópia manual', async () => {
    const usuario = userEvent.setup();
    const escrever = vi.fn(async () => undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: escrever }, configurable: true });
    const { unmount } = montarApp('/carteirinha', fabricarSessao({ flags: { wallet: true } }), rotas);
    expect(await screen.findByRole('button', { name: '+ Adicionar à Wallet' })).toBeInTheDocument();
    await usuario.click(screen.getByRole('button', { name: 'Compartilhar' }));
    await waitFor(() => expect(escrever).toHaveBeenCalledWith(dados.url_verificacao));
    expect(await screen.findByText('Link de verificação copiado')).toBeInTheDocument();
    unmount();

    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true });
    montarApp('/carteirinha', fabricarSessao(), rotas);
    await usuario.click(await screen.findByRole('button', { name: 'Compartilhar' }));
    expect(await screen.findByLabelText('Copie o link de verificação')).toHaveValue(dados.url_verificacao);
  });
});
