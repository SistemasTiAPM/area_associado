import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ContatoCentral, RespostaFaq } from '../api/ajuda';
import { _reiniciarAnalytics, enviarFila } from '../lib/analytics';
import { ID_SOLICITACAO, solicitacao } from '../test/fabricas';
import { fabricarSessao, montarApp, respostaJson, type Rotas } from '../test/utilidades';

const API_FAQ = '/api/v1/ajuda/faq';
const API_CONTATO = '/api/v1/ajuda/contato';
const PRONTA = fabricarSessao({ recursos: { solicitacoes: true, ajuda: true, privacidade: false } });

const FAQ: RespostaFaq = {
  categorias: [
    { codigo: 'beneficios', rotulo: 'Benefícios' },
    { codigo: 'carteirinha', rotulo: 'Carteirinha' },
  ],
  itens: [
    { id: 1, pergunta: 'Como ativo um benefício?', resposta: 'Abra o benefício e toque em Ativar.\n\nA APM avisa cada etapa.', categoria: 'beneficios' },
    { id: 2, pergunta: 'Como compartilho a carteirinha?', resposta: 'Use o botão Compartilhar.', categoria: 'carteirinha' },
  ],
  sugestoes: [],
};

const CONTATO: ContatoCentral = {
  whatsapp: { exibicao: '(11) 3188-6200', url: 'https://wa.me/551131886200?text=Ol%C3%A1.' },
  telefone: { exibicao: '(11) 3188-6200', uri: 'tel:+551131886200' },
  horario: 'Segunda a sexta, das 9h às 18h',
};

type Chamada = { url: string; init: RequestInit | undefined };
const corpoUso = (chamadas: Chamada[]) =>
  chamadas
    .filter((c) => c.url === '/api/v1/uso')
    .flatMap((c) => (JSON.parse(String(c.init?.body)) as { eventos: Record<string, unknown>[] }).eventos);
const corpo = (init: RequestInit | undefined) => JSON.parse(String(init?.body ?? '{}')) as Record<string, unknown>;

function rotasBase(extra?: Rotas, faq: RespostaFaq = FAQ, contato: ContatoCentral = CONTATO): Rotas {
  return (url, init) => {
    const especifica = extra?.(url, init);
    if (especifica) return especifica;
    if (url === API_FAQ) return respostaJson(faq);
    if (url === API_CONTATO) return respostaJson(contato);
    return undefined;
  };
}

