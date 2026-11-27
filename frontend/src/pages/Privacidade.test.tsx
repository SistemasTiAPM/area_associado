import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Consentimento, PedidosTitular, Pergunta, Preferencias } from '../api/privacidade';
import { fabricarSessao, montarApp, respostaJson, type Rotas } from '../test/utilidades';

const PERFIL = {
  nome: 'TELMA NOGUEIRA', email: 'telma@exemplo.org', celular: '(11) 91234-5678', telefone: null, telefone2: null,
  endereco: null, num_contato: '80012345', crm: '123456', crm_uf: 'SP', tipo_associado: 'Efetivo',
  status_associativo: 'Ativo', data_filiacao: '2014-03-01', tem_foto: false, foto_versao: null,
  atualizado_em: '2026-10-17T10:00:00Z', desatualizado: false, email_exige_reautenticacao: false,
  edicao_disponivel: false, endereco_disponivel: false,
};

const OPCOES: Preferencias['opcoes'] = {
  atuacao: [{ valor: 'consultorio_proprio', rotulo: 'Consultório próprio' }, { valor: 'hospital', rotulo: 'Hospital' }],
  temas: [{ valor: 'tecnologia_ia', rotulo: 'Tecnologia e IA' }, { valor: 'comunidade', rotulo: 'Comunidade' }],
  canal_preferido: [{ valor: 'email', rotulo: 'E-mail' }],
  frequencia: [{ valor: 'normal', rotulo: 'Todas as novidades' }, { valor: 'minima', rotulo: 'Só o essencial' }],
  fonte: [{ valor: 'padrao', rotulo: 'Padrão' }, { valor: 'grande', rotulo: 'Grande' }, { valor: 'maior', rotulo: 'Maior' }],
};

function preferencias(parcial: Partial<Preferencias> = {}): Preferencias {
  return {
    tratamento: null, atuacao: [], temas: [], canal_preferido: null, frequencia: null, fonte: 'padrao', atualizado_em: null,
    faltam: ['tratamento', 'atuacao', 'temas', 'frequencia'], opcoes: OPCOES, ...parcial,
  };
}

const PERGUNTA: Pergunta = {
  chave: 'atuacao', titulo: 'Onde você atua?', ajuda: 'Com isso, mostramos primeiro o que faz sentido para a sua rotina.',
  tipo: 'multipla', opcoes: OPCOES.atuacao, maximo: null,
};

function consentimento(parcial: Partial<Consentimento> = {}): Consentimento {
  return {
    finalidade: 'ofertas_parceiros', canal: 'email', titulo: 'Ofertas de parceiros por e-mail',
    texto: 'Autorizo a APM a me enviar ofertas de parceiros por e-mail.', versao: 'v0', concedido: false,
    versao_registrada: null, registrado_em: null, texto_mudou: false, historico: [], ...parcial,
  };
}

function pedidos(parcial: Partial<PedidosTitular> = {}): PedidosTitular {
  return { itens: [], exportacao_disponivel_em: null, exclusao_aberta: null, exige_reautenticacao: false, ...parcial };
}

const corpo = (init: RequestInit | undefined) => JSON.parse(String(init?.body ?? '{}')) as Record<string, unknown>;
const cabecalho = (init: RequestInit | undefined, nome: string) => (init?.headers as Record<string, string>)[nome];
const metodo = (init: RequestInit | undefined) => init?.method ?? 'GET';

const SO_PREFERENCIAS = fabricarSessao({
  recursos: { solicitacoes: true, ajuda: true, privacidade: true }, flags: { perfil_preferencias: true },
});
const SO_LGPD = fabricarSessao({
  recursos: { solicitacoes: true, ajuda: true, privacidade: true }, flags: { lgpd_consentimentos: true },
});

/** Perfil do CRM sempre responde; `extra` cobre as rotas de P13 do teste. */
function rotas(extra: Rotas): Rotas {
  return (url, init) => (url === '/api/v1/perfil' ? respostaJson(PERFIL) : extra(url, init));
}