describe('Ajuda e atendimento (P14; RF-AJ-01..05)', () => {
  beforeEach(() => _reiniciarAnalytics());
  afterEach(() => vi.useRealTimers());

  it('recurso indisponível: "em construção" sem chamar a API; item no rodapé do menu e fora da barra inferior', async () => {
    const { chamadas } = montarApp('/ajuda', fabricarSessao());
    expect(await screen.findByText(/está em construção/)).toBeInTheDocument();
    expect(chamadas.some((c) => c.url.startsWith('/api/v1/ajuda'))).toBe(false);
    const menu = screen.getByRole('navigation', { name: 'Menu principal' });
    const links = within(menu).getAllByRole('link').map((l) => l.textContent);
    expect(links.indexOf('Ajuda')).toBe(links.findIndex((t) => t?.includes('Meu perfil')) - 1);
    expect(within(screen.getByRole('navigation', { name: 'Atalhos' })).queryByRole('link', { name: 'Ajuda' })).toBeNull();
  });

  it('carregando: FAQ e canais anunciam o carregamento', async () => {
    montarApp('/ajuda', PRONTA, (url) => (url.startsWith('/api/v1/ajuda') ? (new Promise(() => {}) as never) : undefined));
    expect(await screen.findByText('Carregando as perguntas frequentes…')).toBeInTheDocument();
    expect(screen.getByText('Carregando os canais da Central…')).toBeInTheDocument();
  });

  it('FAQ vazia: o bloco não aparece (spec v2 §3.2); canais e pedidos comuns continuam', async () => {
    montarApp('/ajuda', PRONTA, rotasBase(undefined, { categorias: [], itens: [], sugestoes: [] }));
    expect(await screen.findByRole('heading', { name: 'Fale com a Central de Relacionamento' })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Perguntas frequentes' })).toBeNull());
    expect(screen.getByRole('heading', { name: 'Pedidos comuns' })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/em breve/i);
  });

  it('FAQ: Accordion por categoria, busca no servidor com ?q= e sugestões quando não encontra', async () => {
    const usuario = userEvent.setup();
    const { chamadas } = montarApp(
      '/ajuda',
      PRONTA,
      rotasBase((url) => {
        if (url === `${API_FAQ}?q=boleto`) return respostaJson({ ...FAQ, itens: [], sugestoes: ['carteirinha', 'inexistente'] });
        if (url === `${API_FAQ}?categoria=carteirinha`) return respostaJson({ ...FAQ, itens: [FAQ.itens[1]] });
        return undefined;
      }),
    );
    expect(await screen.findByRole('heading', { level: 3, name: 'Benefícios' })).toBeInTheDocument();
    const pergunta = screen.getByRole('button', { name: 'Como ativo um benefício?' });
    expect(pergunta).toHaveAttribute('aria-expanded', 'false');
    await usuario.click(pergunta);
    expect(pergunta).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('A APM avisa cada etapa.')).toBeVisible();

    await usuario.type(screen.getByLabelText('Buscar nas perguntas frequentes'), 'boleto');
    expect(await screen.findByText(/Não encontramos perguntas sobre “boleto”/)).toBeInTheDocument();
    expect(screen.getByText('0 perguntas encontradas.')).toBeInTheDocument();
    const sugestoes = screen.getByRole('list', { name: 'Categorias sugeridas' });
    expect(within(sugestoes).getAllByRole('button')).toHaveLength(1); // código desconhecido não vira botão
    await usuario.click(within(sugestoes).getByRole('button', { name: 'Carteirinha' }));
    expect(await screen.findByRole('button', { name: 'Como compartilho a carteirinha?' })).toBeInTheDocument();
    expect(screen.getByLabelText('Buscar nas perguntas frequentes')).toHaveValue('');
    expect(screen.getByText('Mostrando:')).toBeInTheDocument();
    expect(chamadas.filter((c) => c.url === `${API_FAQ}?q=boleto`)).toHaveLength(1);
  });

  it('FAQ com erro: request_id e tentar novamente', async () => {
    const usuario = userEvent.setup();
    let tentativas = 0;
    montarApp(
      '/ajuda',
      PRONTA,
      rotasBase((url) => {
        if (url !== API_FAQ) return undefined;
        tentativas += 1;
        return tentativas === 1
          ? respostaJson({ erro: 'recurso_indisponivel', mensagem: 'A ajuda está indisponível agora.', request_id: 'fedcba9876543210' }, 503)
          : undefined;
      }),
    );
    const alerta = await waitFor(() => {
      const a = screen.getAllByRole('alert').find((el) => el.textContent?.includes('A ajuda está indisponível agora.'));
      expect(a).toBeDefined();
      return a as HTMLElement;
    });
    expect(within(alerta as HTMLElement).getByText('fedcba9876543210')).toBeInTheDocument();
    await usuario.click(within(alerta as HTMLElement).getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByRole('button', { name: 'Como ativo um benefício?' })).toBeInTheDocument();
  });

  it('canais: WhatsApp (nova aba segura), telefone tel:, horário e ajuda_contatar no lugar de central_whatsapp_abrir', async () => {
    const usuario = userEvent.setup();
    const { chamadas } = montarApp('/ajuda', PRONTA, rotasBase());
    const secao = (await screen.findByRole('heading', { name: 'Fale com a Central de Relacionamento' })).closest('section') as HTMLElement;
    expect(await within(secao).findByText('Horário de atendimento: Segunda a sexta, das 9h às 18h')).toBeInTheDocument();
    const whatsapp = within(secao).getByRole('link', { name: /Conversar pelo WhatsApp/ });
    expect(whatsapp).toHaveAttribute('href', CONTATO.whatsapp?.url);
    expect(whatsapp).toHaveAttribute('rel', 'noopener noreferrer');
    const telefone = within(secao).getByRole('link', { name: 'Ligar para a Central' });
    expect(telefone).toHaveAttribute('href', 'tel:+551131886200');
    whatsapp.addEventListener('click', (e) => e.preventDefault());
    telefone.addEventListener('click', (e) => e.preventDefault());
    await usuario.click(whatsapp);
    await usuario.click(telefone);
    enviarFila(true);
    const eventos = corpoUso(chamadas);
    expect(eventos).toContainEqual({ acao: 'ajuda_contatar', entidade: 'central', detalhes: { canal: 'whatsapp' } });
    expect(eventos).toContainEqual({ acao: 'ajuda_contatar', entidade: 'central', detalhes: { canal: 'telefone' } });
    expect(eventos.some((e) => e.acao === 'central_whatsapp_abrir')).toBe(false);
  });

  it('canais sem configuração somem; URL fora da allowlist ou tel: inválido não vira link', async () => {
    montarApp(
      '/ajuda',
      PRONTA,
      rotasBase(undefined, FAQ, {
        whatsapp: { exibicao: 'x', url: 'https://evil.example.com/' },
        telefone: { exibicao: 'y', uri: 'javascript:alert(1)' },
        horario: null,
      }),
    );
    const secao = (await screen.findByRole('heading', { name: 'Fale com a Central de Relacionamento' })).closest('section') as HTMLElement;
    expect(await within(secao).findByRole('button', { name: 'Escrever para a Central' })).toBeInTheDocument();
    expect(within(secao).queryByText('WhatsApp')).toBeNull();
    expect(within(secao).queryByText('Telefone')).toBeNull();
    expect(within(secao).queryByText(/Horário/)).toBeNull();
  });

  it('formulário de dúvida: cria solicitação com a mesma chave na nova tentativa e mostra o caminho para P05', async () => {
    const usuario = userEvent.setup();
    let envios = 0;
    const { chamadas } = montarApp(
      '/ajuda',
      PRONTA,
      rotasBase((url) => {
        if (url !== '/api/v1/ajuda/formulario') return undefined;
        envios += 1;
        return envios === 1
          ? respostaJson({ erro: 'erro_interno', mensagem: 'Não foi possível enviar agora. Tente de novo.', request_id: null }, 500)
          : respostaJson(solicitacao({ prazo_em: '2026-11-03' }), 201);
      }),
    );
    await usuario.click(await screen.findByRole('button', { name: /Enviar dúvida/ }));
    expect(screen.getByRole('heading', { name: 'Escrever para a Central' })).toHaveFocus();
    expect(screen.getByLabelText('Assunto')).toHaveValue('beneficio');
    await usuario.click(screen.getByRole('button', { name: 'Enviar mensagem' }));
    expect(screen.getByText('Escreva sua mensagem antes de enviar.')).toBeInTheDocument();
    await usuario.type(screen.getByLabelText('Mensagem'), 'Como uso o desconto?');
    await usuario.click(screen.getByRole('button', { name: 'Enviar mensagem' }));
    expect(await screen.findByText('Não foi possível enviar agora. Tente de novo.')).toBeInTheDocument();
    await usuario.click(screen.getByRole('button', { name: 'Enviar mensagem' }));
    expect(await screen.findByRole('heading', { name: 'Recebemos sua mensagem' })).toHaveFocus();
    expect(screen.getByText('Prazo de retorno: 03/11/2026.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Acompanhar a solicitação' })).toHaveAttribute('href', `/solicitacoes/${ID_SOLICITACAO}`);

    const envio = chamadas.filter((c) => c.url === '/api/v1/ajuda/formulario').map((c) => corpo(c.init));
    expect(envio).toHaveLength(2);
    expect(envio[0]).toMatchObject({ assunto: 'beneficio', mensagem: 'Como uso o desconto?' });
    expect(envio[0]?.chave_idempotencia).toMatch(/^[0-9a-f-]{36}$/);
    expect(envio[1]?.chave_idempotencia).toBe(envio[0]?.chave_idempotencia);
    enviarFila(true);
    expect(corpoUso(chamadas)).toContainEqual({
      acao: 'ajuda_contatar',
      entidade: 'central',
      detalhes: { canal: 'formulario', assunto: 'beneficios' },
    });
  });

  it('declaração: finalidades da spec e 409 nao_elegivel mostra "Libera em dd/mm/aaaa"', async () => {
    const usuario = userEvent.setup();
    const { chamadas } = montarApp(
      '/ajuda',
      PRONTA,
      rotasBase((url) =>
        url === '/api/v1/solicitacoes'
          ? respostaJson({ erro: 'nao_elegivel', mensagem: 'Ainda não disponível.', request_id: null, libera_em: '2026-11-20' }, 409)
          : undefined,
      ),
    );
    await usuario.click(await screen.findByRole('button', { name: /Solicitar declaração/ }));
    const grupo = screen.getByRole('group', { name: 'Qual declaração você precisa?' });
    expect(within(grupo).getByLabelText(/Declaração de associado/)).toBeInTheDocument();
    await usuario.click(within(grupo).getByLabelText(/AMB para prova de título/));
    const painel = screen.getByRole('heading', { name: 'Pedir uma declaração' }).closest('section') as HTMLElement;
    await usuario.click(within(painel).getByRole('button', { name: 'Solicitar declaração' }));
    expect(await screen.findByText('Libera em 20/11/2026')).toBeInTheDocument();
    expect(corpo(chamadas.find((c) => c.url === '/api/v1/solicitacoes')?.init)).toMatchObject({
      tipo_servico: 'declaracao_associado',
      campos: { finalidade: 'amb_prova_titulo' },
    });
  });

  it('cancelamento: some com a flag desligada', async () => {
    montarApp('/ajuda', PRONTA, rotasBase());
    await screen.findByRole('heading', { name: 'Pedidos comuns' });
    expect(screen.queryByRole('heading', { name: 'Cancelar a associação' })).toBeNull();
  });

  it('cancelamento com a flag: motivo obrigatório e 403 reautenticacao_necessaria vai ao Login APM com reauth', async () => {
    const usuario = userEvent.setup();
    const assign = vi.fn();
    vi.stubGlobal('location', { ...window.location, assign, pathname: '/area/ajuda' });
    const { chamadas } = montarApp(
      '/ajuda',
      fabricarSessao({ recursos: { solicitacoes: true, ajuda: true, privacidade: false }, flags: { cancelamento_online: true } }),
      rotasBase((url) =>
        url === '/api/v1/ajuda/cancelamento'
          ? respostaJson({ erro: 'reautenticacao_necessaria', mensagem: 'Confirme sua senha.', request_id: null }, 403)
          : undefined,
      ),
    );
    await usuario.click(await screen.findByRole('button', { name: 'Quero cancelar minha associação' }));
    const grupo = screen.getByRole('group', { name: 'Por que você quer cancelar?' });
    expect(within(grupo).getAllByRole('radio').map((r) => r.closest('.opcao')?.textContent)).toEqual([
      'Não uso os benefícios',
      'Preço',
      'Mudança de cidade ou de fase',
      'Insatisfação com um serviço',
      'Outro',
    ]);
    expect(within(grupo).getAllByRole('radio')[0]).toHaveFocus();
    await usuario.click(screen.getByRole('button', { name: 'Pedir cancelamento' }));
    expect(screen.getByText('Escolha um motivo para continuar.')).toBeInTheDocument();
    await usuario.click(within(grupo).getByLabelText('Preço'));
    await usuario.click(screen.getByLabelText(/Quero conversar com a Central/));
    await usuario.click(screen.getByRole('button', { name: 'Pedir cancelamento' }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith('/auth/login?reauth=1&next=%2Farea%2Fajuda'));
    expect(corpo(chamadas.find((c) => c.url === '/api/v1/ajuda/cancelamento')?.init)).toMatchObject({
      motivo: 'preco',
      quer_conversa: true,
    });
  });

  it('cancelamento com a flag: sucesso mostra o próximo passo e o caminho para acompanhar', async () => {
    const usuario = userEvent.setup();
    montarApp(
      '/ajuda',
      fabricarSessao({ recursos: { solicitacoes: true, ajuda: true, privacidade: false }, flags: { cancelamento_online: true } }),
      rotasBase((url) =>
        url === '/api/v1/ajuda/cancelamento'
          ? respostaJson(solicitacao({ tipo: { codigo: 'cancelamento_associacao', rotulo: 'Cancelamento da associação' } }), 201)
          : undefined,
      ),
    );
    await usuario.click(await screen.findByRole('button', { name: 'Quero cancelar minha associação' }));
    await usuario.click(screen.getByLabelText('Não uso os benefícios'));
    await usuario.click(screen.getByRole('button', { name: 'Pedir cancelamento' }));
    expect(await screen.findByRole('heading', { name: 'Recebemos seu pedido de cancelamento' })).toHaveFocus();
    expect(screen.getByText(/conclui o cancelamento e confirma com você por e-mail/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Acompanhar o pedido' })).toHaveAttribute('href', `/solicitacoes/${ID_SOLICITACAO}`);
  });
});