afterEach(() => {
  delete document.documentElement.dataset.fonte;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Perfil e privacidade (P13)', () => {
  it('flags desligadas ou migração ausente: tela de sempre, nenhuma chamada de P13', async () => {
    const semMigracao = fabricarSessao({ flags: { perfil_preferencias: true, lgpd_consentimentos: true } });
    for (const sessao of [fabricarSessao(), semMigracao]) {
      const { chamadas, unmount } = montarApp('/perfil', sessao, rotas(() => undefined));
      expect(await screen.findByText('TELMA NOGUEIRA')).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 1, name: 'Meu perfil' })).toBeInTheDocument();
      for (const titulo of ['Sobre você', 'Tamanho do texto', 'Autorizações', 'Seus dados', 'Complete seu perfil']) {
        expect(screen.queryByRole('heading', { name: titulo })).toBeNull();
      }
      expect(chamadas.filter((c) => c.url.startsWith('/api/v1/perfil/'))).toEqual([]);
      unmount();
    }
  });

  it('uma flag não mostra as seções da outra', async () => {
    montarApp('/perfil', SO_PREFERENCIAS, rotas((url) => {
      if (url === '/api/v1/perfil/preferencias') return respostaJson(preferencias({ faltam: [] }));
      return undefined;
    }));
    expect(await screen.findByRole('heading', { name: 'Sobre você' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Perfil e privacidade' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Autorizações' })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Seus dados' })).toBeNull();
    // Perfil completo: nada de "Complete seu perfil" (nem a chamada da pergunta).
    expect(screen.queryByRole('heading', { name: 'Complete seu perfil' })).toBeNull();
  });

  it('complete seu perfil: uma pergunta por visita, respondida some e atualiza o formulário', async () => {
    const usuario = userEvent.setup();
    let resposta: Record<string, unknown> | undefined;
    let buscas = 0;
    montarApp('/perfil', SO_PREFERENCIAS, rotas((url, init) => {
      if (url === '/api/v1/perfil/preferencias') return respostaJson(preferencias());
      if (url === '/api/v1/perfil/pergunta') {
        buscas += 1;
        return respostaJson({ pergunta: PERGUNTA });
      }
      if (url === '/api/v1/perfil/pergunta/atuacao') {
        resposta = corpo(init);
        expect(cabecalho(init, 'X-CSRF-Token')).toBe('token-csrf-teste');
        return respostaJson(preferencias({ atuacao: ['hospital'], atualizado_em: '2026-11-19T12:00:00Z',
          faltam: ['tratamento', 'temas', 'frequencia'] }));
      }
      return undefined;
    }));
    const bloco = (await screen.findByRole('heading', { name: 'Complete seu perfil' })).closest('section') as HTMLElement;
    const grupo = within(bloco).getByRole('group', { name: 'Onde você atua?' });
    expect(within(bloco).getByRole('button', { name: 'Salvar resposta' })).toBeDisabled();
    await usuario.click(within(grupo).getByLabelText('Hospital'));
    await usuario.click(within(bloco).getByRole('button', { name: 'Salvar resposta' }));
    await waitFor(() => expect(resposta).toEqual({ resposta: ['hospital'] }));
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Complete seu perfil' })).toBeNull());
    // O formulário de baixo já mostra a resposta; a próxima pergunta fica para a outra visita.
    const sobre = screen.getByRole('heading', { name: 'Sobre você' }).closest('section') as HTMLElement;
    expect(within(sobre).getByLabelText('Hospital')).toBeChecked();
    expect(buscas).toBe(1);
  });

  it('pergunta pulada some sem gravar resposta', async () => {
    const usuario = userEvent.setup();
    let envio: Record<string, unknown> | undefined;
    montarApp('/perfil', SO_PREFERENCIAS, rotas((url, init) => {
      if (url === '/api/v1/perfil/preferencias') return respostaJson(preferencias());
      if (url === '/api/v1/perfil/pergunta') return respostaJson({ pergunta: PERGUNTA });
      if (url === '/api/v1/perfil/pergunta/atuacao') {
        envio = corpo(init);
        return respostaJson(preferencias());
      }
      return undefined;
    }));
    await usuario.click(await screen.findByRole('button', { name: 'Responder depois' }));
    await waitFor(() => expect(envio).toEqual({ pular: true }));
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Complete seu perfil' })).toBeNull());
  });

  it('salva só o que mudou, mostra o erro no campo e relê a sessão ao trocar o tratamento', async () => {
    const usuario = userEvent.setup();
    const envios: Record<string, unknown>[] = [];
    const { chamadas } = montarApp('/perfil', SO_PREFERENCIAS, rotas((url, init) => {
      if (url === '/api/v1/perfil/pergunta') return respostaJson({ pergunta: null });
      if (url !== '/api/v1/perfil/preferencias') return undefined;
      if (metodo(init) === 'GET') return respostaJson(preferencias({ temas: ['comunidade'], faltam: [] }));
      envios.push(corpo(init));
      if (envios.length === 1) {
        return respostaJson({ erro: 'entrada_invalida', mensagem: 'Confira os dados.', request_id: 'abc',
          detalhes: [{ campo: 'tratamento', mensagem: 'use só letras, espaço, ponto e hífen' }] }, 400);
      }
      return respostaJson(preferencias({ tratamento: 'Dra. Telma', temas: ['comunidade'], frequencia: 'minima',
        atualizado_em: '2026-11-19T12:00:00Z', faltam: [] }));
    }));
    const salvar = await screen.findByRole('button', { name: 'Salvar preferências' });
    expect(salvar).toBeDisabled(); // nada mudou
    const campo = screen.getByLabelText('Como prefere ser chamado');
    await usuario.type(campo, 'Dra. Telma 2');
    await usuario.click(screen.getByLabelText('Só o essencial'));
    await usuario.click(salvar);
    await waitFor(() => expect(envios[0]).toEqual({ tratamento: 'Dra. Telma 2', frequencia: 'minima' }));
    expect(await screen.findByText('use só letras, espaço, ponto e hífen')).toBeInTheDocument();
    expect(campo).toHaveAttribute('aria-invalid', 'true');

    const sessoesAntes = chamadas.filter((c) => c.url === '/api/v1/sessao').length;
    await usuario.clear(campo);
    await usuario.type(campo, 'Dra. Telma');
    await usuario.click(screen.getByRole('button', { name: 'Salvar preferências' }));
    await waitFor(() => expect(envios[1]).toEqual({ tratamento: 'Dra. Telma', frequencia: 'minima' }));
    await waitFor(() => expect(chamadas.filter((c) => c.url === '/api/v1/sessao').length).toBe(sessoesAntes + 1));
    expect(await screen.findByRole('button', { name: 'Salvar preferências' })).toBeDisabled();
  });

  it('tamanho do texto: só aplica depois de o servidor aceitar', async () => {
    const usuario = userEvent.setup();
    let envio: Record<string, unknown> | undefined;
    let falhar = true;
    // Sessão própria: depois de salvar, o servidor passa a devolver o tamanho novo.
    const sessao = fabricarSessao({
      recursos: { solicitacoes: true, ajuda: true, privacidade: true }, flags: { perfil_preferencias: true },
    });
    montarApp('/perfil', sessao, rotas((url, init) => {
      if (url === '/api/v1/perfil/pergunta') return respostaJson({ pergunta: null });
      if (url !== '/api/v1/perfil/preferencias') return undefined;
      if (metodo(init) === 'GET') return respostaJson(preferencias({ faltam: [] }));
      envio = corpo(init);
      if (falhar) return respostaJson({ erro: 'fonte_indisponivel', mensagem: 'Tente de novo.', request_id: 'abc' }, 503);
      sessao.preferencias.fonte = 'maior';
      return respostaJson(preferencias({ fonte: 'maior', faltam: [] }));
    }));
    const grupo = await screen.findByRole('group', { name: 'Tamanho do texto' });
    expect(within(grupo).getByRole('button', { name: 'Padrão' })).toHaveAttribute('aria-pressed', 'true');
    await usuario.click(within(grupo).getByRole('button', { name: 'Maior' }));
    await waitFor(() => expect(envio).toEqual({ fonte: 'maior' }));
    await waitFor(() => expect(within(grupo).getByRole('button', { name: 'Maior' })).toBeEnabled());
    expect(document.documentElement.dataset.fonte).toBeUndefined();
    expect(within(grupo).getByRole('button', { name: 'Maior' })).toHaveAttribute('aria-pressed', 'false');

    falhar = false;
    await usuario.click(within(grupo).getByRole('button', { name: 'Maior' }));
    await waitFor(() => expect(document.documentElement.dataset.fonte).toBe('maior'));
    await waitFor(() => expect(within(grupo).getByRole('button', { name: 'Maior' })).toHaveAttribute('aria-pressed', 'true'));
  });

  it('a sessão aplica o tamanho de fonte e a saudação usa o tratamento escolhido', async () => {
    montarApp('/', fabricarSessao({ preferencias: { fonte: 'grande', tratamento: 'Dra. Telma' } }));
    expect(await screen.findByRole('heading', { name: /^Olá, Dra\. Telma\./ })).toBeInTheDocument();
    expect(document.documentElement.dataset.fonte).toBe('grande');
  });

  it('sem tratamento a saudação é neutra, com o primeiro nome', async () => {
    montarApp('/', fabricarSessao());
    expect(await screen.findByRole('heading', { name: /^Olá, Telma\./ })).toBeInTheDocument();
    expect(document.documentElement.dataset.fonte).toBeUndefined();
  });

  it('autorização: envia a versão do texto lido e mostra o histórico', async () => {
    const usuario = userEvent.setup();
    let envio: Record<string, unknown> | undefined;
    montarApp('/perfil', SO_LGPD, rotas((url, init) => {
      if (url === '/api/v1/perfil/dados/pedidos') return respostaJson(pedidos());
      if (url !== '/api/v1/perfil/consentimentos') return undefined;
      if (metodo(init) === 'GET') return respostaJson({ itens: [consentimento()] });
      envio = corpo(init);
      return respostaJson(consentimento({ concedido: true, versao_registrada: 'v0', registrado_em: '2026-11-19T15:00:00Z',
        historico: [{ valor: 'concedido', versao: 'v0', origem: 'perfil', registrado_em: '2026-11-19T15:00:00Z' }] }));
    }));
    expect(await screen.findByText('Ofertas de parceiros por e-mail')).toBeInTheDocument();
    expect(screen.getByText('Sem autorização registrada · texto v0')).toBeInTheDocument();
    const caixa = screen.getByRole('checkbox', { name: 'Autorizo' });
    expect(caixa).not.toBeChecked();
    expect(caixa).toHaveAccessibleDescription(/Autorizo a APM a me enviar ofertas/);
    await usuario.click(caixa);
    await waitFor(() => expect(envio).toEqual({ finalidade: 'ofertas_parceiros', canal: 'email', versao: 'v0', concedido: true }));
    await waitFor(() => expect(screen.getByRole('checkbox', { name: 'Autorizo' })).toBeChecked());
    expect(screen.getByText('Autorizado em 19/11/2026 às 12:00 · texto v0')).toBeInTheDocument();
    expect(screen.getByText('Autorizou em 19/11/2026 às 12:00 · texto v0')).toBeInTheDocument();
  });

  it('texto mudou depois da leitura: 409 recarrega e a autorização antiga não aparece marcada', async () => {
    const usuario = userEvent.setup();
    let leituras = 0;
    montarApp('/perfil', SO_LGPD, rotas((url, init) => {
      if (url === '/api/v1/perfil/dados/pedidos') return respostaJson(pedidos());
      if (url !== '/api/v1/perfil/consentimentos') return undefined;
      if (metodo(init) === 'GET') {
        leituras += 1;
        return respostaJson({ itens: [leituras === 1
          ? consentimento()
          : consentimento({ versao: 'v1', texto: 'Texto novo da autorização.', concedido: true, versao_registrada: 'v0',
            registrado_em: '2026-11-01T15:00:00Z', texto_mudou: true })] });
      }
      return respostaJson({ erro: 'versao_desatualizada', mensagem: 'O texto desta autorização foi atualizado.',
        request_id: 'abc', detalhes: [{ campo: 'versao', mensagem: 'v1' }] }, 409);
    }));
    await usuario.click(await screen.findByRole('checkbox', { name: 'Autorizo' }));
    expect(await screen.findByText('Texto novo da autorização.')).toBeInTheDocument();
    expect(screen.getByText(/Este texto foi atualizado depois da sua autorização/)).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Autorizo' })).not.toBeChecked();
    expect(leituras).toBe(2);
  });

  it('baixar meus dados: salva o arquivo e passa a mostrar quando há outro', async () => {
    const usuario = userEvent.setup();
    const blobs: Blob[] = [];
    const criarUrl = vi.fn((conteudo: Blob) => `blob:teste-${blobs.push(conteudo)}`);
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: criarUrl, revokeObjectURL: vi.fn() }));
    const clique = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    let exportou = false;
    montarApp('/perfil', SO_LGPD, rotas((url, init) => {
      if (url === '/api/v1/perfil/consentimentos') return respostaJson({ itens: [] });
      if (url === '/api/v1/perfil/dados/pedidos') {
        return respostaJson(pedidos(exportou ? { exportacao_disponivel_em: '2026-11-26T15:00:00Z' } : {}));
      }
      if (url === '/api/v1/perfil/dados/exportar') {
        expect(metodo(init)).toBe('POST');
        expect(cabecalho(init, 'X-CSRF-Token')).toBe('token-csrf-teste');
        exportou = true;
        return respostaJson({ formato: 'minha-apm-dados/1', cadastro: { nome: 'TELMA NOGUEIRA' } });
      }
      return undefined;
    }));
    expect(await screen.findByText('Nenhuma autorização é pedida no momento.')).toBeInTheDocument();
    await usuario.click(await screen.findByRole('button', { name: 'Baixar meus dados' }));
    await waitFor(() => expect(clique).toHaveBeenCalledTimes(1));
    const blob = blobs[0] as Blob;
    expect(blob.type).toBe('application/json');
    expect(JSON.parse(await blob.text())).toEqual({ formato: 'minha-apm-dados/1', cadastro: { nome: 'TELMA NOGUEIRA' } });
    expect(await screen.findByText(/Um novo arquivo fica disponível em 26\/11\/2026 às 12:00/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Baixar meus dados' })).toBeDisabled();
    expect(document.querySelector('a[download]')).toBeNull(); // o link temporário saiu da página
  });

  it('sem senha recente: pede a confirmação de identidade e bloqueia baixar e excluir', async () => {
    montarApp('/perfil', SO_LGPD, rotas((url) => {
      if (url === '/api/v1/perfil/consentimentos') return respostaJson({ itens: [] });
      if (url === '/api/v1/perfil/dados/pedidos') return respostaJson(pedidos({ exige_reautenticacao: true }));
      return undefined;
    }));
    expect(await screen.findByRole('link', { name: 'Confirmar minha identidade' })).toHaveAttribute(
      'href', '/auth/login?reauth=1&next=%2Farea%2Fperfil');
    expect(screen.getByRole('button', { name: 'Baixar meus dados' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Pedir exclusão' })).toBeDisabled();
  });

  it('pedir exclusão: só com a palavra digitada; depois mostra o protocolo e o caminho para desistir', async () => {
    const usuario = userEvent.setup();
    let envio: Record<string, unknown> | undefined;
    const SID = '6f1c1c9e-5d0e-4a51-8a55-2f1f6f0a7a11';
    montarApp('/perfil', SO_LGPD, rotas((url, init) => {
      if (url === '/api/v1/perfil/consentimentos') return respostaJson({ itens: [] });
      if (url === '/api/v1/perfil/dados/pedidos') {
        const aberta = { protocolo: 'LGPD-20261119-ABC234', tipo: 'exclusao' as const, status: 'registrado' as const,
          criado_em: '2026-11-19T15:00:00Z', concluido_em: null, solicitacao_id: SID };
        return respostaJson(pedidos(envio ? { itens: [aberta], exclusao_aberta: aberta } : {}));
      }
      if (url === '/api/v1/perfil/dados/exclusao') {
        envio = corpo(init);
        return respostaJson({ protocolo: 'LGPD-20261119-ABC234', solicitacao_id: SID, registrado_em: '2026-11-19T15:00:00Z' }, 201);
      }
      return undefined;
    }));
    await usuario.click(await screen.findByRole('button', { name: 'Pedir exclusão' }));
    const dialogo = await screen.findByRole('alertdialog', { name: 'Pedir a exclusão dos meus dados' });
    expect(within(dialogo).getByText(/Não cancela a sua associação/)).toBeInTheDocument();
    const confirmar = within(dialogo).getByRole('button', { name: 'Pedir exclusão' });
    expect(confirmar).toBeDisabled();
    await usuario.type(within(dialogo).getByLabelText('Para confirmar, digite EXCLUIR'), 'excluir');
    expect(confirmar).toBeEnabled();
    await usuario.click(confirmar);
    await waitFor(() => expect(envio?.confirmacao).toBe('EXCLUIR'));
    expect(String(envio?.chave_idempotencia)).toMatch(/^[0-9a-f-]{36}$/);
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull());
    expect(await screen.findByText('LGPD-20261119-ABC234')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Acompanhar ou desistir do pedido' })).toHaveAttribute('href', `/solicitacoes/${SID}`);
    expect(screen.queryByRole('button', { name: 'Pedir exclusão' })).toBeNull();
  });

  it('falha ao carregar uma seção não derruba as outras e oferece nova tentativa', async () => {
    const usuario = userEvent.setup();
    let tentativas = 0;
    montarApp('/perfil', SO_LGPD, rotas((url) => {
      if (url === '/api/v1/perfil/dados/pedidos') return respostaJson(pedidos());
      if (url === '/api/v1/perfil/consentimentos') {
        tentativas += 1;
        return tentativas === 1
          ? respostaJson({ erro: 'fonte_indisponivel', mensagem: 'Tente de novo.', request_id: 'abc' }, 503)
          : respostaJson({ itens: [consentimento()] });
      }
      return undefined;
    }));
    expect(await screen.findByText('Não foi possível carregar suas autorizações.')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Baixar meus dados' })).toBeEnabled();
    await usuario.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByRole('checkbox', { name: 'Autorizo' })).toBeInTheDocument();
  });
});
